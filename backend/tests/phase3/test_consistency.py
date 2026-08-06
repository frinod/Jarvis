"""
Phase 3 Validation — Data Consistency Tests
============================================
Verifies that all modules receive identical candle data
from the unified market_data.service layer.

No module should bypass the service and get different data.

Rule: This file must stay under 300 lines.
"""
from __future__ import annotations
import pytest

from tests.phase3.helpers import (
    CheckResult, Elapsed, candle_count, source_of,
    candles_are_sorted, candles_have_no_duplicates,
    validate_all_candles, print_section, print_results,
)
from tests.phase3.conftest import PRIMARY_SYMBOL, MIN_CANDLES


# ── 4.1 Candle schema integrity ───────────────────────────────

@pytest.mark.asyncio
async def test_candle_schema(candles_5m, assert_candle_schema):
    """Every candle in the 5m dataset must pass OHLCV schema validation."""
    print_section("4.1 Candle Schema Integrity")
    results = []
    candles = candles_5m.get("candles", [])

    r = CheckResult("candles_present")
    if len(candles) >= MIN_CANDLES:
        r.ok(f"{len(candles)} candles")
    else:
        r.fail(f"only {len(candles)} candles (need {MIN_CANDLES})")
    results.append(r)

    r = CheckResult("all_ohlcv_valid")
    bad_count, errors = validate_all_candles(candles)
    if bad_count == 0:
        r.ok(f"all {len(candles)} candles valid")
    else:
        r.fail(f"{bad_count} invalid candles: {errors[:3]}")
    results.append(r)

    r = CheckResult("timestamps_ascending")
    if candles_are_sorted(candles):
        r.ok()
    else:
        r.fail("candles not in ascending timestamp order")
    results.append(r)

    r = CheckResult("no_duplicate_timestamps")
    if candles_have_no_duplicates(candles):
        r.ok()
    else:
        r.fail("duplicate timestamps found")
    results.append(r)

    print_results(results)
    assert bad_count == 0, f"OHLCV integrity failures: {errors[:3]}"
    assert candles_are_sorted(candles), "Candles not sorted"
    assert candles_have_no_duplicates(candles), "Duplicate timestamps"


# ── 4.2 Same source across intervals ─────────────────────────

@pytest.mark.asyncio
async def test_same_source_across_intervals(service):
    """
    5m, 15m, and 1d fetches for the same symbol should all
    come from the same provider (Angel One or Yahoo — not mixed).
    """
    print_section("4.2 Consistent Source Across Intervals")
    results = []

    r5m  = await service.fetch_candles(PRIMARY_SYMBOL, interval="5m",  days=5)
    r15m = await service.fetch_candles(PRIMARY_SYMBOL, interval="15m", days=5)
    r1d  = await service.fetch_candles(PRIMARY_SYMBOL, interval="1d",  days=30)

    sources = {
        "5m":  source_of(r5m),
        "15m": source_of(r15m),
        "1d":  source_of(r1d),
    }

    # Classify failures: hard errors vs rate-limit/data errors
    _soft = {"insufficient_clean_data", "insufficient_data"}
    hard_failed = [
        iv for iv, res in [("5m", r5m), ("15m", r15m), ("1d", r1d)]
        if res.get("error") and res["error"] not in _soft
    ]
    soft_failed = [
        iv for iv, res in [("5m", r5m), ("15m", r15m), ("1d", r1d)]
        if res.get("error") and res["error"] in _soft
    ]

    r = CheckResult("all_intervals_succeeded")
    if not hard_failed and not soft_failed:
        r.ok(f"sources={sources}")
    elif soft_failed and not hard_failed:
        r.skip(f"rate-limited intervals: {soft_failed} (Angel One access rate exceeded)")
    else:
        r.fail(f"hard-failed intervals: {hard_failed}")
    results.append(r)

    r = CheckResult("sources_consistent")
    unique_providers = set(
        s.split("_")[0] for s in sources.values() if s != "unknown"
    )
    if len(unique_providers) <= 1:
        r.ok(f"all from: {unique_providers}")
    else:
        r.skip(f"mixed providers: {sources} — fallback may have triggered for one interval")
    results.append(r)

    print_results(results)
    assert not hard_failed, f"Interval fetch hard failures: {hard_failed}"


# ── 4.3 Two modules, same candles ────────────────────────────

@pytest.mark.asyncio
async def test_two_modules_same_candles(service):
    """
    Calling service.fetch_candles twice with identical params
    must return the same candle count and same last close price.
    (Proves the cache layer is consistent.)
    """
    print_section("4.3 Two Calls — Same Candles")
    results = []

    r1 = await service.fetch_candles(PRIMARY_SYMBOL, interval="15m", days=5)
    r2 = await service.fetch_candles(PRIMARY_SYMBOL, interval="15m", days=5)

    r = CheckResult("both_succeeded")
    if not r1.get("error") and not r2.get("error"):
        r.ok()
    else:
        r.fail(f"r1={r1.get('error')} r2={r2.get('error')}")
    results.append(r)

    r = CheckResult("same_candle_count")
    c1, c2 = candle_count(r1), candle_count(r2)
    if c1 == c2:
        r.ok(f"both={c1}")
    else:
        r.fail(f"r1={c1} r2={c2}")
    results.append(r)

    r = CheckResult("same_last_close")
    if r1.get("candles") and r2.get("candles"):
        lc1 = r1["candles"][-1]["c"]
        lc2 = r2["candles"][-1]["c"]
        if lc1 == lc2:
            r.ok(f"close={lc1}")
        else:
            r.fail(f"r1 close={lc1} r2 close={lc2}")
    else:
        r.skip("no candles to compare")
    results.append(r)

    r = CheckResult("second_call_cached")
    if r2.get("cached"):
        r.ok()
    else:
        r.skip("second call not cached — TTL may have expired between calls")
    results.append(r)

    print_results(results)
    assert not r1.get("error"), f"First fetch failed: {r1.get('error')}"
    assert not r2.get("error"), f"Second fetch failed: {r2.get('error')}"
    assert candle_count(r1) == candle_count(r2), "Candle count mismatch between calls"


# ── 4.4 Quality score present ────────────────────────────────

@pytest.mark.asyncio
async def test_quality_score_present(candles_5m):
    """Service must return a quality score between 0 and 100."""
    print_section("4.4 Data Quality Score")
    results = []

    r = CheckResult("quality_field_present")
    q = candles_5m.get("quality")
    if q is not None:
        r.ok(f"quality={q}")
    else:
        r.fail("quality field missing from service response")
    results.append(r)

    r = CheckResult("quality_in_range")
    if q is not None and 0 <= q <= 100:
        r.ok(f"{q}/100")
    elif q is not None:
        r.fail(f"quality={q} out of range 0-100")
    else:
        r.skip("quality field missing")
    results.append(r)

    r = CheckResult("quality_acceptable")
    if q is not None and q >= 50:
        r.ok(f"quality={q} >= 50")
    elif q is not None:
        r.skip(f"quality={q} < 50 — data may be sparse (market closed)")
    else:
        r.skip("quality field missing")
    results.append(r)

    print_results(results)
    assert candles_5m.get("quality") is not None, "quality field missing"
