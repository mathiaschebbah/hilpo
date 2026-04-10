"""Accès aux taxonomies MILPO."""

from __future__ import annotations

import psycopg


def load_visual_formats(conn: psycopg.Connection, scope: str) -> list[dict]:
    """Charge les formats visuels pour un scope (FEED→post_*, REELS→reel_*)."""
    prefix = "post_" if scope == "FEED" else "reel_"
    return conn.execute(
        "SELECT name, description FROM visual_formats WHERE name LIKE %s ORDER BY name",
        (f"{prefix}%",),
    ).fetchall()


def load_categories(conn: psycopg.Connection) -> list[dict]:
    return conn.execute(
        "SELECT name, description FROM categories ORDER BY name"
    ).fetchall()


def load_strategies(conn: psycopg.Connection) -> list[dict]:
    return conn.execute(
        "SELECT name, description FROM strategies ORDER BY name"
    ).fetchall()


def format_descriptions(items: list[dict]) -> str:
    """Formate les descriptions taxonomiques pour injection dans le prompt."""
    lines = []
    for item in items:
        desc = item["description"] or "(pas de description)"
        lines.append(f"- **{item['name']}** : {desc}")
    return "\n".join(lines)
