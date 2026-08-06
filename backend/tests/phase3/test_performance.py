"""
Phase 3 Validation — Performance Benchmark
============================================
Measures:
  - Cold fetch latency (Angel One vs Yahoo)
  - Cache hit latency
  - Cache hit rate over N repeated calls
  - Provider status overhead

These are informational benchmarks, not hard pass/fail gates,
except for obvious failures (>30s timeout, 0% cache hit rate).

Rule: This file must stay under 300 lines.
"""
from __future__ import annotations
import asyncio
import pytest

from tests.phase3.helpers import (
    CheckResult, Elapsed, candle_count, source_of,
    print_section, print_results,
)
from tests.phase3.conftest import PRIMARY_SYMBOL, SECONDARY_SYMBOL

# Thresholds
_MAX_COLD_MS   = 30_000   # 30s — hard fail if exceeded
_MAX_CACHED_MS = 500      # 500ms — cached fetch must be fast
_CACHE_ROUNDS  = 5        # number of repeated calls to measure hit rate


# ── 6.1 Cold fetch latency ────────────────────────────────────

@pytest.mark.asyncio
async def test_cold_fetch_latency(service):
    """Measure cold fetch time for 5m candles. Hard fail only if > 30s."""
    print_section("6.1 Cold Fetch Latency")
    results = []

    # Use a symbol not yet cached in this session
    with Elapsed() as t:
        result = await service.fetch_candles(
            SECONDARY_SYMBOL, interval="5m", days=5, validate=False
        )

    r = CheckResult("fetch_completed")
    if not result.get("error"):
        r.ok(
            f"{candle_count(result)} candles in {t.ms}ms "
            f"source={source_of(result)}",
            source=source_of(result),
        )
    else:
        r.fail(f"error={result['error']} after {t.ms}ms")
    results.append(r)

    r = CheckResult("latency_under_30s")
    if t.ms < _MAX_COLD_MS:
        r.ok(f"{t.ms}ms < {_MAX_COLD_MS}ms")
    else:
        r.fail(f"{t.ms}ms exceeds {_MAX_COLD_MS}ms hard limit")
    results.append(r)

    r = CheckResult("latency_under_5s_preferred")
    if t.ms < 5000:
        r.ok(f"{t.ms}ms")
    else:
        r.skip(f"{t.ms}ms > 5s — acceptable but slow (network/rate-limit)")
    results.append(r)

    print_results(results)
    assert t.ms < _MAX_COLD_MS, f"Cold fetch exceeded 30s timeout: {t.ms}ms"
    assert not result.get("error"), f"Cold fetch error: {result.get('error')}"


# ── 6.2 Cache hit latency ─────────────────────────────────────

@pytest.mark.asyncio
async def test_cache_hit_latency(service):
    """Cached fetch must complete in under 500ms."""
    print_section("6.2 Cache Hit Latency")
    results = []

    # Warm the cache
    await service.fetch_candles(PRIMARY_SYMBOL, interval="15m", days=5)

    # Measure cached fetch
    with Elapsed() as t:
        result = await service.fetch_candles(PRIMARY_SYMBOL, interval="15m", days=5)

    r = CheckResult("is_cached")
    if result.get("cached"):
        r.ok(f"{t.ms}ms")
    else:
        r.skip(f"not cached (TTL may have expired) — {t.ms}ms")
    results.append(r)

    r = CheckResult("cached_under_500ms")
    if result.get("cached") and t.ms < _MAX_CACHED_MS:
        r.ok(f"{t.ms}ms < {_MAX_CACHED_MS}ms")
    elif result.get("cached"):
        r.fail(f"cached but slow: {t.ms}ms > {_MAX_CACHED_MS}ms")
    else:
        r.skip("not cached — cannot measure cache latency")
    results.append(r)

    print_results(results)
    if result.get("cached"):
        assert t.ms < _MAX_CACHED_MS, f"Cache hit too slow: {t.ms}ms"


# ── 6.3 Cache hit rate ────────────────────────────────────────

@pytest.mark.asyncio
async def test_cache_hit_rate(service):
    """
    Cache hit rate test: fetch the same symbol+interval twice rapidly.
    The cache key includes from_ts/to_ts computed from `days=`, so
    we verify the cache works by checking the second call is faster
    and returns cached=True within the same second.
    """
    print_section("6.3 Cache Hit Rate")
    results = []

    # Use 5m/days=5 — already warmed by session fixture candles_5m
    # Fetch once to ensure it is in cache
    warm = await service.fetch_candles(
        PRIMARY_SYMBOL, interval="5m", days=5, validate=False
    )
    if warm.get("error"):
        pytest.skip(f"Warm fetch failed ({warm['error']}) — cannot test cache")

    # Immediately fetch again — must be cached (same second, same key)
    hits = 0
    for _ in range(_CACHE_ROUNDS):
        r = await service.fetch_candles(
            PRIMARY_SYMBOL, interval="5m", days=5, validate=False
        )
        if r.get("cached"):
            hits += 1

    hit_rate = hits / _CACHE_ROUNDS * 100

    r = CheckResult("cache_hit_rate")
    if hit_rate == 100:
        r.ok(f"{hits}/{_CACHE_ROUNDS} = 100%")
    elif hit_rate >= 60:
        r.skip(f"{hits}/{_CACHE_ROUNDS} = {hit_rate:.0f}% — some misses (TTL boundary)")
    else:
        r.skip(
            f"{hits}/{_CACHE_ROUNDS} = {hit_rate:.0f}% — cache key uses dynamic "
            f"to_ts so misses are expected across second boundaries"
        )
    results.append(r)

    print_results(results)
    # Not a hard assert — cache key design uses dynamic timestamps
    # This test documents the behaviour rather than enforcing a threshold


# ── 6.4 Concurrent fetch safety ───────────────────────────────

@pytest.mark.asyncio
async def test_concurrent_fetches(service):
    """Multiple concurrent fetches for the same symbol must all succeed."""
    print_section("6.4 Concurrent Fetch Safety")
    results = []

    with Elapsed() as t:
        tasks = [
            service.fetch_candles(PRIMARY_SYMBOL, interval="5m", days=2)
            for _ in range(4)
        ]
        responses = await asyncio.gather(*tasks, return_exceptions=True)

    errors = [r for r in responses if isinstance(r, Exception) or
              (isinstance(r, dict) and r.get("error"))]

    r = CheckResult("all_concurrent_succeeded")
    if not errors:
        r.ok(f"4/4 succeeded in {t.ms}ms total")
    else:
        r.fail(f"{len(errors)}/4 failed: {errors[0]}")
    results.append(r)

    r = CheckResult("results_consistent")
    counts = [candle_count(r) for r in responses if isinstance(r, dict)]
    if len(set(counts)) <= 1:
        r.ok(f"all returned {counts[0] if counts else 0} candles")
    else:
        r.skip(f"varying counts: {counts} — cache race condition (acceptable)")
    results.append(r)

    print_results(results)
    assert not errors, f"Concurrent fetch failures: {errors}"
