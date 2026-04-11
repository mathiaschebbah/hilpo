"""CRUD pour prompt_rules, prompt_skeletons, signal_vocabulary, dev_split, optimization_steps."""

from __future__ import annotations

import json

import psycopg

from milpo.dsl import DSLRule, compile_rule


# ── Skeletons ──────────────────────────────────────────────────────────────


def insert_skeleton(
    conn: psycopg.Connection,
    agent: str,
    scope: str | None,
    text: str,
) -> int:
    """Insère un skeleton pour un slot. Retourne l'id."""
    row = conn.execute(
        """
        INSERT INTO prompt_skeletons (agent, scope, text)
        VALUES (%s, %s, %s)
        ON CONFLICT (agent, scope) DO UPDATE SET text = EXCLUDED.text
        RETURNING id
        """,
        (agent, scope, text),
    ).fetchone()
    conn.commit()
    return row["id"]


def get_skeleton(
    conn: psycopg.Connection,
    agent: str,
    scope: str | None,
) -> str | None:
    """Retourne le texte du skeleton pour un slot, ou None."""
    if scope is None:
        row = conn.execute(
            "SELECT text FROM prompt_skeletons WHERE agent = %s AND scope IS NULL",
            (agent,),
        ).fetchone()
    else:
        row = conn.execute(
            "SELECT text FROM prompt_skeletons WHERE agent = %s AND scope = %s",
            (agent, scope),
        ).fetchone()
    return row["text"] if row else None


# ── Rules ──────────────────────────────────────────────────────────────────


def insert_rules(
    conn: psycopg.Connection,
    prompt_version_id: int,
    agent: str,
    scope: str | None,
    rules: list[DSLRule],
) -> None:
    """Insère les règles pour un prompt_version. rules = list de DSLRule ordonnées."""
    for position, rule in enumerate(rules):
        compiled = compile_rule(rule)
        conn.execute(
            """
            INSERT INTO prompt_rules
                (prompt_version_id, agent, scope, position, rule_type, rule_data, compiled_text)
            VALUES (%s, %s, %s, %s, %s::dsl_rule_type, %s::jsonb, %s)
            """,
            (
                prompt_version_id,
                agent,
                scope,
                position,
                rule.rule_type.value,
                json.dumps(rule.to_dict()),
                compiled,
            ),
        )
    conn.commit()


def load_rules(
    conn: psycopg.Connection,
    prompt_version_id: int,
) -> list[DSLRule]:
    """Charge les règles ordonnées par position pour un prompt_version."""
    rows = conn.execute(
        """
        SELECT rule_data FROM prompt_rules
        WHERE prompt_version_id = %s
        ORDER BY position
        """,
        (prompt_version_id,),
    ).fetchall()
    return [DSLRule.from_dict(row["rule_data"]) for row in rows]


# ── Signal vocabulary ──────────────────────────────────────────────────────


def insert_signal_vocab(
    conn: psycopg.Connection,
    scope: str,
    signals: list[tuple[str, str]],
) -> None:
    """Insère le vocabulaire de signaux pour un scope. signals = [(name, description), ...]."""
    for name, description in signals:
        conn.execute(
            """
            INSERT INTO signal_vocabulary (scope, signal_name, description)
            VALUES (%s, %s, %s)
            ON CONFLICT (scope, signal_name) DO UPDATE SET description = EXCLUDED.description
            """,
            (scope, name, description),
        )
    conn.commit()


def load_signal_vocab(
    conn: psycopg.Connection,
    scope: str,
) -> set[str]:
    """Charge les noms de signaux pour un scope."""
    rows = conn.execute(
        "SELECT signal_name FROM signal_vocabulary WHERE scope = %s",
        (scope,),
    ).fetchall()
    return {row["signal_name"] for row in rows}


# ── Dev split ──────────────────────────────────────────────────────────────


def insert_dev_split_assignments(
    conn: psycopg.Connection,
    assignments: list[tuple[int, str]],
) -> None:
    """Insère les assignments dev-opt/dev-holdout. assignments = [(ig_media_id, sub_split), ...]."""
    for ig_media_id, sub_split in assignments:
        conn.execute(
            """
            INSERT INTO dev_split_assignment (ig_media_id, sub_split)
            VALUES (%s, %s)
            ON CONFLICT (ig_media_id) DO UPDATE SET sub_split = EXCLUDED.sub_split
            """,
            (ig_media_id, sub_split),
        )
    conn.commit()


def load_dev_split_assignments(
    conn: psycopg.Connection,
) -> dict[int, str]:
    """Charge tous les assignments. Retourne {ig_media_id: sub_split}."""
    rows = conn.execute(
        "SELECT ig_media_id, sub_split FROM dev_split_assignment"
    ).fetchall()
    return {row["ig_media_id"]: row["sub_split"] for row in rows}


def count_dev_split(conn: psycopg.Connection) -> dict[str, int]:
    """Retourne le nombre de posts par sub_split."""
    rows = conn.execute(
        "SELECT sub_split, COUNT(*) as n FROM dev_split_assignment GROUP BY sub_split"
    ).fetchall()
    return {row["sub_split"]: row["n"] for row in rows}


# ── Optimization steps ─────────────────────────────────────────────────────


def insert_optimization_step(
    conn: psycopg.Connection,
    *,
    simulation_run_id: int,
    step_number: int,
    pass_number: int,
    target_agent: str,
    target_scope: str | None,
    op_type: str | None,
    op_index: int | None,
    op_rule_type: str | None,
    op_rule_data: dict | None,
    critique_text: str,
    critique_target_index: int | None,
    j_before: float,
    j_after: float | None,
    accepted: bool,
    state_hash_before: str,
    state_hash_after: str | None,
    tabu_hit: bool,
    skipped_invalid: bool,
    incumbent_prompt_id: int,
    candidate_prompt_id: int | None,
) -> int:
    """Insère un step d'optimisation. Retourne l'id."""
    row = conn.execute(
        """
        INSERT INTO optimization_steps
            (simulation_run_id, step_number, pass_number,
             target_agent, target_scope,
             op_type, op_index, op_rule_type, op_rule_data,
             critique_text, critique_target_index,
             j_before, j_after, accepted,
             state_hash_before, state_hash_after,
             tabu_hit, skipped_invalid,
             incumbent_prompt_id, candidate_prompt_id)
        VALUES (%s, %s, %s,
                %s, %s,
                %s, %s, %s, %s::jsonb,
                %s, %s,
                %s, %s, %s,
                %s, %s,
                %s, %s,
                %s, %s)
        RETURNING id
        """,
        (
            simulation_run_id, step_number, pass_number,
            target_agent, target_scope,
            op_type, op_index, op_rule_type,
            json.dumps(op_rule_data) if op_rule_data else None,
            critique_text, critique_target_index,
            j_before, j_after, accepted,
            state_hash_before, state_hash_after,
            tabu_hit, skipped_invalid,
            incumbent_prompt_id, candidate_prompt_id,
        ),
    ).fetchone()
    conn.commit()
    return row["id"]
