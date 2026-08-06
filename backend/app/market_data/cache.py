"""
Phase 1.10 — Cache Layer
==========================
TTL-based in-memory cache for market data.
Different TTLs per data type:
  - Live quotes:      5s  (near-real-time)
  - Intraday candles: 60s (1-min refresh)
  - Daily candles:    300s (5-min refresh)
  - Fundamentals:     86400s (24h)

WebSocket ticks can invalidate quote cache entries directly.
"""
from __future__ import annotations

import time
import threading
from typing import Any, Dict, Optional, Tuple

# ── TTL constants (seconds) ───────────────────────────────────
TTL_QUOTE_LIVE    = 5       # live LTP from WebSocket/REST
TTL_QUOTE_POLL    = 15      # polled quote (no WebSocket)
TTL_CANDLE_1M     = 60
TTL_CANDLE_5M     = 60
TTL_CANDLE_15M    = 120
TTL_CANDLE_1H     = 300
TTL_CANDLE_1D     = 300
TTL_FUNDAMENTALS  = 86400   # 24 hours
TTL_INSTRUMENTS   = 86400   # 24 hours
TTL_REGIME        = 300     # 5 minutes

_CANDLE_TTL = {
    "1m": TTL_CANDLE_1M,
    "3m": TTL_CANDLE_1M,
    "5m": TTL_CANDLE_5M,
    "10m": TTL_CANDLE_5M,
    "15m": TTL_CANDLE_15M,
    "30m": TTL_CANDLE_15M,
    "1h": TTL_CANDLE_1H,
    "4h": TTL_CANDLE_1H,
    "1d": TTL_CANDLE_1D,
    "1w": TTL_CANDLE_1D,
}


class MarketCache:
    """
    Thread-safe TTL cache.
    Keys are strings; values are (data, expiry_timestamp) tuples.
    """

    def __init__(self):
        self._store: Dict[str, Tuple[Any, float]] = {}
        self._lock  = threading.Lock()

    def get(self, key: str) -> Optional[Any]:
        with self._lock:
            entry = self._store.get(key)
            if entry is None:
                return None
            data, expiry = entry
            if time.time() > expiry:
                del self._store[key]
                return None
            return data

    def set(self, key: str, value: Any, ttl: float):
        with self._lock:
            self._store[key] = (value, time.time() + ttl)

    def invalidate(self, key: str):
        with self._lock:
            self._store.pop(key, None)

    def invalidate_prefix(self, prefix: str):
        """Remove all keys starting with prefix."""
        with self._lock:
            keys = [k for k in self._store if k.startswith(prefix)]
            for k in keys:
                del self._store[k]

    def size(self) -> int:
        with self._lock:
            return len(self._store)

    def purge_expired(self):
        """Remove all expired entries (call periodically)."""
        now = time.time()
        with self._lock:
            expired = [k for k, (_, exp) in self._store.items() if now > exp]
            for k in expired:
                del self._store[k]

    # ── Typed helpers ─────────────────────────────────────────

    def get_candles(self, symbol: str, interval: str, from_ts: int, to_ts: int):
        key = f"candles:{symbol}:{interval}:{from_ts}:{to_ts}"
        return self.get(key)

    def set_candles(self, symbol: str, interval: str, from_ts: int, to_ts: int, data: Any):
        key = f"candles:{symbol}:{interval}:{from_ts}:{to_ts}"
        ttl = _CANDLE_TTL.get(interval, TTL_CANDLE_5M)
        self.set(key, data, ttl)

    def get_quote(self, symbol: str):
        return self.get(f"quote:{symbol}")

    def set_quote(self, symbol: str, data: Any, live: bool = False):
        ttl = TTL_QUOTE_LIVE if live else TTL_QUOTE_POLL
        self.set(f"quote:{symbol}", data, ttl)

    def update_quote_from_tick(self, symbol: str, tick: Dict):
        """Called by WebSocket feed to update quote cache with live tick."""
        self.set(f"quote:{symbol}", tick, TTL_QUOTE_LIVE)

    def get_fundamentals(self, symbol: str):
        return self.get(f"fundamentals:{symbol}")

    def set_fundamentals(self, symbol: str, data: Any):
        self.set(f"fundamentals:{symbol}", data, TTL_FUNDAMENTALS)

    def get_regime(self):
        return self.get("market_regime")

    def set_regime(self, data: Any):
        self.set("market_regime", data, TTL_REGIME)


# ── Module-level singleton ────────────────────────────────────
_cache = MarketCache()


def get_cache() -> MarketCache:
    return _cache
