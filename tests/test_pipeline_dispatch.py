from __future__ import annotations

import unittest
from unittest.mock import patch

from agents.pipeline import classify_post_agentic


class PipelineDispatchTests(unittest.TestCase):
    @patch("agents.pipeline.classify_post_agentic_bounded")
    def test_default_dispatch_uses_bounded(self, bounded_mock) -> None:
        classify_post_agentic(1, media_ctx="ctx", conn="conn")  # type: ignore[arg-type]
        bounded_mock.assert_called_once_with(
            ig_media_id=1,
            media_ctx="ctx",
            conn="conn",
            prompt_source="agent_bounded_v1",
        )

    @patch("agents.pipeline.classify_post_agentic_legacy")
    def test_legacy_dispatch_remaps_default_prompt_source(self, legacy_mock) -> None:
        classify_post_agentic(1, media_ctx="ctx", conn="conn", pipeline_mode="legacy")  # type: ignore[arg-type]
        legacy_mock.assert_called_once_with(
            ig_media_id=1,
            media_ctx="ctx",
            conn="conn",
            prompt_source="agent_v0",
        )


if __name__ == "__main__":
    unittest.main()
