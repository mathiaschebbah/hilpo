"""Structures d'état et métriques de la simulation MILPO."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from milpo.prompting import PROMPT_KEYS, load_active_prompt_records


@dataclass
class PromptState:
    """Prompt actif par (agent, scope)."""

    instructions: dict[tuple[str, str | None], str] = field(default_factory=dict)
    db_ids: dict[tuple[str, str | None], int] = field(default_factory=dict)
    versions: dict[tuple[str, str | None], int] = field(default_factory=dict)


@dataclass
class MatchRecord:
    """Enregistrement d'un match/mismatch par axe."""

    axis: str
    match: bool
    cursor: int
    scope: str | None = None


@dataclass
class MultiEvalResult:
    """Résultats détaillés de la multi-évaluation ProTeGi."""

    matches_by_arm: dict[int, list[bool]] = field(default_factory=dict)
    incumbent_records: list[MatchRecord] = field(default_factory=list)
    incumbent_arm_id: int = 0


@dataclass
class RewriteOutcome:
    """Résultat d'une tentative de rewrite ProTeGi."""

    triggered: bool
    promoted: bool
    winner_db_id: int | None
    incumbent_acc: float | None
    candidate_acc: float | None
    eval_window_consumed: int
    incumbent_records: list[MatchRecord]
    failed: bool = False


@dataclass
class ProtegiArm:
    """Un bras du bandit ProTeGi (edit ou paraphrase) prêt à être évalué."""

    beam_row_id: int
    prompt_db_id: int
    version: int
    kind: str
    instructions: str


def build_run_metrics(
    matches_by_axis: dict[str, int],
    n_processed: int,
    rewrite_count: int,
    total_api_calls: int,
) -> dict:
    """Construit le payload de métriques final ou partiel pour simulation_runs."""
    return {
        "accuracy_category": matches_by_axis["category"] / n_processed if n_processed else 0,
        "accuracy_visual_format": matches_by_axis["visual_format"] / n_processed if n_processed else 0,
        "accuracy_strategy": matches_by_axis["strategy"] / n_processed if n_processed else 0,
        "prompt_iterations": rewrite_count,
        "total_api_calls": total_api_calls,
        "total_cost_usd": None,
    }


def load_prompt_state_from_db(conn, logger: logging.Logger | None = None) -> PromptState:
    """Charge l'état initial du PromptState depuis la BDD."""
    prompt_records, prompt_ids, prompt_versions = load_active_prompt_records(conn, PROMPT_KEYS)
    if logger is not None:
        for agent, scope in PROMPT_KEYS:
            row = prompt_records[(agent, scope)]
            logger.info(
                "  prompt chargé : %s/%s -> v%s (id=%d)",
                agent,
                scope or "all",
                row["version"],
                row["id"],
            )

    return PromptState(
        instructions={key: row["content"] for key, row in prompt_records.items()},
        db_ids=prompt_ids,
        versions=prompt_versions,
    )
