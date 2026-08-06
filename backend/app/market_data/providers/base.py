"""
Phase 1.1 — Provider Base Interface
====================================
Abstract contract every market data provider must implement.
No provider-specific logic lives here — only the interface definition
and shared canonical data types.

All providers (Angel One, Yahoo Finance, Upstox, Kite, etc.) must
subclass MarketDataProvider and implement every abstract method.
The rest of the application only ever sees this interface.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List, Optional, Dict, Any
from enum import Enum
import datetime
import time


# ── Canonical interval enum ───────────────────────────────────
# Provider implementations map these to their own interval strings.
# Callers always use Interval.* — never provider-specific strings.

class Interval(str, Enum):
    MIN_1  = "1m"
    MIN_3  = "3m"
    MIN_5  = "5m"
    MIN_10 = "10m"
    MIN_15 = "15m"
    MIN_30 = "30m"
    HOUR_1 = "1h"
    HOUR_4 = "4h"   # synthesised by resampling 1h candles
    DAY_1  = "1d"
    WEEK_1 = "1w"


# ── Canonical data types ──────────────────────────────────────

@dataclass
class Candle:
    """Single OHLCV candle. Timestamp is Unix milliseconds UTC."""
    t: int        # Unix timestamp milliseconds UTC
    o: float      # open
    h: float      # high
    l: float      # low
    c: float      # close
    v: int        # volume

    def to_dict(self) -> Dict[str, Any]:
        return {"t": self.t, "o": self.o, "h": self.h,
                "l": self.l, "c": self.c, "v": self.v}


@dataclass
class Quote:
    """Live market quote for a single symbol."""
    symbol:     str
    ltp:        float          # last traded price
    open:       float
    high:       float
    low:        float
    close:      float          # previous close
    change:     float          # ltp - close
    change_pct: float          # (change / close) * 100
    volume:     int
    timestamp:  int            # Unix ms UTC
    source:     str = ""       # which provider supplied this

    def to_dict(self) -> Dict[str, Any]:
        return {
            "symbol": self.symbol, "ltp": self.ltp,
            "open": self.open, "high": self.high, "low": self.low,
            "close": self.close, "change": self.change,
            "change_pct": self.change_pct, "volume": self.volume,
            "timestamp": self.timestamp, "source": self.source,
        }


@dataclass
class CandleResult:
    """Return type for fetch_candles()."""
    symbol:   str
    interval: Interval
    candles:  List[Candle]
    source:   str              # provider name that supplied data
    from_ts:  int              # actual start timestamp in data (ms UTC)
    to_ts:    int              # actual end timestamp in data (ms UTC)
    cached:   bool = False
    error:    Optional[str] = None

    @property
    def ok(self) -> bool:
        return self.error is None and len(self.candles) > 0

    def to_legacy_dict(self) -> Dict[str, Any]:
        """Convert to the dict format existing modules expect from fetch_chart()."""
        return {
            "symbol":  self.symbol,
            "candles": [c.to_dict() for c in self.candles],
            "source":  self.source,
            "cached":  self.cached,
        }


@dataclass
class ProviderStatus:
    """Health status of a provider."""
    name:       str
    available:  bool
    logged_in:  bool
    last_error: Optional[str] = None
    latency_ms: Optional[float] = None


# ── Abstract provider interface ───────────────────────────────

class MarketDataProvider(ABC):
    """
    Abstract base class for all market data providers.

    Every provider (Angel One, Yahoo Finance, Upstox, etc.) must
    implement all abstract methods. The provider manager calls these
    and handles fallback transparently.
    """

    # Human-readable name used in logs and status reports
    name: str = "base"

    # Priority — lower = tried first (Angel One = 10, Yahoo = 90)
    priority: int = 50

    # ── Lifecycle ─────────────────────────────────────────────

    @abstractmethod
    async def initialise(self) -> bool:
        """
        One-time setup (login, token fetch, instrument download, etc.).
        Returns True if provider is ready to serve requests.
        Called once at application startup.
        """

    @abstractmethod
    async def is_available(self) -> bool:
        """
        Quick health check — True if provider can serve requests right now.
        Must be fast — use cached state, no network call.
        """

    @abstractmethod
    async def get_status(self) -> ProviderStatus:
        """Return detailed health/status information for monitoring."""

    # ── Historical candles ────────────────────────────────────

    @abstractmethod
    async def fetch_candles(
        self,
        symbol:   str,
        interval: Interval,
        from_ts:  int,     # Unix ms UTC
        to_ts:    int,     # Unix ms UTC
    ) -> CandleResult:
        """
        Fetch OHLCV candles for symbol between from_ts and to_ts.

        - symbol: canonical symbol e.g. "RELIANCE" or "RELIANCE.NS"
          The provider resolves this to its own token/format internally.
        - interval: canonical Interval enum value
        - from_ts / to_ts: Unix milliseconds UTC

        Must return candles sorted ascending by timestamp.
        Must NOT raise — return CandleResult with error set on failure.
        """

    # ── Live quotes ───────────────────────────────────────────

    @abstractmethod
    async def fetch_quote(self, symbol: str) -> Optional[Quote]:
        """
        Fetch a single live quote.
        Returns None if unavailable — never raises.
        """

    @abstractmethod
    async def fetch_quotes(self, symbols: List[str]) -> List[Quote]:
        """
        Fetch live quotes for multiple symbols in one call.
        Returns only successfully fetched quotes (partial results OK).
        """

    # ── Instrument resolution ─────────────────────────────────

    @abstractmethod
    def resolve_symbol(self, symbol: str) -> Optional[str]:
        """
        Translate a canonical symbol (e.g. "RELIANCE") to the
        provider's internal identifier (e.g. token "2885" for Angel One,
        "RELIANCE.NS" for Yahoo Finance).
        Returns None if symbol is unknown to this provider.
        """

    # ── Capability declarations ───────────────────────────────

    @abstractmethod
    def supported_intervals(self) -> List[Interval]:
        """Return list of intervals this provider supports natively."""

    @abstractmethod
    def max_days_per_request(self, interval: Interval) -> int:
        """
        Maximum calendar days this provider can return per single request
        for the given interval. Used by the pagination layer.
        """

    # ── Optional capabilities (default: not supported) ────────

    async def fetch_indices(self) -> List[Quote]:
        """Fetch major index quotes (NIFTY 50, SENSEX, BANK NIFTY)."""
        return []

    async def fetch_market_depth(self, symbol: str) -> Optional[Dict]:
        """Fetch order book / market depth. Override if supported."""
        return None

    async def fetch_option_chain(self, symbol: str, expiry: str) -> Optional[Dict]:
        """Fetch option chain. Override if supported."""
        return None

    # ── Shared helpers available to all subclasses ────────────

    @staticmethod
    def ms_to_ist_str(ts_ms: int, fmt: str = "%Y-%m-%d %H:%M") -> str:
        """Convert Unix ms UTC to IST datetime string."""
        dt_utc = datetime.datetime.utcfromtimestamp(ts_ms / 1000)
        dt_ist = dt_utc + datetime.timedelta(hours=5, minutes=30)
        return dt_ist.strftime(fmt)

    @staticmethod
    def ist_str_to_ms(dt_str: str, fmt: str = "%Y-%m-%d %H:%M") -> int:
        """Convert IST datetime string to Unix ms UTC."""
        dt_ist = datetime.datetime.strptime(dt_str, fmt)
        dt_utc = dt_ist - datetime.timedelta(hours=5, minutes=30)
        return int(dt_utc.timestamp() * 1000)

    @staticmethod
    def now_ms() -> int:
        """Current time as Unix ms UTC."""
        return int(time.time() * 1000)

    @staticmethod
    def days_to_ms(days: int) -> int:
        """Convert number of days to milliseconds."""
        return days * 24 * 60 * 60 * 1000
