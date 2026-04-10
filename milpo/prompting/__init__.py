"""API partagée de prompts et taxonomies."""

from __future__ import annotations

from .catalog import (
    DSPY_MODES,
    PROMPT_KEYS,
    PromptContentMap,
    PromptIdMap,
    PromptKey,
    PromptRecordMap,
    PromptVersionMap,
    build_labels,
    build_prompt_set,
    build_target_descriptions,
    load_active_prompt_records,
    load_descriptor_prompt_configs,
    load_prompt_bundle,
    load_prompt_record,
    prompt_contents_from_records,
)

__all__ = [
    "DSPY_MODES",
    "PROMPT_KEYS",
    "PromptContentMap",
    "PromptIdMap",
    "PromptKey",
    "PromptRecordMap",
    "PromptVersionMap",
    "build_labels",
    "build_prompt_set",
    "build_target_descriptions",
    "load_active_prompt_records",
    "load_descriptor_prompt_configs",
    "load_prompt_bundle",
    "load_prompt_record",
    "prompt_contents_from_records",
]
