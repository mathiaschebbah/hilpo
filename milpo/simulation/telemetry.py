"""Bridge de télémétrie websocket pour la simulation MILPO."""

from __future__ import annotations

import json
import logging
import os
import time

from websockets.sync.client import connect as ws_connect

log = logging.getLogger("simulation")

_ws = None
_init_t0 = 0.0
_init_stage = ""
_init_stage_t0 = 0.0


def init_telemetry():
    """Connecte au WS server de la TUI TypeScript avec retry."""
    global _ws
    host = os.environ.get("MILPO_WS_HOST", "127.0.0.1")
    port = os.environ.get("MILPO_WS_PORT")
    if port is None:
        return
    for attempt in range(5):
        try:
            _ws = ws_connect(f"ws://{host}:{port}")
            return
        except (ConnectionRefusedError, OSError):
            if attempt < 4:
                time.sleep(0.5)
    log.warning(
        "Impossible de se connecter au WS server TUI sur %s:%s — télémétrie désactivée",
        host,
        port,
    )


def emit_telemetry(display) -> None:
    """Envoie l'état complet au WS server."""
    if _ws is not None:
        try:
            _ws.send(json.dumps(display.to_json()))
        except Exception as exc:
            log.debug("emit_telemetry échoué: %s", exc)


def reset_init_telemetry():
    global _init_t0, _init_stage, _init_stage_t0
    _init_t0 = time.monotonic()
    _init_stage = ""
    _init_stage_t0 = _init_t0


def emit_init_status(
    phase: str,
    *,
    stage: str | None = None,
    done: int | None = None,
    total: int | None = None,
    unit: str | None = None,
):
    """Envoie un message d'initialisation léger à la TUI."""
    global _init_stage, _init_stage_t0
    if _ws is None:
        return
    try:
        now = time.monotonic()
        if stage is not None and stage != _init_stage:
            _init_stage = stage
            _init_stage_t0 = now

        payload: dict[str, object] = {"init": True, "phase": phase}
        if stage is not None:
            payload["stage"] = stage
        if done is not None:
            payload["done"] = done
        if total is not None:
            payload["total"] = total
        if unit is not None:
            payload["unit"] = unit
        payload["elapsedSec"] = round(now - _init_t0, 1)
        payload["stageElapsedSec"] = round(now - _init_stage_t0, 1)
        if done is not None and total is not None and done > 0:
            elapsed = max(now - _init_stage_t0, 1e-6)
            rate = done / elapsed
            payload["rate"] = round(rate, 2)
            if total >= done and rate > 0:
                payload["etaSec"] = round((total - done) / rate, 1)
        _ws.send(json.dumps(payload))
    except Exception as exc:
        log.debug("emit_init_status échoué: %s", exc)
