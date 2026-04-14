"""Entry point CLI MILPO — classification d'un set sur un mode d'inférence.

Un seul point d'entrée pour évaluer la pipeline MILPO sur un dataset annoté.

Usage (via le binaire `classification` défini dans pyproject.toml) :

    uv run classification --alma --alpha
    uv run classification --simple --test
    uv run classification --alma --dev --limit 20 --no-persist

Modes d'inférence (mutuellement exclusifs, obligatoire) :
- `--alma`   : pipeline ASSIST 2 étages (Alma multimodal + 3 classifieurs text-only)
- `--simple` : 1 appel multimodal ASSIST par post (3 labels d'un coup)

Dataset (mutuellement exclusifs, obligatoire) :
- `--dev`   : `sample_posts.split = 'dev'`
- `--test`  : `sample_posts.split = 'test'`
- `--alpha` : `eval_sets.set_name = 'alpha'`

Options :
- `--limit N`        : limite le nombre de posts (smoke test)
- `--since YYYY-MM-DD`: ne garde que les posts publiés à partir de la date
- `--no-persist`     : dry run, rien n'est écrit en BDD
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import time

from milpo.config import (
    MODEL_CLASSIFIER,
    MODEL_CLASSIFIER_VISUAL_FORMAT,
    MODEL_DESCRIPTOR_FEED,
    MODEL_DESCRIPTOR_REELS,
    MODEL_SIMPLE,
)
from milpo.db import get_conn, load_post_media, load_posts_media
from milpo.gcs import sign_all_posts_media
from milpo.inference import (
    PostInput,
    async_classify_alma_batch,
    async_classify_simple_batch,
)
from milpo.persistence import create_run, finish_run, store_results
from milpo.prompting import build_labels

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(message)s",
    datefmt="%H:%M:%S",
)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("openai").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)
log = logging.getLogger("classification")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="classification",
        description="Classifie les posts d'un set d'évaluation via la pipeline MILPO.",
    )

    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument(
        "--alma",
        action="store_true",
        help="Pipeline ASSIST 2 étages (Alma multimodal + 3 classifieurs text-only).",
    )
    mode.add_argument(
        "--simple",
        action="store_true",
        help="Pipeline 1 appel multimodal ASSIST (3 labels en un coup).",
    )

    dataset = parser.add_mutually_exclusive_group(required=True)
    dataset.add_argument(
        "--dev", action="store_true", help="Split dev (sample_posts.split='dev')."
    )
    dataset.add_argument(
        "--test", action="store_true", help="Split test (sample_posts.split='test')."
    )
    dataset.add_argument(
        "--alpha",
        action="store_true",
        help="Set alpha (eval_sets.set_name='alpha').",
    )

    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Limite le nombre de posts (smoke test).",
    )
    parser.add_argument(
        "--since",
        type=str,
        default=None,
        help="Filtre posts publiés à partir de YYYY-MM-DD.",
    )
    parser.add_argument(
        "--no-persist",
        action="store_true",
        help="Désactive l'écriture en BDD (dry run).",
    )

    return parser


def _pick_mode(args) -> str:
    return "alma" if args.alma else "simple"


def _pick_dataset(args) -> str:
    if args.dev:
        return "dev"
    if args.test:
        return "test"
    return "alpha"


def _load_posts(conn, dataset: str, since: str | None, limit: int | None) -> list[dict]:
    """Charge les posts annotés d'un dataset, prêts à être classifiés."""
    params: dict = {}
    if dataset == "alpha":
        query = """
            SELECT p.ig_media_id, p.caption,
                   p.media_type::text AS media_type,
                   p.media_product_type::text AS media_product_type,
                   p.timestamp AS posted_at
            FROM eval_sets es
            JOIN posts p ON p.ig_media_id = es.ig_media_id
            JOIN annotations a ON a.ig_media_id = p.ig_media_id
            WHERE es.set_name = 'alpha'
              AND a.visual_format_id IS NOT NULL
              AND a.doubtful = false
        """
    else:
        query = """
            SELECT p.ig_media_id, p.caption,
                   p.media_type::text AS media_type,
                   p.media_product_type::text AS media_product_type,
                   p.timestamp AS posted_at
            FROM sample_posts sp
            JOIN posts p ON p.ig_media_id = sp.ig_media_id
            JOIN annotations a ON a.ig_media_id = p.ig_media_id
            WHERE sp.split = %(split)s
              AND a.visual_format_id IS NOT NULL
        """
        params["split"] = dataset

    if since:
        query += " AND p.timestamp >= %(since)s::timestamp"
        params["since"] = since

    query += " ORDER BY p.timestamp"
    if limit:
        query += f" LIMIT {int(limit)}"

    return conn.execute(query, params).fetchall()


def _build_progress(t0: float):
    def on_progress(done: int, total: int, errors: int) -> None:
        elapsed = time.monotonic() - t0
        rate = done / elapsed if elapsed > 0 else 0
        eta = (total - done) / rate if rate > 0 else 0
        filled = done * 30 // total if total else 0
        bar = "█" * filled + "░" * (30 - filled)
        print(
            f"\r  {bar} {done:>3}/{total} "
            f"({(done * 100 // total) if total else 0:>2}%) "
            f"| {rate:.1f} posts/s "
            f"| ETA {eta:.0f}s "
            f"| erreurs {errors}",
            end="",
            flush=True,
        )

    return on_progress


def _models_config(mode: str) -> dict[str, str]:
    if mode == "alma":
        return {
            "descriptor_feed": MODEL_DESCRIPTOR_FEED,
            "descriptor_reels": MODEL_DESCRIPTOR_REELS,
            "classifier": MODEL_CLASSIFIER,
            "classifier_visual_format": MODEL_CLASSIFIER_VISUAL_FORMAT,
        }
    return {"simple": MODEL_SIMPLE}


async def run_classification(args) -> int:
    mode = _pick_mode(args)
    dataset = _pick_dataset(args)

    conn = get_conn()
    t0 = time.monotonic()

    suffix = "_".join(
        [mode, dataset]
        + ([f"since_{args.since}"] if args.since else [])
        + ([f"limit_{args.limit}"] if args.limit else [])
    )

    log.info("=" * 55)
    log.info("MILPO classification — %s", suffix)
    log.info("=" * 55)

    raw_posts = _load_posts(conn, dataset, args.since, args.limit)
    log.info("Posts chargés : %d", len(raw_posts))

    run_id: int | None = None
    if not args.no_persist:
        run_id = create_run(
            conn,
            {
                "name": f"classification_{suffix}",
                "pipeline_mode": mode,
                "dataset": dataset,
                "since": args.since,
                "limit": args.limit,
                "models": _models_config(mode),
            },
        )
        log.info("simulation_run id=%d", run_id)
    else:
        log.info("--no-persist activé : aucune écriture BDD")

    log.info("Signature des URLs GCS...")
    signed_by_post = sign_all_posts_media(
        raw_posts,
        load_post_media,
        conn,
        max_workers=20,
        load_all_media_fn=load_posts_media,
    )

    post_inputs: list[PostInput] = []
    skipped = 0
    for post in raw_posts:
        signed = signed_by_post.get(post["ig_media_id"], [])
        if not signed:
            skipped += 1
            continue
        post_inputs.append(
            PostInput(
                ig_media_id=post["ig_media_id"],
                media_product_type=post["media_product_type"],
                media_urls=[url for url, _ in signed],
                media_types=[media_type for _, media_type in signed],
                caption=post["caption"],
                posted_at=post.get("posted_at"),
            )
        )

    feed = sum(1 for post in post_inputs if post.media_product_type == "FEED")
    reels = len(post_inputs) - feed
    log.info(
        "Prêts : %d (FEED %d / REELS %d) — %d skippés",
        len(post_inputs),
        feed,
        reels,
        skipped,
    )

    labels_by_scope = {scope: build_labels(conn, scope) for scope in ("FEED", "REELS")}
    on_progress = _build_progress(t0)

    log.info("Classification en cours (mode %s)...", mode)

    if mode == "alma":
        results = await async_classify_alma_batch(
            posts=post_inputs,
            labels_by_scope=labels_by_scope,
            max_concurrent_api=20,
            max_concurrent_posts=10,
            on_progress=on_progress,
        )
    else:
        results = await async_classify_simple_batch(
            posts=post_inputs,
            labels_by_scope=labels_by_scope,
            model=MODEL_SIMPLE,
            max_concurrent=10,
            on_progress=on_progress,
        )

    errors = len(post_inputs) - len(results)
    print()
    log.info(
        "Classifiés : %d / %d (erreurs : %d)",
        len(results),
        len(post_inputs),
        errors,
    )

    n = len(results)
    total_api = sum(len(result.api_calls) for result in results)
    matches = {"category": 0, "visual_format": 0, "strategy": 0}

    if not args.no_persist and run_id is not None:
        log.info("Stockage en BDD...")
        matches, total_api = store_results(conn, results, post_inputs, run_id)
        acc = {axis: (value / n if n else 0) for axis, value in matches.items()}
        finish_run(
            conn,
            run_id,
            {
                "accuracy_category": acc["category"],
                "accuracy_visual_format": acc["visual_format"],
                "accuracy_strategy": acc["strategy"],
                "prompt_iterations": None,
                "total_api_calls": total_api,
                "total_cost_usd": None,
            },
        )

    elapsed = time.monotonic() - t0
    total_in = sum(call.input_tokens for r in results for call in r.api_calls)
    total_out = sum(call.output_tokens for r in results for call in r.api_calls)

    log.info("")
    log.info("=" * 55)
    log.info("RÉSULTATS")
    log.info("=" * 55)
    log.info("  Mode           : %s", mode)
    log.info("  Dataset        : %s", dataset)
    log.info("  Posts          : %d", n)
    log.info("  Appels API     : %d", total_api)
    log.info("  Tokens         : %s in / %s out", f"{total_in:,}", f"{total_out:,}")
    log.info("  Durée          : %.0fs (%.1f min)", elapsed, elapsed / 60)
    if not args.no_persist and n:
        log.info("")
        log.info(
            "  Accuracy catégorie     : %.1f%% (%d/%d)",
            matches["category"] * 100 / n,
            matches["category"],
            n,
        )
        log.info(
            "  Accuracy visual_format : %.1f%% (%d/%d)",
            matches["visual_format"] * 100 / n,
            matches["visual_format"],
            n,
        )
        log.info(
            "  Accuracy stratégie     : %.1f%% (%d/%d)",
            matches["strategy"] * 100 / n,
            matches["strategy"],
            n,
        )
        log.info("")
        log.info("  simulation_run_id = %d", run_id)
    log.info("✓ Classification terminée")

    conn.close()
    return run_id or 0


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return asyncio.run(run_classification(args))


if __name__ == "__main__":
    raise SystemExit(main())
