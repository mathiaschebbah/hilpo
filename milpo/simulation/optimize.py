"""Boucle d'optimisation structurée à patches atomiques pour MILPO.

optimize_slot : optimise un slot unique avec la boucle critic→editor→eval.
coordinate_ascent : passes multiples sur tous les slots optimisables.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable

from milpo.db.prompts import insert_prompt_version, promote_prompt
from milpo.db.rules import insert_optimization_step, insert_rules
from milpo.dsl import compile_rule, validate_rule
from milpo.eval_cache import EvalCache, prompt_hash
from milpo.inference import PostInput
from milpo.objective import compute_j, macro_f1, accuracy as acc_fn
from milpo.prompting import build_labels, build_target_descriptions
from milpo.rule_rewriter import rule_critique, rule_edit
from milpo.rewriter import ErrorCase
from milpo.rules import OPTIMIZABLE_SLOTS, OpType, PatchOp, RuleState, apply_patch
from milpo.simulation.evaluation import evaluate_j_candidate_axis
from milpo.simulation.state import (
    CoordinateAscentResult,
    PromptState,
    SlotOptResult,
)
from milpo.tabu import TabuList

log = logging.getLogger("simulation")


def _compute_j_from_axis_results(
    axis_results: dict[str, list[tuple[str, str]]],
) -> float:
    """Compute J depuis les résultats par axe {axis: [(true, pred), ...]}."""
    vf = axis_results.get("visual_format", [])
    cat = axis_results.get("category", [])
    strat = axis_results.get("strategy", [])
    return compute_j(
        [t for t, _ in vf], [p for _, p in vf],
        [t for t, _ in cat], [p for _, p in cat],
        [t for t, _ in strat], [p for _, p in strat],
    )


def _collect_errors_from_results(
    axis_results: dict[str, list[tuple[str, str]]],
    target_agent: str,
    conn,
) -> list[ErrorCase]:
    """Extrait les erreurs du target_agent depuis les résultats d'évaluation."""
    target_results = axis_results.get(target_agent, [])
    errors: list[ErrorCase] = []
    for true_label, pred_label in target_results:
        if true_label != pred_label:
            errors.append(ErrorCase(
                ig_media_id=0,  # pas de post_id dans les résultats agrégés
                axis=target_agent,
                prompt_scope=None,
                post_scope="",
                predicted=pred_label,
                expected=true_label,
                features_json="",
                caption=None,
                desc_predicted=pred_label,
                desc_expected=true_label,
                confidence="unknown",
            ))
    return errors


async def optimize_slot(
    conn,
    run_id: int,
    pass_number: int,
    rule_state: RuleState,
    prompt_state: PromptState,
    dev_opt_posts: list[PostInput],
    annotations: dict[int, dict],
    cached_features: dict[int, str],
    cached_axis_results: dict[str, list[tuple[str, str]]],
    labels_by_scope: dict[str, dict[str, list[str]]],
    tabu: TabuList,
    patience: int = 5,
    max_steps: int = 30,
    n_patches: int = 3,
    on_status: Callable[[str], None] | None = None,
) -> SlotOptResult:
    """Optimise un slot avec la boucle structurée critic→editor→eval.

    Returns:
        SlotOptResult avec les métriques de l'optimisation.
        rule_state et prompt_state sont modifiés in-place si des steps sont acceptés.
    """
    target_agent = rule_state.agent
    target_scope = rule_state.scope
    slot_key = rule_state.slot_key()
    all_descriptions = build_target_descriptions(conn, target_agent, target_scope)

    # J initial
    j_current = _compute_j_from_axis_results(cached_axis_results)
    j_initial = j_current

    steps_taken = 0
    steps_accepted = 0
    tabu_hits = 0
    skipped_invalid = 0
    patience_left = patience

    # Ajouter l'état initial au tabu
    tabu.add(slot_key, rule_state.state_hash())

    incumbent_prompt_id = prompt_state.db_ids.get(
        (target_agent, target_scope),
        0,
    )

    for step in range(max_steps):
        if patience_left <= 0:
            break

        steps_taken += 1
        step_number = step + 1

        if on_status:
            on_status(f"slot {slot_key} step {step_number}/{max_steps} (J={j_current:.4f})")

        # 1. Collecter les erreurs
        errors = _collect_errors_from_results(cached_axis_results, target_agent, conn)
        if not errors:
            log.info("[OPT] %s step %d: 0 erreurs, arrêt.", slot_key, step_number)
            break

        # Limiter les erreurs au batch
        errors = errors[:20]

        # 2. Critic
        if on_status:
            on_status(f"slot {slot_key} step {step_number} — critic...")
        try:
            critique_result = await asyncio.to_thread(
                rule_critique,
                rule_state=rule_state,
                errors=errors,
                all_descriptions=all_descriptions,
            )
        except Exception as exc:
            log.warning("[OPT] %s step %d: critic failed: %s", slot_key, step_number, exc)
            patience_left -= 1
            continue

        # 3. Editor → 3 patches
        if on_status:
            on_status(f"slot {slot_key} step {step_number} — editor (×{n_patches})...")
        try:
            patches_result = await asyncio.to_thread(
                rule_edit,
                rule_state=rule_state,
                critique=critique_result.critique,
                target_rule_index=critique_result.target_rule_index,
                errors=errors,
                all_descriptions=all_descriptions,
                n_patches=n_patches,
            )
        except Exception as exc:
            log.warning("[OPT] %s step %d: editor failed: %s", slot_key, step_number, exc)
            patience_left -= 1
            continue

        # 4. Évaluer chaque patch
        best_j = j_current
        best_candidate = None
        best_op = None
        best_reasoning = ""
        best_hash = ""

        for patch_op, reasoning in patches_result.patches:
            # 4a. Appliquer le patch
            try:
                candidate_state = apply_patch(rule_state, patch_op)
            except ValueError as exc:
                log.debug("[OPT] %s step %d: patch invalide: %s", slot_key, step_number, exc)
                skipped_invalid += 1
                continue

            # 4b. Tabu check
            candidate_hash = candidate_state.state_hash()
            if tabu.is_tabu(slot_key, candidate_hash):
                tabu_hits += 1
                log.debug("[OPT] %s step %d: tabu hit", slot_key, step_number)
                continue

            # 4c. Render et évaluer
            candidate_prompt = candidate_state.render()
            if on_status:
                on_status(f"slot {slot_key} step {step_number} — eval candidate...")

            try:
                candidate_axis_results = await asyncio.wait_for(
                    evaluate_j_candidate_axis(
                        dev_opt_posts=dev_opt_posts,
                        annotations=annotations,
                        target_agent=target_agent,
                        target_scope=target_scope,
                        candidate_instructions=candidate_prompt,
                        base_prompt_state=prompt_state,
                        labels_by_scope=labels_by_scope,
                        cached_features=cached_features,
                        conn=conn,
                    ),
                    timeout=300,
                )
            except (asyncio.TimeoutError, Exception) as exc:
                log.warning("[OPT] %s step %d: eval failed: %s", slot_key, step_number, exc)
                continue

            # Construire J avec les résultats candidats pour l'axe cible + les autres axes cachées
            mixed_results = dict(cached_axis_results)
            mixed_results[target_agent] = candidate_axis_results
            candidate_j = _compute_j_from_axis_results(mixed_results)

            # Ajouter au tabu
            tabu.add(slot_key, candidate_hash)

            if candidate_j > best_j:
                best_j = candidate_j
                best_candidate = candidate_state
                best_op = patch_op
                best_reasoning = reasoning
                best_hash = candidate_hash

        # 5. Décision accept/reject
        if best_candidate is not None and best_j > j_current:
            # ACCEPT
            steps_accepted += 1
            patience_left = patience  # reset

            # Persister le nouveau prompt en BDD
            incumbent_version = prompt_state.versions.get((target_agent, target_scope), 0)
            new_version = incumbent_version + 1
            new_prompt_id = insert_prompt_version(
                conn, target_agent, target_scope, new_version,
                best_candidate.render(), status="draft",
                parent_id=incumbent_prompt_id,
                simulation_run_id=run_id,
            )
            insert_rules(conn, new_prompt_id, target_agent, target_scope, best_candidate.rules)
            promote_prompt(conn, target_agent, target_scope, new_prompt_id)

            # Update state in-place
            rule_state.rules = best_candidate.rules
            prompt_state.instructions[(target_agent, target_scope)] = best_candidate.render()
            prompt_state.db_ids[(target_agent, target_scope)] = new_prompt_id
            prompt_state.versions[(target_agent, target_scope)] = new_version

            # Update cached results for this axis
            mixed = dict(cached_axis_results)
            # Re-evaluate to get the actual results (already computed above)
            # The candidate_axis_results is already the correct one
            cached_axis_results[target_agent] = candidate_axis_results if 'candidate_axis_results' in dir() else cached_axis_results[target_agent]

            delta = best_j - j_current
            j_current = best_j
            incumbent_prompt_id = new_prompt_id

            log.info(
                "[OPT] %s step %d: ACCEPTED J=%.4f→%.4f (+%.4f)",
                slot_key, step_number, j_current - delta, j_current, delta,
            )
        else:
            # REJECT
            patience_left -= 1
            log.info(
                "[OPT] %s step %d: REJECTED (patience=%d/%d)",
                slot_key, step_number, patience_left, patience,
            )

        # 6. Log step
        insert_optimization_step(
            conn,
            simulation_run_id=run_id,
            step_number=step_number,
            pass_number=pass_number,
            target_agent=target_agent,
            target_scope=target_scope,
            op_type=best_op.op_type.value if best_op else None,
            op_index=best_op.index if best_op else None,
            op_rule_type=best_op.new_rule.rule_type.value if best_op and best_op.new_rule else None,
            op_rule_data=best_op.new_rule.to_dict() if best_op and best_op.new_rule else None,
            critique_text=critique_result.critique,
            critique_target_index=critique_result.target_rule_index,
            j_before=j_current if best_candidate is None else j_current - (best_j - j_current),
            j_after=best_j if best_candidate else j_current,
            accepted=best_candidate is not None,
            state_hash_before=rule_state.state_hash(),
            state_hash_after=best_hash if best_candidate else None,
            tabu_hit=False,
            skipped_invalid=skipped_invalid > 0,
            incumbent_prompt_id=incumbent_prompt_id,
            candidate_prompt_id=new_prompt_id if best_candidate else None,
        )

    return SlotOptResult(
        agent=target_agent,
        scope=target_scope,
        steps_taken=steps_taken,
        steps_accepted=steps_accepted,
        j_initial=j_initial,
        j_final=j_current,
        tabu_hits=tabu_hits,
        patience_exhausted=patience_left <= 0,
        skipped_invalid=skipped_invalid,
    )


async def coordinate_ascent(
    conn,
    run_id: int,
    rule_states: dict[tuple[str, str | None], RuleState],
    prompt_state: PromptState,
    dev_opt_posts: list[PostInput],
    annotations: dict[int, dict],
    cached_features: dict[int, str],
    initial_axis_results: dict[str, list[tuple[str, str]]],
    labels_by_scope: dict[str, dict[str, list[str]]],
    patience: int = 5,
    max_steps_per_slot: int = 30,
    max_passes: int = 5,
    n_patches: int = 3,
    on_status: Callable[[str], None] | None = None,
) -> CoordinateAscentResult:
    """Coordinate ascent : passes multiples sur tous les slots.

    Après chaque passe, si au moins un slot a amélioré J, on invalide
    le tabu et on recommence. Arrêt quand aucune passe n'améliore.
    """
    tabu = TabuList()
    j_global_initial = _compute_j_from_axis_results(initial_axis_results)
    j_global_best = j_global_initial
    all_slot_results: list[SlotOptResult] = []
    cached_axis_results = dict(initial_axis_results)

    slots_to_optimize = [
        slot for slot in OPTIMIZABLE_SLOTS if slot in rule_states
    ]

    for pass_num in range(1, max_passes + 1):
        any_improved = False

        log.info("[COORD] === Passe %d/%d (J=%.4f) ===", pass_num, max_passes, j_global_best)

        for agent, scope in slots_to_optimize:
            slot_key = f"{agent}/{scope or 'all'}"
            rule_state = rule_states[(agent, scope)]

            if on_status:
                on_status(f"passe {pass_num} — {slot_key}")

            log.info("[COORD] Optimisation %s...", slot_key)

            result = await optimize_slot(
                conn=conn,
                run_id=run_id,
                pass_number=pass_num,
                rule_state=rule_state,
                prompt_state=prompt_state,
                dev_opt_posts=dev_opt_posts,
                annotations=annotations,
                cached_features=cached_features,
                cached_axis_results=cached_axis_results,
                labels_by_scope=labels_by_scope,
                tabu=tabu,
                patience=patience,
                max_steps=max_steps_per_slot,
                n_patches=n_patches,
                on_status=on_status,
            )

            all_slot_results.append(result)

            if result.j_final > result.j_initial:
                any_improved = True
                log.info(
                    "[COORD] %s amélioré : J=%.4f→%.4f (+%.4f, %d steps accepted)",
                    slot_key, result.j_initial, result.j_final,
                    result.j_final - result.j_initial, result.steps_accepted,
                )
            else:
                log.info(
                    "[COORD] %s inchangé : J=%.4f (%d steps, patience épuisée=%s)",
                    slot_key, result.j_final, result.steps_taken, result.patience_exhausted,
                )

        j_after_pass = _compute_j_from_axis_results(cached_axis_results)
        if j_after_pass > j_global_best:
            j_global_best = j_after_pass

        if not any_improved:
            log.info("[COORD] Aucune amélioration dans la passe %d, arrêt.", pass_num)
            break

        # Invalider le tabu entre les passes pour ré-exploration
        tabu.invalidate_all()
        log.info("[COORD] Tabu invalidé, nouvelle passe.")

    j_global_final = _compute_j_from_axis_results(cached_axis_results)

    return CoordinateAscentResult(
        passes=pass_num,
        slot_results=all_slot_results,
        j_global_initial=j_global_initial,
        j_global_final=j_global_final,
        j_global_best=j_global_best,
    )
