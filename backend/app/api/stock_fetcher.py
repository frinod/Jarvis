"""stock_fetcher.py — Compatibility shim.

Provides batch quote fetching (get_all_stocks), single quote/index helpers
(fetch_quote, fetch_index), and shared constants (HEADERS, YF_BASE).

fetch_chart has been removed — all callers now use market_data.service.fetch_candles
directly. This file is retained for the above exports only.
"""
from __future__ import annotations
import asyncio
import time
from typing import Dict, List, Optional
import httpx

from app.api.stock_universe import INDICES, UNIVERSE_MAP, NAME_MAP, SECTOR_MAP

# Keep HEADERS exported — stock_data.py imports it
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}
YF_BASE = "https://query1.finance.yahoo.com/v8/finance/chart"

_BATCH_SIZE  = 20
_BATCH_DELAY = 0.3
_CACHE: Dict[str, Dict] = {}
_CACHE_TTL: Dict[str, int] = {
    "nifty50": 60, "nifty100": 120, "midcap": 120,
    "smallcap": 120, "extended": 180, "all": 180,
}
_FETCH_LOCKS: Dict[str, asyncio.Lock] = {}


async def fetch_quote(symbol: str, client: httpx.AsyncClient) -> Optional[Dict]:
    """Fetch a single stock quote."""
    try:
        r = await client.get(f"{YF_BASE}/{symbol}?interval=1m&range=1d", timeout=10.0)
        if r.status_code != 200:
            return None
        result = r.json().get("chart", {}).get("result", [])
        if not result:
            return None
        meta = result[0].get("meta", {})
        price = meta.get("regularMarketPrice", 0)
        prev  = meta.get("chartPreviousClose") or meta.get("previousClose") or price
        # Prefer Yahoo's own change% to avoid stale-cache 0.00% issue
        yf_chg_pct = meta.get("regularMarketChangePercent")
        if yf_chg_pct is not None:
            change_pct = round(yf_chg_pct * 100 if abs(yf_chg_pct) < 1 else yf_chg_pct, 2)
            change = round(price - prev, 2)
        else:
            change = round(price - prev, 2)
            change_pct = round((change / prev * 100) if prev else 0, 2)
        q = result[0].get("indicators", {}).get("quote", [{}])[0]
        highs   = [h for h in q.get("high",   []) if h is not None]
        lows    = [l for l in q.get("low",    []) if l is not None]
        volumes = [v for v in q.get("volume", []) if v is not None]
        return {
            "symbol":       symbol.replace(".NS", ""),
            "full_symbol":  symbol,
            "name":         NAME_MAP.get(symbol, symbol.replace(".NS", "")),
            "sector":       SECTOR_MAP.get(symbol, "Other"),
            "price":        round(price, 2),
            "prev_close":   round(prev, 2),
            "change":       change,
            "change_pct":   change_pct,
            "day_high":     round(max(highs), 2) if highs else price,
            "day_low":      round(min(lows),  2) if lows  else price,
            "volume":       sum(volumes) if volumes else 0,
            "currency":     meta.get("currency", "INR"),
            "market_state": meta.get("marketState", "CLOSED"),
        }
    except Exception:
        return None


async def fetch_index(symbol: str, name: str, client: httpx.AsyncClient) -> Optional[Dict]:
    """Fetch a single index quote with sparkline."""
    try:
        r = await client.get(f"{YF_BASE}/{symbol}?interval=1m&range=1d", timeout=10.0)
        if r.status_code != 200:
            return None
        result = r.json().get("chart", {}).get("result", [])
        if not result:
            return None
        meta   = result[0].get("meta", {})
        price  = meta.get("regularMarketPrice", 0)
        prev   = meta.get("chartPreviousClose", price)
        change = price - prev
        closes = result[0].get("indicators", {}).get("quote", [{}])[0].get("close", [])
        return {
            "name":       name,
            "symbol":     symbol,
            "price":      round(price, 2),
            "prev_close": round(prev, 2),
            "change":     round(change, 2),
            "change_pct": round((change / prev * 100) if prev else 0, 2),
            "sparkline":  [round(c, 2) for c in closes if c is not None][-30:],
        }
    except Exception:
        return None


async def _fetch_batch(symbols: List[str], client: httpx.AsyncClient) -> List[Dict]:
    """Fetch one batch of symbols concurrently."""
    results = await asyncio.gather(*[fetch_quote(s, client) for s in symbols], return_exceptions=True)
    return [r for r in results if r and not isinstance(r, Exception)]


async def get_all_stocks(universe: str = "nifty50") -> Dict:
    """
    Fetch all stocks for the requested universe.
    Results are cached per universe (TTL: 60–180s) to avoid hammering Yahoo Finance.
    """
    # Ensure a lock exists for this universe
    if universe not in _FETCH_LOCKS:
        _FETCH_LOCKS[universe] = asyncio.Lock()

    # Fast path — return cached data if still fresh
    cached = _CACHE.get(universe)
    ttl = _CACHE_TTL.get(universe, 120)
    if cached and (time.time() - cached["ts"]) < ttl:
        return cached["data"]

    # Slow path — only one coroutine fetches at a time per universe
    async with _FETCH_LOCKS[universe]:
        # Re-check after acquiring lock (another coroutine may have just fetched)
        cached = _CACHE.get(universe)
        if cached and (time.time() - cached["ts"]) < ttl:
            return cached["data"]

        symbols = UNIVERSE_MAP.get(universe, UNIVERSE_MAP["nifty50"])

        async with httpx.AsyncClient(headers=HEADERS) as client:
            index_results = await asyncio.gather(
                *[fetch_index(sym, name, client) for name, sym in INDICES.items()],
                return_exceptions=True,
            )
            indices = [r for r in index_results if r and not isinstance(r, Exception)]

            stocks: List[Dict] = []
            for i in range(0, len(symbols), _BATCH_SIZE):
                batch = symbols[i: i + _BATCH_SIZE]
                batch_results = await _fetch_batch(batch, client)
                stocks.extend(batch_results)
                if i + _BATCH_SIZE < len(symbols):
                    await asyncio.sleep(_BATCH_DELAY)

        stocks.sort(key=lambda x: x.get("change_pct", 0), reverse=True)
        result = {
            "indices":  indices,
            "stocks":   stocks,
            "universe": universe,
            "total":    len(stocks),
        }
        _CACHE[universe] = {"data": result, "ts": time.time()}
        return result
