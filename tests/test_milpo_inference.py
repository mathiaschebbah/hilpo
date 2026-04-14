"""Tests unitaires du module milpo.inference (modes alma + simple)."""

from __future__ import annotations

import asyncio
import unittest
from unittest.mock import AsyncMock, patch

from milpo.inference import (
    ApiCallLog,
    PostInput,
    _extract_json_from_text,
    async_classify_post_alma,
    async_classify_post_simple,
)


def _features() -> str:
    return (
        "Slide 1 : Photo plein cadre, titre editorial Views overlay, "
        "logo Views en haut à gauche, gabarit reconnaissable."
    )


def _post() -> PostInput:
    return PostInput(
        ig_media_id=1,
        media_product_type="FEED",
        media_urls=["https://example.com/img.jpg"],
        media_types=["IMAGE"],
        caption="caption",
    )


class AlmaPipelineTests(unittest.IsolatedAsyncioTestCase):
    """Pipeline ASSIST 2 étages : descripteur + 3 classifieurs en parallèle."""

    async def test_descriptor_then_three_classifiers(self) -> None:
        with (
            patch(
                "milpo.inference.async_call_descriptor",
                new=AsyncMock(
                    return_value=(
                        _features(),
                        ApiCallLog("descriptor", "gemini", 3, 1, 5),
                    )
                ),
            ),
            patch(
                "milpo.inference.async_call_classifier",
                new=AsyncMock(
                    side_effect=[
                        ("news", "high", "reason", ApiCallLog("category", "qwen", 1, 1, 1)),
                        ("post_news", "high", "reason", ApiCallLog("visual_format", "qwen", 1, 1, 1)),
                        ("awareness", "low", "reason", ApiCallLog("strategy", "qwen", 1, 1, 1)),
                    ]
                ),
            ),
        ):
            result = await async_classify_post_alma(
                post=_post(),
                category_labels=["news"],
                visual_format_labels=["post_news"],
                strategy_labels=["awareness"],
                client=object(),
                semaphore=asyncio.Semaphore(4),
            )

        self.assertEqual(result.prediction.ig_media_id, 1)
        self.assertEqual(result.prediction.category, "news")
        self.assertEqual(result.prediction.visual_format, "post_news")
        self.assertEqual(result.prediction.strategy, "awareness")
        self.assertEqual(len(result.api_calls), 4)  # 1 descriptor + 3 classifiers


class SimplePipelineTests(unittest.IsolatedAsyncioTestCase):
    """Pipeline --simple : 1 appel multimodal ASSIST qui sort les 3 labels."""

    async def test_single_call_returns_three_labels(self) -> None:
        with patch(
            "milpo.inference.async_call_simple",
            new=AsyncMock(
                return_value=(
                    {
                        "visual_format": "post_news",
                        "category": "news",
                        "strategy": "awareness",
                    },
                    "high",
                    "raisonnement",
                    ApiCallLog("simple", "gemini", 100, 50, 200),
                )
            ),
        ):
            result = await async_classify_post_simple(
                post=_post(),
                category_labels=["news"],
                visual_format_labels=["post_news"],
                strategy_labels=["awareness"],
                client=object(),
                semaphore=asyncio.Semaphore(4),
                model="gemini",
            )

        self.assertEqual(result.prediction.visual_format, "post_news")
        self.assertEqual(result.prediction.category, "news")
        self.assertEqual(result.prediction.strategy, "awareness")
        self.assertEqual(len(result.api_calls), 1)
        self.assertEqual(result.confidences["visual_format"], "high")


class JsonFallbackTests(unittest.TestCase):
    """Fallback d'extraction JSON quand le modèle ne renvoie pas de tool_call."""

    def test_extracts_fenced_json_block(self) -> None:
        raw = 'bla bla\n```json\n{"label": "x", "confidence": "high"}\n```\nfin'
        self.assertEqual(
            _extract_json_from_text(raw),
            '{"label": "x", "confidence": "high"}',
        )

    def test_extracts_raw_braces_when_no_fence(self) -> None:
        raw = 'reasoning text {"label": "x"} trailing'
        self.assertEqual(_extract_json_from_text(raw), '{"label": "x"}')

    def test_returns_none_when_no_json(self) -> None:
        self.assertIsNone(_extract_json_from_text("pas de json ici"))


if __name__ == "__main__":
    unittest.main()
