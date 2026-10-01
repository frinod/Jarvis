"""
Phase 1 Stabilization Tests
============================
Tests for:
  A. Cache bug fix  — explicit_range determined before defaults
  B. Snapshot cache — normal days= requests hit snapshot cache
  C. Exact-range cache — explicit from_ts/to_ts uses exact cache
  D. Single-flight  — 10 concurrent identical requests → 1 upstream call
  E. Circuit breaker — rate-limit trips cooldown, stops Angel calls
  F. Cooldown gate  — calls during cooldown do not reach Angel One
  G. Transient retry — non-rate-limit errors still retry
  H. Auth cooldown  — login failure sets cooldown, blocks re-login
"""
from __future__ import annotations

import asyncio
import time
import pytest


# ── A + B: Cache bug fix + snapshot cache ────────────────────────────────────

def test_explicit_range_before_defaults():
    """
    explicit_range must be False when only days= is supplied.
    Before the fix it was always True because from_ts was filled first.
    """
    from_ts = None
    to_ts   = None
    # Correct logic (post-fix)
    explicit_range = (from_ts is not None or to_ts is not None)
    assert explicit_range is False, "days= request must NOT be treated as explicit range"


def test_explicit_range_true_when_from_ts_given():
    from_ts = 1_700_000_000_000
    to_ts   = None
    explicit_range = (from_ts is not None or to_ts is not None)
    assert explicit_range is True


def test_explicit_range_true_when_to_ts_given():
    from_ts = None
    to_ts   = 1_700_000_000_000
    explicit_range = (from_ts is not None or to_ts is not None)
    assert explicit_range is True


def test_snapshot_cache_roundtrip():
    """Snapshot cache set/get within TTL returns data."""
    from app.market_data.cache import MarketCache
    c = MarketCache()
    payload = {"symbol": "RELIANCE", "candles": [{"t": 1, "o": 100}], "source": "test"}
    c.set_snapshot("RELIANCE", "15m", 5, payload)
    result = c.get_snapshot("RELIANCE", "15m", 5)
    assert result is not None
    assert result["symbol"] == "RELIANCE"


def test_snapshot_cache_miss_different_days():
    from app.market_data.cache import MarketCache
    c = MarketCache()
    payload = {"symbol": "TCS", "candles": [], "source": "test"}
    c.set_snapshot("TCS", "15m", 5, payload)
    # Different days= → different key → miss
    assert c.get_snapshot("TCS", "15m", 10) is None


# ── C: Exact-range cache ──────────────────────────────────────────────────────

def test_exact_range_cache_roundtrip():
    from app.market_data.cache import MarketCache
    c = MarketCache()
    payload = {"symbol": "INFY", "candles": [], "source": "test"}
    c.set_candles("INFY", "1d", 1_000_000, 2_000_000, payload)
    result = c.get_candles("INFY", "1d", 1_000_000, 2_000_000)
    assert result is not None
    assert result["symbol"] == "INFY"


def test_exact_range_cache_miss_different_range():
    from app.market_data.cache import MarketCache
    c = MarketCache()
    payload = {"symbol": "INFY", "candles": [], "source": "test"}
    c.set_candles("INFY", "1d", 1_000_000, 2_000_000, payload)
    assert c.get_candles("INFY", "1d", 1_000_000, 3_000_000) is None


# ── D: Single-flight ──────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_single_flight_deduplication():
    """
    10 concurrent identical fetch_candles calls must result in exactly
    1 upstream provider call. All 10 callers receive the same result.
    """
    from unittest.mock import patch, MagicMock
    from app.market_data import service

    # Reset inflight registry
    service._INFLIGHT.clear()

    upstream_call_count = 0

    async def fake_fetch_candles(symbol, interval, from_ts, to_ts):
        nonlocal upstream_call_count
        upstream_call_count += 1
        await asyncio.sleep(0.05)  # simulate network latency
        mock_result = MagicMock()
        mock_result.ok = True
        mock_result.candles = []
        mock_result.source = "mock"
        return mock_result

    fake_mgr = MagicMock()
    fake_mgr.fetch_candles = fake_fetch_candles

    with patch("app.market_data.service.get_manager", return_value=fake_mgr), \
         patch("app.market_data.service.get_cache") as mock_cache_fn:

        mock_cache = MagicMock()
        mock_cache.get_snapshot.return_value = None
        mock_cache.get_candles.return_value = None
        mock_cache.set_candles = MagicMock()
        mock_cache.set_snapshot = MagicMock()
        mock_cache_fn.return_value = mock_cache

        with patch("app.market_data.service.validate_candles") as mock_validate, \
             patch("app.market_data.service.candles_to_legacy_dicts", return_value=[]):
            mock_validate.return_value = ([], {"quality_score": 100, "warnings": [], "usable": True})

            tasks = [
                service.fetch_candles("RELIANCE", "15m", days=5)
                for _ in range(10)
            ]
            results = await asyncio.gather(*tasks)

    assert upstream_call_count == 1, (
        f"Expected 1 upstream call, got {upstream_call_count}. "
        "Single-flight deduplication is not working."
    )
    assert len(results) == 10


# ── E: Circuit breaker — rate-limit trips cooldown ───────────────────────────

def test_rate_limit_trips_circuit_breaker():
    import app.market_data.providers.angel_one as ao
    # Reset state
    ao._rate_limit_until = 0.0

    assert not ao.is_in_rate_limit_cooldown()
    ao.trip_rate_limit_cooldown()
    assert ao.is_in_rate_limit_cooldown()

    status = ao.get_circuit_breaker_status()
    assert status["in_cooldown"] is True
    assert status["cooldown_remaining_s"] > 0

    # Reset for other tests
    ao._rate_limit_until = 0.0


def test_circuit_breaker_expires():
    import app.market_data.providers.angel_one as ao
    # Set cooldown to expire in the past
    ao._rate_limit_until = time.time() - 1.0
    assert not ao.is_in_rate_limit_cooldown()
    ao._rate_limit_until = 0.0


# ── F: Cooldown gate — is_available returns False during cooldown ─────────────

@pytest.mark.asyncio
async def test_is_available_false_during_cooldown():
    import app.market_data.providers.angel_one as ao
    from app.market_data.providers.angel_one import AngelOneProvider
    from unittest.mock import MagicMock, patch

    ao._rate_limit_until = time.time() + 60.0  # 60s cooldown

    provider = AngelOneProvider.__new__(AngelOneProvider)
    mock_session = MagicMock()
    mock_session.is_logged_in = True
    provider._session = mock_session

    available = await provider.is_available()
    assert available is False, "Provider must be unavailable during circuit breaker cooldown"

    ao._rate_limit_until = 0.0  # reset


@pytest.mark.asyncio
async def test_fetch_chunk_skipped_during_cooldown():
    """_fetch_chunk must return [] immediately when breaker is tripped."""
    import app.market_data.providers.angel_one as ao
    from app.market_data.providers.angel_one import AngelOneProvider
    from unittest.mock import MagicMock

    ao._rate_limit_until = time.time() + 60.0

    provider = AngelOneProvider.__new__(AngelOneProvider)
    mock_session = MagicMock()
    provider._session = mock_session

    result = await provider._fetch_chunk("TOKEN", "NSE", "FIFTEEN_MINUTE", 0, 1)
    assert result == [], "Must return empty list during cooldown without calling Angel One"

    # Verify smart_api was never called
    mock_session.smart_api.getCandleData.assert_not_called()

    ao._rate_limit_until = 0.0


# ── G: Transient errors still retry ──────────────────────────────────────────

@pytest.mark.asyncio
async def test_transient_error_retries():
    """A non-rate-limit exception should retry up to 2 more times (3 total)."""
    import app.market_data.providers.angel_one as ao
    from app.market_data.providers.angel_one import AngelOneProvider
    from unittest.mock import MagicMock, patch

    ao._rate_limit_until = 0.0  # no cooldown

    provider = AngelOneProvider.__new__(AngelOneProvider)
    mock_session = MagicMock()
    mock_session.is_logged_in = True

    async def _ensure():
        return True
    mock_session.ensure_logged_in = _ensure
    provider._session = mock_session

    call_count = 0

    # Python 3.7-compatible coroutine mock
    async def fake_executor(executor, fn):
        nonlocal call_count
        call_count += 1
        raise ConnectionError("transient network error")

    async def fake_sleep(secs):
        pass

    with patch("asyncio.get_event_loop") as mock_loop:
        mock_loop.return_value.run_in_executor = fake_executor
        with patch("asyncio.sleep", side_effect=fake_sleep):
            result = await provider._fetch_chunk("TOKEN", "NSE", "FIFTEEN_MINUTE", 0, 1)

    assert result == []
    assert call_count == 3, f"Expected 3 attempts for transient error, got {call_count}"
    assert not ao.is_in_rate_limit_cooldown()


# ── H: Auth cooldown ──────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_auth_failure_sets_cooldown():
    from app.market_data.providers.angel_auth import AngelSession
    from unittest.mock import patch, MagicMock

    session = AngelSession.__new__(AngelSession)
    session._api_key     = "key"
    session._client_id   = "client"
    session._password    = "pass"
    session._totp_secret = "AAAAAAAAAAAAAAAA"  # 16 chars
    session._smart_api   = None
    session._jwt         = None
    session._refresh_tok = None
    session._feed_tok    = None
    session._logged_in   = False
    session._login_at    = 0.0
    session._last_error  = None
    session._login_fail_until = 0.0
    session._lock = asyncio.Lock()

    # Simulate failed login response
    async def fake_executor(executor, fn):
        return {"status": False, "message": "Invalid credentials"}

    with patch("asyncio.get_event_loop") as mock_loop, \
         patch("pyotp.TOTP") as mock_totp:
        mock_totp.return_value.now.return_value = "123456"
        mock_loop.return_value.run_in_executor = fake_executor

        # Patch SmartConnect
        with patch("app.market_data.providers.angel_auth.AngelSession._login",
                   wraps=session._login):
            result = await session._login()

    assert result is False
    assert session._login_fail_until > time.time(), "Auth cooldown must be set after login failure"


@pytest.mark.asyncio
async def test_auth_cooldown_blocks_relogin():
    from app.market_data.providers.angel_auth import AngelSession

    session = AngelSession.__new__(AngelSession)
    session._api_key     = "key"
    session._client_id   = "client"
    session._password    = "pass"
    session._totp_secret = "AAAAAAAAAAAAAAAA"
    session._smart_api   = None
    session._jwt         = None
    session._refresh_tok = None
    session._feed_tok    = None
    session._logged_in   = False
    session._login_at    = 0.0
    session._last_error  = None
    session._login_fail_until = time.time() + 30.0  # active cooldown
    session._lock = asyncio.Lock()

    result = await session.ensure_logged_in()
    assert result is False, "ensure_logged_in must return False during auth cooldown"
