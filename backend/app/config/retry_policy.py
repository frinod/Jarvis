"""
config/retry_policy.py
======================
Re-export shim. Retry logic lives in app.resilience.retry.
This file exists so callers can import from either location:

    from app.config import RetryPolicy        # via config/__init__.py
    from app.resilience import RetryPolicy    # direct

Both are valid. Prefer app.resilience for new code.
"""
from app.resilience.retry import (  # noqa: F401
    RetryPolicy,
    RetryStrategy,
    RetryEvent,
    RetryObserver,
    RetryExhaustedError,
    with_retry,
    PROVIDER_RETRY,
    LLM_RETRY,
    BROKER_RETRY,
    DEFAULT_RETRY,
)
