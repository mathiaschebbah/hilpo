"""Rate limiting réactif pour la pipeline agentique.

Le scheduler suit un token bucket local pour coller au comportement Anthropic:
- budget requests/minute
- budget input tokens/minute
- budget output tokens/minute quand Anthropic expose la limite via les headers

Les estimations input sont apprises en ligne à partir du payload réellement envoyé.
"""

from __future__ import annotations

import json
import math
import threading
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Any, Mapping

TOKEN_HEADER_ROUNDING = 500.0
MIN_WAIT_SECONDS = 0.01


def _json_default(value: Any) -> Any:
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")
    if hasattr(value, "to_dict"):
        return value.to_dict()
    if isinstance(value, set):
        return sorted(value)
    if hasattr(value, "__dict__"):
        return value.__dict__
    return str(value)


def _parse_int(raw: str | None) -> int | None:
    if raw is None:
        return None
    try:
        return int(raw)
    except ValueError:
        return None


def _parse_retry_after(headers: Mapping[str, str] | None) -> float | None:
    if not headers:
        return None

    retry_ms = headers.get("retry-after-ms")
    if retry_ms is not None:
        try:
            return max(0.0, float(retry_ms) / 1000.0)
        except ValueError:
            pass

    retry_after = headers.get("retry-after")
    if retry_after is None:
        return None

    try:
        return max(0.0, float(retry_after))
    except ValueError:
        pass

    try:
        dt = parsedate_to_datetime(retry_after)
    except (TypeError, ValueError, IndexError):
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return max(0.0, dt.timestamp() - time.time())


def _parse_reset_delta(raw: str | None) -> float | None:
    if raw is None:
        return None
    try:
        dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None
    return max(0.0, dt.timestamp() - time.time())


@dataclass(frozen=True)
class RequestEstimate:
    input_tokens: int
    payload_chars: int


@dataclass(frozen=True)
class RateLimitLease:
    input_tokens: int
    output_tokens: int = 0
    requests: int = 1
    queue_wait_ms: float = 0.0
    bottleneck: str = "none"


@dataclass
class _TokenBucket:
    limit_per_minute: float
    available: float
    last_refill: float
    enabled: bool = True

    @property
    def refill_per_second(self) -> float:
        return self.limit_per_minute / 60.0 if self.limit_per_minute > 0 else 0.0

    def refresh(self, now: float) -> None:
        if not self.enabled:
            self.last_refill = now
            return
        if now <= self.last_refill:
            return
        refill = (now - self.last_refill) * self.refill_per_second
        self.available = min(self.limit_per_minute, self.available + refill)
        self.last_refill = now

    def wait_time(self, units: int) -> float:
        if not self.enabled or units <= 0:
            return 0.0
        if self.available >= units:
            return 0.0
        rate = self.refill_per_second
        if rate <= 0:
            return float("inf")
        return (units - self.available) / rate

    def consume(self, units: int) -> None:
        if not self.enabled or units <= 0:
            return
        self.available -= units

    def reconcile(self, reserved: int, actual: int) -> None:
        if not self.enabled:
            return
        self.available += reserved - actual
        if self.available > self.limit_per_minute:
            self.available = self.limit_per_minute

    def update_limit(self, limit_per_minute: int, now: float, starting_available: float | None = None) -> None:
        new_limit = float(limit_per_minute)
        was_enabled = self.enabled
        self.limit_per_minute = new_limit
        self.enabled = new_limit > 0
        self.last_refill = now
        if not self.enabled:
            self.available = 0.0
            return
        if starting_available is not None and not was_enabled:
            self.available = min(new_limit, starting_available)
            return
        self.available = min(new_limit, self.available)


class RequestTokenEstimator:
    """Approxime les input tokens à partir du payload JSON réellement envoyé."""

    def __init__(
        self,
        default_chars_per_token: float = 3.6,
        safety_margin: float = 1.06,
        bias_tokens: float = 96.0,
        min_tokens: int = 256,
    ):
        self._chars_per_token = default_chars_per_token
        self._safety_margin = safety_margin
        self._bias_tokens = bias_tokens
        self._min_tokens = min_tokens
        self._lock = threading.Lock()

    def estimate(
        self,
        *,
        model: str,
        max_tokens: int,
        system: str,
        messages: list[dict],
        tools: list[dict],
        betas: list[str] | None = None,
    ) -> RequestEstimate:
        payload = {
            "model": model,
            "max_tokens": max_tokens,
            "system": system,
            "messages": messages,
            "tools": tools,
            "betas": betas or [],
        }
        payload_chars = len(json.dumps(payload, ensure_ascii=False, separators=(",", ":"), default=_json_default))
        with self._lock:
            chars_per_token = self._chars_per_token
            safety_margin = self._safety_margin
            bias_tokens = self._bias_tokens

        raw_tokens = payload_chars / max(chars_per_token, 0.5)
        estimate = int(math.ceil(raw_tokens * safety_margin + bias_tokens))
        return RequestEstimate(input_tokens=max(self._min_tokens, estimate), payload_chars=payload_chars)

    def observe(self, estimate: RequestEstimate, actual_input_tokens: int) -> None:
        if actual_input_tokens <= 0:
            return

        sample_chars_per_token = estimate.payload_chars / actual_input_tokens
        sample_ratio = actual_input_tokens / max(estimate.input_tokens, 1)
        sample_bias = max(64.0, float(actual_input_tokens - estimate.input_tokens + 64))

        with self._lock:
            self._chars_per_token = (0.85 * self._chars_per_token) + (0.15 * sample_chars_per_token)

            target_margin = min(1.30, max(1.0, sample_ratio + 0.02))
            margin_blend = 0.20 if sample_ratio > self._safety_margin else 0.05
            self._safety_margin = ((1.0 - margin_blend) * self._safety_margin) + (margin_blend * target_margin)

            target_bias = min(2048.0, sample_bias)
            bias_blend = 0.20 if actual_input_tokens > estimate.input_tokens else 0.05
            self._bias_tokens = ((1.0 - bias_blend) * self._bias_tokens) + (bias_blend * target_bias)

    def snapshot(self) -> dict[str, float | str | bool]:
        with self._lock:
            return {
                "chars_per_token": self._chars_per_token,
                "safety_margin": self._safety_margin,
                "bias_tokens": self._bias_tokens,
            }


class ReactiveRateLimiter:
    """Token bucket réactif avec feedback des headers Anthropic."""

    def __init__(
        self,
        *,
        max_input_tokens_per_minute: int,
        max_requests_per_minute: int,
        max_output_tokens_per_minute: int | None = None,
        warmup_max_concurrency: int = 0,
    ):
        now = time.monotonic()
        self._condition = threading.Condition()
        self._cooldown_until = 0.0
        self._warmup_max_concurrency = max(0, warmup_max_concurrency)
        self._headers_observed = False
        self._inflight_requests = 0
        self._waiters = 0
        self._last_queue_wait_ms = 0.0
        self._last_bottleneck = "none"
        self._header_remaining: dict[str, int | None] = {
            "requests": None,
            "input_tokens": None,
            "output_tokens": None,
        }
        self._header_reset_seconds: dict[str, float | None] = {
            "requests": None,
            "input_tokens": None,
            "output_tokens": None,
        }
        self._requests = _TokenBucket(
            limit_per_minute=float(max_requests_per_minute),
            available=float(max_requests_per_minute),
            last_refill=now,
        )
        self._input_tokens = _TokenBucket(
            limit_per_minute=float(max_input_tokens_per_minute),
            available=float(max_input_tokens_per_minute),
            last_refill=now,
        )
        output_limit = float(max_output_tokens_per_minute or 0)
        self._output_tokens = _TokenBucket(
            limit_per_minute=output_limit,
            available=output_limit,
            last_refill=now,
            enabled=output_limit > 0,
        )

    def uses_output_budget(self) -> bool:
        with self._condition:
            return self._output_tokens.enabled

    def acquire(self, estimated_input_tokens: int, estimated_output_tokens: int = 0) -> RateLimitLease:
        input_tokens = max(1, int(math.ceil(estimated_input_tokens)))
        output_tokens = max(0, int(math.ceil(estimated_output_tokens)))
        started = time.monotonic()
        counted_waiter = False

        with self._condition:
            while True:
                now = time.monotonic()
                self._refresh_locked(now)
                wait_time, bottleneck = self._compute_wait_locked(
                    now=now,
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                )

                if wait_time <= 0:
                    if counted_waiter:
                        self._waiters = max(0, self._waiters - 1)
                    self._requests.consume(1)
                    self._input_tokens.consume(input_tokens)
                    self._output_tokens.consume(output_tokens)
                    self._inflight_requests += 1
                    queue_wait_ms = max(0.0, (time.monotonic() - started) * 1000.0)
                    self._last_queue_wait_ms = queue_wait_ms
                    self._last_bottleneck = bottleneck
                    return RateLimitLease(
                        input_tokens=input_tokens,
                        output_tokens=output_tokens,
                        requests=1,
                        queue_wait_ms=queue_wait_ms,
                        bottleneck=bottleneck,
                    )

                if not counted_waiter:
                    self._waiters += 1
                    counted_waiter = True
                self._condition.wait(timeout=max(MIN_WAIT_SECONDS, wait_time))

    def finalize(
        self,
        lease: RateLimitLease,
        *,
        actual_input_tokens: int,
        actual_output_tokens: int = 0,
        actual_requests: int = 1,
        headers: Mapping[str, str] | None = None,
    ) -> None:
        with self._condition:
            now = time.monotonic()
            self._refresh_locked(now)
            self._inflight_requests = max(0, self._inflight_requests - lease.requests)
            self._requests.reconcile(lease.requests, max(0, actual_requests))
            self._input_tokens.reconcile(lease.input_tokens, max(0, actual_input_tokens))
            self._output_tokens.reconcile(lease.output_tokens, max(0, actual_output_tokens))
            self._observe_headers_locked(headers, now)
            self._condition.notify_all()

    def reject(
        self,
        lease: RateLimitLease,
        *,
        headers: Mapping[str, str] | None = None,
        retry_after_seconds: float | None = None,
    ) -> None:
        with self._condition:
            now = time.monotonic()
            self._refresh_locked(now)
            self._inflight_requests = max(0, self._inflight_requests - lease.requests)
            self._requests.reconcile(lease.requests, 0)
            self._input_tokens.reconcile(lease.input_tokens, 0)
            self._output_tokens.reconcile(lease.output_tokens, 0)

            self._observe_headers_locked(headers, now)
            wait_seconds = retry_after_seconds if retry_after_seconds is not None else _parse_retry_after(headers)
            if wait_seconds is None:
                wait_seconds = self._fallback_cooldown_from_resets(headers)
            if wait_seconds is not None:
                self._cooldown_until = max(self._cooldown_until, now + wait_seconds)
            self._condition.notify_all()

    def snapshot(self) -> dict[str, float]:
        with self._condition:
            now = time.monotonic()
            self._refresh_locked(now)
            return {
                "cooldown_for": max(0.0, self._cooldown_until - now),
                "headers_observed": self._headers_observed,
                "warmup_max_concurrency": float(self._warmup_max_concurrency),
                "inflight_requests": float(self._inflight_requests),
                "waiters": float(self._waiters),
                "last_queue_wait_ms": self._last_queue_wait_ms,
                "bottleneck": self._last_bottleneck,
                "requests_available": self._requests.available,
                "requests_limit": self._requests.limit_per_minute,
                "requests_remaining": float(self._header_remaining["requests"] or 0),
                "requests_reset_seconds": float(self._header_reset_seconds["requests"] or 0.0),
                "input_available": self._input_tokens.available,
                "input_limit": self._input_tokens.limit_per_minute,
                "input_remaining": float(self._header_remaining["input_tokens"] or 0),
                "input_reset_seconds": float(self._header_reset_seconds["input_tokens"] or 0.0),
                "output_available": self._output_tokens.available,
                "output_limit": self._output_tokens.limit_per_minute,
                "output_remaining": float(self._header_remaining["output_tokens"] or 0),
                "output_reset_seconds": float(self._header_reset_seconds["output_tokens"] or 0.0),
            }

    def _refresh_locked(self, now: float) -> None:
        self._requests.refresh(now)
        self._input_tokens.refresh(now)
        self._output_tokens.refresh(now)

    def _compute_wait_locked(self, *, now: float, input_tokens: int, output_tokens: int) -> tuple[float, str]:
        waits = {
            "cooldown": max(0.0, self._cooldown_until - now),
            "requests": self._requests.wait_time(1),
            "input_tokens": self._input_tokens.wait_time(input_tokens),
        }
        if self._output_tokens.enabled and output_tokens > 0:
            waits["output_tokens"] = self._output_tokens.wait_time(output_tokens)
        if self._warmup_max_concurrency > 0 and not self._headers_observed:
            waits["warmup"] = 0.0 if self._inflight_requests < self._warmup_max_concurrency else MIN_WAIT_SECONDS

        bottleneck = max(waits, key=waits.get)
        return waits[bottleneck], bottleneck if waits[bottleneck] > 0 else "none"

    def _observe_headers_locked(self, headers: Mapping[str, str] | None, now: float) -> None:
        if not headers:
            return
        self._headers_observed = True

        self._sync_request_bucket_locked(headers, now)
        self._sync_token_bucket_locked(
            bucket=self._input_tokens,
            headers=headers,
            now=now,
            bucket_name="input_tokens",
            limit_header="anthropic-ratelimit-input-tokens-limit",
            remaining_header="anthropic-ratelimit-input-tokens-remaining",
            reset_header="anthropic-ratelimit-input-tokens-reset",
            rounded=True,
        )
        self._sync_token_bucket_locked(
            bucket=self._output_tokens,
            headers=headers,
            now=now,
            bucket_name="output_tokens",
            limit_header="anthropic-ratelimit-output-tokens-limit",
            remaining_header="anthropic-ratelimit-output-tokens-remaining",
            reset_header="anthropic-ratelimit-output-tokens-reset",
            rounded=True,
        )

    def _sync_request_bucket_locked(self, headers: Mapping[str, str], now: float) -> None:
        limit = _parse_int(headers.get("anthropic-ratelimit-requests-limit"))
        remaining = _parse_int(headers.get("anthropic-ratelimit-requests-remaining"))
        self._header_remaining["requests"] = remaining
        self._header_reset_seconds["requests"] = _parse_reset_delta(
            headers.get("anthropic-ratelimit-requests-reset")
        )

        if limit is not None and limit > 0:
            starting_available = float(limit if remaining is None else remaining)
            self._requests.update_limit(limit, now, starting_available=starting_available)

        if remaining is not None:
            self._requests.available = min(self._requests.available, float(remaining))

    def _sync_token_bucket_locked(
        self,
        *,
        bucket: _TokenBucket,
        headers: Mapping[str, str],
        now: float,
        bucket_name: str,
        limit_header: str,
        remaining_header: str,
        reset_header: str,
        rounded: bool,
    ) -> None:
        limit = _parse_int(headers.get(limit_header))
        remaining = _parse_int(headers.get(remaining_header))
        self._header_remaining[bucket_name] = remaining
        self._header_reset_seconds[bucket_name] = _parse_reset_delta(headers.get(reset_header))

        if limit is not None and limit > 0:
            rounded_headroom = TOKEN_HEADER_ROUNDING if rounded else 0.0
            if remaining is None:
                starting_available = float(limit)
            else:
                starting_available = min(float(limit), float(remaining) + rounded_headroom)
            bucket.update_limit(limit, now, starting_available=starting_available)

        if remaining is not None and bucket.enabled:
            upper_bound = float(remaining) + (TOKEN_HEADER_ROUNDING if rounded else 0.0)
            bucket.available = min(bucket.available, upper_bound)

    def _fallback_cooldown_from_resets(self, headers: Mapping[str, str] | None) -> float | None:
        if not headers:
            return None
        deltas = [
            _parse_reset_delta(headers.get("anthropic-ratelimit-requests-reset")),
            _parse_reset_delta(headers.get("anthropic-ratelimit-input-tokens-reset")),
            _parse_reset_delta(headers.get("anthropic-ratelimit-output-tokens-reset")),
            _parse_reset_delta(headers.get("anthropic-ratelimit-tokens-reset")),
        ]
        deltas = [delta for delta in deltas if delta is not None and delta > 0]
        if not deltas:
            return None
        return min(deltas)
