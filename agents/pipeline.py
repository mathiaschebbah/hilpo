"""Pipelines agentiques A0 legacy et A1 bounded."""

from __future__ import annotations

import json
import logging
import time
from concurrent.futures import Future, ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from typing import Any, Mapping

import anthropic

from agents.config import (
    ANTHROPIC_API_KEY,
    BOUNDED_EXAMPLE_CALLS_MAX,
    BOUNDED_EXAMPLES_PER_CALL_MAX,
    MAX_BOUNDED_AGENT_ROUNDS,
    MAX_TOKENS_BOUNDED_TURN,
    MAX_TOKENS_PER_TURN,
    MAX_TOOL_ROUNDS,
    MODEL_EXECUTOR,
    RATE_LIMIT_INPUT_TOKENS_PER_MINUTE,
    RATE_LIMIT_OUTPUT_TOKENS_PER_MINUTE,
    RATE_LIMIT_REQUESTS_PER_MINUTE,
    RATE_LIMIT_WARMUP_CONCURRENCY,
)
from agents.rate_limit import ReactiveRateLimiter, RequestTokenEstimator, _parse_retry_after
from agents.tools import (
    MediaContext,
    ToolPrompts,
    build_bounded_tools,
    build_tools_for_phase,
    execute_describe_media,
    execute_tool,
    load_tool_prompts,
)
from milpo.db import (
    format_descriptions,
    get_active_prompt,
    get_conn,
    load_categories,
    load_strategies,
    load_visual_formats,
)

log = logging.getLogger("agents")


_REQUEST_BETAS = ["advisor-tool-2026-03-01"]
_DESCRIPTOR_PREFETCH_POOL = ThreadPoolExecutor(max_workers=8, thread_name_prefix="descriptor-prefetch")


def _usage_input_tokens(usage: Any) -> int:
    if not usage:
        return 0
    total = getattr(usage, "input_tokens", 0) or 0
    total += getattr(usage, "cache_creation_input_tokens", 0) or 0
    total += getattr(usage, "cache_read_input_tokens", 0) or 0
    return int(total)


def _usage_output_tokens(usage: Any) -> int:
    if not usage:
        return 0
    return int(getattr(usage, "output_tokens", 0) or 0)


def _usage_cache_creation_tokens(usage: Any) -> int:
    if not usage:
        return 0
    return int(getattr(usage, "cache_creation_input_tokens", 0) or 0)


def _usage_cache_read_tokens(usage: Any) -> int:
    if not usage:
        return 0
    return int(getattr(usage, "cache_read_input_tokens", 0) or 0)


_request_estimator = RequestTokenEstimator()
_rate_limiter = ReactiveRateLimiter(
    max_input_tokens_per_minute=RATE_LIMIT_INPUT_TOKENS_PER_MINUTE,
    max_requests_per_minute=RATE_LIMIT_REQUESTS_PER_MINUTE,
    max_output_tokens_per_minute=RATE_LIMIT_OUTPUT_TOKENS_PER_MINUTE or None,
    warmup_max_concurrency=RATE_LIMIT_WARMUP_CONCURRENCY,
)


@dataclass
class AxisClassification:
    label: str
    confidence: str
    reasoning: str


@dataclass
class ApiCallRecord:
    agent: str
    model: str
    input_tokens: int
    output_tokens: int
    latency_ms: int


@dataclass
class RequestEvent:
    simulation_run_id: int | None
    ig_media_id: int
    provider: str
    component: str
    stage: str
    attempt_index: int
    request_id: str | None
    status: str
    model_name: str
    estimated_input_tokens: int
    actual_input_tokens: int
    actual_output_tokens: int
    cache_creation_input_tokens: int
    cache_read_input_tokens: int
    queue_wait_ms: int
    latency_ms: int
    retry_after_ms: int | None
    rate_limit_headers: dict[str, Any] | None = None
    error_code: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "simulation_run_id": self.simulation_run_id,
            "ig_media_id": self.ig_media_id,
            "provider": self.provider,
            "component": self.component,
            "stage": self.stage,
            "attempt_index": self.attempt_index,
            "request_id": self.request_id,
            "status": self.status,
            "model_name": self.model_name,
            "estimated_input_tokens": self.estimated_input_tokens,
            "actual_input_tokens": self.actual_input_tokens,
            "actual_output_tokens": self.actual_output_tokens,
            "cache_creation_input_tokens": self.cache_creation_input_tokens,
            "cache_read_input_tokens": self.cache_read_input_tokens,
            "queue_wait_ms": self.queue_wait_ms,
            "latency_ms": self.latency_ms,
            "retry_after_ms": self.retry_after_ms,
            "rate_limit_headers": self.rate_limit_headers,
            "error_code": self.error_code,
        }


@dataclass
class TraceEvent:
    type: str
    phase: str
    data: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {"type": self.type, "stage": self.phase, **self.data}


@dataclass
class AgentResult:
    ig_media_id: int
    category: AxisClassification
    visual_format: AxisClassification
    strategy: AxisClassification
    api_calls: list[ApiCallRecord] = field(default_factory=list)
    request_events: list[RequestEvent] = field(default_factory=list)
    advisor_calls: int = 0
    advisor_requests: int = 0
    executor_requests: int = 0
    tool_calls: int = 0
    example_calls: int = 0
    rate_limit_events: int = 0
    queue_wait_ms_executor: int = 0
    cache_creation_input_tokens_executor: int = 0
    cache_read_input_tokens_executor: int = 0
    trace: list[TraceEvent] = field(default_factory=list)
    latency_ms: int = 0
    prompt_version_id: int | None = None
    limiter_snapshot: dict[str, Any] = field(default_factory=dict)


def load_agent_system_prompt(
    conn,
    source: str = "agent_v0",
) -> tuple[str, int]:
    row = get_active_prompt(conn, "agent_executor", None, source=source)
    if row is None:
        raise RuntimeError(f"Prompt agent_executor/{source} introuvable en base.")
    return row["content"], row["id"]


def _get_client() -> anthropic.Anthropic:
    if not ANTHROPIC_API_KEY:
        raise RuntimeError("ANTHROPIC_API_KEY non définie. Ajoute-la dans .env.")
    return anthropic.Anthropic(api_key=ANTHROPIC_API_KEY, max_retries=0)


def _log_json(event: str, **data: Any) -> None:
    payload = {"event": event, **data}
    log.info(json.dumps(payload, ensure_ascii=False, default=str))


def _extract_request_id(headers: Mapping[str, str] | None, response: Any | None = None) -> str | None:
    if headers:
        return headers.get("request-id") or headers.get("x-request-id")
    if response is not None:
        return getattr(response, "id", None)
    return None


def _failure_axis(label: str, reason: str) -> AxisClassification:
    return AxisClassification(label=label, confidence="low", reasoning=reason[-280:])


def _full_taxonomy_context(
    *,
    scope: str,
    categories: list[dict],
    visual_formats: list[dict],
    strategies: list[dict],
) -> str:
    cat_desc = "\n".join(f"- **{c['name']}** : {c['description'] or '(pas de description)'}" for c in categories)
    vf_desc = "\n".join(f"- **{v['name']}** : {v['description'] or '(pas de description)'}" for v in visual_formats)
    str_desc = "\n".join(f"- **{s['name']}** : {s['description'] or '(pas de description)'}" for s in strategies)
    return (
        f"## Taxonomie — category\n{cat_desc}\n\n"
        f"## Taxonomie — visual_format ({scope})\n{vf_desc}\n\n"
        f"## Taxonomie — strategy\n{str_desc}"
    )


def _bounded_initial_message(media_ctx: MediaContext, taxonomy: str) -> str:
    caption = (media_ctx.caption or "(pas de caption)")[:700]
    return (
        f"Post Instagram Views à classer ({media_ctx.scope}).\n\n"
        f"Caption:\n{caption}\n\n"
        f"{taxonomy}"
    )


def _start_descriptor_prefetch(
    *,
    ig_media_id: int,
    media_ctx: MediaContext,
    tool_prompts: ToolPrompts,
) -> Future[tuple[str, dict]] | None:
    if media_ctx._descriptor_prefetch_future is not None:
        return media_ctx._descriptor_prefetch_future

    _log_json("descriptor_prefetch_start", ig_media_id=ig_media_id, scope=media_ctx.scope)
    future = _DESCRIPTOR_PREFETCH_POOL.submit(execute_describe_media, media_ctx, None, tool_prompts.descriptor_focus)

    def _store_prefetch_result(done: Future[tuple[str, dict]]) -> None:
        try:
            result = done.result()
        except Exception as exc:  # pragma: no cover - log only
            log.warning("descriptor prefetch failed for post %s: %s", ig_media_id, exc)
            return

        media_ctx._descriptor_prefetch_result = result
        api_usage = result[1]
        _log_json(
            "descriptor_prefetch_done",
            ig_media_id=ig_media_id,
            model=api_usage.get("model"),
            cached=bool(api_usage.get("cached")),
            input_tokens=api_usage.get("input_tokens", 0),
            output_tokens=api_usage.get("output_tokens", 0),
            latency_ms=api_usage.get("latency_ms", 0),
        )

    future.add_done_callback(_store_prefetch_result)
    media_ctx._descriptor_prefetch_future = future
    return future


def _extract_advisor_data(
    *,
    response: Any,
    ig_media_id: int,
    stage: str,
) -> tuple[int, list[ApiCallRecord], list[RequestEvent], list[TraceEvent]]:
    advisor_calls = 0
    api_calls: list[ApiCallRecord] = []
    request_events: list[RequestEvent] = []
    trace_events: list[TraceEvent] = []

    advisor_input: dict[str, Any] | None = None
    advisor_error_code: str | None = None
    for block in getattr(response, "content", []) or []:
        if getattr(block, "type", None) == "server_tool_use" and getattr(block, "name", None) == "advisor":
            advisor_input = getattr(block, "input", None) or {}
        if getattr(block, "type", None) == "advisor_tool_result":
            content = getattr(block, "content", None)
            if content and getattr(content, "type", None) == "advisor_tool_result_error":
                advisor_error_code = getattr(content, "error_code", "unknown")

    for idx, iteration in enumerate(getattr(getattr(response, "usage", None), "iterations", []) or [], start=1):
        if getattr(iteration, "type", None) != "advisor_message":
            continue
        advisor_calls += 1
        model_name = getattr(iteration, "model", "claude-opus-4-6")
        input_tokens = int(getattr(iteration, "input_tokens", 0) or 0)
        output_tokens = int(getattr(iteration, "output_tokens", 0) or 0)
        api_calls.append(
            ApiCallRecord(
                agent=f"advisor/{stage}",
                model=model_name,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                latency_ms=0,
            )
        )
        request_events.append(
            RequestEvent(
                simulation_run_id=None,
                ig_media_id=ig_media_id,
                provider="anthropic",
                component="advisor",
                stage=stage,
                attempt_index=idx,
                request_id=None,
                status="success" if advisor_error_code is None else "error",
                model_name=model_name,
                estimated_input_tokens=input_tokens,
                actual_input_tokens=input_tokens,
                actual_output_tokens=output_tokens,
                cache_creation_input_tokens=0,
                cache_read_input_tokens=0,
                queue_wait_ms=0,
                latency_ms=0,
                retry_after_ms=None,
                rate_limit_headers=None,
                error_code=advisor_error_code,
            )
        )
        trace_events.append(
            TraceEvent(
                type="advisor_call",
                phase="advisor_call",
                data={"turn_stage": stage, "reason": advisor_input, "error_code": advisor_error_code},
            )
        )
    return advisor_calls, api_calls, request_events, trace_events


def _call_executor_turn(
    *,
    client: anthropic.Anthropic,
    ig_media_id: int,
    system: str | list[dict[str, Any]],
    messages: list[dict[str, Any]],
    tools: list[dict[str, Any]],
    turn_index: int,
    max_tokens: int,
    tool_choice: dict[str, Any] | None = None,
) -> tuple[Any, list[ApiCallRecord], list[RequestEvent], list[TraceEvent]]:
    stage = f"executor_turn_{turn_index}"
    estimate = _request_estimator.estimate(
        model=MODEL_EXECUTOR,
        max_tokens=max_tokens,
        system=system,  # type: ignore[arg-type]
        messages=messages,
        tools=tools,
        betas=_REQUEST_BETAS,
    )

    last_rate_limit_error: anthropic.RateLimitError | None = None
    request_events: list[RequestEvent] = []

    for attempt in range(1, 4):
        reserved_output = max_tokens if _rate_limiter.uses_output_budget() else 0
        lease = _rate_limiter.acquire(
            estimated_input_tokens=estimate.input_tokens,
            estimated_output_tokens=reserved_output,
        )
        t0 = time.monotonic()
        response_headers: dict[str, str] | None = None

        try:
            raw_response = client.beta.messages.with_raw_response.create(
                model=MODEL_EXECUTOR,
                max_tokens=max_tokens,
                system=system,
                tools=tools,
                messages=messages,
                tool_choice=tool_choice,
                betas=_REQUEST_BETAS,
            )
            response_headers = dict(raw_response.headers.items())
            response = raw_response.parse()

            input_tokens = int(getattr(getattr(response, "usage", None), "input_tokens", 0) or 0)
            output_tokens = int(getattr(getattr(response, "usage", None), "output_tokens", 0) or 0)
            cache_creation_tokens = _usage_cache_creation_tokens(getattr(response, "usage", None))
            cache_read_tokens = _usage_cache_read_tokens(getattr(response, "usage", None))
            actual_input_total = _usage_input_tokens(getattr(response, "usage", None))
            actual_output = _usage_output_tokens(getattr(response, "usage", None))
            _request_estimator.observe(estimate, actual_input_total)
            _rate_limiter.finalize(
                lease,
                actual_input_tokens=actual_input_total,
                actual_output_tokens=actual_output,
                headers=response_headers,
            )

            latency_ms = int((time.monotonic() - t0) * 1000)
            request_events.append(
                RequestEvent(
                    simulation_run_id=None,
                    ig_media_id=ig_media_id,
                    provider="anthropic",
                    component="executor",
                    stage=stage,
                    attempt_index=attempt,
                    request_id=_extract_request_id(response_headers, response),
                    status="success",
                    model_name=MODEL_EXECUTOR,
                    estimated_input_tokens=estimate.input_tokens,
                    actual_input_tokens=input_tokens,
                    actual_output_tokens=output_tokens,
                    cache_creation_input_tokens=cache_creation_tokens,
                    cache_read_input_tokens=cache_read_tokens,
                    queue_wait_ms=int(round(lease.queue_wait_ms)),
                    latency_ms=latency_ms,
                    retry_after_ms=None,
                    rate_limit_headers=response_headers,
                    error_code=None,
                )
            )

            api_calls = [
                ApiCallRecord(
                    agent=f"executor/{stage}",
                    model=MODEL_EXECUTOR,
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    latency_ms=latency_ms,
                )
            ]
            advisor_count, advisor_api_calls, advisor_events, advisor_traces = _extract_advisor_data(
                response=response,
                ig_media_id=ig_media_id,
                stage=stage,
            )
            if advisor_count:
                request_events.extend(advisor_events)
                api_calls.extend(advisor_api_calls)
            return response, api_calls, request_events, advisor_traces
        except anthropic.RateLimitError as exc:
            last_rate_limit_error = exc
            response_headers = dict(exc.response.headers.items()) if getattr(exc, "response", None) else None
            retry_after = _parse_retry_after(response_headers)
            _rate_limiter.reject(lease, headers=response_headers, retry_after_seconds=retry_after)
            request_events.append(
                RequestEvent(
                    simulation_run_id=None,
                    ig_media_id=ig_media_id,
                    provider="anthropic",
                    component="executor",
                    stage=stage,
                    attempt_index=attempt,
                    request_id=_extract_request_id(response_headers),
                    status="rate_limited",
                    model_name=MODEL_EXECUTOR,
                    estimated_input_tokens=estimate.input_tokens,
                    actual_input_tokens=0,
                    actual_output_tokens=0,
                    cache_creation_input_tokens=0,
                    cache_read_input_tokens=0,
                    queue_wait_ms=int(round(lease.queue_wait_ms)),
                    latency_ms=int((time.monotonic() - t0) * 1000),
                    retry_after_ms=int(round((retry_after or 0.0) * 1000)),
                    rate_limit_headers=response_headers,
                    error_code="rate_limit_error",
                )
            )
            _log_json(
                "rate_limited",
                ig_media_id=ig_media_id,
                stage=stage,
                attempt=attempt,
                retry_after_ms=int(round((retry_after or 0.0) * 1000)),
                request_id=_extract_request_id(response_headers),
            )
            continue
        except Exception as exc:
            _rate_limiter.finalize(
                lease,
                actual_input_tokens=0,
                actual_output_tokens=0,
                actual_requests=0,
            )
            request_events.append(
                RequestEvent(
                    simulation_run_id=None,
                    ig_media_id=ig_media_id,
                    provider="anthropic",
                    component="executor",
                    stage=stage,
                    attempt_index=attempt,
                    request_id=_extract_request_id(response_headers),
                    status="error",
                    model_name=MODEL_EXECUTOR,
                    estimated_input_tokens=estimate.input_tokens,
                    actual_input_tokens=0,
                    actual_output_tokens=0,
                    cache_creation_input_tokens=0,
                    cache_read_input_tokens=0,
                    queue_wait_ms=int(round(lease.queue_wait_ms)),
                    latency_ms=int((time.monotonic() - t0) * 1000),
                    retry_after_ms=None,
                    rate_limit_headers=response_headers,
                    error_code=type(exc).__name__,
                )
            )
            raise

    if last_rate_limit_error is not None:
        raise last_rate_limit_error
    raise RuntimeError("rate limit épuisé après 3 retries — aucune RateLimitError capturée")


@dataclass
class _ToolExecutionResult:
    tool_use_id: str
    name: str
    tool_input: dict[str, Any]
    result_text: str
    api_usage: dict[str, Any] | None
    latency_ms: int
    consumed_examples_budget: bool = False


def _execute_single_tool_bounded(
    *,
    tool_name: str,
    tool_use_id: str,
    tool_input: dict[str, Any],
    media_ctx: MediaContext,
    tool_prompts: ToolPrompts,
    examples_allowed: bool,
) -> _ToolExecutionResult:
    started = time.monotonic()

    try:
        if tool_name == "get_examples" and not examples_allowed:
            return _ToolExecutionResult(
                tool_use_id=tool_use_id,
                name=tool_name,
                tool_input=tool_input,
                result_text="Budget get_examples déjà consommé pour ce post.",
                api_usage=None,
                latency_ms=int((time.monotonic() - started) * 1000),
            )

        normalized_input = dict(tool_input or {})
        if tool_name == "get_examples":
            normalized_input["n"] = min(
                max(int(normalized_input.get("n", 1) or 1), 1),
                BOUNDED_EXAMPLES_PER_CALL_MAX,
            )

        if tool_name == "describe_media":
            focus = (normalized_input or {}).get("focus")
            if focus is None and media_ctx._descriptor_prefetch_result is not None:
                result_text, api_usage = media_ctx._descriptor_prefetch_result
            elif focus is None and media_ctx._descriptor_prefetch_future is not None:
                result_text, api_usage = media_ctx._descriptor_prefetch_future.result()
            else:
                result_text, api_usage = execute_tool(tool_name, normalized_input, media_ctx, None, tool_prompts)
        elif tool_name in {"get_taxonomy", "get_examples"}:
            with get_conn() as tool_conn:
                result_text, api_usage = execute_tool(tool_name, normalized_input, media_ctx, tool_conn, tool_prompts)
        else:
            with get_conn() as tool_conn:
                result_text, api_usage = execute_tool(tool_name, normalized_input, media_ctx, tool_conn, tool_prompts)

        return _ToolExecutionResult(
            tool_use_id=tool_use_id,
            name=tool_name,
            tool_input=normalized_input,
            result_text=result_text,
            api_usage=api_usage,
            latency_ms=int((time.monotonic() - started) * 1000),
            consumed_examples_budget=tool_name == "get_examples" and examples_allowed,
        )
    except Exception as exc:
        return _ToolExecutionResult(
            tool_use_id=tool_use_id,
            name=tool_name,
            tool_input=tool_input,
            result_text=f"Erreur tool {tool_name}: {type(exc).__name__}: {exc}",
            api_usage=None,
            latency_ms=int((time.monotonic() - started) * 1000),
        )


def _execute_tool_batch_bounded(
    *,
    ig_media_id: int,
    tool_uses: list[Any],
    media_ctx: MediaContext,
    tool_prompts: ToolPrompts,
    example_calls_used: int,
) -> list[_ToolExecutionResult]:
    remaining_example_budget = max(0, BOUNDED_EXAMPLE_CALLS_MAX - example_calls_used)
    examples_allowed_by_id: dict[str, bool] = {}
    for tool_use in tool_uses:
        if tool_use.name != "get_examples":
            continue
        allow = remaining_example_budget > 0
        examples_allowed_by_id[tool_use.id] = allow
        if allow:
            remaining_example_budget -= 1

    _log_json(
        "tool_batch_start",
        ig_media_id=ig_media_id,
        tools=[tool_use.name for tool_use in tool_uses],
        count=len(tool_uses),
    )

    results_by_id: dict[str, _ToolExecutionResult] = {}
    with ThreadPoolExecutor(max_workers=max(1, len(tool_uses)), thread_name_prefix="bounded-tools") as executor:
        future_map = {
            executor.submit(
                _execute_single_tool_bounded,
                tool_name=tool_use.name,
                tool_use_id=tool_use.id,
                tool_input=tool_use.input or {},
                media_ctx=media_ctx,
                tool_prompts=tool_prompts,
                examples_allowed=examples_allowed_by_id.get(tool_use.id, True),
            ): tool_use.id
            for tool_use in tool_uses
        }
        for future in as_completed(future_map):
            result = future.result()
            results_by_id[result.tool_use_id] = result

    ordered_results = [results_by_id[tool_use.id] for tool_use in tool_uses]
    _log_json(
        "tool_batch_done",
        ig_media_id=ig_media_id,
        tools=[result.name for result in ordered_results],
        max_latency_ms=max((result.latency_ms for result in ordered_results), default=0),
    )
    return ordered_results


def _parse_submit_all(tool_use: Any) -> tuple[AxisClassification, AxisClassification, AxisClassification]:
    payload = tool_use.input or {}

    def _axis(name: str) -> AxisClassification:
        axis_payload = payload.get(name, {}) or {}
        return AxisClassification(
            label=str(axis_payload.get("label", "MISSING")),
            confidence=str(axis_payload.get("confidence", "low")),
            reasoning=str(axis_payload.get("reasoning", ""))[:280],
        )

    return _axis("category"), _axis("visual_format"), _axis("strategy")


def _build_failure_result(
    *,
    ig_media_id: int,
    label: str,
    reason: str,
    api_calls: list[ApiCallRecord],
    request_events: list[RequestEvent],
    trace: list[TraceEvent],
    advisor_calls: int,
    executor_requests: int,
    tool_calls: int,
    example_calls: int,
    rate_limit_events: int,
    queue_wait_ms_executor: int,
    cache_creation_input_tokens_executor: int,
    cache_read_input_tokens_executor: int,
    latency_ms: int,
    prompt_version_id: int | None,
) -> AgentResult:
    axis = _failure_axis(label, reason)
    trace.append(TraceEvent(type="final_classification", phase="final_classification", data={"label": label}))
    return AgentResult(
        ig_media_id=ig_media_id,
        category=axis,
        visual_format=axis,
        strategy=axis,
        api_calls=api_calls,
        request_events=request_events,
        advisor_calls=advisor_calls,
        advisor_requests=advisor_calls,
        executor_requests=executor_requests,
        tool_calls=tool_calls,
        example_calls=example_calls,
        rate_limit_events=rate_limit_events,
        queue_wait_ms_executor=queue_wait_ms_executor,
        cache_creation_input_tokens_executor=cache_creation_input_tokens_executor,
        cache_read_input_tokens_executor=cache_read_input_tokens_executor,
        trace=trace,
        latency_ms=latency_ms,
        prompt_version_id=prompt_version_id,
        limiter_snapshot=_rate_limiter.snapshot(),
    )


def classify_post_agentic_bounded(
    ig_media_id: int,
    media_ctx: MediaContext,
    conn,
    prompt_source: str = "agent_bounded_v1",
) -> AgentResult:
    client = _get_client()
    started = time.monotonic()

    system_template, prompt_version_id = load_agent_system_prompt(conn, source=prompt_source)
    tool_prompts = load_tool_prompts(conn)
    format_prefix = "post" if media_ctx.scope == "FEED" else "reel"
    system_text = system_template.format(scope=media_ctx.scope, format_prefix=format_prefix)

    categories = load_categories(conn)
    visual_formats = load_visual_formats(conn, media_ctx.scope)
    strategies = load_strategies(conn)
    taxonomy = _full_taxonomy_context(
        scope=media_ctx.scope,
        categories=categories,
        visual_formats=visual_formats,
        strategies=strategies,
    )

    system_blocks = [
        {"type": "text", "text": system_text},
        {"type": "text", "text": taxonomy, "cache_control": {"type": "ephemeral", "ttl": "1h"}},
    ]
    tools = build_bounded_tools(
        prompts=tool_prompts,
        category_labels=[item["name"] for item in categories],
        visual_format_labels=[item["name"] for item in visual_formats],
        strategy_labels=[item["name"] for item in strategies],
    )

    _log_json("post_start", ig_media_id=ig_media_id, scope=media_ctx.scope, pipeline="agent_a1_bounded")
    _start_descriptor_prefetch(ig_media_id=ig_media_id, media_ctx=media_ctx, tool_prompts=tool_prompts)

    messages: list[dict[str, Any]] = [
        {
            "role": "user",
            "content": _bounded_initial_message(media_ctx, taxonomy),
        }
    ]
    trace: list[TraceEvent] = [
        TraceEvent(
            type="plan",
            phase="plan",
            data={"max_rounds": MAX_BOUNDED_AGENT_ROUNDS, "max_examples": BOUNDED_EXAMPLE_CALLS_MAX},
        )
    ]
    api_calls: list[ApiCallRecord] = []
    request_events: list[RequestEvent] = []
    advisor_calls = 0
    executor_requests = 0
    tool_calls = 0
    example_calls = 0
    rate_limit_events = 0
    queue_wait_ms_executor = 0
    cache_creation_input_tokens_executor = 0
    cache_read_input_tokens_executor = 0
    full_reasoning: list[str] = []

    for turn_index in range(1, MAX_BOUNDED_AGENT_ROUNDS + 1):
        tool_choice = None
        if turn_index == MAX_BOUNDED_AGENT_ROUNDS:
            tool_choice = {
                "type": "tool",
                "name": "submit_all_classifications",
                "disable_parallel_tool_use": True,
            }
        else:
            tool_choice = {"type": "auto", "disable_parallel_tool_use": False}

        _log_json("executor_turn_start", ig_media_id=ig_media_id, turn=turn_index)
        response, turn_api_calls, turn_request_events, advisor_trace_events = _call_executor_turn(
            client=client,
            ig_media_id=ig_media_id,
            system=system_blocks,
            messages=messages,
            tools=tools,
            turn_index=turn_index,
            max_tokens=MAX_TOKENS_BOUNDED_TURN,
            tool_choice=tool_choice,
        )
        _log_json("executor_turn_done", ig_media_id=ig_media_id, turn=turn_index, stop_reason=response.stop_reason)

        api_calls.extend(turn_api_calls)
        request_events.extend(turn_request_events)
        trace.extend(advisor_trace_events)
        advisor_calls += sum(1 for event in turn_request_events if event.component == "advisor")
        executor_requests += 1
        rate_limit_events += sum(1 for event in turn_request_events if event.status == "rate_limited")

        for event in turn_request_events:
            if event.component != "executor" or event.status != "success":
                continue
            queue_wait_ms_executor += event.queue_wait_ms
            cache_creation_input_tokens_executor += event.cache_creation_input_tokens
            cache_read_input_tokens_executor += event.cache_read_input_tokens

        for block in getattr(response, "content", []) or []:
            if hasattr(block, "text"):
                full_reasoning.append(block.text)

        messages.append({"role": "assistant", "content": response.content})

        tool_uses = [block for block in response.content if getattr(block, "type", None) == "tool_use"]
        submit_tool_use = next(
            (tool_use for tool_use in tool_uses if tool_use.name == "submit_all_classifications"),
            None,
        )
        if submit_tool_use is not None:
            category, visual_format, strategy = _parse_submit_all(submit_tool_use)
            messages.append(
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "tool_result",
                            "tool_use_id": submit_tool_use.id,
                            "content": "Classifications enregistrées.",
                        }
                    ],
                }
            )
            trace.append(
                TraceEvent(
                    type="final_classification",
                    phase="final_classification",
                    data={
                        "category": category.label,
                        "visual_format": visual_format.label,
                        "strategy": strategy.label,
                    },
                )
            )
            total_latency = int((time.monotonic() - started) * 1000)
            result = AgentResult(
                ig_media_id=ig_media_id,
                category=category,
                visual_format=visual_format,
                strategy=strategy,
                api_calls=api_calls,
                request_events=request_events,
                advisor_calls=advisor_calls,
                advisor_requests=advisor_calls,
                executor_requests=executor_requests,
                tool_calls=tool_calls,
                example_calls=example_calls,
                rate_limit_events=rate_limit_events,
                queue_wait_ms_executor=queue_wait_ms_executor,
                cache_creation_input_tokens_executor=cache_creation_input_tokens_executor,
                cache_read_input_tokens_executor=cache_read_input_tokens_executor,
                trace=trace,
                latency_ms=total_latency,
                prompt_version_id=prompt_version_id,
                limiter_snapshot=_rate_limiter.snapshot(),
            )
            _log_json(
                "post_complete",
                ig_media_id=ig_media_id,
                status="ok",
                latency_ms=total_latency,
                executor_requests=executor_requests,
                advisor_requests=advisor_calls,
                example_calls=example_calls,
            )
            return result

        if response.stop_reason != "tool_use":
            total_latency = int((time.monotonic() - started) * 1000)
            result = _build_failure_result(
                ig_media_id=ig_media_id,
                label="NO_SUBMIT",
                reason="\n".join(full_reasoning),
                api_calls=api_calls,
                request_events=request_events,
                trace=trace,
                advisor_calls=advisor_calls,
                executor_requests=executor_requests,
                tool_calls=tool_calls,
                example_calls=example_calls,
                rate_limit_events=rate_limit_events,
                queue_wait_ms_executor=queue_wait_ms_executor,
                cache_creation_input_tokens_executor=cache_creation_input_tokens_executor,
                cache_read_input_tokens_executor=cache_read_input_tokens_executor,
                latency_ms=total_latency,
                prompt_version_id=prompt_version_id,
            )
            _log_json("post_complete", ig_media_id=ig_media_id, status="no_submit", latency_ms=total_latency)
            return result

        perception_tools = [tool_use for tool_use in tool_uses if tool_use.name != "submit_all_classifications"]
        if not perception_tools:
            break

        tool_results = _execute_tool_batch_bounded(
            ig_media_id=ig_media_id,
            tool_uses=perception_tools,
            media_ctx=media_ctx,
            tool_prompts=tool_prompts,
            example_calls_used=example_calls,
        )
        tool_result_blocks = []
        for tool_result in tool_results:
            tool_calls += 1
            if tool_result.consumed_examples_budget:
                example_calls += 1
            trace.append(
                TraceEvent(
                    type="tool_call",
                    phase="tool_call",
                    data={
                        "turn": turn_index,
                        "tool": tool_result.name,
                        "input": tool_result.tool_input,
                        "latency_ms": tool_result.latency_ms,
                    },
                )
            )
            if tool_result.api_usage:
                api_calls.append(
                    ApiCallRecord(
                        agent=f"tool/{tool_result.name}",
                        model=tool_result.api_usage.get("model", "unknown"),
                        input_tokens=int(tool_result.api_usage.get("input_tokens", 0) or 0),
                        output_tokens=int(tool_result.api_usage.get("output_tokens", 0) or 0),
                        latency_ms=int(tool_result.api_usage.get("latency_ms", 0) or 0),
                    )
                )
                request_events.append(
                    RequestEvent(
                        simulation_run_id=None,
                        ig_media_id=ig_media_id,
                        provider="openrouter",
                        component="descriptor",
                        stage=f"tool_{tool_result.name}",
                        attempt_index=1,
                        request_id=None,
                        status="success",
                        model_name=tool_result.api_usage.get("model", "unknown"),
                        estimated_input_tokens=int(tool_result.api_usage.get("input_tokens", 0) or 0),
                        actual_input_tokens=int(tool_result.api_usage.get("input_tokens", 0) or 0),
                        actual_output_tokens=int(tool_result.api_usage.get("output_tokens", 0) or 0),
                        cache_creation_input_tokens=0,
                        cache_read_input_tokens=0,
                        queue_wait_ms=0,
                        latency_ms=int(tool_result.api_usage.get("latency_ms", 0) or 0),
                        retry_after_ms=None,
                        rate_limit_headers=None,
                        error_code=None,
                    )
                )
            tool_result_blocks.append(
                {
                    "type": "tool_result",
                    "tool_use_id": tool_result.tool_use_id,
                    "content": tool_result.result_text,
                }
            )

        messages.append({"role": "user", "content": tool_result_blocks})

    total_latency = int((time.monotonic() - started) * 1000)
    result = _build_failure_result(
        ig_media_id=ig_media_id,
        label="MAX_ROUNDS",
        reason="\n".join(full_reasoning),
        api_calls=api_calls,
        request_events=request_events,
        trace=trace,
        advisor_calls=advisor_calls,
        executor_requests=executor_requests,
        tool_calls=tool_calls,
        example_calls=example_calls,
        rate_limit_events=rate_limit_events,
        queue_wait_ms_executor=queue_wait_ms_executor,
        cache_creation_input_tokens_executor=cache_creation_input_tokens_executor,
        cache_read_input_tokens_executor=cache_read_input_tokens_executor,
        latency_ms=total_latency,
        prompt_version_id=prompt_version_id,
    )
    _log_json("post_complete", ig_media_id=ig_media_id, status="max_rounds", latency_ms=total_latency)
    return result


def _run_agent_phase(
    client: anthropic.Anthropic,
    system: str,
    messages: list[dict[str, Any]],
    tools: list[dict[str, Any]],
    media_ctx: MediaContext,
    conn,
    axis: str,
    tool_prompts: ToolPrompts | None = None,
) -> tuple[AxisClassification, list[ApiCallRecord], list[TraceEvent], int, int]:
    api_calls: list[ApiCallRecord] = []
    trace_events: list[TraceEvent] = []
    advisor_count = 0
    tool_count = 0
    full_reasoning: list[str] = []

    for _round_idx in range(MAX_TOOL_ROUNDS):
        estimate = _request_estimator.estimate(
            model=MODEL_EXECUTOR,
            max_tokens=MAX_TOKENS_PER_TURN,
            system=system,
            messages=messages,
            tools=tools,
            betas=_REQUEST_BETAS,
        )

        last_rate_limit_error: anthropic.RateLimitError | None = None
        for _attempt in range(3):
            reserved_output = MAX_TOKENS_PER_TURN if _rate_limiter.uses_output_budget() else 0
            lease = _rate_limiter.acquire(
                estimated_input_tokens=estimate.input_tokens,
                estimated_output_tokens=reserved_output,
            )
            t0 = time.monotonic()
            try:
                raw_response = client.beta.messages.with_raw_response.create(
                    model=MODEL_EXECUTOR,
                    max_tokens=MAX_TOKENS_PER_TURN,
                    system=system,
                    tools=tools,
                    messages=messages,
                    betas=_REQUEST_BETAS,
                )
                response_headers = dict(raw_response.headers.items())
                response = raw_response.parse()
                actual_input = _usage_input_tokens(response.usage)
                actual_output = _usage_output_tokens(response.usage)
                _request_estimator.observe(estimate, actual_input)
                _rate_limiter.finalize(
                    lease,
                    actual_input_tokens=actual_input,
                    actual_output_tokens=actual_output,
                    headers=response_headers,
                )
                break
            except anthropic.RateLimitError as exc:
                last_rate_limit_error = exc
                response_headers = dict(exc.response.headers.items()) if getattr(exc, "response", None) else None
                _rate_limiter.reject(lease, headers=response_headers)
                continue
            except Exception:
                _rate_limiter.finalize(
                    lease,
                    actual_input_tokens=0,
                    actual_output_tokens=0,
                    actual_requests=0,
                )
                raise
        else:
            if last_rate_limit_error is not None:
                raise last_rate_limit_error
            raise anthropic.RateLimitError("rate limit épuisé après 3 retries")

        latency_ms = int((time.monotonic() - t0) * 1000)

        if response.usage:
            api_calls.append(
                ApiCallRecord(
                    agent=f"agent/{axis}",
                    model=MODEL_EXECUTOR,
                    input_tokens=response.usage.input_tokens,
                    output_tokens=response.usage.output_tokens,
                    latency_ms=latency_ms,
                )
            )

        if hasattr(response, "usage") and response.usage:
            for iteration in getattr(response.usage, "iterations", []) or []:
                if getattr(iteration, "type", None) == "advisor_message":
                    api_calls.append(
                        ApiCallRecord(
                            agent=f"advisor/{axis}",
                            model=getattr(iteration, "model", "claude-opus-4-6"),
                            input_tokens=getattr(iteration, "input_tokens", 0),
                            output_tokens=getattr(iteration, "output_tokens", 0),
                            latency_ms=0,
                        )
                    )
                    advisor_count += 1
                    trace_events.append(TraceEvent(type="advisor_call", phase=axis))

        for block in response.content:
            if hasattr(block, "text"):
                full_reasoning.append(block.text)
            if getattr(block, "type", None) == "advisor_tool_result":
                content = getattr(block, "content", None)
                if content and getattr(content, "type", None) == "advisor_tool_result_error":
                    error_code = getattr(content, "error_code", "unknown")
                    trace_events.append(
                        TraceEvent(type="advisor_error", phase=axis, data={"error_code": error_code})
                    )

        tool_uses = [block for block in response.content if block.type == "tool_use"]
        submit_tu = next((block for block in tool_uses if block.name == "submit_classification"), None)

        if submit_tu:
            label = submit_tu.input.get("label", "MISSING")
            confidence = submit_tu.input.get("confidence", "low")
            reasoning = submit_tu.input.get("reasoning", "")
            trace_events.append(
                TraceEvent(type="final_classification", phase=axis, data={"label": label, "confidence": confidence})
            )
            messages.append({"role": "assistant", "content": response.content})
            messages.append(
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "tool_result",
                            "tool_use_id": submit_tu.id,
                            "content": f"Classification enregistrée : {label} ({confidence})",
                        }
                    ],
                }
            )
            return (
                AxisClassification(label=label, confidence=confidence, reasoning=(reasoning or "\n".join(full_reasoning)[-500:])),
                api_calls,
                trace_events,
                advisor_count,
                tool_count,
            )

        if response.stop_reason != "tool_use":
            messages.append({"role": "assistant", "content": response.content})
            return (
                AxisClassification(label="NO_SUBMIT", confidence="low", reasoning="\n".join(full_reasoning)[-500:]),
                api_calls,
                trace_events,
                advisor_count,
                tool_count,
            )

        perception_tools = [block for block in tool_uses if block.name != "submit_classification"]
        if not perception_tools:
            break

        messages.append({"role": "assistant", "content": response.content})
        tool_results = []
        for tool_use in perception_tools:
            tool_count += 1
            tool_started = time.monotonic()
            result_text, api_usage = execute_tool(tool_use.name, tool_use.input, media_ctx, conn, tool_prompts)
            tool_latency = int((time.monotonic() - tool_started) * 1000)
            trace_events.append(
                TraceEvent(
                    type="tool_call",
                    phase=axis,
                    data={"tool": tool_use.name, "input": tool_use.input or {}, "latency_ms": tool_latency},
                )
            )
            if api_usage:
                api_calls.append(
                    ApiCallRecord(
                        agent=f"tool/{tool_use.name}",
                        model=api_usage.get("model", "unknown"),
                        input_tokens=api_usage.get("input_tokens", 0),
                        output_tokens=api_usage.get("output_tokens", 0),
                        latency_ms=api_usage.get("latency_ms", 0),
                    )
                )
            tool_results.append({"type": "tool_result", "tool_use_id": tool_use.id, "content": result_text})

        messages.append({"role": "user", "content": tool_results})

    return (
        AxisClassification(label="MAX_ROUNDS", confidence="low", reasoning="\n".join(full_reasoning)[-500:]),
        api_calls,
        trace_events,
        advisor_count,
        tool_count,
    )


def classify_post_agentic_legacy(
    ig_media_id: int,
    media_ctx: MediaContext,
    conn,
    prompt_source: str = "agent_v0",
) -> AgentResult:
    client = _get_client()
    system_template, prompt_version_id = load_agent_system_prompt(conn, source=prompt_source)
    tool_prompts = load_tool_prompts(conn)
    format_prefix = "post" if media_ctx.scope == "FEED" else "reel"
    system = system_template.format(scope=media_ctx.scope, format_prefix=format_prefix)

    category_labels = [item["name"] for item in load_categories(conn)]
    visual_format_labels = [item["name"] for item in load_visual_formats(conn, media_ctx.scope)]
    strategy_labels = [item["name"] for item in load_strategies(conn)]

    all_api_calls: list[ApiCallRecord] = []
    all_trace: list[TraceEvent] = []
    total_advisor = 0
    total_tools = 0
    messages: list[dict[str, Any]] = []

    started = time.monotonic()

    tools_category = build_tools_for_phase("category", category_labels, tool_prompts)
    messages.append(
        {
            "role": "user",
            "content": (
                f"Voici un post Instagram Views ({media_ctx.scope}).\n\n"
                f"- Caption : {(media_ctx.caption or '(pas de caption)')[:500]}\n\n"
                "Étape 1/3: classifie category."
            ),
        }
    )
    category, calls, trace, advisor_count, tool_count = _run_agent_phase(
        client, system, messages, tools_category, media_ctx, conn, "category", tool_prompts
    )
    all_api_calls.extend(calls)
    all_trace.extend(trace)
    total_advisor += advisor_count
    total_tools += tool_count

    tools_visual_format = build_tools_for_phase("visual_format", visual_format_labels, tool_prompts)
    messages.append(
        {
            "role": "user",
            "content": (
                f"Catégorie classifiée: {category.label} ({category.confidence}).\n\n"
                "Étape 2/3: classifie visual_format."
            ),
        }
    )
    visual_format, calls, trace, advisor_count, tool_count = _run_agent_phase(
        client, system, messages, tools_visual_format, media_ctx, conn, "visual_format", tool_prompts
    )
    all_api_calls.extend(calls)
    all_trace.extend(trace)
    total_advisor += advisor_count
    total_tools += tool_count

    tools_strategy = build_tools_for_phase("strategy", strategy_labels, tool_prompts)
    messages.append(
        {
            "role": "user",
            "content": (
                f"Visual format classifié: {visual_format.label} ({visual_format.confidence}).\n\n"
                "Étape 3/3: classifie strategy."
            ),
        }
    )
    strategy, calls, trace, advisor_count, tool_count = _run_agent_phase(
        client, system, messages, tools_strategy, media_ctx, conn, "strategy", tool_prompts
    )
    all_api_calls.extend(calls)
    all_trace.extend(trace)
    total_advisor += advisor_count
    total_tools += tool_count

    return AgentResult(
        ig_media_id=ig_media_id,
        category=category,
        visual_format=visual_format,
        strategy=strategy,
        api_calls=all_api_calls,
        request_events=[],
        advisor_calls=total_advisor,
        advisor_requests=total_advisor,
        executor_requests=3,
        tool_calls=total_tools,
        example_calls=0,
        rate_limit_events=0,
        queue_wait_ms_executor=0,
        cache_creation_input_tokens_executor=0,
        cache_read_input_tokens_executor=0,
        trace=all_trace,
        latency_ms=int((time.monotonic() - started) * 1000),
        prompt_version_id=prompt_version_id,
        limiter_snapshot=_rate_limiter.snapshot(),
    )


def classify_post_agentic(
    ig_media_id: int,
    media_ctx: MediaContext,
    conn,
    prompt_source: str = "agent_bounded_v1",
    pipeline_mode: str = "bounded",
) -> AgentResult:
    if pipeline_mode == "legacy":
        return classify_post_agentic_legacy(
            ig_media_id=ig_media_id,
            media_ctx=media_ctx,
            conn=conn,
            prompt_source="agent_v0" if prompt_source == "agent_bounded_v1" else prompt_source,
        )
    return classify_post_agentic_bounded(
        ig_media_id=ig_media_id,
        media_ctx=media_ctx,
        conn=conn,
        prompt_source=prompt_source,
    )
