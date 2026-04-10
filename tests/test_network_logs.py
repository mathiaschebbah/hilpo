"""Tests TDD pour les logs réseau temps réel dans la simulation MILPO.

Fonctionnalités testées :
1. DisplayEvent structuré avec champ type
2. add_api_log() crée des events formatés de type "api"
3. to_json() sérialise le type
4. Events deque assez large pour le flux réseau
5. Hooks d'appels API dans async_inference et rewriter
"""

from __future__ import annotations

import time
import unittest

from milpo.simulation.display import SimulationDisplay


class DisplayEventTypeTests(unittest.TestCase):
    """add_event supporte un paramètre event_type."""

    def _display(self) -> SimulationDisplay:
        return SimulationDisplay(run_id=1, total=100, batch_size=30)

    def test_add_event_default_type_is_event(self) -> None:
        d = self._display()
        d.add_event("test message")
        events = d.to_json()["events"]
        self.assertEqual(events[0]["type"], "event")

    def test_add_event_custom_type(self) -> None:
        d = self._display()
        d.add_event("api call done", event_type="api")
        events = d.to_json()["events"]
        self.assertEqual(events[0]["type"], "api")

    def test_add_event_error_type(self) -> None:
        d = self._display()
        d.add_event("TIMEOUT batch", event_type="error")
        events = d.to_json()["events"]
        self.assertEqual(events[0]["type"], "error")


class AddApiLogTests(unittest.TestCase):
    """add_api_log() crée un event formaté avec agent, model, latence, tokens."""

    def _display(self) -> SimulationDisplay:
        return SimulationDisplay(run_id=1, total=100, batch_size=30)

    def test_creates_api_type_event(self) -> None:
        d = self._display()
        d.add_api_log("descriptor", "gemini-3-flash-preview", 1234, 5000, 500, "ok")
        ev = d.to_json()["events"][0]
        self.assertEqual(ev["type"], "api")

    def test_msg_contains_agent(self) -> None:
        d = self._display()
        d.add_api_log("descriptor", "gemini-3-flash", 1234, 5000, 500, "ok")
        self.assertIn("descriptor", d.to_json()["events"][0]["msg"])

    def test_msg_contains_latency(self) -> None:
        d = self._display()
        d.add_api_log("category", "qwen-3.5-flash", 456, 2000, 100, "ok")
        self.assertIn("456ms", d.to_json()["events"][0]["msg"])

    def test_msg_contains_tokens(self) -> None:
        d = self._display()
        d.add_api_log("category", "qwen-3.5-flash", 456, 2100, 200, "ok")
        msg = d.to_json()["events"][0]["msg"]
        self.assertIn("2.1K", msg)
        self.assertIn("0.2K", msg)

    def test_ok_status_has_checkmark(self) -> None:
        d = self._display()
        d.add_api_log("descriptor", "gemini", 1000, 3000, 300, "ok")
        self.assertIn("\u2713", d.to_json()["events"][0]["msg"])

    def test_error_status_has_err_marker(self) -> None:
        d = self._display()
        d.add_api_log("category", "qwen", 5000, 2000, 0, "error")
        self.assertIn("ERR", d.to_json()["events"][0]["msg"])

    def test_retry_status_has_retry_marker(self) -> None:
        d = self._display()
        d.add_api_log("vf", "qwen", 2000, 1000, 0, "retry")
        msg = d.to_json()["events"][0]["msg"]
        self.assertTrue("retry" in msg.lower() or "\u21bb" in msg)

    def test_updates_heartbeat(self) -> None:
        d = self._display()
        old = d.last_activity
        time.sleep(0.01)
        d.add_api_log("descriptor", "gemini", 1000, 3000, 300, "ok")
        self.assertGreater(d.last_activity, old)

    def test_model_name_truncated_if_long(self) -> None:
        d = self._display()
        d.add_api_log("descriptor", "google/gemini-3-flash-preview-04-17", 1000, 3000, 300, "ok")
        msg = d.to_json()["events"][0]["msg"]
        # Model name should be shortened (no provider prefix, reasonable length)
        self.assertNotIn("google/", msg)


class EventsCapacityTests(unittest.TestCase):
    """Le deque events est assez large pour contenir le flux réseau."""

    def test_deque_holds_at_least_200_events(self) -> None:
        d = SimulationDisplay(run_id=1, total=100, batch_size=30)
        for i in range(200):
            d.add_event(f"event {i}")
        self.assertEqual(len(d.to_json()["events"]), 200)

    def test_oldest_events_dropped_when_full(self) -> None:
        d = SimulationDisplay(run_id=1, total=100, batch_size=30)
        for i in range(300):
            d.add_event(f"event {i}")
        events = d.to_json()["events"]
        # newest first — event 299 should be first
        self.assertIn("299", events[0]["msg"])
        # event 0 should be gone
        msgs = [e["msg"] for e in events]
        self.assertNotIn("event 0", msgs)


class ToJsonMixedTypesTests(unittest.TestCase):
    """to_json sérialise correctement un mix d'events et d'api logs."""

    def test_mixed_types_preserved(self) -> None:
        d = SimulationDisplay(run_id=1, total=100, batch_size=30)
        d.add_event("Config loaded")
        d.add_api_log("descriptor", "gemini", 1000, 3000, 300, "ok")
        d.add_api_log("category", "qwen", 500, 2000, 100, "ok")
        d.add_event("batch done")
        events = d.to_json()["events"]
        types = [e["type"] for e in events]
        # newest first
        self.assertEqual(types, ["event", "api", "api", "event"])


class ApiCallHookTests(unittest.TestCase):
    """Hooks module-level pour capturer les appels API."""

    def test_set_inference_hook(self) -> None:
        from milpo import async_inference
        from milpo.async_inference import set_api_call_hook
        calls: list[tuple] = []

        def hook(agent, model, latency_ms, in_tok, out_tok, status):
            calls.append((agent, model, latency_ms, status))

        set_api_call_hook(hook)
        self.assertIs(async_inference._on_api_call, hook)
        set_api_call_hook(None)  # cleanup
        self.assertIsNone(async_inference._on_api_call)

    def test_set_rewriter_hook(self) -> None:
        from milpo import rewriter
        from milpo.rewriter import set_rewriter_api_hook
        calls: list[tuple] = []

        def hook(label, model, latency_ms, in_tok, out_tok, status):
            calls.append((label, model, latency_ms, status))

        set_rewriter_api_hook(hook)
        self.assertIs(rewriter._on_api_call, hook)
        set_rewriter_api_hook(None)  # cleanup
        self.assertIsNone(rewriter._on_api_call)


if __name__ == "__main__":
    unittest.main()
