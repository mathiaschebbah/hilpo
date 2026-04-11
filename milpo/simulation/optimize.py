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
from milpo.eval_cache import EvalCache
from milpo.simulation.evaluation import FullEvalResult, evaluate_j_candidate_axis
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


def _collect_errors_grounded(
    eval_result: FullEvalResult,
    target_agent: str,
    conn,
) -> list[ErrorCase]:
    """Construit des ErrorCase grounded avec features, caption et post_id réels.

    Utilise les données per-post conservées par FullEvalResult (fix P2).
    """
    from milpo.simulation.evaluation import _get_label_description

    errors: list[ErrorCase] = []
    for post_id, preds in eval_result.per_post_results.items():
        anns = eval_result.per_post_annotations.get(post_id, {})
        true_label = anns.get(target_agent)
        pred_label = preds.get(target_agent)
        if true_label is None or pred_label is None or true_label == pred_label:
            continue

        features = eval_result.features_by_post.get(post_id, "")
        caption = eval_result.per_post_captions.get(post_id)

        errors.append(ErrorCase(
            ig_media_id=post_id,
            axis=target_agent,
            prompt_scope=None,
            post_scope="",
            predicted=pred_label,
            expected=true_label,
            features_json=features[:4000],
            caption=caption,
            desc_predicted=_get_label_description(conn, target_agent, pred_label),
            desc_expected=_get_label_description(conn, target_agent, true_label),
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
    eval_result: FullEvalResult,
    labels_by_scope: dict[str, dict[str, list[str]]],
    tabu: TabuList,
    eval_cache: EvalCache | None = None,
    patience: int = 5,
    max_steps: int = 30,
    n_patches: int = 3,
    on_status: Callable[[str], None] | None = None,
    on_event: Callable[[dict], None] | None = None,
) -> SlotOptResult:
    """Optimise un slot avec la boucle structurée critic→editor→eval.

    Args:
        eval_result: FullEvalResult de l'évaluation initiale, utilisé pour
            construire des ErrorCase grounded (fix P2).
        cached_axis_results: dict mutable {axis: [(true, pred), ...]},
            mis à jour in-place quand un step est accepté avec les résultats
            du candidat gagnant (fix P1).
        eval_cache: EvalCache optionnel pour le déterminisme de J.

    Returns:
        SlotOptResult. rule_state et prompt_state sont modifiés in-place
        si des steps sont acceptés.
    """
    target_agent = rule_state.agent
    target_scope = rule_state.scope
    slot_key = rule_state.slot_key()
    all_descriptions = build_target_descriptions(conn, target_agent, target_scope)

    j_current = _compute_j_from_axis_results(cached_axis_results)
    j_initial = j_current

    steps_taken = 0
    steps_accepted = 0
    tabu_hits = 0
    skipped_invalid = 0
    patience_left = patience

    tabu.add(slot_key, rule_state.state_hash())

    incumbent_prompt_id = prompt_state.db_ids.get(
        (target_agent, target_scope), 0,
    )

    for step in range(max_steps):
        if patience_left <= 0:
            break

        steps_taken += 1
        step_number = step + 1

        if on_status:
            on_status(f"slot {slot_key} step {step_number}/{max_steps} (J={j_current:.4f})")
        if on_event:
            on_event({
                "type": "step_start",
                "slot_key": slot_key,
                "agent": target_agent,
                "scope": target_scope,
                "step": step_number,
                "max_steps": max_steps,
                "j_current": j_current,
            })

        # 1. Collecter les erreurs grounded
        errors = _collect_errors_grounded(eval_result, target_agent, conn)
        if not errors:
            log.info("[OPT] %s step %d: 0 erreurs, arrêt.", slot_key, step_number)
            break
        errors = errors[:20]

        # 2. Critic
        if on_status:
            on_status(f"slot {slot_key} step {step_number} — critic...")
        if on_event:
            on_event({"type": "sub_phase", "sub_phase": "critic"})
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

        # 3. Editor → n_patches patches
        if on_status:
            on_status(f"slot {slot_key} step {step_number} — editor (×{n_patches})...")
        if on_event:
            on_event({"type": "sub_phase", "sub_phase": "editor"})
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

        # 4. Évaluer chaque patch — tracker le gagnant ET ses résultats (fix P1)
        best_j = j_current
        best_candidate = None
        best_op = None
        best_reasoning = ""
        best_hash = ""
        best_candidate_axis_results: list[tuple[str, str]] | None = None

        for patch_op, reasoning in patches_result.patches:
            try:
                candidate_state = apply_patch(rule_state, patch_op)
            except ValueError as exc:
                log.debug("[OPT] %s step %d: patch invalide: %s", slot_key, step_number, exc)
                skipped_invalid += 1
                continue

            candidate_hash = candidate_state.state_hash()
            if tabu.is_tabu(slot_key, candidate_hash):
                tabu_hits += 1
                if on_event:
                    on_event({"type": "tabu_hit"})
                continue

            candidate_prompt = candidate_state.render()
            if on_status:
                on_status(f"slot {slot_key} step {step_number} — eval candidate...")
            if on_event:
                on_event({"type": "sub_phase", "sub_phase": "eval"})

            try:
                this_candidate_results = await asyncio.wait_for(
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
                        eval_cache=eval_cache,
                    ),
                    timeout=300,
                )
            except (asyncio.TimeoutError, Exception) as exc:
                log.warning("[OPT] %s step %d: eval failed: %s", slot_key, step_number, exc)
                continue

            mixed_results = dict(cached_axis_results)
            mixed_results[target_agent] = this_candidate_results
            candidate_j = _compute_j_from_axis_results(mixed_results)

            tabu.add(slot_key, candidate_hash)

            if candidate_j > best_j:
                best_j = candidate_j
                best_candidate = candidate_state
                best_op = patch_op
                best_reasoning = reasoning
                best_hash = candidate_hash
                best_candidate_axis_results = this_candidate_results  # fix P1

        # 5. Décision accept/reject
        new_prompt_id = None
        j_before_step = j_current

        if best_candidate is not None and best_j > j_current:
            steps_accepted += 1
            patience_left = patience

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

            rule_state.rules = best_candidate.rules
            prompt_state.instructions[(target_agent, target_scope)] = best_candidate.render()
            prompt_state.db_ids[(target_agent, target_scope)] = new_prompt_id
            prompt_state.versions[(target_agent, target_scope)] = new_version

            # Update cached results pour l'axe cible avec les résultats du GAGNANT (fix P1)
            cached_axis_results[target_agent] = best_candidate_axis_results

            # Update eval_result per-post pour les prochains steps
            for true_label, pred_label in best_candidate_axis_results:
                pass  # axis-level update suffit pour J; per-post sera re-collect via errors

            j_current = best_j
            incumbent_prompt_id = new_prompt_id

            log.info(
                "[OPT] %s step %d: ACCEPTED J=%.4f→%.4f (+%.4f)",
                slot_key, step_number, j_before_step, j_current, j_current - j_before_step,
            )
            if on_event:
                on_event({
                    "type": "step_accepted",
                    "slot_key": slot_key,
                    "step": step_number,
                    "j_before": j_before_step,
                    "j_after": j_current,
                    "rule_summary": best_op.op_type.value if best_op else "",
                })
        else:
            patience_left -= 1
            log.info(
                "[OPT] %s step %d: REJECTED (patience=%d/%d)",
                slot_key, step_number, patience_left, patience,
            )
            if on_event:
                on_event({
                    "type": "step_rejected",
                    "slot_key": slot_key,
                    "step": step_number,
                    "patience_left": patience_left,
                    "patience_max": patience,
                })

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
            j_before=j_before_step,
            j_after=best_j if best_candidate else j_current,
            accepted=best_candidate is not None and best_j > j_before_step,
            state_hash_before=rule_state.state_hash(),
            state_hash_after=best_hash or None,
            tabu_hit=False,
            skipped_invalid=skipped_invalid > 0,
            incumbent_prompt_id=incumbent_prompt_id,
            candidate_prompt_id=new_prompt_id,
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
    initial_eval_result: FullEvalResult,
    labels_by_scope: dict[str, dict[str, list[str]]],
    patience: int = 5,
    max_steps_per_slot: int = 30,
    max_passes: int = 5,
    n_patches: int = 3,
    on_status: Callable[[str], None] | None = None,
    on_event: Callable[[dict], None] | None = None,
) -> CoordinateAscentResult:
    """Coordinate ascent : passes multiples sur tous les slots."""
    eval_cache = EvalCache()
    tabu = TabuList()
    cached_axis_results = dict(initial_eval_result.axis_results)
    j_global_initial = _compute_j_from_axis_results(cached_axis_results)
    j_global_best = j_global_initial
    all_slot_results: list[SlotOptResult] = []

    slots_to_optimize = [
        slot for slot in OPTIMIZABLE_SLOTS if slot in rule_states
    ]

    pass_num = 0
    for pass_num in range(1, max_passes + 1):
        any_improved = False

        log.info("[COORD] === Passe %d/%d (J=%.4f) ===", pass_num, max_passes, j_global_best)
        if on_event:
            on_event({
                "type": "pass_start",
                "pass_num": pass_num,
                "pass_max": max_passes,
                "j_global": j_global_best,
            })

        for agent, scope in slots_to_optimize:
            slot_key = f"{agent}/{scope or 'all'}"
            rule_state = rule_states[(agent, scope)]

            if on_status:
                on_status(f"passe {pass_num} — {slot_key}")

            log.info("[COORD] Optimisation %s...", slot_key)

            if on_event:
                on_event({
                    "type": "slot_start",
                    "agent": agent,
                    "scope": scope,
                    "slot_key": slot_key,
                    "j_initial": _compute_j_from_axis_results(cached_axis_results),
                    "max_steps": max_steps_per_slot,
                })

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
                eval_result=initial_eval_result,
                labels_by_scope=labels_by_scope,
                tabu=tabu,
                eval_cache=eval_cache,
                patience=patience,
                max_steps=max_steps_per_slot,
                n_patches=n_patches,
                on_status=on_status,
                on_event=on_event,
            )

            all_slot_results.append(result)
            if on_event:
                on_event({
                    "type": "slot_done",
                    "agent": agent,
                    "scope": scope,
                    "slot_key": slot_key,
                    "steps_taken": result.steps_taken,
                    "steps_accepted": result.steps_accepted,
                    "j_initial": result.j_initial,
                    "j_final": result.j_final,
                    "tabu_hits": result.tabu_hits,
                })

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

        if on_event:
            on_event({
                "type": "pass_done",
                "pass_num": pass_num,
                "any_improved": any_improved,
                "j_global": j_after_pass,
            })

        if not any_improved:
            log.info("[COORD] Aucune amélioration dans la passe %d, arrêt.", pass_num)
            break

        tabu.invalidate_all()
        log.info("[COORD] Tabu invalidé, nouvelle passe.")

    j_global_final = _compute_j_from_axis_results(cached_axis_results)

    return CoordinateAscentResult(
        passes=pass_num if pass_num else 1,
        slot_results=all_slot_results,
        j_global_initial=j_global_initial,
        j_global_final=j_global_final,
        j_global_best=j_global_best,
    )
