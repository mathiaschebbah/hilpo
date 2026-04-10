from __future__ import annotations

import unittest

from agents.tools import (
    ToolPrompts,
    build_bounded_tools,
    build_submit_all_classifications_tool,
)


class AgentToolsTests(unittest.TestCase):
    def setUp(self) -> None:
        self.prompts = ToolPrompts(
            describe_media="Describe media.",
            get_taxonomy="Get taxonomy.",
            get_examples="Get examples.",
            descriptor_focus="Focus prompt.",
        )

    def test_submit_all_classifications_schema_is_strict(self) -> None:
        tool = build_submit_all_classifications_tool(
            category_labels=["news", "mood"],
            visual_format_labels=["post_news", "post_mood"],
            strategy_labels=["awareness", "conversion"],
        )

        self.assertTrue(tool["strict"])
        self.assertEqual(
            set(tool["input_schema"]["required"]),
            {"category", "visual_format", "strategy"},
        )
        self.assertEqual(
            tool["input_schema"]["properties"]["category"]["properties"]["label"]["enum"],
            ["news", "mood"],
        )

    def test_bounded_tools_limit_advisor_and_examples(self) -> None:
        tools = build_bounded_tools(
            prompts=self.prompts,
            category_labels=["news"],
            visual_format_labels=["post_news"],
            strategy_labels=["awareness"],
        )

        advisor = next(tool for tool in tools if tool["name"] == "advisor")
        get_examples = next(tool for tool in tools if tool["name"] == "get_examples")

        self.assertEqual(advisor["max_uses"], 2)
        self.assertIn("n <= 3", get_examples["description"])


if __name__ == "__main__":
    unittest.main()
