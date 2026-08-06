"""
Phase 1.7 + 1.8 — Yahoo Finance Provider
==========================================
Wraps existing Yahoo Finance fetch logic as a MarketDataProvider.
Used as fallback when Angel One is unavailable.
Also the only source for fundamentals (PE, ROE, financials, etc.)
since Angel One has no fundamentals API.
"""
from __future__ import annotations

import logging
import time
from typing import List, Optional, Dict

import httpx

from app.market_data.providers.base import (
    MarketDataProvider, Interval, Candle, Quote,
    CandleResult, ProviderStatus,
)

log = logging.getLogger(__name__)

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}
_YF_BASE = "https://query1.finance.yahoo.com/v8/finance/chart"

# Canonical interval → Yahoo Finance interval string
_INTERVAL_MAP: Dict[Interval, str] = {
    Interval.MIN_1:  "1m",
    Interval.MIN_3:  "2m",
    Interval.MIN_5:  "5m",
    Interval.MIN_10: "5m",
    Interval.MIN_15: "15m",
    Interval.MIN_30: "30m",
    Interval.HOUR_1: "60m",
    Interval.HOUR_4: "60m",   # resampled
    Interval.DAY_1:  "1d",
    Interval.WEEK_1: "1wk",
}

# Max days Yahoo Finance reliably returns per interval
_MAX_DAYS: Dict[Interval, int] = {
    Interval.MIN_1:  7,
    Interval.MIN_3:  60,
    Interval.MIN_5:  60,
    Interval.MIN_10: 60,
    Interval.MIN_15: 60,
    Interval.MIN_30: 60,
    Interval.HOUR_1: 730,
    Interval.HOUR_4: 730,
    Interval.DAY_1:  1825,
    Interval.WEEK_1: 1825,
}

# Days → Yahoo range string (used when we need a simple range query)
def _days_to_yf_range(days: int) -> str:
    if days <= 1:   return "1d"
    if days <= 5:   return "5d"
    if days <= 30:  return "1mo"
    if days <= 90:  return "3mo"
    if days <= 180: return "6mo"
    if days <= 365: return "1y"
    if days <= 730: return "2y"
    if days <= 1825: return "5y"
    return "max"


class YahooFinanceProvider(MarketDataProvider):
    """
    Yahoo Finance implementation of MarketDataProvider.
    Fallback provider — priority 90 (tried last).
    """

    name     = "yahoo_finance"
    priority = 90

    def __init__(self):
        self._available = True   # always available (no auth needed)

    # ── Lifecycle ─────────────────────────────────────────────

    async def initialise(self) -> bool:
        # No auth needed — just verify network
        try:
            async with httpx.AsyncClient(timeout=5) as c:
                r = await c.get("https://query1.finance.yahoo.com", headers=_HEADERS)
                self._available = r.status_code < 500
        except Exception:
            self._available = True   # assume available, fail on actual request
        return True

    async def is_available(self) -> bool:
        return self._available

    async def get_status(self) -> ProviderStatus:
        return ProviderStatus(
            name      = self.name,
            available = self._available,
            logged_in = True,   # no auth concept
        )

    # ── Instrument resolution ─────────────────────────────────

    def resolve_symbol(self, symbol: str) -> Optional[str]:
        """Convert canonical symbol to Yahoo Finance format."""
        s = symbol.strip().upper()
        # Already has suffix
        if "." in s:
            return s
        # Known index symbols
        _idx = {"^NSEI": "^NSEI", "NIFTY": "^NSEI", "NIFTY 50": "^NSEI",
                "SENSEX": "^BSESN", "^BSESN": "^BSESN",
                "BANKNIFTY": "^NSEBANK", "NIFTY BANK": "^NSEBANK"}
        if s in _idx:
            return _idx[s]
        return s + ".NS"   # default to NSE

    def supported_intervals(self) -> List[Interval]:
        return list(_INTERVAL_MAP.keys())

    def max_days_per_request(self, interval: Interval) -> int:
        return _MAX_DAYS.get(interval, 60)

    # ── Historical candles ────────────────────────────────────

    async def fetch_candles(
        self,
        symbol:   str,
        interval: Interval,
        from_ts:  int,
        to_ts:    int,
    ) -> CandleResult:
        empty = CandleResult(
            symbol=symbol, interval=interval, candles=[],
            source=self.name, from_ts=from_ts, to_ts=to_ts,
        )

        yf_sym      = self.resolve_symbol(symbol)
        yf_interval = _INTERVAL_MAP.get(interval, "5m")
        days        = max(1, int((to_ts - from_ts) / (24 * 3600 * 1000)))
        yf_range    = _days_to_yf_range(days)

        url = f"{_YF_BASE}/{yf_sym}?interval={yf_interval}&range={yf_range}"

        try:
            async with httpx.AsyncClient(headers=_HEADERS, timeout=15) as client:
                r = await client.get(url)
                if r.status_code != 200:
                    empty.error = f"Yahoo HTTP {r.status_code}"
                    return empty

                result = r.json().get("chart", {}).get("result", [])
                if not result:
                    empty.error = "Yahoo returned no data"
                    return empty

                ts_list = result[0].get("timestamp", [])
                q       = result[0].get("indicators", {}).get("quote", [{}])[0]
                opens   = q.get("open",   [])
                highs   = q.get("high",   [])
                lows    = q.get("low",    [])
                closes  = q.get("close",  [])
                volumes = q.get("volume", [])

                candles = []
                for i, ts in enumerate(ts_list):
                    try:
                        c = closes[i]
                        if c is None:
                            continue
                        candles.append(Candle(
                            t=int(ts) * 1000,
                            o=float(opens[i]   or c),
                            h=float(highs[i]   or c),
                            l=float(lows[i]    or c),
                            c=float(c),
                            v=int(volumes[i]   or 0),
                        ))
                    except (IndexError, TypeError, ValueError):
                        continue

                # Filter to requested range
                candles = [c for c in candles if from_ts <= c.t <= to_ts]

                # Resample 1h → 4h if needed
                if interval == Interval.HOUR_4 and candles:
                    candles = _resample(candles, 4)

                if not candles:
                    empty.error = "No candles in requested range"
                    return empty

                return CandleResult(
                    symbol   = symbol,
                    interval = interval,
                    candles  = candles,
                    source   = self.name,
                    from_ts  = candles[0].t,
                    to_ts    = candles[-1].t,
                )

        except Exception as e:
            empty.error = str(e)
            log.warning(f"[Yahoo] fetch_candles({symbol}) failed: {e}")
            return empty

    # ── Live quotes ───────────────────────────────────────────

    async def fetch_quote(self, symbol: str) -> Optional[Quote]:
        yf_sym = self.resolve_symbol(symbol)
        url    = f"{_YF_BASE}/{yf_sym}?interval=1m&range=1d"
        try:
            async with httpx.AsyncClient(headers=_HEADERS, timeout=8) as client:
                r = await client.get(url)
                if r.status_code != 200:
                    return None
                result = r.json().get("chart", {}).get("result", [])
                if not result:
                    return None
                meta  = result[0].get("meta", {})
                ltp   = float(meta.get("regularMarketPrice", 0))
                close = float(meta.get("chartPreviousClose") or
                              meta.get("previousClose") or ltp)
                chg   = round(ltp - close, 2)
                chg_p = round((chg / close * 100) if close else 0, 2)

                q_data = result[0].get("indicators", {}).get("quote", [{}])[0]
                vols   = [v for v in q_data.get("volume", []) if v]

                clean = symbol.replace(".NS", "").replace(".BO", "").upper()
                return Quote(
                    symbol     = clean,
                    ltp        = ltp,
                    open       = float(meta.get("regularMarketOpen",    ltp)),
                    high       = float(meta.get("regularMarketDayHigh", ltp)),
                    low        = float(meta.get("regularMarketDayLow",  ltp)),
                    close      = close,
                    change     = chg,
                    change_pct = chg_p,
                    volume     = sum(vols) if vols else 0,
                    timestamp  = self.now_ms(),
                    source     = self.name,
                )
        except Exception as e:
            log.warning(f"[Yahoo] fetch_quote({symbol}) failed: {e}")
            return None

    async def fetch_quotes(self, symbols: List[str]) -> List[Quote]:
        import asyncio
        tasks   = [self.fetch_quote(s) for s in symbols]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        return [r for r in results if isinstance(r, Quote)]

    async def fetch_indices(self) -> List[Quote]:
        index_syms = ["^NSEI", "^BSESN", "^NSEBANK"]
        return await self.fetch_quotes(index_syms)


def _resample(candles: List[Candle], n: int) -> List[Candle]:
    out = []
    for i in range(0, len(candles) - n + 1, n):
        g = candles[i:i + n]
        out.append(Candle(
            t=g[-1].t, o=g[0].o,
            h=max(c.h for c in g), l=min(c.l for c in g),
            c=g[-1].c, v=sum(c.v for c in g),
        ))
    return out
