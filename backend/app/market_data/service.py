"""
Phase 1.12 — Unified Market Data API
======================================
This is the ONLY file any other module should import from.
All provider details, caching, validation, and fallback logic
are hidden behind these functions.

Usage:
    from app.market_data.service import (
        fetch_candles, fetch_quote, fetch_quotes,
        fetch_indices, fetch_fundamentals,
        get_provider_status, initialise,
    )

No module should ever import from:
    - stock_fetcher.py  (legacy — now a shim)
    - angel_feed.py     (internal)
    - providers/*.py    (internal)
"""
from __future__ import annotations

import datetime
import logging
import time
from typing import List, Optional, Dict, Any

from app.market_data.providers.base import Interval, CandleResult, Quote
from app.market_data.providers.manager import get_manager
from app.market_data.cache import get_cache
from app.market_data.validator import validate_candles, candles_to_legacy_dicts

log = logging.getLogger(__name__)

# ── Startup ───────────────────────────────────────────────────

async def initialise():
    """
    Initialise all providers. Call once at application startup.
    Safe to call multiple times.
    """
    from app.market_data import instruments
    mgr = get_manager()
    await mgr.initialise_all()
    await instruments.ensure_loaded()
    log.info(f"[MarketData] Initialised. Providers: {mgr.provider_names}")


# ── Candle fetching ───────────────────────────────────────────

async def fetch_candles(
    symbol:   str,
    interval: str = "5m",
    days:     int = 5,
    from_ts:  Optional[int] = None,
    to_ts:    Optional[int] = None,
    validate: bool = True,
) -> Dict[str, Any]:
    """
    Fetch OHLCV candles. Returns dict compatible with existing modules.

    Args:
        symbol:   e.g. "RELIANCE", "RELIANCE.NS", "TCS"
        interval: "1m","3m","5m","10m","15m","30m","1h","4h","1d","1w"
        days:     how many calendar days of history (used if from_ts not given)
        from_ts:  Unix ms UTC start (overrides days)
        to_ts:    Unix ms UTC end (defaults to now)
        validate: run data quality validation (default True)

    Returns:
        {
            "symbol":   str,
            "candles":  [{"t","o","h","l","c","v"}, ...],
            "source":   str,   # which provider served this
            "cached":   bool,
            "quality":  int,   # 0-100 quality score
            "warnings": [...],
        }
        On error: {"error": str, "symbol": str}
    """
    iv = _parse_interval(interval)
    if iv is None:
        return {"error": f"Unknown interval: {interval}", "symbol": symbol}

    now_ms = int(time.time() * 1000)
    if to_ts is None:
        to_ts = now_ms
    if from_ts is None:
        from_ts = to_ts - days * 24 * 3600 * 1000

    # Check cache
    cache = get_cache()
    cached = cache.get_candles(symbol, interval, from_ts, to_ts)
    if cached:
        return {**cached, "cached": True}

    # Fetch from provider
    mgr    = get_manager()
    result = await mgr.fetch_candles(symbol, iv, from_ts, to_ts)

    if not result.ok:
        return {"error": result.error or "fetch_failed", "symbol": symbol}

    # Validate
    quality_score = 100
    warnings: List[str] = []
    candles = result.candles

    if validate:
        candles, report = validate_candles(candles)
        quality_score   = report["quality_score"]
        warnings        = report["warnings"]
        if not report["usable"]:
            return {
                "error":    "insufficient_clean_data",
                "symbol":   symbol,
                "quality":  quality_score,
                "warnings": warnings,
            }

    out = {
        "symbol":   symbol,
        "candles":  candles_to_legacy_dicts(candles),
        "source":   result.source,
        "cached":   False,
        "quality":  quality_score,
        "warnings": warnings,
    }

    # Store in cache
    cache.set_candles(symbol, interval, from_ts, to_ts, out)
    return out


# ── Quote fetching ────────────────────────────────────────────

async def fetch_quote(symbol: str) -> Optional[Dict[str, Any]]:
    """
    Fetch a single live quote.
    Returns dict with price/change/volume or None on failure.
    """
    cache = get_cache()

    # Check WebSocket tick cache first (freshest data)
    cached = cache.get_quote(symbol)
    if cached:
        return cached

    mgr   = get_manager()
    quote = await mgr.fetch_quote(symbol)
    if not quote:
        return None

    d = quote.to_dict()
    # Map to legacy field names existing modules expect
    d["price"]      = quote.ltp
    d["change_pct"] = quote.change_pct
    d["prev_close"] = quote.close
    d["day_high"]   = quote.high
    d["day_low"]    = quote.low

    cache.set_quote(symbol, d, live=False)
    return d


async def fetch_quotes(symbols: List[str]) -> List[Dict[str, Any]]:
    """Fetch live quotes for multiple symbols."""
    mgr    = get_manager()
    quotes = await mgr.fetch_quotes(symbols)
    result = []
    cache  = get_cache()
    for q in quotes:
        d = q.to_dict()
        d["price"]      = q.ltp
        d["change_pct"] = q.change_pct
        d["prev_close"] = q.close
        d["day_high"]   = q.high
        d["day_low"]    = q.low
        cache.set_quote(q.symbol, d, live=False)
        result.append(d)
    return result


async def fetch_indices() -> List[Dict[str, Any]]:
    """Fetch major index quotes (NIFTY 50, SENSEX, BANK NIFTY)."""
    mgr     = get_manager()
    indices = await mgr.fetch_indices()
    return [
        {
            "name":       _INDEX_NAMES.get(q.symbol, q.symbol),
            "symbol":     q.symbol,
            "price":      q.ltp,
            "prev_close": q.close,
            "change":     q.change,
            "change_pct": q.change_pct,
            "source":     q.source,
        }
        for q in indices
    ]


# ── Fundamentals (Yahoo Finance only — Angel One has no equivalent) ──

async def fetch_fundamentals(symbol: str) -> Dict[str, Any]:
    """
    Fetch company fundamentals (PE, ROE, financials, etc.).
    Always uses Yahoo Finance — Angel One has no fundamentals API.
    Cached for 24 hours.
    """
    cache  = get_cache()
    cached = cache.get_fundamentals(symbol)
    if cached:
        return cached

    # Delegate to existing stock_data module (Yahoo Finance v10)
    try:
        from app.api.stock_data import fetch_fundamentals as _yf_fundamentals
        data = await _yf_fundamentals(symbol)
        if not data.get("error"):
            cache.set_fundamentals(symbol, data)
        return data
    except Exception as e:
        return {"error": str(e), "symbol": symbol}


# ── Provider status ───────────────────────────────────────────

async def get_provider_status() -> Dict[str, Any]:
    """Return health status of all registered providers."""
    mgr      = get_manager()
    statuses = await mgr.get_all_status()
    cache    = get_cache()
    return {
        "providers":    statuses,
        "primary":      mgr.primary.name if mgr.primary else None,
        "cache_size":   cache.size(),
    }


# ── WebSocket tick integration ────────────────────────────────

def update_from_tick(symbol: str, tick: Dict):
    """
    Called by the Angel One WebSocket feed when a new tick arrives.
    Updates the quote cache so all modules see live prices immediately.
    """
    cache = get_cache()
    # Normalise tick to standard quote format
    d = {
        "symbol":     symbol,
        "price":      tick.get("price", 0),
        "ltp":        tick.get("price", 0),
        "change":     tick.get("change", 0),
        "change_pct": tick.get("change_pct", 0),
        "prev_close": tick.get("prev_close", 0),
        "day_high":   tick.get("day_high", 0),
        "day_low":    tick.get("day_low", 0),
        "volume":     tick.get("volume", 0),
        "source":     "angel_one_ws",
        "timestamp":  int(time.time() * 1000),
    }
    cache.update_quote_from_tick(symbol, d)


# ── Helpers ───────────────────────────────────────────────────

_INTERVAL_ALIASES: Dict[str, Interval] = {
    "1m":  Interval.MIN_1,  "1min":  Interval.MIN_1,
    "3m":  Interval.MIN_3,  "3min":  Interval.MIN_3,
    "5m":  Interval.MIN_5,  "5min":  Interval.MIN_5,
    "10m": Interval.MIN_10, "10min": Interval.MIN_10,
    "15m": Interval.MIN_15, "15min": Interval.MIN_15,
    "30m": Interval.MIN_30, "30min": Interval.MIN_30,
    "1h":  Interval.HOUR_1, "60m":   Interval.HOUR_1,
    "4h":  Interval.HOUR_4,
    "1d":  Interval.DAY_1,  "daily": Interval.DAY_1,
    "1w":  Interval.WEEK_1, "weekly": Interval.WEEK_1,
}

_INDEX_NAMES = {
    "99926000": "NIFTY 50",
    "^NSEI":    "NIFTY 50",
    "99919000": "SENSEX",
    "^BSESN":   "SENSEX",
    "99926009": "BANK NIFTY",
    "^NSEBANK": "BANK NIFTY",
}


def _parse_interval(s: str) -> Optional[Interval]:
    return _INTERVAL_ALIASES.get(s.lower())
