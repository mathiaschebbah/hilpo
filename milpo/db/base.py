"""Connexion BDD pour le moteur MILPO."""

from __future__ import annotations

import psycopg
from psycopg.rows import dict_row

from milpo.config import DATABASE_DSN


def get_conn() -> psycopg.Connection:
    return psycopg.connect(DATABASE_DSN, row_factory=dict_row)
