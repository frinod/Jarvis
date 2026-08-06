"""
resilience/retry.py
===================
Generic retry framework for JARVIS OS.

Supports any async or sync callable. Zero coupling to any provider,
broker, or AI service -- those pass in a RetryPolicy and call with_retry().

Strategies
----------
  FIXED              -- constant delay between attempts
  LINEAR             -- delay grows linearly: base * attempt
  EXPONENTIAL        -- delay doubles each attempt: base * (multiplier ** attempt)
  EXPONENTIAL_JITTER -- exponential + random jitter to avoid thundering herd
  CUSTOM             -- caller supplies a delay_fn(attempt, policy) -> float

Observability
-------------
Every attempt emits a RetryEvent. Attach a RetryObserver to receive them.
The default observer is a no-op. Future: wire to metrics.increment() and
structured logging without changing any caller.

Circuit Breaker Extension Point
--------------------------------
RetryObserver.on_attempt() / on_success() / on_failure() are the hooks
a circuit breaker will implement. The interface is defined now so adding
circuit_breaker.py in Phase 5.5 requires zero changes to this file.

Cancellation
------------
Pass a threading.Event (sync) or asyncio.Event (async) as cancel_event.
Retries stop cleanly when the event is set.
"""
from __future__ import annotations

import asyncio
import inspect
import random
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import (
    Any, Callable, Dict, List, Optional, Set, Tuple, Type
)


# ── Strategy enum ─────────────────────────────────────────────

class RetryStrategy(str, Enum):
    FIXED              = "fixed"
    LINEAR             = "linear"
    EXPONENTIAL        = "exponential"
    EXPONENTIAL_JITTER = "exponential_jitter"
    CUSTOM             = "custom"


# ── Observability ─────────────────────────────────────────────

@dataclass
class RetryEvent:
    """Structured record emitted on every retry attempt."""
    operation:      str
    attempt:        int          # 1-based
    max_attempts:   int
    delay_s:        float        # delay applied before this attempt (0 on first)
    elapsed_s:      float        # total elapsed since first attempt
    exception_type: str          # "" on success
    exception_msg:  str          # "" on success
    succeeded:      bool
    provider:       str = ""     # optional tag (e.g. "angel_one", "groq")
    context:        Dict[str, Any] = field(default_factory=dict)


class RetryObserver(ABC):
    """
    Extension point for circuit breakers, metrics collectors, and loggers.
    Implement this interface and pass to RetryPolicy.observer.
    All methods have default no-op implementations so partial overrides work.
    """

    def on_attempt(self, event: RetryEvent) -> None:
        """Called before each attempt (including the first)."""

    def on_success(self, event: RetryEvent) -> None:
        """Called when an attempt succeeds."""

    def on_failure(self, event: RetryEvent) -> None:
        """Called when an attempt fails (exception raised)."""

    def on_exhausted(self, event: RetryEvent) -> None:
        """Called when all attempts are exhausted without success."""


class _NoOpObserver(RetryObserver):
    """Default observer — does nothing."""


# ── Policy ────────────────────────────────────────────────────

@dataclass
class RetryPolicy:
    """
    Complete retry configuration. No hardcoded values.

    Fields
    ------
    max_attempts        : total attempts including the first (not just retries)
    strategy            : which backoff strategy to use
    base_delay_s        : initial delay in seconds
    max_delay_s         : cap on computed delay (prevents runaway backoff)
    multiplier          : backoff multiplier (used by EXPONENTIAL strategies)
    jitter_pct          : 0.0-1.0 -- fraction of delay to randomise
    timeout_s           : hard wall-clock timeout across all attempts (None = no limit)
    retryable_on        : exception types that trigger a retry (empty = retry on all)
    no_retry_on         : exception types that always abort immediately
    delay_fn            : custom delay function (strategy=CUSTOM only)
    observer            : RetryObserver instance for metrics/circuit-breaker hooks
    provider            : optional tag attached to RetryEvents
    """
    max_attempts:  int                          = 3
    strategy:      RetryStrategy               = RetryStrategy.EXPONENTIAL_JITTER
    base_delay_s:  float                       = 1.0
    max_delay_s:   float                       = 30.0
    multiplier:    float                       = 2.0
    jitter_pct:    float                       = 0.25
    timeout_s:     Optional[float]             = None
    retryable_on:  Tuple[Type[Exception], ...] = ()
    no_retry_on:   Tuple[Type[Exception], ...] = ()
    delay_fn:      Optional[Callable[[int, "RetryPolicy"], float]] = None
    observer:      RetryObserver               = field(default_factory=_NoOpObserver)
    provider:      str                         = ""

    def compute_delay(self, attempt: int) -> float:
        """
        Compute delay (seconds) before attempt number `attempt` (1-based).
        Returns 0.0 for the first attempt.
        """
        if attempt <= 1:
            return 0.0

        n = attempt - 1  # number of retries so far

        if self.strategy == RetryStrategy.FIXED:
            delay = self.base_delay_s

        elif self.strategy == RetryStrategy.LINEAR:
            delay = self.base_delay_s * n

        elif self.strategy == RetryStrategy.EXPONENTIAL:
            delay = self.base_delay_s * (self.multiplier ** (n - 1))

        elif self.strategy == RetryStrategy.EXPONENTIAL_JITTER:
            base = self.base_delay_s * (self.multiplier ** (n - 1))
            jitter = base * self.jitter_pct * random.random()
            delay = base + jitter

        elif self.strategy == RetryStrategy.CUSTOM:
            if self.delay_fn is None:
                raise ValueError("RetryPolicy.delay_fn must be set when strategy=CUSTOM")
            delay = self.delay_fn(attempt, self)

        else:
            delay = self.base_delay_s

        return min(delay, self.max_delay_s)

    def should_retry(self, exc: Exception) -> bool:
        """
        Return True if this exception type should trigger a retry.
        no_retry_on takes precedence over retryable_on.
        """
        if self.no_retry_on and isinstance(exc, self.no_retry_on):
            return False
        if self.retryable_on:
            return isinstance(exc, self.retryable_on)
        # Default: retry on any exception
        return True


# ── Pre-built named policies ──────────────────────────────────

def _import_jarvis_exceptions():
    """Lazy import to avoid circular dependency at module load."""
    try:
        from app.config.exceptions import (
            MarketDataError, RateLimitError,
            AuthenticationError, SessionExpiredError,
            LLMTimeoutError, AIError,
            ConfigurationError, InvalidSymbolError,
            InsufficientDataError,
        )
        return {
            "market":  (MarketDataError, RateLimitError),
            "no_retry_market": (ConfigurationError, InvalidSymbolError, InsufficientDataError),
            "broker":  (AuthenticationError, SessionExpiredError),
            "llm":     (LLMTimeoutError, AIError),
        }
    except ImportError:
        return {}


def _make_provider_policy() -> RetryPolicy:
    exc = _import_jarvis_exceptions()
    return RetryPolicy(
        max_attempts  = 3,
        strategy      = RetryStrategy.EXPONENTIAL_JITTER,
        base_delay_s  = 1.0,
        max_delay_s   = 15.0,
        multiplier    = 2.0,
        jitter_pct    = 0.25,
        timeout_s     = 30.0,
        retryable_on  = exc.get("market", ()),
        no_retry_on   = exc.get("no_retry_market", ()),
        provider      = "market_data",
    )


def _make_llm_policy() -> RetryPolicy:
    exc = _import_jarvis_exceptions()
    return RetryPolicy(
        max_attempts  = 3,
        strategy      = RetryStrategy.EXPONENTIAL_JITTER,
        base_delay_s  = 2.0,
        max_delay_s   = 20.0,
        multiplier    = 1.5,
        jitter_pct    = 0.2,
        timeout_s     = 60.0,
        retryable_on  = exc.get("llm", ()),
        provider      = "llm",
    )


def _make_broker_policy() -> RetryPolicy:
    exc = _import_jarvis_exceptions()
    return RetryPolicy(
        max_attempts  = 2,
        strategy      = RetryStrategy.EXPONENTIAL,
        base_delay_s  = 0.5,
        max_delay_s   = 5.0,
        multiplier    = 2.0,
        jitter_pct    = 0.0,
        timeout_s     = 10.0,
        retryable_on  = exc.get("broker", ()),
        provider      = "broker",
    )


PROVIDER_RETRY: RetryPolicy = _make_provider_policy()
LLM_RETRY:      RetryPolicy = _make_llm_policy()
BROKER_RETRY:   RetryPolicy = _make_broker_policy()
DEFAULT_RETRY:  RetryPolicy = RetryPolicy(
    max_attempts = 2,
    strategy     = RetryStrategy.EXPONENTIAL_JITTER,
    base_delay_s = 0.5,
    max_delay_s  = 10.0,
)


# ── Core retry executor ───────────────────────────────────────

class RetryExhaustedError(Exception):
    """Raised when all retry attempts are exhausted."""
    def __init__(self, operation: str, attempts: int, last_exc: Exception):
        super().__init__(
            f"'{operation}' failed after {attempts} attempt(s): {last_exc}"
        )
        self.operation  = operation
        self.attempts   = attempts
        self.last_exc   = last_exc


async def with_retry(
    policy:       RetryPolicy,
    fn:           Callable,
    *args:        Any,
    operation:    str = "",
    cancel_event: Optional[Any] = None,
    context:      Optional[Dict[str, Any]] = None,
    **kwargs:     Any,
) -> Any:
    """
    Execute fn(*args, **kwargs) with retry according to policy.

    Works with both sync and async callables.
    cancel_event: asyncio.Event -- set it to abort retries cleanly.
    operation:    human-readable name for logs/metrics (defaults to fn.__name__).
    context:      extra dict attached to every RetryEvent.
    """
    op       = operation or getattr(fn, "__name__", "unknown")
    ctx      = context or {}
    start_ts = time.monotonic()
    last_exc: Optional[Exception] = None

    for attempt in range(1, policy.max_attempts + 1):

        # ── Cancellation check ────────────────────────────────
        if cancel_event is not None:
            cancelled = (
                cancel_event.is_set()
                if hasattr(cancel_event, "is_set")
                else False
            )
            if cancelled:
                raise asyncio.CancelledError(f"Retry cancelled for '{op}'")

        # ── Timeout check ─────────────────────────────────────
        elapsed = time.monotonic() - start_ts
        if policy.timeout_s is not None and elapsed >= policy.timeout_s:
            break

        # ── Compute and apply delay ───────────────────────────
        delay = policy.compute_delay(attempt)
        if delay > 0:
            # Honour timeout: don't sleep past the deadline
            if policy.timeout_s is not None:
                remaining = policy.timeout_s - elapsed
                delay = min(delay, max(remaining, 0))
            if delay > 0:
                await asyncio.sleep(delay)

        elapsed = time.monotonic() - start_ts
        event = RetryEvent(
            operation      = op,
            attempt        = attempt,
            max_attempts   = policy.max_attempts,
            delay_s        = delay,
            elapsed_s      = elapsed,
            exception_type = "",
            exception_msg  = "",
            succeeded      = False,
            provider       = policy.provider,
            context        = ctx,
        )
        policy.observer.on_attempt(event)

        # ── Execute ───────────────────────────────────────────
        try:
            if inspect.iscoroutinefunction(fn):
                result = await fn(*args, **kwargs)
            else:
                result = fn(*args, **kwargs)

            event.succeeded = True
            policy.observer.on_success(event)
            return result

        except Exception as exc:
            last_exc = exc
            event.exception_type = type(exc).__name__
            event.exception_msg  = str(exc)
            policy.observer.on_failure(event)

            if not policy.should_retry(exc):
                raise

            if attempt == policy.max_attempts:
                break

    # All attempts exhausted
    final_event = RetryEvent(
        operation      = op,
        attempt        = policy.max_attempts,
        max_attempts   = policy.max_attempts,
        delay_s        = 0.0,
        elapsed_s      = time.monotonic() - start_ts,
        exception_type = type(last_exc).__name__ if last_exc else "",
        exception_msg  = str(last_exc) if last_exc else "",
        succeeded      = False,
        provider       = policy.provider,
        context        = ctx,
    )
    policy.observer.on_exhausted(final_event)
    raise RetryExhaustedError(op, policy.max_attempts, last_exc or Exception("timeout"))
