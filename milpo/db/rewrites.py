"""Persistance ProTeGi et logs de rewrite."""

from __future__ import annotations

import json

import psycopg


def store_rewrite_log(
    conn: psycopg.Connection,
    prompt_before_id: int,
    prompt_after_id: int,
    error_batch: list[dict],
    rewriter_reasoning: str,
    accepted: bool,
    simulation_run_id: int,
    target_agent: str,
    target_scope: str | None,
    incumbent_accuracy: float,
    candidate_accuracy: float,
    eval_sample_size: int,
    iteration: int,
) -> int:
    """Insère un log de rewrite. Retourne l'id."""
    row = conn.execute(
        """
        INSERT INTO rewrite_logs
            (prompt_before_id, prompt_after_id, error_batch, rewriter_reasoning,
             accepted, simulation_run_id, target_agent, target_scope,
             incumbent_accuracy, candidate_accuracy, eval_sample_size, iteration)
        VALUES (%s, %s, %s::jsonb, %s, %s, %s, %s::agent_type, %s, %s, %s, %s, %s)
        RETURNING id
        """,
        (
            prompt_before_id,
            prompt_after_id,
            json.dumps(error_batch),
            rewriter_reasoning,
            accepted,
            simulation_run_id,
            target_agent,
            target_scope,
            incumbent_accuracy,
            candidate_accuracy,
            eval_sample_size,
            iteration,
        ),
    ).fetchone()
    conn.commit()
    return row["id"]


def store_gradient(
    conn: psycopg.Connection,
    *,
    simulation_run_id: int,
    iteration: int,
    target_agent: str,
    target_scope: str | None,
    prompt_id: int,
    gradient_text: str,
    n_critiques: int,
    model: str,
    input_tokens: int,
    output_tokens: int,
    latency_ms: int,
) -> int:
    """Insère un row dans rewrite_gradients (1 row par appel critic LLM_∇)."""
    row = conn.execute(
        """
        INSERT INTO rewrite_gradients
            (simulation_run_id, iteration, target_agent, target_scope, prompt_id,
             gradient_text, n_critiques, model,
             input_tokens, output_tokens, latency_ms)
        VALUES (%s, %s, %s::agent_type, %s::media_product_type, %s,
                %s, %s, %s,
                %s, %s, %s)
        RETURNING id
        """,
        (
            simulation_run_id,
            iteration,
            target_agent,
            target_scope,
            prompt_id,
            gradient_text,
            n_critiques,
            model,
            input_tokens,
            output_tokens,
            latency_ms,
        ),
    ).fetchone()
    conn.commit()
    return row["id"]


def store_beam_candidate(
    conn: psycopg.Connection,
    *,
    simulation_run_id: int,
    iteration: int,
    target_agent: str,
    target_scope: str | None,
    parent_prompt_id: int,
    candidate_prompt_id: int,
    gradient_id: int,
    generation_kind: str,
    eval_accuracy: float | None = None,
    eval_sample_size: int | None = None,
    sr_phase: int | None = None,
    sr_eliminated: bool = False,
    is_winner: bool = False,
) -> int:
    """Insère un candidat du beam ProTeGi dans rewrite_beam_candidates."""
    if generation_kind not in ("edit", "paraphrase"):
        raise ValueError(
            f"store_beam_candidate: generation_kind invalide '{generation_kind}'"
        )
    row = conn.execute(
        """
        INSERT INTO rewrite_beam_candidates
            (simulation_run_id, iteration, target_agent, target_scope,
             parent_prompt_id, candidate_prompt_id, gradient_id, generation_kind,
             eval_accuracy, eval_sample_size, sr_phase, sr_eliminated, is_winner)
        VALUES (%s, %s, %s::agent_type, %s::media_product_type,
                %s, %s, %s, %s::generation_kind,
                %s, %s, %s, %s, %s)
        RETURNING id
        """,
        (
            simulation_run_id,
            iteration,
            target_agent,
            target_scope,
            parent_prompt_id,
            candidate_prompt_id,
            gradient_id,
            generation_kind,
            eval_accuracy,
            eval_sample_size,
            sr_phase,
            sr_eliminated,
            is_winner,
        ),
    ).fetchone()
    conn.commit()
    return row["id"]


def update_beam_candidate_eval(
    conn: psycopg.Connection,
    *,
    candidate_row_id: int,
    eval_accuracy: float,
    eval_sample_size: int,
) -> None:
    """Renseigne l'accuracy d'un candidat après multi_evaluate."""
    conn.execute(
        """
        UPDATE rewrite_beam_candidates
        SET eval_accuracy = %s, eval_sample_size = %s
        WHERE id = %s
        """,
        (eval_accuracy, eval_sample_size, candidate_row_id),
    )
    conn.commit()


def update_beam_candidate_sr(
    conn: psycopg.Connection,
    *,
    candidate_row_id: int,
    sr_phase: int | None,
    sr_eliminated: bool,
    is_winner: bool = False,
) -> None:
    """Renseigne le résultat de Successive Rejects pour un candidat."""
    conn.execute(
        """
        UPDATE rewrite_beam_candidates
        SET sr_phase = %s, sr_eliminated = %s, is_winner = %s
        WHERE id = %s
        """,
        (sr_phase, sr_eliminated, is_winner, candidate_row_id),
    )
    conn.commit()
