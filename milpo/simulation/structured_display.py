"""État de télémétrie pour l'optimisation structurée.

Exposé à la TUI TypeScript Ink via WebSocket sous la forme
`{"mode": "structured", ...}` — discriminé côté TS pour choisir le Dashboard.
"""

from __future__ import annotations

import time
from collections import deque
from dataclasses import dataclass
from datetime import datetime

MAX_EVENTS = 200

# Estimation de coût (mêmes ratios que workflows/simulation.py)
COST_IN_PER_TOKEN = 0.0001 / 1000
COST_OUT_PER_TOKEN = 0.0003 / 1000


@dataclass
class StructuredEvent:
    ts: str
    msg: str
    type: str = "event"  # event | step | accept | reject | api | error


@dataclass
class SlotStatus:
    agent: str
    scope: str | None
    steps_taken: int = 0
    steps_accepted: int = 0
    j_initial: float = 0.0
    j_current: float = 0.0
    tabu_hits: int = 0
    done: bool = False


class StructuredDisplay:
    def __init__(self, run_id: int, flags: list[str] | None = None):
        self.run_id = run_id
        self.flags = flags or []
        self.t0 = time.monotonic()

        self.phase = "bootstrap"
        self.phase_started_at = self.t0
        self.phase_done = 0
        self.phase_total = 0
        self.phase_unit: str | None = None

        self.pass_num = 0
        self.pass_max = 0
        self.current_slot_key: str | None = None
        self.current_step = 0
        self.current_step_max = 0
        self.current_sub_phase: str | None = None

        self.j_global_initial: float | None = None
        self.j_global_current: float | None = None
        self.j_components: dict[str, float] = {}
        self.j_holdout: float | None = None
        self.j_holdout_components: dict[str, float] = {}

        self.slots: dict[str, SlotStatus] = {}

        # Compteurs macro
        self.n_steps_global = 0
        self.n_steps_accepted_global = 0
        self.n_passes_completed = 0
        self.n_slots_done = 0

        # API / coût cumulés
        self.total_input_tokens = 0
        self.total_output_tokens = 0
        self.cost_usd = 0.0
        self.api_calls_count = 0

        self.events: deque[StructuredEvent] = deque(maxlen=MAX_EVENTS)

        self.last_activity = time.monotonic()
        self.last_activity_label = "init"

    # ── Events et heartbeat ────────────────────────────────────────────────

    def heartbeat(self, label: str = "") -> None:
        self.last_activity = time.monotonic()
        if label:
            self.last_activity_label = label

    def add_event(self, msg: str, event_type: str = "event") -> None:
        ts = datetime.now().strftime("%H:%M:%S")
        self.events.appendleft(StructuredEvent(ts=ts, msg=msg, type=event_type))
        self.heartbeat(msg[:30])

    # ── API calls ──────────────────────────────────────────────────────────

    def add_api_call(
        self,
        agent: str,
        model: str,
        latency_ms: int,
        in_tok: int,
        out_tok: int,
        status: str,
    ) -> None:
        self.total_input_tokens += in_tok
        self.total_output_tokens += out_tok
        self.cost_usd += in_tok * COST_IN_PER_TOKEN + out_tok * COST_OUT_PER_TOKEN
        self.api_calls_count += 1

        short_model = model.split("/")[-1] if "/" in model else model
        if len(short_model) > 20:
            short_model = short_model[:20]
        icon = "✓" if status == "ok" else ("ERR" if status == "error" else "↻")
        msg = (
            f"{agent:<12s} {short_model:<20s} "
            f"{latency_ms:>5d}ms  "
            f"{_fmt_tok(in_tok)}→{_fmt_tok(out_tok)}  "
            f"{icon}"
        )
        self.add_event(msg, event_type="api")

    # ── Phase ──────────────────────────────────────────────────────────────

    def set_phase(self, phase: str, unit: str | None = None) -> None:
        self.phase = phase
        self.phase_started_at = time.monotonic()
        self.phase_done = 0
        self.phase_total = 0
        self.phase_unit = unit
        self.add_event(f"phase → {phase}")

    def set_phase_progress(self, done: int, total: int) -> None:
        self.phase_done = done
        self.phase_total = total

    # ── J ──────────────────────────────────────────────────────────────────

    def set_j_initial(self, j: float, components: dict[str, float]) -> None:
        self.j_global_initial = j
        self.j_global_current = j
        self.j_components = dict(components)

    def update_j_current(
        self, j: float, components: dict[str, float] | None = None
    ) -> None:
        self.j_global_current = j
        if components is not None:
            self.j_components = dict(components)

    def set_j_holdout(self, j: float, components: dict[str, float]) -> None:
        self.j_holdout = j
        self.j_holdout_components = dict(components)

    # ── Pass / slot / step ─────────────────────────────────────────────────

    def set_pass(self, pass_num: int, pass_max: int) -> None:
        self.pass_num = pass_num
        self.pass_max = pass_max

    def register_pass_done(self) -> None:
        self.n_passes_completed += 1

    def start_slot(
        self,
        agent: str,
        scope: str | None,
        j_initial: float,
        max_steps: int,
    ) -> None:
        slot_key = f"{agent}/{scope or 'all'}"
        self.current_slot_key = slot_key
        self.current_step = 0
        self.current_step_max = max_steps
        self.current_sub_phase = None
        if slot_key not in self.slots:
            self.slots[slot_key] = SlotStatus(
                agent=agent,
                scope=scope,
                j_initial=j_initial,
                j_current=j_initial,
            )
        else:
            self.slots[slot_key].j_current = j_initial
        self.add_event(f"slot start {slot_key} J={j_initial:.4f}", "step")

    def slot_step(self, step: int, sub_phase: str | None = None) -> None:
        self.current_step = step
        self.current_sub_phase = sub_phase
        self.heartbeat(f"{self.current_slot_key} step {step} {sub_phase or ''}")

    def accept_step(
        self, j_before: float, j_after: float, rule_summary: str
    ) -> None:
        self.n_steps_global += 1
        self.n_steps_accepted_global += 1
        if self.current_slot_key and self.current_slot_key in self.slots:
            slot = self.slots[self.current_slot_key]
            slot.steps_taken += 1
            slot.steps_accepted += 1
            slot.j_current = j_after
        self.update_j_current(j_after)
        self.add_event(
            f"ACCEPT {self.current_slot_key} J={j_before:.4f}→{j_after:.4f} ({rule_summary})",
            "accept",
        )

    def reject_step(self, patience_left: int, patience_max: int) -> None:
        self.n_steps_global += 1
        if self.current_slot_key and self.current_slot_key in self.slots:
            self.slots[self.current_slot_key].steps_taken += 1
        self.add_event(
            f"reject {self.current_slot_key} patience={patience_left}/{patience_max}",
            "reject",
        )

    def inc_tabu(self) -> None:
        if self.current_slot_key and self.current_slot_key in self.slots:
            self.slots[self.current_slot_key].tabu_hits += 1

    def finish_slot(
        self,
        steps_taken: int,
        steps_accepted: int,
        j_initial: float,
        j_final: float,
        tabu_hits: int,
    ) -> None:
        slot_key = self.current_slot_key
        if slot_key and slot_key in self.slots:
            slot = self.slots[slot_key]
            slot.steps_taken = steps_taken
            slot.steps_accepted = steps_accepted
            slot.j_initial = j_initial
            slot.j_current = j_final
            slot.tabu_hits = tabu_hits
            slot.done = True
        self.n_slots_done += 1
        delta = j_final - j_initial
        self.add_event(
            f"slot done {slot_key} Δ={delta:+.4f} ({steps_accepted}/{steps_taken} accepted)",
            "step",
        )
        self.current_slot_key = None
        self.current_step = 0
        self.current_step_max = 0
        self.current_sub_phase = None

    # ── Sérialisation ──────────────────────────────────────────────────────

    def _compute_rate_eta(self) -> tuple[float, float | None]:
        """Retourne (rate, eta) en fonction de la phase courante.

        - Eval phases : rate = posts/s, eta basée sur phase_done/phase_total.
        - coord_ascent : rate = steps/s global, pas d'eta (trop variable).
        - Autres : rate = 0, pas d'eta.
        """
        phase_elapsed = max(time.monotonic() - self.phase_started_at, 1e-6)
        if self.phase in ("eval_initial", "eval_holdout", "bootstrap"):
            rate = self.phase_done / phase_elapsed if self.phase_done else 0.0
            if rate > 0 and self.phase_total > self.phase_done:
                eta = (self.phase_total - self.phase_done) / rate
                return rate, eta
            return rate, None
        if self.phase == "coord_ascent":
            rate = self.n_steps_global / phase_elapsed if self.n_steps_global else 0.0
            return rate, None
        return 0.0, None

    def to_json(self) -> dict:
        elapsed = time.monotonic() - self.t0
        phase_elapsed = time.monotonic() - self.phase_started_at
        idle = time.monotonic() - self.last_activity
        rate, eta = self._compute_rate_eta()
        return {
            "mode": "structured",
            "runId": self.run_id,
            "flags": self.flags,
            "phase": self.phase,
            "phaseElapsedSec": round(phase_elapsed),
            "phaseDone": self.phase_done,
            "phaseTotal": self.phase_total,
            "phaseUnit": self.phase_unit,
            "elapsedSec": round(elapsed),
            "rate": round(rate, 2),
            "etaSec": round(eta) if eta is not None else None,
            "lastActivitySec": round(idle),
            "lastActivityLabel": self.last_activity_label,
            "passNum": self.pass_num,
            "passMax": self.pass_max,
            "currentSlot": self.current_slot_key,
            "currentStep": self.current_step,
            "currentStepMax": self.current_step_max,
            "currentSubPhase": self.current_sub_phase,
            "jInitial": self.j_global_initial,
            "jCurrent": self.j_global_current,
            "jComponents": self.j_components,
            "jHoldout": self.j_holdout,
            "jHoldoutComponents": self.j_holdout_components,
            "slots": [
                {
                    "key": key,
                    "agent": slot.agent,
                    "scope": slot.scope,
                    "stepsTaken": slot.steps_taken,
                    "stepsAccepted": slot.steps_accepted,
                    "jInitial": round(slot.j_initial, 4),
                    "jCurrent": round(slot.j_current, 4),
                    "tabuHits": slot.tabu_hits,
                    "done": slot.done,
                }
                for key, slot in self.slots.items()
            ],
            "nStepsGlobal": self.n_steps_global,
            "nStepsAcceptedGlobal": self.n_steps_accepted_global,
            "nPassesCompleted": self.n_passes_completed,
            "nSlotsDone": self.n_slots_done,
            "costUsd": round(self.cost_usd, 3),
            "inputTokens": self.total_input_tokens,
            "outputTokens": self.total_output_tokens,
            "apiCallsCount": self.api_calls_count,
            "events": [
                {"ts": e.ts, "msg": e.msg, "type": e.type}
                for e in list(self.events)
            ],
        }


def _fmt_tok(n: int) -> str:
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}M"
    if n >= 1_000:
        return f"{n / 1_000:.1f}K"
    return str(n)
