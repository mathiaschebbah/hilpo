"""Helpers de cycle de vie des runs expérimentaux."""

from __future__ import annotations

import json


FEATURE_EXTRACTION_RUN_NAME = "feature_cache_dev"


def create_run(conn, config: dict) -> int:
    """Crée un run de simulation/baseline avec le payload config fourni."""
    row = conn.execute(
        """
        INSERT INTO simulation_runs (seed, batch_size, config, status, started_at)
        VALUES (42, %s, %s::jsonb, 'running', NOW())
        RETURNING id
        """,
        (config.get("batch_size", 0), json.dumps(config)),
    ).fetchone()
    conn.commit()
    return row["id"]


def finish_run(conn, run_id: int, metrics: dict):
    conn.execute(
        """
        UPDATE simulation_runs SET
            status = 'completed', finished_at = NOW(),
            final_accuracy_category = %s,
            final_accuracy_visual_format = %s,
            final_accuracy_strategy = %s,
            prompt_iterations = %s,
            total_api_calls = %s, total_cost_usd = %s
        WHERE id = %s
        """,
        (
            metrics["accuracy_category"],
            metrics["accuracy_visual_format"],
            metrics["accuracy_strategy"],
            metrics.get("prompt_iterations"),
            metrics["total_api_calls"],
            metrics.get("total_cost_usd"),
            run_id,
        ),
    )
    conn.commit()


def fail_run(conn, run_id: int, error_message: str, metrics: dict):
    """Marque un run comme échoué en conservant les métriques partielles."""
    conn.execute(
        """
        UPDATE simulation_runs SET
            status = 'failed', finished_at = NOW(),
            final_accuracy_category = %s,
            final_accuracy_visual_format = %s,
            final_accuracy_strategy = %s,
            prompt_iterations = %s,
            total_api_calls = %s, total_cost_usd = %s,
            config = COALESCE(config, '{}'::jsonb) || jsonb_build_object('failure_reason', %s::text)
        WHERE id = %s
        """,
        (
            metrics["accuracy_category"],
            metrics["accuracy_visual_format"],
            metrics["accuracy_strategy"],
            metrics.get("prompt_iterations"),
            metrics["total_api_calls"],
            metrics.get("total_cost_usd"),
            error_message[:1000] or "unknown error",
            run_id,
        ),
    )
    conn.commit()


def get_or_create_extraction_run(
    conn,
    run_name: str = FEATURE_EXTRACTION_RUN_NAME,
) -> int:
    """Retourne l'id du run de feature extraction dev (existant ou nouveau)."""
    row = conn.execute(
        """
        SELECT id FROM simulation_runs
        WHERE config->>'name' = %s
        ORDER BY id DESC LIMIT 1
        """,
        (run_name,),
    ).fetchone()
    if row is not None:
        return row["id"]

    row = conn.execute(
        """
        INSERT INTO simulation_runs (seed, batch_size, config, status, started_at)
        VALUES (42, 0, %s::jsonb, 'running', NOW())
        RETURNING id
        """,
        (json.dumps({
            "name": run_name,
            "kind": "feature_extraction",
            "split": "dev",
            "description": (
                "Cache des features descripteur pour les posts dev annotés. "
                "Permet à DSPy et autres méthodes d'optimisation d'éviter de "
                "réappeler le descripteur multimodal à chaque itération."
            ),
        }),),
    ).fetchone()
    conn.commit()
    return row["id"]


def finish_extraction_run(conn, run_id: int, n_processed: int, n_skipped: int) -> None:
    conn.execute(
        """
        UPDATE simulation_runs
        SET status = 'completed', finished_at = NOW(),
            config = config || %s::jsonb
        WHERE id = %s
        """,
        (
            json.dumps({
                "n_processed": n_processed,
                "n_skipped_already_cached": n_skipped,
            }),
            run_id,
        ),
    )
    conn.commit()
