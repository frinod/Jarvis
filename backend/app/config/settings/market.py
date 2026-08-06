"""
config/settings/market.py
=========================
Market intelligence configuration layer for JARVIS OS.

Covers every market JARVIS can operate in:
  Equities  -- NSE, BSE, international
  Derivatives -- NFO, BFO, CDS, MCX
  Crypto, Forex, Commodities, Indices

Each market is a MarketProfile with:
  - Identity and metadata (exchange code, currency, timezone, tick size)
  - TradingSession (open/close/pre-open/post-close times, timezone)
  - Supported intervals
  - AI analysis defaults (prediction horizon, confidence threshold)
  - Regime detection thresholds
  - Trading calendar hook (wired in future, not now)

Design principles
-----------------
  No hardcoded intervals in analysis modules -- they read from here
  No hardcoded session times -- they read from TradingSession
  Calendar-ready -- calendar_provider field exists, not yet wired
  AI-first -- every market exposes AI analysis defaults
  Query-friendly -- enabled_markets(), supports_derivatives(), etc.
  Immutable after load -- allow_mutation = False

Internal pattern (standard for all settings modules)
  1. Domain models
  2. Validation
  3. Factory function
  4. Safe serialisation
  5. Convenience methods
  6. Future extension hooks
"""
from __future__ import annotations

import os
from enum import Enum
from typing import Dict, List, Optional, Set, Tuple

from pydantic import BaseModel, validator


# ── Interval enum ─────────────────────────────────────────────

class MarketInterval(str, Enum):
    MIN_1   = "1m"
    MIN_3   = "3m"
    MIN_5   = "5m"
    MIN_10  = "10m"
    MIN_15  = "15m"
    MIN_30  = "30m"
    HOUR_1  = "1h"
    HOUR_4  = "4h"
    DAY_1   = "1d"
    WEEK_1  = "1w"
    MONTH_1 = "1M"

    @classmethod
    def intraday(cls) -> List["MarketInterval"]:
        return [cls.MIN_1, cls.MIN_3, cls.MIN_5, cls.MIN_10,
                cls.MIN_15, cls.MIN_30, cls.HOUR_1, cls.HOUR_4]

    @classmethod
    def swing(cls) -> List["MarketInterval"]:
        return [cls.DAY_1, cls.WEEK_1, cls.MONTH_1]


class MarketType(str, Enum):
    EQUITY      = "equity"
    DERIVATIVE  = "derivative"
    COMMODITY   = "commodity"
    CURRENCY    = "currency"
    CRYPTO      = "crypto"
    FOREX       = "forex"
    INDEX       = "index"


# ── Trading session ───────────────────────────────────────────

class TradingSession(BaseModel):
    """
    Configurable trading session for one market.
    Times are strings in HH:MM format (24h), interpreted in `timezone`.
    Calendar integration: set calendar_provider to a dotted class path
    when holiday/special-session support is added.
    """
    timezone:          str  = "Asia/Kolkata"
    open_time:         str  = "09:15"
    close_time:        str  = "15:30"
    pre_open_start:    str  = "09:00"
    pre_open_end:      str  = "09:08"
    post_close_start:  str  = "15:40"
    post_close_end:    str  = "16:00"
    calendar_provider: str  = ""    # e.g. "app.calendar.nse.NSECalendar"

    class Config:
        allow_mutation = False
        extra          = "ignore"

    @validator("open_time", "close_time", "pre_open_start",
               "pre_open_end", "post_close_start", "post_close_end")
    def valid_time_format(cls, v: str) -> str:
        parts = v.split(":")
        if len(parts) != 2:
            raise ValueError(f"Time must be HH:MM, got: {v!r}")
        h, m = parts
        if not (h.isdigit() and m.isdigit()):
            raise ValueError(f"Time must be HH:MM digits, got: {v!r}")
        if not (0 <= int(h) <= 23 and 0 <= int(m) <= 59):
            raise ValueError(f"Time out of range: {v!r}")
        return v

    @validator("close_time")
    def close_after_open(cls, v: str, values: dict) -> str:
        open_t = values.get("open_time", "00:00")
        def _to_minutes(t: str) -> int:
            h, m = t.split(":")
            return int(h) * 60 + int(m)
        if _to_minutes(v) <= _to_minutes(open_t):
            raise ValueError(
                f"close_time {v!r} must be after open_time {open_t!r}"
            )
        return v

    def to_dict(self) -> dict:
        return self.dict()


# ── Market metadata ───────────────────────────────────────────

class MarketMetadata(BaseModel):
    """
    Static facts about a market. Used by AI and UI modules.
    tick_size: minimum price movement (e.g. 0.05 for NSE equities)
    lot_size:  minimum tradeable quantity (1 for equities, varies for F&O)
    decimal_precision: price display precision
    """
    exchange_code:     str   = ""
    display_name:      str   = ""
    currency:          str   = "INR"
    timezone:          str   = "Asia/Kolkata"
    tick_size:         float = 0.05
    lot_size:          int   = 1
    decimal_precision: int   = 2
    country_code:      str   = "IN"

    class Config:
        allow_mutation = False
        extra          = "ignore"

    @validator("currency")
    def currency_uppercase(cls, v: str) -> str:
        return v.upper().strip()

    @validator("tick_size")
    def tick_positive(cls, v: float) -> float:
        if v <= 0:
            raise ValueError("tick_size must be positive")
        return v

    @validator("decimal_precision")
    def precision_non_negative(cls, v: int) -> int:
        if v < 0:
            raise ValueError("decimal_precision must be >= 0")
        return v

    def to_dict(self) -> dict:
        return self.dict()


# ── AI market defaults ────────────────────────────────────────

class AIMarketDefaults(BaseModel):
    """
    AI analysis defaults per market. Configuration only -- no logic.
    prediction_horizon_bars: how many bars ahead to forecast
    preferred_intervals:     ordered list of intervals for multi-timeframe analysis
    confidence_threshold:    minimum AI confidence to act on a signal (0.0-1.0)
    forecast_refresh_s:      how often to refresh AI forecast (seconds)
    mtf_combinations:        multi-timeframe ladder as (fast, medium, slow) tuples
    """
    prediction_horizon_bars: int              = 6
    preferred_intervals:     List[str]        = ["5m", "15m", "1h", "1d"]
    confidence_threshold:    float            = 0.65
    forecast_refresh_s:      int              = 300
    mtf_combinations:        List[Tuple[str, str, str]] = [
        ("5m", "15m", "1h"),
        ("15m", "1h", "1d"),
        ("1h", "1d", "1w"),
    ]
    max_lookback_days:       int              = 365
    default_candle_days:     int              = 10

    class Config:
        allow_mutation = False
        extra          = "ignore"

    @validator("confidence_threshold")
    def threshold_in_range(cls, v: float) -> float:
        if not (0.0 <= v <= 1.0):
            raise ValueError("confidence_threshold must be 0.0-1.0")
        return v

    @validator("prediction_horizon_bars")
    def horizon_positive(cls, v: int) -> int:
        if v < 1:
            raise ValueError("prediction_horizon_bars must be >= 1")
        return v

    def to_dict(self) -> dict:
        return self.dict()


# ── Regime thresholds ─────────────────────────────────────────

class RegimeThresholds(BaseModel):
    """
    Thresholds for AI market regime detection. Configuration only.
    trending_adx_min:    ADX above this = trending market
    ranging_adx_max:     ADX below this = ranging market
    high_vol_percentile: realised vol above this percentile = high volatility
    low_vol_percentile:  realised vol below this percentile = low volatility
    """
    trending_adx_min:    float = 25.0
    ranging_adx_max:     float = 20.0
    high_vol_percentile: float = 75.0
    low_vol_percentile:  float = 25.0
    vol_lookback_days:   int   = 20

    class Config:
        allow_mutation = False
        extra          = "ignore"

    @validator("high_vol_percentile", "low_vol_percentile")
    def percentile_in_range(cls, v: float) -> float:
        if not (0.0 < v < 100.0):
            raise ValueError("percentile must be between 0 and 100")
        return v

    def to_dict(self) -> dict:
        return self.dict()


# ── Market profile ────────────────────────────────────────────

class MarketProfile(BaseModel):
    """
    Complete configuration for one market.
    Identified by a unique name key (e.g. "NSE", "CRYPTO_BTC").
    """
    name:               str                      = ""
    market_type:        MarketType               = MarketType.EQUITY
    enabled:            bool                     = True
    supports_derivatives: bool                   = False
    supports_options:   bool                     = False
    supports_futures:   bool                     = False
    supported_intervals: List[str]               = [i.value for i in MarketInterval]
    session:            TradingSession           = TradingSession()
    metadata:           MarketMetadata           = MarketMetadata()
    ai_defaults:        AIMarketDefaults         = AIMarketDefaults()
    regime:             RegimeThresholds         = RegimeThresholds()

    class Config:
        allow_mutation = False
        extra          = "ignore"
        use_enum_values = True

    @validator("name")
    def name_not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("MarketProfile.name must not be empty")
        return v.strip().upper()

    def supports_interval(self, interval: str) -> bool:
        return interval in self.supported_intervals

    def to_dict(self) -> dict:
        return {
            "name":                  self.name,
            "market_type":           self.market_type,
            "enabled":               self.enabled,
            "supports_derivatives":  self.supports_derivatives,
            "supports_options":      self.supports_options,
            "supports_futures":      self.supports_futures,
            "supported_intervals":   self.supported_intervals,
            "session":               self.session.to_dict(),
            "metadata":              self.metadata.to_dict(),
            "ai_defaults":           self.ai_defaults.to_dict(),
            "regime":                self.regime.to_dict(),
        }


# ── Domain settings object ────────────────────────────────────

class MarketSettings(BaseModel):
    """
    Registry of all market profiles plus global market data defaults.
    """
    markets:              Dict[str, MarketProfile] = {}
    default_market:       str                      = "NSE"
    default_interval:     str                      = "5m"
    default_candle_days:  int                      = 10
    max_candle_days:      int                      = 365
    default_universe:     str                      = "nifty50"

    class Config:
        allow_mutation = False
        extra          = "ignore"

    @validator("default_candle_days", "max_candle_days")
    def days_positive(cls, v: int) -> int:
        if v < 1:
            raise ValueError("candle days must be >= 1")
        return v

    # ── Convenience queries ───────────────────────────────────

    def get_market(self, name: str) -> Optional[MarketProfile]:
        return self.markets.get(name.upper())

    def get_default(self) -> Optional[MarketProfile]:
        return self.markets.get(self.default_market)

    def enabled_markets(self) -> List[MarketProfile]:
        return [m for m in self.markets.values() if m.enabled]

    def markets_by_type(self, market_type: str) -> List[MarketProfile]:
        return [m for m in self.markets.values()
                if m.market_type == market_type and m.enabled]

    def supports_derivatives(self, name: str) -> bool:
        m = self.get_market(name)
        return m.supports_derivatives if m else False

    def supports_options(self, name: str) -> bool:
        m = self.get_market(name)
        return m.supports_options if m else False

    def supports_futures(self, name: str) -> bool:
        m = self.get_market(name)
        return m.supports_futures if m else False

    def available_intervals(self, market_name: str = "") -> List[str]:
        if market_name:
            m = self.get_market(market_name)
            return m.supported_intervals if m else []
        return [i.value for i in MarketInterval]

    def to_dict(self) -> dict:
        return {
            "default_market":      self.default_market,
            "default_interval":    self.default_interval,
            "default_candle_days": self.default_candle_days,
            "max_candle_days":     self.max_candle_days,
            "default_universe":    self.default_universe,
            "markets":             {k: v.to_dict() for k, v in self.markets.items()},
        }


# ── Built-in market profiles ──────────────────────────────────

_ALL_INTERVALS = [i.value for i in MarketInterval]
_INTRADAY      = [i.value for i in MarketInterval.intraday()]

_NSE = MarketProfile(
    name="NSE", market_type=MarketType.EQUITY,
    supports_derivatives=True, supports_options=False, supports_futures=False,
    supported_intervals=_ALL_INTERVALS,
    session=TradingSession(
        timezone="Asia/Kolkata", open_time="09:15", close_time="15:30",
        pre_open_start="09:00", pre_open_end="09:08",
    ),
    metadata=MarketMetadata(
        exchange_code="NSE", display_name="National Stock Exchange",
        currency="INR", timezone="Asia/Kolkata", tick_size=0.05,
    ),
)

_NFO = MarketProfile(
    name="NFO", market_type=MarketType.DERIVATIVE,
    supports_derivatives=True, supports_options=True, supports_futures=True,
    supported_intervals=_ALL_INTERVALS,
    session=TradingSession(
        timezone="Asia/Kolkata", open_time="09:15", close_time="15:30",
    ),
    metadata=MarketMetadata(
        exchange_code="NFO", display_name="NSE Futures & Options",
        currency="INR", tick_size=0.05,
    ),
)

_MCX = MarketProfile(
    name="MCX", market_type=MarketType.COMMODITY,
    supported_intervals=_ALL_INTERVALS,
    session=TradingSession(
        timezone="Asia/Kolkata", open_time="09:00", close_time="23:30",
    ),
    metadata=MarketMetadata(
        exchange_code="MCX", display_name="Multi Commodity Exchange",
        currency="INR", tick_size=0.01,
    ),
)

_CRYPTO = MarketProfile(
    name="CRYPTO", market_type=MarketType.CRYPTO,
    supported_intervals=_ALL_INTERVALS,
    enabled=False,   # disabled until crypto provider is added
    session=TradingSession(
        timezone="UTC", open_time="00:00", close_time="23:59",
    ),
    metadata=MarketMetadata(
        exchange_code="CRYPTO", display_name="Cryptocurrency",
        currency="USD", timezone="UTC", tick_size=0.01, country_code="GLOBAL",
    ),
)


# ── Factory ───────────────────────────────────────────────────

def build_market_settings(overrides: Optional[dict] = None) -> MarketSettings:
    """
    Construct MarketSettings from environment variables + optional overrides.

    Environment variables:
      DEFAULT_MARKET        -- market name (default: "NSE")
      DEFAULT_INTERVAL      -- candle interval (default: "5m")
      DEFAULT_CANDLE_DAYS   -- int (default: 10)
      MAX_CANDLE_DAYS       -- int (default: 365)
      DEFAULT_UNIVERSE      -- stock universe (default: "nifty50")
      CRYPTO_ENABLED        -- true|false (default: "false")
    """
    crypto_enabled = os.getenv("CRYPTO_ENABLED", "false").strip().lower() == "true"
    crypto_profile = MarketProfile(**{**_CRYPTO.dict(), "enabled": crypto_enabled})

    markets: Dict[str, MarketProfile] = {
        "NSE":    _NSE,
        "NFO":    _NFO,
        "MCX":    _MCX,
        "CRYPTO": crypto_profile,
    }

    values: dict = {
        "markets":             markets,
        "default_market":      os.getenv("DEFAULT_MARKET",       "NSE"),
        "default_interval":    os.getenv("DEFAULT_INTERVAL",     "5m"),
        "default_candle_days": int(os.getenv("DEFAULT_CANDLE_DAYS", "10")),
        "max_candle_days":     int(os.getenv("MAX_CANDLE_DAYS",     "365")),
        "default_universe":    os.getenv("DEFAULT_UNIVERSE",     "nifty50"),
    }

    if overrides:
        values.update(overrides)

    return MarketSettings(**values)
