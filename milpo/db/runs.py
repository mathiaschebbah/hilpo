"""Persistance liée aux runs et aux logs de classification."""

from __future__ import annotations

import json

import psycopg


def store_prediction(
    conn: psycopg.Connection,
    ig_media_id: int,
    agent: str,
    prompt_version_id: int,
    predicted_value: str | None,
    raw_response: dict | None = None,
    simulation_run_id: int | None = None,
) -> int:
    """Stocke une prédiction. Le trigger calcule match automatiquement."""
    row = conn.execute(
        """
        INSERT INTO predictions
            (ig_media_id, agent, prompt_version_id, predicted_value, raw_response, simulation_run_id)
        VALUES (%s, %s::agent_type, %s, %s, %s::jsonb, %s)
        RETURNING id, match
        """,
        (
            ig_media_id,
            agent,
            prompt_version_id,
            predicted_value,
            json.dumps(raw_response) if raw_response else None,
            simulation_run_id,
        ),
    ).fetchone()
    conn.commit()
    return row["id"]


def store_api_call(
    conn: psycopg.Connection,
    call_type: str,
    agent: str,
    model_name: str,
    prompt_version_id: int | None,
    ig_media_id: int | None,
    input_tokens: int,
    output_tokens: int,
    cost_usd: float | None,
    latency_ms: int,
    simulation_run_id: int | None = None,
    reasoning_tokens: int = 0,
) -> int:
    row = conn.execute(
        """
        INSERT INTO api_calls
            (call_type, agent, model_name, prompt_version_id, ig_media_id,
             input_tokens, output_tokens, cost_usd, latency_ms, simulation_run_id,
             reasoning_tokens)
        VALUES (%s::api_call_type, %s::agent_type, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        RETURNING id
        """,
        (
            call_type,
            agent,
            model_name,
            prompt_version_id,
            ig_media_id,
            input_tokens,
            output_tokens,
            cost_usd,
            latency_ms,
            simulation_run_id,
            reasoning_tokens,
        ),
    ).fetchone()
    conn.commit()
    return row["id"]
