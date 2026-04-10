"""Entrypoint workflow pour l'import des CSV."""

from __future__ import annotations

from milpo.importing import run_import as _run_import


def run_import(_args=None):
    _run_import()


def main(argv: list[str] | None = None):
    del argv
    return run_import()


__all__ = ["main", "run_import"]
