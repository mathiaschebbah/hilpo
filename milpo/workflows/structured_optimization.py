"""Workflow d'optimisation structurée MILPO — patches atomiques DSL.

Remplace la boucle ProTeGi libre par une recherche locale sur un espace
discret de règles typées, avec coordinate ascent et évaluation sur dev-opt fixe.

Usage :
    python -m milpo.workflows.structured_optimization [options]
"""

from __future__ import annotations

import argparse
import asyncio
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
from milpo.persistence import create_run, fail_run, finish_run
from milpo.prompting import build_labels
from milpo.rules import OPTIMIZABLE_SLOTS, RuleState
from milpo.rules_bootstrap import bootstrap_slot_rules, verify_bootstrap
from milpo.simulation.evaluation import evaluate_full_dev_opt
from milpo.simulation.optimize import coordinate_ascent
from milpo.simulation.state import PromptState, build_run_metrics, load_prompt_state_from_db

console = Console()
logging.basicConfig(level=logging.INFO, format="%(asctime)s  %(message)s", datefmt="%H:%M:%S")
log = logging.getLogger("simulation")


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

        # Annotations
        annotations = load_dev_annotations(conn, split=args.split)
        opt_annotations = {pid: ann for pid, ann in annotations.items() if pid in opt_ids}
        console.print(f"  annotations dev-opt: {len(opt_annotations)}")

        # Load posts
        from milpo.db import load_dev_posts, load_posts_media
        raw_posts = load_dev_posts(conn, limit=args.limit, split=args.split)
        raw_posts = [p for p in raw_posts if p["ig_media_id"] in opt_ids]

        console.print(f"  signing GCS URLs for {len(raw_posts)} posts...")
        from milpo.db import load_post_media
        signed_by_post = sign_all_posts_media(
            raw_posts, load_post_media, conn, max_workers=20,
            load_all_media_fn=load_posts_media,
        )

        post_inputs: list[PostInput] = []
        for post in raw_posts:
            signed = signed_by_post.get(post["ig_media_id"], [])
            if not signed:
                continue
            post_inputs.append(PostInput(
                ig_media_id=post["ig_media_id"],
                media_product_type=post["media_product_type"],
                media_urls=[url for url, _ in signed],
                media_types=[mt for _, mt in signed],
                caption=post["caption"],
            ))

        if args.limit:
            post_inputs = post_inputs[:args.limit]

        console.print(f"  posts prêts: {len(post_inputs)}")

        # Prompt state
        prompt_state = load_prompt_state_from_db(conn, logger=log)
        labels_by_scope = {scope: build_labels(conn, scope) for scope in ("FEED", "REELS")}

        # Bootstrap rules pour les slots optimisables
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
            for i, rule in enumerate(rule_state.rules):
                compiled = compile_rule(rule)
                console.print(f"    [{i}] {rule.rule_type.value}: {compiled[:80]}")

        # Create run
        run_config = {
            "name": "MILPO_structured_opt",
            "mode": "structured_optimization",
            "opt_patience": args.opt_patience,
            "opt_max_steps": args.opt_max_steps,
            "opt_max_passes": args.opt_max_passes,
            "n_patches": args.n_patches,
            "dry_run": args.dry_run,
        }
        run_id = create_run(conn, run_config)
        console.print(f"\n  simulation_run_id = {run_id}")

        # ── 2. ÉVALUATION INITIALE ────────────────────────────────────
        console.print("\n[bold]Phase 2 : ÉVALUATION INITIALE sur dev-opt[/bold]\n")
        console.print(f"  Classifying {len(post_inputs)} posts...")

        def _on_eval_progress(done: int, total: int):
            if done % 10 == 0 or done == total:
                console.print(f"    {done}/{total} posts classified", end="\r")

        initial_axis_results = await evaluate_full_dev_opt(
            dev_opt_posts=post_inputs,
            annotations=opt_annotations,
            prompt_state=prompt_state,
            labels_by_scope=labels_by_scope,
            conn=conn,
            run_id=run_id,
            on_progress=_on_eval_progress,
        )

        # Cache descriptor features pour la réutilisation
        # (dans l'évaluation candidate, on ne rappelle pas le descripteur)
        cached_features: dict[int, str] = {}
        # TODO: extraire features du résultat initial pour le cache
        # Pour l'instant, evaluate_j_candidate_axis gère ses propres features

        j_components = compute_j_components(
            [t for t, _ in initial_axis_results.get("visual_format", [])],
            [p for _, p in initial_axis_results.get("visual_format", [])],
            [t for t, _ in initial_axis_results.get("category", [])],
            [p for _, p in initial_axis_results.get("category", [])],
            [t for t, _ in initial_axis_results.get("strategy", [])],
            [p for _, p in initial_axis_results.get("strategy", [])],
        )

        console.print(f"\n  J_initial = {j_components['J']:.4f}")
        console.print(f"    macroF1_vf  = {j_components['macroF1_vf']:.4f}")
        console.print(f"    macroF1_cat = {j_components['macroF1_cat']:.4f}")
        console.print(f"    acc_strat   = {j_components['acc_strat']:.4f}")

        if args.dry_run:
            console.print("\n[yellow]--dry-run : arrêt après évaluation initiale.[/yellow]")
            metrics = {"j_initial": j_components["J"], **j_components}
            finish_run(conn, run_id, metrics)
            return run_id

        # ── 3. OPTIMISATION ────────────────────────────────────────────
        console.print("\n[bold]Phase 3 : COORDINATE ASCENT[/bold]\n")

        def _on_opt_status(msg: str):
            console.print(f"  {msg}", end="\r")

        ascent_result = await coordinate_ascent(
            conn=conn,
            run_id=run_id,
            rule_states=rule_states,
            prompt_state=prompt_state,
            dev_opt_posts=post_inputs,
            annotations=opt_annotations,
            cached_features=cached_features,
            initial_axis_results=initial_axis_results,
            labels_by_scope=labels_by_scope,
            patience=args.opt_patience,
            max_steps_per_slot=args.opt_max_steps,
            max_passes=args.opt_max_passes,
            n_patches=args.n_patches,
            on_status=_on_opt_status,
        )

        # ── 4. RÉSULTATS ──────────────────────────────────────────────
        console.print("\n[bold]Phase 4 : RÉSULTATS[/bold]\n")

        elapsed = time.monotonic() - t0

        table = Table(title="Résultats par slot")
        table.add_column("Slot")
        table.add_column("Steps")
        table.add_column("Accepted")
        table.add_column("J_initial")
        table.add_column("J_final")
        table.add_column("Delta")
        table.add_column("Tabu hits")

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
        console.print(f"  J_global: {ascent_result.j_global_initial:.4f} → {ascent_result.j_global_final:.4f}")
        console.print(f"  J_global_best: {ascent_result.j_global_best:.4f}")
        console.print(f"  Durée: {elapsed:.0f}s ({elapsed/60:.1f} min)")
        console.print(f"  simulation_run_id = {run_id}")

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

        metrics = {
            "j_initial": ascent_result.j_global_initial,
            "j_final": ascent_result.j_global_final,
            "j_best": ascent_result.j_global_best,
            "passes": ascent_result.passes,
            "total_steps": sum(r.steps_taken for r in ascent_result.slot_results),
            "total_accepted": sum(r.steps_accepted for r in ascent_result.slot_results),
        }
        finish_run(conn, run_id, metrics)
        return run_id

    except (KeyboardInterrupt, SystemExit):
        log.info("Optimisation interrompue (run_id=%s)", run_id)
        if run_id is not None:
            try:
                conn.rollback()
                fail_run(conn, run_id, "interrupted", {})
            except Exception:
                pass
        sys.exit(1)
    except Exception as exc:
        log.exception("[FATAL] Optimisation échouée: %s", exc)
        if run_id is not None:
            try:
                conn.rollback()
                fail_run(conn, run_id, str(exc), {})
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
