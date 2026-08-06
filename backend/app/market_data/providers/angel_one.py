"""
Phase 1.4 + 1.5 — Angel One Provider
======================================
Implements MarketDataProvider using Angel One SmartAPI.
- Historical candles with automatic pagination
- Live quotes via ltpData
- Batch quotes via concurrent ltpData calls
- Auto re-login on session failure
"""
from __future__ import annotations

import asyncio
import concurrent.futures
import datetime
import logging
import time
from typing import List, Optional, Dict

_executor = concurrent.futures.ThreadPoolExecutor(max_workers=4)

from app.market_data.providers.base import (
    MarketDataProvider, Interval, Candle, Quote,
    CandleResult, ProviderStatus,
)
from app.market_data.providers.angel_auth import get_session
from app.market_data import instruments

log = logging.getLogger(__name__)

# ── Interval mapping: Interval → Angel One string ─────────────
_INTERVAL_MAP: Dict[Interval, str] = {
    Interval.MIN_1:  "ONE_MINUTE",
    Interval.MIN_3:  "THREE_MINUTE",
    Interval.MIN_5:  "FIVE_MINUTE",
    Interval.MIN_10: "TEN_MINUTE",
    Interval.MIN_15: "FIFTEEN_MINUTE",
    Interval.MIN_30: "THIRTY_MINUTE",
    Interval.HOUR_1: "ONE_HOUR",
    Interval.DAY_1:  "ONE_DAY",
}

# ── Max days per request (Angel One documented limits) ─────────
_MAX_DAYS: Dict[Interval, int] = {
    Interval.MIN_1:  30,
    Interval.MIN_3:  60,
    Interval.MIN_5:  100,
    Interval.MIN_10: 100,
    Interval.MIN_15: 200,
    Interval.MIN_30: 200,
    Interval.HOUR_1: 400,
    Interval.DAY_1:  2000,
}


class AngelOneProvider(MarketDataProvider):
    """
    Angel One SmartAPI implementation of MarketDataProvider.
    Primary data source — priority 10 (tried first).
    """

    name     = "angel_one"
    priority = 10

    def __init__(self):
        self._session = get_session()

    # ── Lifecycle ─────────────────────────────────────────────

    async def initialise(self) -> bool:
        ok = await self._session.ensure_logged_in()
        if ok:
            await instruments.ensure_loaded()
            log.info("[AngelOne] Provider initialised")
        return ok

    async def is_available(self) -> bool:
        return self._session.is_logged_in

    async def get_status(self) -> ProviderStatus:
        s = self._session.get_status_dict()
        return ProviderStatus(
            name       = self.name,
            available  = s["logged_in"],
            logged_in  = s["logged_in"],
            last_error = s["last_error"],
        )

    # ── Instrument resolution ─────────────────────────────────

    def resolve_symbol(self, symbol: str) -> Optional[str]:
        result = instruments.resolve(symbol)
        return result[0] if result else None

    def supported_intervals(self) -> List[Interval]:
        return list(_INTERVAL_MAP.keys())

    def max_days_per_request(self, interval: Interval) -> int:
        return _MAX_DAYS.get(interval, 30)

    # ── Historical candles ────────────────────────────────────

    async def fetch_candles(
        self,
        symbol:   str,
        interval: Interval,
        from_ts:  int,
        to_ts:    int,
    ) -> CandleResult:
        """
        Fetch candles with automatic pagination.
        Splits large date ranges into chunks within Angel One limits,
        fetches each chunk, merges and deduplicates results.
        """
        empty = CandleResult(
            symbol=symbol, interval=interval, candles=[],
            source=self.name, from_ts=from_ts, to_ts=to_ts,
        )

        # Ensure session is valid
        if not await self._session.ensure_logged_in():
            empty.error = "Angel One session unavailable"
            return empty

        # Resolve symbol to token
        resolved = instruments.resolve(symbol)
        if not resolved:
            empty.error = f"Symbol not found in instrument master: {symbol}"
            return empty
        token, exchange = resolved

        # Angel One only supports these intervals natively
        if interval == Interval.HOUR_4:
            # 4h is synthesised from 1h — fetch 1h and resample
            result_1h = await self.fetch_candles(symbol, Interval.HOUR_1, from_ts, to_ts)
            if not result_1h.ok:
                return result_1h
            resampled = _resample_candles(result_1h.candles, 4)
            return CandleResult(
                symbol=symbol, interval=interval, candles=resampled,
                source=self.name, from_ts=from_ts, to_ts=to_ts,
            )

        if interval == Interval.WEEK_1:
            result_1d = await self.fetch_candles(symbol, Interval.DAY_1, from_ts, to_ts)
            if not result_1d.ok:
                return result_1d
            resampled = _resample_candles(result_1d.candles, 5)
            return CandleResult(
                symbol=symbol, interval=interval, candles=resampled,
                source=self.name, from_ts=from_ts, to_ts=to_ts,
            )

        angel_interval = _INTERVAL_MAP.get(interval)
        if not angel_interval:
            empty.error = f"Interval {interval} not supported by Angel One"
            return empty

        # ── Pagination ────────────────────────────────────────
        max_days  = self.max_days_per_request(interval)
        chunk_ms  = max_days * 24 * 3600 * 1000
        all_candles: List[Candle] = []
        chunk_start = from_ts

        while chunk_start < to_ts:
            chunk_end = min(chunk_start + chunk_ms, to_ts)
            chunk = await self._fetch_chunk(
                token, exchange, angel_interval, chunk_start, chunk_end
            )
            if chunk:
                all_candles.extend(chunk)
            elif not all_candles:
                # First chunk failed — propagate error
                empty.error = f"No data returned for {symbol} [{interval}]"
                return empty
            chunk_start = chunk_end + 1
            if chunk_start < to_ts:
                await asyncio.sleep(0.15)   # rate-limit guard

        # Deduplicate and sort
        seen: set = set()
        unique = []
        for c in sorted(all_candles, key=lambda x: x.t):
            if c.t not in seen:
                seen.add(c.t)
                unique.append(c)

        if not unique:
            empty.error = f"Empty candle response for {symbol}"
            return empty

        return CandleResult(
            symbol   = symbol,
            interval = interval,
            candles  = unique,
            source   = self.name,
            from_ts  = unique[0].t,
            to_ts    = unique[-1].t,
        )

    async def _fetch_chunk(
        self,
        token:    str,
        exchange: str,
        interval: str,
        from_ms:  int,
        to_ms:    int,
    ) -> List[Candle]:
        """Fetch a single date-range chunk from Angel One getCandleData."""
        from_str = self.ms_to_ist_str(from_ms)
        to_str   = self.ms_to_ist_str(to_ms)

        params = {
            "exchange":    exchange,
            "symboltoken": token,
            "interval":    interval,
            "fromdate":    from_str,
            "todate":      to_str,
        }

        for attempt in range(3):
            try:
                loop = asyncio.get_event_loop()
                resp = await loop.run_in_executor(
                    _executor,
                    lambda p=params: self._session.smart_api.getCandleData(p)
                )
                if not resp or resp.get("status") is not True:
                    msg = resp.get("message", "no message") if resp else "null response"
                    # Token expired mid-session
                    if "token" in msg.lower() or "unauthori" in msg.lower():
                        await self._session.invalidate()
                        if await self._session.ensure_logged_in():
                            continue
                    log.warning(f"[AngelOne] getCandleData failed: {msg}")
                    return []

                raw = resp.get("data", [])
                if not isinstance(raw, list):
                    return []

                candles = []
                for row in raw:
                    try:
                        # Angel One format: [timestamp_iso, open, high, low, close, volume]
                        ts_ms = _iso_to_ms(row[0])
                        candles.append(Candle(
                            t=ts_ms,
                            o=float(row[1]),
                            h=float(row[2]),
                            l=float(row[3]),
                            c=float(row[4]),
                            v=int(row[5]),
                        ))
                    except (IndexError, ValueError, TypeError):
                        continue
                return candles

            except Exception as e:
                log.warning(f"[AngelOne] Chunk fetch attempt {attempt+1} failed: {e}")
                if attempt < 2:
                    await asyncio.sleep(0.5 * (attempt + 1))

        return []

    # ── Live quotes ───────────────────────────────────────────

    async def fetch_quote(self, symbol: str) -> Optional[Quote]:
        if not await self._session.ensure_logged_in():
            return None

        resolved = instruments.resolve(symbol)
        if not resolved:
            return None
        token, exchange = resolved

        # Derive trading symbol (e.g. "RELIANCE-EQ")
        clean = symbol.replace(".NS", "").replace(".BO", "").upper()
        trading_sym = clean + "-EQ" if exchange == "NSE" else clean

        try:
            loop = asyncio.get_event_loop()
            resp = await loop.run_in_executor(
                _executor,
                lambda: self._session.smart_api.ltpData(
                    exchange, trading_sym, token
                )
            )
            if not resp or resp.get("status") is not True:
                return None

            d = resp.get("data", {})
            ltp   = float(d.get("ltp",   0))
            close = float(d.get("close", 0))
            chg   = round(ltp - close, 2)
            chg_p = round((chg / close * 100) if close else 0, 2)

            return Quote(
                symbol     = clean,
                ltp        = ltp,
                open       = float(d.get("open",  0)),
                high       = float(d.get("high",  0)),
                low        = float(d.get("low",   0)),
                close      = close,
                change     = chg,
                change_pct = chg_p,
                volume     = 0,   # ltpData doesn't return volume
                timestamp  = self.now_ms(),
                source     = self.name,
            )
        except Exception as e:
            log.warning(f"[AngelOne] fetch_quote({symbol}) failed: {e}")
            return None

    async def fetch_quotes(self, symbols: List[str]) -> List[Quote]:
        """Fetch multiple quotes concurrently (max 10 at a time)."""
        results = []
        sem = asyncio.Semaphore(10)

        async def _one(sym):
            async with sem:
                q = await self.fetch_quote(sym)
                if q:
                    results.append(q)

        await asyncio.gather(*[_one(s) for s in symbols], return_exceptions=True)
        return results

    # ── Indices ───────────────────────────────────────────────

    async def fetch_indices(self) -> List[Quote]:
        index_symbols = ["NIFTY 50", "SENSEX", "BANKNIFTY"]
        return await self.fetch_quotes(index_symbols)


# ── Helpers ───────────────────────────────────────────────────

def _iso_to_ms(ts_str: str) -> int:
    """
    Convert Angel One ISO timestamp to Unix ms UTC.
    Angel One returns: "2026-08-06T09:15:00+05:30"
    """
    try:
        # Remove timezone offset and parse as IST
        ts_clean = ts_str[:19]   # "2026-08-06T09:15:00"
        dt_ist = datetime.datetime.strptime(ts_clean, "%Y-%m-%dT%H:%M:%S")
        dt_utc = dt_ist - datetime.timedelta(hours=5, minutes=30)
        return int(dt_utc.timestamp() * 1000)
    except Exception:
        return 0


def _resample_candles(candles: List[Candle], n: int) -> List[Candle]:
    """Resample candles into n-bar aggregates (e.g. 1h → 4h)."""
    resampled = []
    for i in range(0, len(candles) - n + 1, n):
        group = candles[i:i + n]
        resampled.append(Candle(
            t=group[-1].t,
            o=group[0].o,
            h=max(c.h for c in group),
            l=min(c.l for c in group),
            c=group[-1].c,
            v=sum(c.v for c in group),
        ))
    return resampled
