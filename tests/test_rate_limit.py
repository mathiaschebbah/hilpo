from __future__ import annotations

import time
import unittest

from agents.rate_limit import ReactiveRateLimiter


class ReactiveRateLimiterTests(unittest.TestCase):
    def test_finalize_refunds_reserved_input_tokens(self) -> None:
        limiter = ReactiveRateLimiter(
            max_input_tokens_per_minute=60,
            max_requests_per_minute=60,
        )

        lease = limiter.acquire(40)
        limiter.finalize(lease, actual_input_tokens=10)

        snapshot = limiter.snapshot()
        self.assertGreaterEqual(snapshot["input_available"], 49.0)

    def test_headers_clamp_overoptimistic_local_budget(self) -> None:
        limiter = ReactiveRateLimiter(
            max_input_tokens_per_minute=50_000,
            max_requests_per_minute=50,
        )

        lease = limiter.acquire(1_000)
        limiter.finalize(
            lease,
            actual_input_tokens=1_000,
            headers={
                "anthropic-ratelimit-input-tokens-limit": "50000",
                "anthropic-ratelimit-input-tokens-remaining": "1000",
            },
        )

        snapshot = limiter.snapshot()
        self.assertLess(snapshot["input_available"], 1_501.0)

    def test_retry_after_cooldown_blocks_next_acquire(self) -> None:
        limiter = ReactiveRateLimiter(
            max_input_tokens_per_minute=60_000,
            max_requests_per_minute=60,
        )

        lease = limiter.acquire(1_000)
        limiter.reject(lease, retry_after_seconds=0.05)

        start = time.perf_counter()
        limiter.acquire(1_000)
        elapsed = time.perf_counter() - start

        self.assertGreaterEqual(elapsed, 0.045)

    def test_warmup_concurrency_blocks_until_first_request_finishes(self) -> None:
        limiter = ReactiveRateLimiter(
            max_input_tokens_per_minute=60_000,
            max_requests_per_minute=60,
            warmup_max_concurrency=1,
        )

        lease = limiter.acquire(1_000)

        def release() -> None:
            time.sleep(0.05)
            limiter.finalize(lease, actual_input_tokens=1_000)

        import threading

        thread = threading.Thread(target=release)
        thread.start()

        start = time.perf_counter()
        next_lease = limiter.acquire(1_000)
        elapsed = time.perf_counter() - start
        limiter.finalize(next_lease, actual_input_tokens=1_000)
        thread.join()

        self.assertGreaterEqual(elapsed, 0.045)


if __name__ == "__main__":
    unittest.main()
