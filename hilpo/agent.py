"""Agents HILPO : descripteur multimodal et classifieurs text-only."""

from __future__ import annotations

import logging
import time

from openai import OpenAI

from hilpo.errors import LLMCallError
from hilpo.schemas import (
    ClassifierDecision,
    DescriptorFeatures,
    build_classifier_response_schema,
    build_json_schema_response_format,
)

log = logging.getLogger("hilpo")

MAX_SYNC_RETRIES = 3


def _sleep_before_retry(attempt: int) -> None:
    """Backoff exponentiel simple pour les appels sync."""
    time.sleep(2 ** attempt)


# ── Descripteur multimodal ─────────────────────────────────────


def build_descriptor_messages(
    media_urls: list[str],
    media_types: list[str],
    caption: str | None,
    instructions: str,
    descriptions_taxonomiques: str,
) -> list[dict]:
    """Construit les messages pour le descripteur multimodal.

    Args:
        media_urls: URLs signées GCS (images ou vidéos).
        media_types: Type de chaque média ('IMAGE' ou 'VIDEO').
        caption: Caption du post Instagram.
        instructions: Instructions I_t optimisables par HILPO.
        descriptions_taxonomiques: Critères discriminants Δ^m.
    """
    system = (
        f"{instructions}\n\n"
        f"## Critères discriminants à observer\n\n"
        f"{descriptions_taxonomiques}"
    )

    content: list[dict] = []

    # Médias (images et vidéos)
    for url, mtype in zip(media_urls, media_types):
        if mtype == "VIDEO":
            content.append({
                "type": "video_url",
                "video_url": {"url": url},
            })
        else:
            content.append({
                "type": "image_url",
                "image_url": {"url": url},
            })

    # Caption
    caption_text = caption or "(pas de caption)"
    content.append({
        "type": "text",
        "text": f"Caption du post :\n{caption_text}",
    })

    return [
        {"role": "system", "content": system},
        {"role": "user", "content": content},
    ]


def call_descriptor(
    client: OpenAI,
    model: str,
    media_urls: list[str],
    media_types: list[str],
    caption: str | None,
    instructions: str,
    descriptions_taxonomiques: str,
) -> tuple[DescriptorFeatures, dict]:
    """Appelle le descripteur multimodal et retourne les features.

    Returns:
        Tuple (features, api_usage) avec les métriques d'appel.
    """
    messages = build_descriptor_messages(
        media_urls, media_types, caption,
        instructions, descriptions_taxonomiques,
    )

    response_format = build_json_schema_response_format(
        "descriptor_features",
        DescriptorFeatures.model_json_schema(),
    )

    start = time.monotonic()
    last_error: Exception | None = None

    for attempt in range(MAX_SYNC_RETRIES):
        try:
            response = client.chat.completions.create(
                model=model,
                messages=messages,
                response_format=response_format,
                temperature=0.1,
            )

            if not response.choices:
                raise RuntimeError("Descriptor: réponse vide")

            raw = response.choices[0].message.content
            if not raw:
                raise RuntimeError("Descriptor: content vide")

            features = DescriptorFeatures.model_validate_json(raw)
            latency_ms = int((time.monotonic() - start) * 1000)
            usage = response.usage
            api_usage = {
                "input_tokens": usage.prompt_tokens if usage else 0,
                "output_tokens": usage.completion_tokens if usage else 0,
                "latency_ms": latency_ms,
                "model": model,
            }
            return features, api_usage
        except Exception as exc:
            last_error = exc
            log.warning("Descriptor appel échoué (attempt %d/%d): %s",
                        attempt + 1, MAX_SYNC_RETRIES, exc)
            if attempt < MAX_SYNC_RETRIES - 1:
                _sleep_before_retry(attempt)
                continue

    raise LLMCallError("Descriptor: épuisé les retries") from last_error


# ── Classifieur text-only (structured output strict) ───────────


def parse_classifier_response(raw: str, axis: str, labels: list[str]) -> tuple[str, str]:
    """Valide la sortie structurée d'un classifieur."""

    parsed = ClassifierDecision.model_validate_json(raw)
    if parsed.label not in labels:
        raise RuntimeError(f"Classifier {axis}: label invalide '{parsed.label}'")
    return parsed.label, parsed.confidence


def build_classifier_messages(
    features_json: str,
    caption: str | None,
    instructions: str,
    descriptions_taxonomiques: str,
) -> list[dict]:
    """Construit les messages pour un classifieur text-only."""
    system = (
        f"{instructions}\n\n"
        f"## Descriptions des labels\n\n"
        f"{descriptions_taxonomiques}"
    )

    user_text = (
        f"## Features extraites du post\n\n"
        f"```json\n{features_json}\n```\n\n"
        f"## Caption du post\n\n"
        f"{caption or '(pas de caption)'}"
    )

    return [
        {"role": "system", "content": system},
        {"role": "user", "content": user_text},
    ]


def call_classifier(
    client: OpenAI,
    model: str,
    axis: str,
    labels: list[str],
    features_json: str,
    caption: str | None,
    instructions: str,
    descriptions_taxonomiques: str,
) -> tuple[str, str, dict]:
    """Appelle un classifieur text-only avec tool use.

    Returns:
        Tuple (label, confidence, api_usage).
    """
    messages = build_classifier_messages(
        features_json, caption,
        instructions, descriptions_taxonomiques,
    )
    response_format = build_json_schema_response_format(
        f"{axis}_classification",
        build_classifier_response_schema(labels),
    )

    start = time.monotonic()
    last_error: Exception | None = None

    for attempt in range(MAX_SYNC_RETRIES):
        try:
            response = client.chat.completions.create(
                model=model,
                messages=messages,
                response_format=response_format,
                temperature=0.1,
            )

            if not response.choices:
                raise RuntimeError(f"Classifier {axis}: réponse vide")

            raw = response.choices[0].message.content or ""
            if not raw:
                raise RuntimeError(f"Classifier {axis}: content vide")

            label, confidence = parse_classifier_response(raw, axis, labels)

            latency_ms = int((time.monotonic() - start) * 1000)
            usage = response.usage
            api_usage = {
                "input_tokens": usage.prompt_tokens if usage else 0,
                "output_tokens": usage.completion_tokens if usage else 0,
                "latency_ms": latency_ms,
                "model": model,
            }
            return label, confidence, api_usage
        except Exception as exc:
            last_error = exc
            log.warning("Classifier %s appel échoué (attempt %d/%d): %s",
                        axis, attempt + 1, MAX_SYNC_RETRIES, exc)
            if attempt < MAX_SYNC_RETRIES - 1:
                _sleep_before_retry(attempt)
                continue

    raise LLMCallError(f"Classifier {axis}: épuisé les retries") from last_error
