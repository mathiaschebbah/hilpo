"""Accès aux versions de prompts."""

from __future__ import annotations

import psycopg


def get_active_prompt(
    conn: psycopg.Connection,
    agent: str,
    scope: str | None,
    source: str = "human_v0",
) -> dict | None:
    """Retourne le prompt actif pour un agent × scope × source."""
    if scope is None:
        return conn.execute(
            """
            SELECT id, agent, scope, version, content, status, source
            FROM prompt_versions
            WHERE agent = %s::agent_type AND scope IS NULL
              AND source = %s AND status = 'active'
            """,
            (agent, source),
        ).fetchone()
    return conn.execute(
        """
        SELECT id, agent, scope, version, content, status, source
        FROM prompt_versions
        WHERE agent = %s::agent_type AND scope = %s::media_product_type
          AND source = %s AND status = 'active'
        """,
        (agent, scope, source),
    ).fetchone()


def get_prompt_version(
    conn: psycopg.Connection,
    agent: str,
    scope: str | None,
    version: int,
    source: str = "human_v0",
) -> dict | None:
    """Retourne une version précise de prompt pour un agent × scope × source."""
    if scope is None:
        return conn.execute(
            """
            SELECT id, agent, scope, version, content, status, source
            FROM prompt_versions
            WHERE agent = %s::agent_type AND scope IS NULL
              AND version = %s AND source = %s
            """,
            (agent, version, source),
        ).fetchone()
    return conn.execute(
        """
        SELECT id, agent, scope, version, content, status, source
        FROM prompt_versions
        WHERE agent = %s::agent_type AND scope = %s::media_product_type
          AND version = %s AND source = %s
        """,
        (agent, scope, version, source),
    ).fetchone()


def insert_prompt_version(
    conn: psycopg.Connection,
    agent: str,
    scope: str | None,
    version: int,
    content: str,
    status: str = "active",
    parent_id: int | None = None,
    simulation_run_id: int | None = None,
    source: str = "human_v0",
) -> int:
    """Insère une nouvelle version de prompt. Retourne l'id."""
    row = conn.execute(
        """
        INSERT INTO prompt_versions
            (agent, scope, version, content, status, parent_id, simulation_run_id, source)
        VALUES (%s, %s, %s, %s, %s::prompt_status, %s, %s, %s)
        RETURNING id
        """,
        (agent, scope, version, content, status, parent_id, simulation_run_id, source),
    ).fetchone()
    conn.commit()
    return row["id"]


def promote_prompt(
    conn: psycopg.Connection,
    agent: str,
    scope: str | None,
    new_id: int,
    source: str = "human_v0",
) -> None:
    """Retire tout prompt actif du slot (agent, scope, source) et active le nouveau."""
    with conn.transaction():
        conn.execute(
            """
            UPDATE prompt_versions
            SET status = 'retired'::prompt_status
            WHERE agent = %s::agent_type
              AND scope IS NOT DISTINCT FROM %s::media_product_type
              AND source = %s
              AND status = 'active'::prompt_status
            """,
            (agent, scope, source),
        )
        conn.execute(
            "UPDATE prompt_versions SET status = 'active'::prompt_status WHERE id = %s",
            (new_id,),
        )
