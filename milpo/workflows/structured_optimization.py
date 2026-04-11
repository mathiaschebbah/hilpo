"""Workflow d'optimisation structurée MILPO — patches atomiques DSL.

Remplace la boucle ProTeGi libre par une recherche locale sur un espace
discret de règles typées, avec coordinate ascent et évaluation sur dev-opt fixe.

Usage :
    python -m milpo.workflows.structured_optimization [options]
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys
import time

from rich.console import Console
from rich.table import Table

from milpo.db import get_conn, load_dev_annotations
from milpo.dev_split import audit_dev_split, create_dev_split
from milpo.dsl import compile_rule
from milpo.gcs import sign_all_posts_media
from milpo.inference import PostInput
from milpo.objective import compute_j_components
from milpo.prompting import build_labels
from milpo.rules import OPTIMIZABLE_SLOTS, RuleState
from milpo.rules_bootstrap import bootstrap_slot_rules, verify_bootstrap
from milpo.simulation.evaluation import FullEvalResult, evaluate_full_dev_opt
from milpo.simulation.optimize import coordinate_ascent
from milpo.simulation.state import PromptState, load_prompt_state_from_db

console = Console()
logging.basicConfig(level=logging.INFO, format="%(asctime)s  %(message)s", datefmt="%H:%M:%S")
log = logging.getLogger("simulation")


def _finish_structured_run(conn, run_id: int, metrics: dict) -> None:
    """Marque un run d'optimisation structurée comme terminé.

    Adapte le payload au schéma simulation_runs existant (fix P1 finish_run).
    """
    conn.execute(
        """
        UPDATE simulation_runs SET
            status = 'completed', finished_at = NOW(),
            final_accuracy_category = %s,
            final_accuracy_visual_format = %s,
            final_accuracy_strategy = %s,
            prompt_iterations = %s,
            total_api_calls = %s, total_cost_usd = %s,
            config = COALESCE(config, '{}'::jsonb) || %s::jsonb
        WHERE id = %s
        """,
        (
            metrics.get("accuracy_category", 0),
            metrics.get("accuracy_visual_format", 0),
            metrics.get("accuracy_strategy", 0),
            metrics.get("total_steps", 0),
            metrics.get("total_api_calls", 0),
            None,
            json.dumps({k: v for k, v in metrics.items()
                        if k not in ("accuracy_category", "accuracy_visual_format",
                                     "accuracy_strategy", "total_api_calls")}),
            run_id,
        ),
    )
    conn.commit()


def _fail_structured_run(conn, run_id: int, error: str) -> None:
    """Marque un run d'optimisation structurée comme échoué."""
    conn.execute(
        """
        UPDATE simulation_runs SET
            status = 'failed', finished_at = NOW(),
            config = COALESCE(config, '{}'::jsonb) || jsonb_build_object('failure_reason', %s::text)
        WHERE id = %s
        """,
        (error[:1000], run_id),
    )
    conn.commit()


def _create_structured_run(conn, config: dict) -> int:
    """Crée un run d'optimisation structurée."""
    row = conn.execute(
        """
        INSERT INTO simulation_runs (seed, batch_size, config, status, started_at)
        VALUES (42, 0, %s::jsonb, 'running', NOW())
        RETURNING id
        """,
        (json.dumps(config),),
    ).fetchone()
    conn.commit()
    return row["id"]


def _j_components_from_axis_results(axis_results: dict[str, list[tuple[str, str]]]) -> dict[str, float]:
    """Extrait les composantes J depuis les résultats par axe."""
    return compute_j_components(
        [t for t, _ in axis_results.get("visual_format", [])],
        [p for _, p in axis_results.get("visual_format", [])],
        [t for t, _ in axis_results.get("category", [])],
        [p for _, p in axis_results.get("category", [])],
        [t for t, _ in axis_results.get("strategy", [])],
        [p for _, p in axis_results.get("strategy", [])],
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Optimisation structurée MILPO — patches atomiques DSL",
    )
    parser.add_argument("--opt-patience", type=int, default=5,
                        help="Steps sans amélioration avant d'arrêter un slot (défaut 5)")
    parser.add_argument("--opt-max-steps", type=int, default=30,
                        help="Max optimization steps par slot (défaut 30)")
    parser.add_argument("--opt-max-passes", type=int, default=5,
                        help="Max passes coordinate ascent (défaut 5)")
    parser.add_argument("--n-patches", type=int, default=3,
                        help="Candidats par step (défaut 3)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Bootstrap + eval initiale sans optimisation")
    parser.add_argument("--limit", type=int, default=None,
                        help="Nombre max de posts dev-opt")
    parser.add_argument("--split", choices=["dev", "test"], default="dev")
    return parser


async def run_structured_optimization(args) -> int:
    conn = get_conn()
    run_id = None
    t0 = time.monotonic()

    try:
        # ── 1. BOOTSTRAP ───────────────────────────────────────────────
        console.print("\n[bold]Phase 1 : BOOTSTRAP[/bold]\n")

        # Dev split
        console.print("Creating/loading dev-opt / dev-holdout split...")
        split_result = create_dev_split(conn)
        opt_ids = set(split_result["dev_opt"])
        holdout_ids = set(split_result["dev_holdout"])
        console.print(f"  dev-opt: {len(opt_ids)} posts, dev-holdout: {len(holdout_ids)} posts")

        audit = audit_dev_split(conn)
        console.print(f"  ratio: {audit['ratio_opt']:.1%} opt / {1-audit['ratio_opt']:.1%} holdout")

        # Annotations (tout le split)
        all_annotations = load_dev_annotations(conn, split=args.split)
        opt_annotations = {pid: ann for pid, ann in all_annotations.items() if pid in opt_ids}
        holdout_annotations = {pid: ann for pid, ann in all_annotations.items() if pid in holdout_ids}
        console.print(f"  annotations dev-opt: {len(opt_annotations)}, dev-holdout: {len(holdout_annotations)}")

        # Load ALL posts (opt + holdout) pour signer les URLs
        from milpo.db import load_dev_posts, load_posts_media, load_post_media
        all_raw_posts = load_dev_posts(conn, limit=None, split=args.split)
        annotated_ids = set(all_annotations.keys())
        all_raw_posts = [p for p in all_raw_posts if p["ig_media_id"] in annotated_ids]

        console.print(f"  signing GCS URLs for {len(all_raw_posts)} posts...")
        signed_by_post = sign_all_posts_media(
            all_raw_posts, load_post_media, conn, max_workers=20,
            load_all_media_fn=load_posts_media,
        )

        all_post_inputs: dict[int, PostInput] = {}
        for post in all_raw_posts:
            signed = signed_by_post.get(post["ig_media_id"], [])
            if not signed:
                continue
            pi = PostInput(
                ig_media_id=post["ig_media_id"],
                media_product_type=post["media_product_type"],
                media_urls=[url for url, _ in signed],
                media_types=[mt for _, mt in signed],
                caption=post["caption"],
            )
            all_post_inputs[post["ig_media_id"]] = pi

        opt_post_inputs = [all_post_inputs[pid] for pid in opt_ids if pid in all_post_inputs]
        holdout_post_inputs = [all_post_inputs[pid] for pid in holdout_ids if pid in all_post_inputs]

        if args.limit:
            opt_post_inputs = opt_post_inputs[:args.limit]

        console.print(f"  posts prêts: {len(opt_post_inputs)} opt, {len(holdout_post_inputs)} holdout")

        # Prompt state
        prompt_state = load_prompt_state_from_db(conn, logger=log)
        labels_by_scope = {scope: build_labels(conn, scope) for scope in ("FEED", "REELS")}

        # Bootstrap rules
        console.print("\n[bold]Bootstrap v0 → skeleton + DSL rules[/bold]\n")
        rule_states: dict[tuple[str, str | None], RuleState] = {}
        for agent, scope in OPTIMIZABLE_SLOTS:
            rule_state = bootstrap_slot_rules(conn, agent, scope)
            rule_states[(agent, scope)] = rule_state

            from milpo.db.prompts import get_prompt_version
            v0 = get_prompt_version(conn, agent, scope, version=0, source="human_v0")
            report = verify_bootstrap(v0["content"] if v0 else "", rule_state)

            console.print(f"  {agent}/{scope or 'all'}: {report['n_rules']} rules "
                          f"({report['valid_rules']} valid, {report['invalid_rules']} invalid)")
            for i, rule in enumerate(rule_state.rules[:5]):
                compiled = compile_rule(rule)
                console.print(f"    [{i}] {rule.rule_type.value}: {compiled[:80]}")
            if rule_state.rule_count() > 5:
                console.print(f"    ... ({rule_state.rule_count() - 5} more)")

        # Create run
        run_config = {
            "name": "MILPO_structured_opt",
            "mode": "structured_optimization",
            "opt_patience": args.opt_patience,
            "opt_max_steps": args.opt_max_steps,
            "opt_max_passes": args.opt_max_passes,
            "n_patches": args.n_patches,
            "dry_run": args.dry_run,
            "n_opt_posts": len(opt_post_inputs),
            "n_holdout_posts": len(holdout_post_inputs),
        }
        run_id = _create_structured_run(conn, run_config)
        console.print(f"\n  simulation_run_id = {run_id}")

        # ── 2. ÉVALUATION INITIALE sur dev-opt ────────────────────────
        console.print("\n[bold]Phase 2 : ÉVALUATION INITIALE sur dev-opt[/bold]\n")
        console.print(f"  Classifying {len(opt_post_inputs)} posts...")

        def _on_eval_progress(done: int, total: int):
            if done % 10 == 0 or done == total:
                console.print(f"    {done}/{total}", end="\r")

        initial_eval: FullEvalResult = await evaluate_full_dev_opt(
            dev_opt_posts=opt_post_inputs,
            annotations=opt_annotations,
            prompt_state=prompt_state,
            labels_by_scope=labels_by_scope,
            conn=conn,
            run_id=run_id,
            on_progress=_on_eval_progress,
        )

        # P0 fix : peupler cached_features depuis l'évaluation initiale
        cached_features: dict[int, str] = dict(initial_eval.features_by_post)
        console.print(f"  cached features: {len(cached_features)} posts")

        j_init = _j_components_from_axis_results(initial_eval.axis_results)
        console.print(f"\n  J_initial = {j_init['J']:.4f}")
        console.print(f"    macroF1_vf  = {j_init['macroF1_vf']:.4f}")
        console.print(f"    macroF1_cat = {j_init['macroF1_cat']:.4f}")
        console.print(f"    acc_strat   = {j_init['acc_strat']:.4f}")

        if args.dry_run:
            console.print("\n[yellow]--dry-run : arrêt après évaluation initiale.[/yellow]")
            _finish_structured_run(conn, run_id, {
                "accuracy_category": j_init["macroF1_cat"],
                "accuracy_visual_format": j_init["macroF1_vf"],
                "accuracy_strategy": j_init["acc_strat"],
                "total_api_calls": 0,
                "j_initial": j_init["J"],
                "j_final": j_init["J"],
                "total_steps": 0,
            })
            return run_id

        # ── 3. OPTIMISATION ────────────────────────────────────────────
        console.print("\n[bold]Phase 3 : COORDINATE ASCENT[/bold]\n")

        def _on_opt_status(msg: str):
            console.print(f"  {msg}")

        ascent_result = await coordinate_ascent(
            conn=conn,
            run_id=run_id,
            rule_states=rule_states,
            prompt_state=prompt_state,
            dev_opt_posts=opt_post_inputs,
            annotations=opt_annotations,
            cached_features=cached_features,
            initial_eval_result=initial_eval,
            labels_by_scope=labels_by_scope,
            patience=args.opt_patience,
            max_steps_per_slot=args.opt_max_steps,
            max_passes=args.opt_max_passes,
            n_patches=args.n_patches,
            on_status=_on_opt_status,
        )

        # ── 4. VALIDATION HOLDOUT ─────────────────────────────────────
        console.print("\n[bold]Phase 4 : VALIDATION sur dev-holdout[/bold]\n")
        console.print(f"  Classifying {len(holdout_post_inputs)} holdout posts...")

        holdout_eval: FullEvalResult = await evaluate_full_dev_opt(
            dev_opt_posts=holdout_post_inputs,
            annotations=holdout_annotations,
            prompt_state=prompt_state,
            labels_by_scope=labels_by_scope,
            conn=conn,
            run_id=run_id,
            on_progress=_on_eval_progress,
        )

        j_holdout = _j_components_from_axis_results(holdout_eval.axis_results)
        console.print(f"\n  J_holdout = {j_holdout['J']:.4f}")
        console.print(f"    macroF1_vf  = {j_holdout['macroF1_vf']:.4f}")
        console.print(f"    macroF1_cat = {j_holdout['macroF1_cat']:.4f}")
        console.print(f"    acc_strat   = {j_holdout['acc_strat']:.4f}")

        # ── 5. RÉSULTATS ──────────────────────────────────────────────
        console.print("\n[bold]Phase 5 : RÉSULTATS[/bold]\n")

        elapsed = time.monotonic() - t0

        table = Table(title="Résultats par slot")
        table.add_column("Slot")
        table.add_column("Steps")
        table.add_column("Accepted")
        table.add_column("J_initial")
        table.add_column("J_final")
        table.add_column("Delta")
        table.add_column("Tabu")

        for r in ascent_result.slot_results:
            delta = r.j_final - r.j_initial
            table.add_row(
                f"{r.agent}/{r.scope or 'all'}",
                str(r.steps_taken),
                str(r.steps_accepted),
                f"{r.j_initial:.4f}",
                f"{r.j_final:.4f}",
                f"{delta:+.4f}",
                str(r.tabu_hits),
            )

        console.print(table)
        console.print(f"\n  Passes: {ascent_result.passes}")
        console.print(f"  J_opt:     {ascent_result.j_global_initial:.4f} → {ascent_result.j_global_final:.4f}")
        console.print(f"  J_holdout: {j_holdout['J']:.4f}")
        console.print(f"  Durée:     {elapsed:.0f}s ({elapsed/60:.1f} min)")
        console.print(f"  run_id:    {run_id}")

        # Prompts finaux
        console.print("\n  Prompts finaux :")
        for (agent, scope), version in sorted(prompt_state.versions.items()):
            console.print(f"    {agent}/{scope or 'all'} : v{version}")

        # Règles finales
        console.print("\n  Règles finales :")
        for slot, state in sorted(rule_states.items()):
            console.print(f"\n  [{state.agent}/{state.scope or 'all'}] ({state.rule_count()} rules)")
            for i, rule in enumerate(state.rules):
                compiled = compile_rule(rule)
                console.print(f"    [{i}] {compiled[:100]}")

        _finish_structured_run(conn, run_id, {
            "accuracy_category": j_holdout["macroF1_cat"],
            "accuracy_visual_format": j_holdout["macroF1_vf"],
            "accuracy_strategy": j_holdout["acc_strat"],
            "total_api_calls": 0,
            "j_opt_initial": ascent_result.j_global_initial,
            "j_opt_final": ascent_result.j_global_final,
            "j_holdout": j_holdout["J"],
            "passes": ascent_result.passes,
            "total_steps": sum(r.steps_taken for r in ascent_result.slot_results),
            "total_accepted": sum(r.steps_accepted for r in ascent_result.slot_results),
        })
        return run_id

    except (KeyboardInterrupt, SystemExit):
        log.info("Optimisation interrompue (run_id=%s)", run_id)
        if run_id is not None:
            try:
                conn.rollback()
                _fail_structured_run(conn, run_id, "interrupted")
            except Exception:
                pass
        sys.exit(1)
    except Exception as exc:
        log.exception("[FATAL] Optimisation échouée: %s", exc)
        if run_id is not None:
            try:
                conn.rollback()
                _fail_structured_run(conn, run_id, str(exc))
            except Exception:
                pass
        raise
    finally:
        conn.close()


def main(argv: list[str] | None = None):
    parser = build_parser()
    args = parser.parse_args(argv)
    return asyncio.run(run_structured_optimization(args))


__all__ = ["build_parser", "main", "run_structured_optimization"]
