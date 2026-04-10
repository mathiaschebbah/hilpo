"""Sous-modules de simulation MILPO."""

from __future__ import annotations

from .display import SimulationDisplay
from .evaluation import async_multi_evaluate, evaluate_result_and_store, target_metric_matches
from .rewrite import INCUMBENT_ARM_ID, get_target_errors, pick_rewrite_target, run_protegi_rewrite
from .state import (
    MatchRecord,
    MultiEvalResult,
    PromptState,
    ProtegiArm,
    RewriteOutcome,
    build_run_metrics,
    load_prompt_state_from_db,
)
from .telemetry import emit_init_status, emit_telemetry, init_telemetry, reset_init_telemetry

__all__ = [
    "INCUMBENT_ARM_ID",
    "MatchRecord",
    "MultiEvalResult",
    "PromptState",
    "ProtegiArm",
    "RewriteOutcome",
    "SimulationDisplay",
    "async_multi_evaluate",
    "build_run_metrics",
    "emit_init_status",
    "emit_telemetry",
    "evaluate_result_and_store",
    "get_target_errors",
    "init_telemetry",
    "load_prompt_state_from_db",
    "pick_rewrite_target",
    "reset_init_telemetry",
    "run_protegi_rewrite",
    "target_metric_matches",
]
