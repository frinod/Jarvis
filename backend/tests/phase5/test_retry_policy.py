"""
test_retry_policy.py -- Task 3 validation
Tests for app/resilience/retry.py and app/config/retry_policy.py
"""
from __future__ import annotations

import asyncio
import time
import pytest

from app.resilience.retry import (
    RetryPolicy, RetryStrategy, RetryEvent, RetryObserver,
    RetryExhaustedError, with_retry,
    PROVIDER_RETRY, LLM_RETRY, BROKER_RETRY, DEFAULT_RETRY,
)


# ── Helpers ───────────────────────────────────────────────────

class _RecordingObserver(RetryObserver):
    """Captures all events for assertion."""
    def __init__(self):
        self.attempts  = []
        self.successes = []
        self.failures  = []
        self.exhausted = []

    def on_attempt(self, e):  self.attempts.append(e)
    def on_success(self, e):  self.successes.append(e)
    def on_failure(self, e):  self.failures.append(e)
    def on_exhausted(self, e): self.exhausted.append(e)


def _make_flaky(fail_times: int):
    """Returns a sync callable that fails `fail_times` then succeeds."""
    calls = {"n": 0}
    def fn():
        calls["n"] += 1
        if calls["n"] <= fail_times:
            raise ValueError(f"fail #{calls['n']}")
        return "ok"
    return fn


async def _make_async_flaky(fail_times: int):
    """Returns an async callable that fails `fail_times` then succeeds."""
    calls = {"n": 0}
    async def fn():
        calls["n"] += 1
        if calls["n"] <= fail_times:
            raise ValueError(f"async fail #{calls['n']}")
        return "async_ok"
    return fn


# ── Delay computation ─────────────────────────────────────────

class TestDelayComputation:

    def test_first_attempt_no_delay(self):
        p = RetryPolicy(base_delay_s=2.0)
        assert p.compute_delay(1) == 0.0

    def test_fixed_strategy(self):
        p = RetryPolicy(strategy=RetryStrategy.FIXED, base_delay_s=3.0)
        assert p.compute_delay(2) == 3.0
        assert p.compute_delay(3) == 3.0
        assert p.compute_delay(5) == 3.0

    def test_linear_strategy(self):
        p = RetryPolicy(strategy=RetryStrategy.LINEAR, base_delay_s=2.0)
        assert p.compute_delay(2) == 2.0   # 2 * 1
        assert p.compute_delay(3) == 4.0   # 2 * 2
        assert p.compute_delay(4) == 6.0   # 2 * 3

    def test_exponential_strategy(self):
        p = RetryPolicy(
            strategy=RetryStrategy.EXPONENTIAL,
            base_delay_s=1.0, multiplier=2.0
        )
        assert p.compute_delay(2) == 1.0   # 1 * 2^0
        assert p.compute_delay(3) == 2.0   # 1 * 2^1
        assert p.compute_delay(4) == 4.0   # 1 * 2^2

    def test_exponential_capped_at_max(self):
        p = RetryPolicy(
            strategy=RetryStrategy.EXPONENTIAL,
            base_delay_s=1.0, multiplier=10.0, max_delay_s=5.0
        )
        assert p.compute_delay(5) == 5.0   # would be 1000, capped at 5

    def test_exponential_jitter_within_bounds(self):
        p = RetryPolicy(
            strategy=RetryStrategy.EXPONENTIAL_JITTER,
            base_delay_s=1.0, multiplier=2.0, jitter_pct=0.5, max_delay_s=100.0
        )
        for _ in range(50):
            d = p.compute_delay(2)
            assert 1.0 <= d <= 1.5, f"jitter out of bounds: {d}"

    def test_custom_strategy(self):
        p = RetryPolicy(
            strategy=RetryStrategy.CUSTOM,
            delay_fn=lambda attempt, _: attempt * 10.0,
            max_delay_s=1000.0,
        )
        assert p.compute_delay(2) == 20.0
        assert p.compute_delay(3) == 30.0

    def test_custom_strategy_missing_fn_raises(self):
        p = RetryPolicy(strategy=RetryStrategy.CUSTOM, delay_fn=None)
        with pytest.raises(ValueError, match="delay_fn"):
            p.compute_delay(2)


# ── should_retry logic ────────────────────────────────────────

class TestShouldRetry:

    def test_default_retries_on_any_exception(self):
        p = RetryPolicy()
        assert p.should_retry(ValueError("x")) is True
        assert p.should_retry(RuntimeError("x")) is True

    def test_retryable_on_filters(self):
        p = RetryPolicy(retryable_on=(ValueError,))
        assert p.should_retry(ValueError("x")) is True
        assert p.should_retry(RuntimeError("x")) is False

    def test_no_retry_on_takes_precedence(self):
        p = RetryPolicy(
            retryable_on=(Exception,),
            no_retry_on=(ValueError,),
        )
        assert p.should_retry(ValueError("x")) is False
        assert p.should_retry(RuntimeError("x")) is True

    def test_subclass_matched_by_parent(self):
        class MyError(ValueError): pass
        p = RetryPolicy(retryable_on=(ValueError,))
        assert p.should_retry(MyError("x")) is True


# ── Sync retry execution ──────────────────────────────────────

class TestSyncRetry:

    def test_success_on_first_attempt(self):
        fn = _make_flaky(0)
        policy = RetryPolicy(max_attempts=3, base_delay_s=0.0)
        result = asyncio.get_event_loop().run_until_complete(
            with_retry(policy, fn, operation="test_op")
        )
        assert result == "ok"

    def test_success_after_retries(self):
        fn = _make_flaky(2)
        policy = RetryPolicy(
            max_attempts=3,
            strategy=RetryStrategy.FIXED,
            base_delay_s=0.0,
        )
        result = asyncio.get_event_loop().run_until_complete(
            with_retry(policy, fn, operation="test_op")
        )
        assert result == "ok"

    def test_exhausted_raises_retry_exhausted_error(self):
        fn = _make_flaky(99)
        policy = RetryPolicy(
            max_attempts=3,
            strategy=RetryStrategy.FIXED,
            base_delay_s=0.0,
        )
        with pytest.raises(RetryExhaustedError) as exc_info:
            asyncio.get_event_loop().run_until_complete(
                with_retry(policy, fn, operation="test_op")
            )
        assert exc_info.value.attempts == 3
        assert exc_info.value.operation == "test_op"

    def test_non_retryable_exception_propagates_immediately(self):
        calls = {"n": 0}
        def fn():
            calls["n"] += 1
            raise TypeError("not retryable")

        policy = RetryPolicy(
            max_attempts=5,
            base_delay_s=0.0,
            no_retry_on=(TypeError,),
        )
        with pytest.raises(TypeError):
            asyncio.get_event_loop().run_until_complete(
                with_retry(policy, fn)
            )
        assert calls["n"] == 1   # only one attempt made


# ── Async retry execution ─────────────────────────────────────

class TestAsyncRetry:

    def test_async_success_on_first_attempt(self):
        async def fn(): return "async_ok"
        policy = RetryPolicy(max_attempts=3, base_delay_s=0.0)
        result = asyncio.get_event_loop().run_until_complete(
            with_retry(policy, fn)
        )
        assert result == "async_ok"

    def test_async_success_after_retries(self):
        calls = {"n": 0}
        async def fn():
            calls["n"] += 1
            if calls["n"] < 3:
                raise ValueError("not yet")
            return "done"

        policy = RetryPolicy(
            max_attempts=3,
            strategy=RetryStrategy.FIXED,
            base_delay_s=0.0,
        )
        result = asyncio.get_event_loop().run_until_complete(
            with_retry(policy, fn)
        )
        assert result == "done"
        assert calls["n"] == 3

    def test_async_exhausted(self):
        async def fn(): raise RuntimeError("always fails")
        policy = RetryPolicy(
            max_attempts=2,
            strategy=RetryStrategy.FIXED,
            base_delay_s=0.0,
        )
        with pytest.raises(RetryExhaustedError):
            asyncio.get_event_loop().run_until_complete(
                with_retry(policy, fn)
            )


# ── Observer hooks ────────────────────────────────────────────

class TestObserver:

    def test_observer_receives_attempt_events(self):
        obs = _RecordingObserver()
        fn = _make_flaky(2)
        policy = RetryPolicy(
            max_attempts=3,
            strategy=RetryStrategy.FIXED,
            base_delay_s=0.0,
            observer=obs,
        )
        asyncio.get_event_loop().run_until_complete(
            with_retry(policy, fn, operation="obs_test")
        )
        assert len(obs.attempts) == 3
        assert len(obs.successes) == 1
        assert len(obs.failures) == 2
        assert len(obs.exhausted) == 0

    def test_observer_receives_exhausted_event(self):
        obs = _RecordingObserver()
        async def fn(): raise ValueError("always")
        policy = RetryPolicy(
            max_attempts=2,
            strategy=RetryStrategy.FIXED,
            base_delay_s=0.0,
            observer=obs,
        )
        with pytest.raises(RetryExhaustedError):
            asyncio.get_event_loop().run_until_complete(
                with_retry(policy, fn)
            )
        assert len(obs.exhausted) == 1

    def test_event_fields_populated(self):
        obs = _RecordingObserver()
        async def fn(): return 42
        policy = RetryPolicy(
            max_attempts=1,
            base_delay_s=0.0,
            observer=obs,
            provider="test_provider",
        )
        asyncio.get_event_loop().run_until_complete(
            with_retry(policy, fn, operation="field_test", context={"k": "v"})
        )
        e = obs.attempts[0]
        assert e.operation    == "field_test"
        assert e.provider     == "test_provider"
        assert e.context["k"] == "v"
        assert e.max_attempts == 1
        assert e.attempt      == 1


# ── Cancellation ──────────────────────────────────────────────

class TestCancellation:

    def test_cancel_event_stops_retries(self):
        cancel = asyncio.Event()
        calls = {"n": 0}

        async def fn():
            calls["n"] += 1
            cancel.set()          # signal cancellation after first attempt
            raise ValueError("fail")

        policy = RetryPolicy(
            max_attempts=5,
            strategy=RetryStrategy.FIXED,
            base_delay_s=0.0,
        )
        with pytest.raises((asyncio.CancelledError, RetryExhaustedError)):
            asyncio.get_event_loop().run_until_complete(
                with_retry(policy, fn, cancel_event=cancel)
            )
        # Should not have made all 5 attempts
        assert calls["n"] < 5


# ── Named policies ────────────────────────────────────────────

class TestNamedPolicies:

    def test_provider_retry_config(self):
        assert PROVIDER_RETRY.max_attempts == 3
        assert PROVIDER_RETRY.timeout_s    == 30.0
        assert PROVIDER_RETRY.provider     == "market_data"

    def test_llm_retry_config(self):
        assert LLM_RETRY.max_attempts == 3
        assert LLM_RETRY.timeout_s    == 60.0
        assert LLM_RETRY.provider     == "llm"

    def test_broker_retry_config(self):
        assert BROKER_RETRY.max_attempts == 2
        assert BROKER_RETRY.timeout_s    == 10.0
        assert BROKER_RETRY.provider     == "broker"

    def test_default_retry_config(self):
        assert DEFAULT_RETRY.max_attempts == 2

    def test_config_shim_imports_same_objects(self):
        from app.config.retry_policy import (
            RetryPolicy as RP2, PROVIDER_RETRY as PR2
        )
        assert RP2 is RetryPolicy
        assert PR2 is PROVIDER_RETRY


# ── RetryExhaustedError ───────────────────────────────────────

class TestRetryExhaustedError:

    def test_carries_last_exception(self):
        original = ValueError("root cause")
        err = RetryExhaustedError("my_op", 3, original)
        assert err.last_exc is original
        assert err.attempts == 3
        assert err.operation == "my_op"
        assert "my_op" in str(err)
        assert "3" in str(err)
