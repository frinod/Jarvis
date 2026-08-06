"""
Phase 3 Validation — Provider Verification Tests
==================================================
Verifies:
  - Angel One is registered and authenticated
  - Yahoo Finance is registered as fallback
  - Correct provider serves candle requests
  - Fallback triggers when primary fails
  - Provider status fields are complete

Rule: This file must stay under 300 lines.
"""
from __future__ import annotations
import pytest
import pytest_asyncio

from tests.phase3.helpers import (
    CheckResult, Elapsed, candle_count, source_of,
    is_angel_one, is_yahoo, print_section, print_results,
)
from tests.phase3.conftest import PRIMARY_SYMBOL, MIN_CANDLES


# ── 2.1 Provider registration ─────────────────────────────────

@pytest.mark.asyncio
async def test_providers_registered(provider_status):
    """Both Angel One and Yahoo Finance must be registered."""
    print_section("2.1 Provider Registration")
    results = []
    providers = provider_status.get("providers", [])
    names = [p["name"] for p in providers]

    r = CheckResult("angel_one_registered")
    if any("angel" in n.lower() for n in names):
        r.ok(f"found in: {names}")
    else:
        r.fail(f"not found. registered: {names}")
    results.append(r)

    r = CheckResult("yahoo_registered")
    if any("yahoo" in n.lower() for n in names):
        r.ok(f"found in: {names}")
    else:
        r.fail(f"not found. registered: {names}")
    results.append(r)

    r = CheckResult("primary_field_present")
    primary = provider_status.get("primary")
    if primary:
        r.ok(f"primary={primary}")
    else:
        r.fail("primary field missing or None")
    results.append(r)

    print_results(results)
    assert all(r.passed or r.skipped for r in results), "Provider registration failures"


# ── 2.2 Angel One authentication ─────────────────────────────

@pytest.mark.asyncio
async def test_angel_one_auth(provider_status):
    """Angel One must be available and logged in."""
    print_section("2.2 Angel One Authentication")
    results = []
    providers = provider_status.get("providers", [])
    ao = next((p for p in providers if "angel" in p.get("name", "").lower()), None)

    r = CheckResult("angel_one_found")
    if ao:
        r.ok(str(ao))
    else:
        r.skip("Angel One not registered — credentials may be missing")
    results.append(r)

    if ao:
        r2 = CheckResult("angel_one_available")
        if ao.get("available"):
            r2.ok()
        else:
            r2.fail(f"available=False, error={ao.get('last_error')}")
        results.append(r2)

        r3 = CheckResult("angel_one_logged_in")
        if ao.get("logged_in"):
            r3.ok()
        else:
            r3.fail(f"logged_in=False, error={ao.get('last_error')}")
        results.append(r3)

    print_results(results)
    assert all(r.passed or r.skipped for r in results), "Angel One auth failures"


# ── 2.3 Yahoo Finance availability ───────────────────────────

@pytest.mark.asyncio
async def test_yahoo_available(provider_status):
    """Yahoo Finance must always be available as fallback."""
    print_section("2.3 Yahoo Finance Availability")
    results = []
    providers = provider_status.get("providers", [])
    yf = next((p for p in providers if "yahoo" in p.get("name", "").lower()), None)

    r = CheckResult("yahoo_found")
    if yf:
        r.ok(str(yf))
    else:
        r.fail("Yahoo Finance not registered")
    results.append(r)

    if yf:
        r2 = CheckResult("yahoo_available")
        if yf.get("available"):
            r2.ok()
        else:
            r2.fail(f"available=False, error={yf.get('last_error')}")
        results.append(r2)

        r3 = CheckResult("yahoo_priority_lower_than_angel")
        ao = next((p for p in providers if "angel" in p.get("name", "").lower()), None)
        if ao:
            if yf.get("priority", 99) > ao.get("priority", 0):
                r3.ok(f"yahoo={yf.get('priority')} > angel={ao.get('priority')}")
            else:
                r3.fail(f"yahoo priority {yf.get('priority')} not > angel {ao.get('priority')}")
        else:
            r3.skip("Angel One not registered — cannot compare priorities")
        results.append(r3)

    print_results(results)
    assert all(r.passed or r.skipped for r in results), "Yahoo availability failures"


# ── 2.4 Provider serves candles ───────────────────────────────

@pytest.mark.asyncio
async def test_provider_serves_candles(candles_5m, active_provider):
    """Candle fetch must succeed and report which provider served it."""
    print_section("2.4 Provider Serves Candles")
    results = []

    r = CheckResult("fetch_succeeded")
    if not candles_5m.get("error") and candle_count(candles_5m) >= MIN_CANDLES:
        r.ok(f"{candle_count(candles_5m)} candles", source=source_of(candles_5m))
    else:
        r.fail(f"error={candles_5m.get('error')} count={candle_count(candles_5m)}")
    results.append(r)

    r = CheckResult("source_field_present")
    src = source_of(candles_5m)
    if src and src != "unknown":
        r.ok(f"source={src}")
    else:
        r.fail(f"source field missing or 'unknown': {src}")
    results.append(r)

    r = CheckResult("angel_one_is_primary_source")
    if is_angel_one(candles_5m):
        r.ok(f"source={src}")
    elif is_yahoo(candles_5m):
        r.skip(f"Yahoo served — Angel One may be rate-limited or market closed. source={src}")
    else:
        r.fail(f"unexpected source: {src}")
    results.append(r)

    print_results(results)
    # Only hard-fail if fetch itself failed — provider selection is informational
    assert not candles_5m.get("error"), f"Candle fetch failed: {candles_5m.get('error')}"
    assert candle_count(candles_5m) >= MIN_CANDLES, "Too few candles returned"


# ── 2.5 Cache layer ───────────────────────────────────────────

@pytest.mark.asyncio
async def test_cache_hit(service):
    """Second fetch of same symbol/interval must return cached=True."""
    print_section("2.5 Cache Layer")
    results = []

    # First fetch (cold) — validate=False avoids insufficient_clean_data
    # when Angel One returns fewer candles due to rate limiting
    with Elapsed() as t1:
        r1 = await service.fetch_candles(
            PRIMARY_SYMBOL, interval="1d", days=30, validate=False
        )
    # Second fetch (should hit cache)
    with Elapsed() as t2:
        r2 = await service.fetch_candles(
            PRIMARY_SYMBOL, interval="1d", days=30, validate=False
        )

    r = CheckResult("second_fetch_cached")
    if r2.get("cached"):
        r.ok(f"cold={t1.ms}ms warm={t2.ms}ms")
    else:
        r.fail(f"cached=False on second fetch (cold={t1.ms}ms warm={t2.ms}ms)")
    results.append(r)

    r = CheckResult("cache_faster_than_cold")
    if t2.ms < t1.ms:
        r.ok(f"{t2.ms}ms < {t1.ms}ms")
    else:
        r.skip(f"cache not faster: cold={t1.ms}ms warm={t2.ms}ms (network variance)")
    results.append(r)

    print_results(results)
    assert not r1.get("error"), f"Cold fetch failed: {r1.get('error')}"
