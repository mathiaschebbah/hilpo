"""Tests unitaires pour la pipeline A1 bounded.

Couvre les garanties runtime du plan :
- Budget : max 2 tours, 1 advisor, 1 get_examples
- Prefetch descripteur : utilisé quand focus=None, ignoré quand focus présent
"""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

from agents.pipeline import _execute_single_tool_bounded, _ToolExecutionResult
from agents.tools import MediaContext, ToolPrompts


def _make_tool_prompts() -> ToolPrompts:
    return ToolPrompts(
        describe_media="Describe media.",
        get_taxonomy="Get taxonomy.",
        get_examples="Get examples.",
        descriptor_focus="Focus prompt.",
    )


def _make_media_ctx(**overrides) -> MediaContext:
    defaults = dict(
        media_urls=["https://example.com/img.jpg"],
        media_types=["IMAGE"],
        caption="Test caption",
        scope="FEED",
        post_year=2025,
        descriptor_instructions="Describe.",
        descriptor_descriptions="Formats.",
    )
    defaults.update(overrides)
    return MediaContext(**defaults)


class PrefetchDescriptorTests(unittest.TestCase):
    """Le prefetch ne doit court-circuiter que quand focus est absent."""

    def test_prefetch_used_when_no_focus(self) -> None:
        media_ctx = _make_media_ctx()
        media_ctx._descriptor_prefetch_result = ('{"features": "json"}', {"input_tokens": 0, "output_tokens": 0, "latency_ms": 0, "model": "test", "cached": True})

        result = _execute_single_tool_bounded(
            tool_name="describe_media",
            tool_use_id="tu_1",
            tool_input={},
            media_ctx=media_ctx,
            tool_prompts=_make_tool_prompts(),
            examples_allowed=True,
        )

        self.assertEqual(result.result_text, '{"features": "json"}')
        self.assertTrue(result.api_usage.get("cached"))

    @patch("agents.pipeline.execute_tool")
    def test_prefetch_ignored_when_focus_present(self, mock_execute_tool) -> None:
        media_ctx = _make_media_ctx()
        media_ctx._descriptor_prefetch_result = ('{"features": "json"}', {"cached": True})

        mock_execute_tool.return_value = ("Focus answer text", {"input_tokens": 100, "output_tokens": 50, "latency_ms": 200, "model": "gemini"})

        result = _execute_single_tool_bounded(
            tool_name="describe_media",
            tool_use_id="tu_2",
            tool_input={"focus": "Le chiffre est-il mis en avant ?"},
            media_ctx=media_ctx,
            tool_prompts=_make_tool_prompts(),
            examples_allowed=True,
        )

        self.assertEqual(result.result_text, "Focus answer text")
        mock_execute_tool.assert_called_once()
        call_args = mock_execute_tool.call_args
        self.assertEqual(call_args[0][1]["focus"], "Le chiffre est-il mis en avant ?")

    def test_prefetch_future_used_when_no_focus(self) -> None:
        media_ctx = _make_media_ctx()
        future = MagicMock()
        future.result.return_value = ('{"prefetched": true}', {"input_tokens": 500, "output_tokens": 100, "latency_ms": 1000, "model": "gemini"})
        media_ctx._descriptor_prefetch_future = future

        result = _execute_single_tool_bounded(
            tool_name="describe_media",
            tool_use_id="tu_3",
            tool_input={},
            media_ctx=media_ctx,
            tool_prompts=_make_tool_prompts(),
            examples_allowed=True,
        )

        self.assertEqual(result.result_text, '{"prefetched": true}')
        future.result.assert_called_once()

    @patch("agents.pipeline.execute_tool")
    def test_prefetch_future_ignored_when_focus_present(self, mock_execute_tool) -> None:
        media_ctx = _make_media_ctx()
        future = MagicMock()
        future.result.return_value = ('{"prefetched": true}', {})
        media_ctx._descriptor_prefetch_future = future

        mock_execute_tool.return_value = ("Direct focus answer", {"input_tokens": 100, "output_tokens": 50, "latency_ms": 200, "model": "gemini"})

        result = _execute_single_tool_bounded(
            tool_name="describe_media",
            tool_use_id="tu_4",
            tool_input={"focus": "Quel format ?"},
            media_ctx=media_ctx,
            tool_prompts=_make_tool_prompts(),
            examples_allowed=True,
        )

        self.assertEqual(result.result_text, "Direct focus answer")
        future.result.assert_not_called()


class BudgetExamplesTests(unittest.TestCase):
    """get_examples est borné à 1 appel et n<=2."""

    @patch("agents.pipeline.get_conn")
    @patch("agents.pipeline.execute_tool")
    def test_examples_refused_when_budget_exhausted(self, mock_execute_tool, mock_get_conn) -> None:
        media_ctx = _make_media_ctx()

        result = _execute_single_tool_bounded(
            tool_name="get_examples",
            tool_use_id="tu_5",
            tool_input={"axis": "category", "label": "news", "n": 3},
            media_ctx=media_ctx,
            tool_prompts=_make_tool_prompts(),
            examples_allowed=False,
        )

        self.assertIn("Budget get_examples déjà consommé", result.result_text)
        mock_execute_tool.assert_not_called()

    @patch("agents.pipeline.get_conn")
    @patch("agents.pipeline.execute_tool")
    def test_examples_n_clamped_to_max(self, mock_execute_tool, mock_get_conn) -> None:
        media_ctx = _make_media_ctx()
        mock_conn = MagicMock()
        mock_get_conn.return_value.__enter__ = MagicMock(return_value=mock_conn)
        mock_get_conn.return_value.__exit__ = MagicMock(return_value=False)
        mock_execute_tool.return_value = ("Examples result", None)

        result = _execute_single_tool_bounded(
            tool_name="get_examples",
            tool_use_id="tu_6",
            tool_input={"axis": "category", "label": "news", "n": 10},
            media_ctx=media_ctx,
            tool_prompts=_make_tool_prompts(),
            examples_allowed=True,
        )

        call_args = mock_execute_tool.call_args[0]
        actual_n = call_args[1].get("n")
        self.assertLessEqual(actual_n, 2)

    @patch("agents.pipeline.get_conn")
    @patch("agents.pipeline.execute_tool")
    def test_examples_consumed_budget_flag_set(self, mock_execute_tool, mock_get_conn) -> None:
        media_ctx = _make_media_ctx()
        mock_conn = MagicMock()
        mock_get_conn.return_value.__enter__ = MagicMock(return_value=mock_conn)
        mock_get_conn.return_value.__exit__ = MagicMock(return_value=False)
        mock_execute_tool.return_value = ("Examples result", None)

        result = _execute_single_tool_bounded(
            tool_name="get_examples",
            tool_use_id="tu_7",
            tool_input={"axis": "category", "label": "news"},
            media_ctx=media_ctx,
            tool_prompts=_make_tool_prompts(),
            examples_allowed=True,
        )

        self.assertTrue(result.consumed_examples_budget)


if __name__ == "__main__":
    unittest.main()
