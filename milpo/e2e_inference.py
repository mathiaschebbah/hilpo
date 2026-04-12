"""Pipeline end-to-end : un seul appel multimodal par post → 3 axes.

Deux modes :
- E2E naïf (--e2e) : 1 appel par post, T=0, pas d'oracle
- E2E harness (--e2e-harness) : k=3 appels à T=0.3, vote majoritaire,
  oracle Sonnet 4.6 sur les vf medium/low confidence
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
import time
from collections import Counter

from openai import AsyncOpenAI

from milpo.async_inference import get_async_client
from milpo.inference import ApiCallLog, PipelineResult, PostInput, PromptSet
from milpo.schemas import PostPrediction

log = logging.getLogger("milpo")

_E2E_SYSTEM_PROMPT = """\
Tu es un classificateur de posts Instagram pour le média Views (@viewsfrance).

Tu reçois les images du post (slides du carousel ou image unique) et la caption.
Tu dois classifier le post sur 3 axes indépendants en un seul appel.

## Formats visuels ({scope})

{vf_descriptions}

## Catégories

{cat_descriptions}

## Stratégies

{strat_descriptions}
"""


async def async_classify_post_e2e(
    client: AsyncOpenAI,
    model: str,
    post: PostInput,
    prompts: PromptSet,
    vf_labels: list[str],
    cat_labels: list[str],
    strat_labels: list[str],
    semaphore: asyncio.Semaphore,
) -> PipelineResult:
    scope = "FEED" if post.media_product_type == "FEED" else "REELS"

    system = _E2E_SYSTEM_PROMPT.format(
        scope=scope,
        vf_descriptions=prompts.visual_format_descriptions,
        cat_descriptions=prompts.category_descriptions,
        strat_descriptions=prompts.strategy_descriptions,
    )

    content: list[dict] = []
    for url, media_type in zip(post.media_urls, post.media_types):
        content.append({"type": "image_url", "image_url": {"url": url}})
    content.append({
        "type": "text",
        "text": f"Caption du post :\n{post.caption or '(pas de caption)'}",
    })

    tool = {
        "type": "function",
        "function": {
            "name": "classify_post",
            "description": "Classifie le post sur les 3 axes.",
            "parameters": {
                "type": "object",
                "properties": {
                    "reasoning": {
                        "type": "string",
                        "description": "Raisonnement bref avant de décider.",
                    },
                    "visual_format": {"type": "string", "enum": vf_labels},
                    "category": {"type": "string", "enum": cat_labels},
                    "strategy": {"type": "string", "enum": strat_labels},
                },
                "required": ["reasoning", "visual_format", "category", "strategy"],
                "additionalProperties": False,
            },
        },
    }

    t0 = time.monotonic()
    async with semaphore:
        response = await client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": content},
            ],
            tools=[tool],
            tool_choice={"type": "function", "function": {"name": "classify_post"}},
            temperature=0,
        )
    latency_ms = int((time.monotonic() - t0) * 1000)

    choice = response.choices[0]
    arguments_raw: str | None = None

    if choice.message.tool_calls:
        arguments_raw = choice.message.tool_calls[0].function.arguments
    else:
        txt = (choice.message.content or "").strip()
        code_blocks = re.findall(r"```(?:json)?\s*(\{.*?\})\s*```", txt, re.DOTALL)
        if code_blocks:
            arguments_raw = code_blocks[-1]
        else:
            first_brace = txt.find("{")
            last_brace = txt.rfind("}")
            if first_brace != -1 and last_brace > first_brace:
                arguments_raw = txt[first_brace : last_brace + 1]

    if not arguments_raw:
        raise RuntimeError(f"E2E post {post.ig_media_id}: pas de réponse exploitable")

    parsed = json.loads(arguments_raw)
    vf_label = parsed.get("visual_format", vf_labels[0])
    cat_label = parsed.get("category", cat_labels[0])
    strat_label = parsed.get("strategy", strat_labels[0])

    in_tok = response.usage.prompt_tokens if response.usage else 0
    out_tok = response.usage.completion_tokens if response.usage else 0

    prediction = PostPrediction(
        ig_media_id=post.ig_media_id,
        category=cat_label,
        visual_format=vf_label,
        strategy=strat_label,
        features="[e2e — pas de features séparées]",
    )

    api_call = ApiCallLog(
        agent="e2e",
        model=model,
        input_tokens=in_tok,
        output_tokens=out_tok,
        latency_ms=latency_ms,
    )

    return PipelineResult(
        prediction=prediction,
        api_calls=[api_call],
        confidences={},
        reasonings={"e2e": parsed.get("reasoning", "")},
    )


async def async_classify_e2e_batch(
    posts: list[PostInput],
    prompts_by_scope: dict[str, PromptSet],
    labels_by_scope: dict[str, dict[str, list[str]]],
    model: str,
    max_concurrent: int = 10,
    on_progress=None,
) -> list[PipelineResult]:
    client = get_async_client()
    semaphore = asyncio.Semaphore(max_concurrent)
    results: list[PipelineResult | None] = [None] * len(posts)
    done_count = 0
    error_count = 0

    async def process(idx: int, post: PostInput):
        nonlocal done_count, error_count
        scope = "FEED" if post.media_product_type == "FEED" else "REELS"
        prompts = prompts_by_scope[scope]
        labels = labels_by_scope[scope]
        try:
            result = await async_classify_post_e2e(
                client=client,
                model=model,
                post=post,
                prompts=prompts,
                vf_labels=labels["visual_format"],
                cat_labels=labels["category"],
                strat_labels=labels["strategy"],
                semaphore=semaphore,
            )
            results[idx] = result
        except Exception as exc:
            log.warning("E2E post %s error: %s: %s", post.ig_media_id, type(exc).__name__, exc)
            error_count += 1
        done_count += 1
        if on_progress:
            on_progress(done_count, len(posts), error_count)

    await asyncio.gather(*(process(i, p) for i, p in enumerate(posts)))
    return [r for r in results if r is not None]


# ── E2E + self-consistency k=3 + oracle cascade ──────────────


async def _e2e_single_sample(
    client: AsyncOpenAI,
    model: str,
    messages: list[dict],
    tool: dict,
    semaphore: asyncio.Semaphore,
) -> tuple[dict, int, int, int]:
    """Un appel E2E à T=0.3. Retourne (parsed_dict, in_tok, out_tok, latency_ms)."""
    t0 = time.monotonic()
    async with semaphore:
        response = await client.chat.completions.create(
            model=model,
            messages=messages,
            tools=[tool],
            tool_choice={"type": "function", "function": {"name": "classify_post"}},
            temperature=0.3,
        )
    latency_ms = int((time.monotonic() - t0) * 1000)

    choice = response.choices[0]
    arguments_raw: str | None = None

    if choice.message.tool_calls:
        arguments_raw = choice.message.tool_calls[0].function.arguments
    else:
        txt = (choice.message.content or "").strip()
        code_blocks = re.findall(r"```(?:json)?\s*(\{.*?\})\s*```", txt, re.DOTALL)
        if code_blocks:
            arguments_raw = code_blocks[-1]
        else:
            first_brace = txt.find("{")
            last_brace = txt.rfind("}")
            if first_brace != -1 and last_brace > first_brace:
                arguments_raw = txt[first_brace : last_brace + 1]

    if not arguments_raw:
        raise RuntimeError("E2E sample: pas de réponse exploitable")

    in_tok = response.usage.prompt_tokens if response.usage else 0
    out_tok = response.usage.completion_tokens if response.usage else 0
    return json.loads(arguments_raw), in_tok, out_tok, latency_ms


def _majority_vote(samples: list[dict], key: str, fallback: str) -> tuple[str, str]:
    """Vote majoritaire sur un axe. Retourne (label, confidence)."""
    labels = [s.get(key, fallback) for s in samples]
    counter = Counter(labels)
    winner, count = counter.most_common(1)[0]
    k = len(samples)
    if count == k:
        confidence = "high"
    elif count > k // 2:
        confidence = "medium"
    else:
        confidence = "low"
    return winner, confidence


async def async_classify_post_e2e_harness(
    client: AsyncOpenAI,
    model: str,
    post: PostInput,
    prompts: PromptSet,
    vf_labels: list[str],
    cat_labels: list[str],
    strat_labels: list[str],
    semaphore: asyncio.Semaphore,
    k: int = 3,
) -> PipelineResult:
    """E2E + self-consistency k samples + oracle cascade sur vf medium/low."""
    scope = "FEED" if post.media_product_type == "FEED" else "REELS"

    system = _E2E_SYSTEM_PROMPT.format(
        scope=scope,
        vf_descriptions=prompts.visual_format_descriptions,
        cat_descriptions=prompts.category_descriptions,
        strat_descriptions=prompts.strategy_descriptions,
    )

    content: list[dict] = []
    for url, media_type in zip(post.media_urls, post.media_types):
        content.append({"type": "image_url", "image_url": {"url": url}})
    content.append({
        "type": "text",
        "text": f"Caption du post :\n{post.caption or '(pas de caption)'}",
    })

    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": content},
    ]

    tool = {
        "type": "function",
        "function": {
            "name": "classify_post",
            "description": "Classifie le post sur les 3 axes.",
            "parameters": {
                "type": "object",
                "properties": {
                    "reasoning": {
                        "type": "string",
                        "description": "Raisonnement bref avant de décider.",
                    },
                    "visual_format": {"type": "string", "enum": vf_labels},
                    "category": {"type": "string", "enum": cat_labels},
                    "strategy": {"type": "string", "enum": strat_labels},
                },
                "required": ["reasoning", "visual_format", "category", "strategy"],
                "additionalProperties": False,
            },
        },
    }

    # k samples en parallèle
    tasks = [
        _e2e_single_sample(client, model, messages, tool, semaphore)
        for _ in range(k)
    ]
    sample_results = await asyncio.gather(*tasks, return_exceptions=True)

    samples: list[dict] = []
    api_calls: list[ApiCallLog] = []
    for r in sample_results:
        if isinstance(r, Exception):
            log.warning("E2E harness sample error: %s", r)
            continue
        parsed, in_tok, out_tok, lat = r
        samples.append(parsed)
        api_calls.append(ApiCallLog(
            agent="e2e",
            model=model,
            input_tokens=in_tok,
            output_tokens=out_tok,
            latency_ms=lat,
        ))

    if not samples:
        raise RuntimeError(f"E2E harness post {post.ig_media_id}: tous les samples ont échoué")

    vf_label, vf_conf = _majority_vote(samples, "visual_format", vf_labels[0])
    cat_label, cat_conf = _majority_vote(samples, "category", cat_labels[0])
    strat_label, strat_conf = _majority_vote(samples, "strategy", strat_labels[0])

    reasonings = [s.get("reasoning", "") for s in samples]
    sample_dicts = [{"label": s.get("visual_format", "?")} for s in samples]

    extra_info: dict = {
        "samples": sample_dicts,
        "classifier_majority_label": vf_label,
        "oracle": {"triggered": False},
    }

    # Oracle cascade sur vf medium/low
    if vf_conf in ("medium", "low"):
        from milpo.config import ORACLE_ENABLED
        if ORACLE_ENABLED:
            from milpo.oracle import async_call_oracle_visual_format
            oracle_verdict = await async_call_oracle_visual_format(
                features_json="\n---\n".join(reasonings),
                caption=post.caption,
                descriptions_taxonomiques=prompts.visual_format_descriptions,
                labels=vf_labels,
                posted_at=post.posted_at,
                classifier_prediction=vf_label,
                classifier_confidence=vf_conf,
                classifier_samples=sample_dicts,
            )
            if oracle_verdict.error is None:
                vf_label = oracle_verdict.label
                vf_conf = oracle_verdict.confidence
            extra_info["oracle"] = {
                "triggered": True,
                "label": oracle_verdict.label,
                "confidence": oracle_verdict.confidence,
                "reasoning": oracle_verdict.reasoning[:500],
                "model": oracle_verdict.model,
                "latency_ms": oracle_verdict.latency_ms,
                "input_tokens": oracle_verdict.input_tokens,
                "output_tokens": oracle_verdict.output_tokens,
                "error": oracle_verdict.error,
            }
            api_calls.append(ApiCallLog(
                agent="e2e_oracle",
                model=oracle_verdict.model,
                input_tokens=oracle_verdict.input_tokens,
                output_tokens=oracle_verdict.output_tokens,
                latency_ms=oracle_verdict.latency_ms,
            ))

    prediction = PostPrediction(
        ig_media_id=post.ig_media_id,
        category=cat_label,
        visual_format=vf_label,
        strategy=strat_label,
        features="[e2e-harness — pas de features séparées]",
    )

    return PipelineResult(
        prediction=prediction,
        api_calls=api_calls,
        confidences={
            "visual_format": vf_conf,
            "category": cat_conf,
            "strategy": strat_conf,
        },
        reasonings={
            "visual_format": reasonings[0] if reasonings else "",
            "category": reasonings[0] if reasonings else "",
            "strategy": reasonings[0] if reasonings else "",
        },
        extras={"visual_format": extra_info},
    )


async def async_classify_e2e_harness_batch(
    posts: list[PostInput],
    prompts_by_scope: dict[str, PromptSet],
    labels_by_scope: dict[str, dict[str, list[str]]],
    model: str,
    max_concurrent: int = 10,
    k: int = 3,
    on_progress=None,
) -> list[PipelineResult]:
    client = get_async_client()
    semaphore = asyncio.Semaphore(max_concurrent)
    results: list[PipelineResult | None] = [None] * len(posts)
    done_count = 0
    error_count = 0

    async def process(idx: int, post: PostInput):
        nonlocal done_count, error_count
        scope = "FEED" if post.media_product_type == "FEED" else "REELS"
        prompts = prompts_by_scope[scope]
        labels = labels_by_scope[scope]
        try:
            result = await async_classify_post_e2e_harness(
                client=client,
                model=model,
                post=post,
                prompts=prompts,
                vf_labels=labels["visual_format"],
                cat_labels=labels["category"],
                strat_labels=labels["strategy"],
                semaphore=semaphore,
                k=k,
            )
            results[idx] = result
        except Exception as exc:
            log.warning("E2E-harness post %s error: %s: %s", post.ig_media_id, type(exc).__name__, exc)
            error_count += 1
        done_count += 1
        if on_progress:
            on_progress(done_count, len(posts), error_count)

    await asyncio.gather(*(process(i, p) for i, p in enumerate(posts)))
    return [r for r in results if r is not None]
