"""
config/settings/broker.py
=========================
Broker configuration domain for JARVIS OS.

Introduces ProviderSettings -- a reusable base model for every provider
type in the platform (brokers, news, AI, voice, notifications, storage).
All share: enabled, priority, timeout_s, retry_policy_name, credentials_key.

BrokerProfile extends ProviderSettings with broker-specific concerns:
  capabilities, supported markets, trading mode, risk controls, health slots.

BrokerSettings is the domain object: a registry of named profiles plus
active broker selection and fallback chain.

Design principles
-----------------
  No broker-specific fields at the top level -- all under named profiles
  Capability advertising -- modules query, never assume
  Fallback chain -- automatic degradation without code changes
  Health slots -- populated at runtime, not at config load
  Plugin-ready -- profiles discovered by name, not hardcoded class references
  Immutable after load -- allow_mutation = False

ACP note
--------
ProviderSettings was extracted to config/settings/provider.py in Task 7
when ai.py became the second consumer. This file now imports from there.
"""
from __future__ import annotations

import os
from enum import Enum
from typing import Dict, List, Optional, Set

from pydantic import BaseModel, validator

from app.config.settings.provider import ProviderSettings  # noqa: F401 -- re-exported


# ── Broker-specific enums ─────────────────────────────────────

class TradingMode(str, Enum):
    READ_ONLY    = "read_only"     # fetch data only, no orders
    PAPER        = "paper"         # simulated orders, no real money
    LIVE         = "live"          # real orders, real money
    SIMULATION   = "simulation"    # backtesting / replay mode


class BrokerMarket(str, Enum):
    NSE          = "NSE"
    BSE          = "BSE"
    MCX          = "MCX"
    NFO          = "NFO"    # NSE F&O
    CDS          = "CDS"    # Currency derivatives
    BFO          = "BFO"    # BSE F&O
    INTERNATIONAL = "INTERNATIONAL"


# ── Capability advertising ────────────────────────────────────

class BrokerCapabilities(BaseModel):
    """
    What a broker can do. Modules query this instead of hardcoding
    broker-specific logic. Add new capabilities here as JARVIS grows.
    """
    historical_data:  bool = False
    live_quotes:      bool = False
    websocket_feed:   bool = False
    order_placement:  bool = False
    order_cancel:     bool = False
    portfolio:        bool = False
    holdings:         bool = False
    options_chain:    bool = False
    margin_trading:   bool = False
    gtt_orders:       bool = False    # Good Till Triggered
    basket_orders:    bool = False
    paper_trading:    bool = False
    market_depth:     bool = False

    class Config:
        allow_mutation = False
        extra          = "ignore"

    def supports(self, capability: str) -> bool:
        """Query a capability by name string. Returns False for unknown names."""
        return bool(getattr(self, capability, False))

    def supported_list(self) -> List[str]:
        """Return list of capability names that are True."""
        return [k for k, v in self.dict().items() if v is True]


# ── Risk controls (config values only -- enforcement is in trading layer) ──

class BrokerRiskConfig(BaseModel):
    """
    Risk control parameters declared per broker profile.
    These are configuration values only -- the trading layer enforces them.
    """
    max_order_value:      float = 50000.0   # INR per single order
    max_daily_loss:       float = 5000.0    # INR -- halt if breached
    max_position_size:    float = 10000.0   # INR per symbol
    max_open_positions:   int   = 10
    allowed_products:     List[str] = ["INTRADAY", "DELIVERY"]
    market_open_ist:      str   = "09:15"
    market_close_ist:     str   = "15:30"
    emergency_stop:       bool  = False     # if True, all new orders blocked

    class Config:
        allow_mutation = False
        extra          = "ignore"


# ── Health metadata (slots populated at runtime) ──────────────

class BrokerHealthSlot(BaseModel):
    """
    Health metadata slots. Values are None at config load time.
    The health monitoring layer populates these at runtime without
    changing the configuration model.
    """
    connected:       Optional[bool]  = None
    authenticated:   Optional[bool]  = None
    last_heartbeat:  Optional[str]   = None   # ISO timestamp string
    latency_ms:      Optional[float] = None
    last_failure:    Optional[str]   = None   # error message or None

    class Config:
        allow_mutation = True    # health slots ARE mutable -- runtime updates
        extra          = "ignore"


# ── Broker profile ────────────────────────────────────────────

class BrokerProfile(ProviderSettings):
    """
    Complete configuration for one broker instance.

    A profile is identified by a name (e.g. "angel_primary", "paper").
    Multiple profiles can be active simultaneously -- the active_broker
    field in BrokerSettings selects which one handles orders.

    plugin_class: dotted import path to the BrokerProvider implementation.
    Empty string means the broker is discovered by name from the registry.
    """
    name:           str                  = ""
    display_name:   str                  = ""
    plugin_class:   str                  = ""    # e.g. "app.brokers.angel_one.AngelOneProvider"
    trading_mode:   TradingMode          = TradingMode.PAPER
    markets:        List[BrokerMarket]   = []
    capabilities:   BrokerCapabilities  = BrokerCapabilities()
    risk:           BrokerRiskConfig     = BrokerRiskConfig()
    health:         BrokerHealthSlot     = BrokerHealthSlot()

    class Config:
        allow_mutation = False
        extra          = "ignore"
        use_enum_values = True

    @validator("name")
    def name_not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("BrokerProfile.name must not be empty")
        return v.strip()

    @validator("priority")
    def priority_positive(cls, v: int) -> int:
        if v < 1:
            raise ValueError("priority must be >= 1")
        return v

    @property
    def is_live(self) -> bool:
        return self.trading_mode == TradingMode.LIVE and self.enabled

    @property
    def is_paper(self) -> bool:
        return self.trading_mode == TradingMode.PAPER and self.enabled

    @property
    def is_read_only(self) -> bool:
        return self.trading_mode == TradingMode.READ_ONLY

    def supports(self, capability: str) -> bool:
        return self.capabilities.supports(capability)

    def supports_market(self, market: str) -> bool:
        return market.upper() in [m.upper() for m in self.markets]

    def to_safe_dict(self) -> dict:
        """Serialise without exposing credentials_key value."""
        d = self.dict()
        d["credentials_key"] = "[REDACTED]" if self.credentials_key else ""
        return d


# ── Domain settings object ────────────────────────────────────

class BrokerSettings(BaseModel):
    """
    Registry of all broker profiles plus active selection and fallback chain.

    profiles:       named dict of BrokerProfile instances
    active_broker:  name of the profile currently handling orders
    fallback_chain: ordered list of profile names to try if active is down
    paper_capital:  starting capital for paper trading profiles (INR)
    """
    profiles:       Dict[str, BrokerProfile] = {}
    active_broker:  str                      = "paper"
    fallback_chain: List[str]                = ["paper"]
    paper_capital:  float                    = 100000.0

    class Config:
        allow_mutation = False
        extra          = "ignore"

    @validator("paper_capital")
    def capital_positive(cls, v: float) -> float:
        if v <= 0:
            raise ValueError("paper_capital must be positive")
        return v

    def get_active(self) -> Optional[BrokerProfile]:
        return self.profiles.get(self.active_broker)

    def get_profile(self, name: str) -> Optional[BrokerProfile]:
        return self.profiles.get(name)

    def enabled_profiles(self) -> List[BrokerProfile]:
        return [p for p in self.profiles.values() if p.enabled]

    def live_profiles(self) -> List[BrokerProfile]:
        return [p for p in self.profiles.values() if p.is_live]

    def fallback_sequence(self) -> List[BrokerProfile]:
        """Return profiles in fallback order, skipping missing names."""
        return [self.profiles[n] for n in self.fallback_chain if n in self.profiles]

    def has_live_broker(self) -> bool:
        return any(p.is_live for p in self.profiles.values())


# ── Default profiles ──────────────────────────────────────────

_PAPER_PROFILE = BrokerProfile(
    name          = "paper",
    display_name  = "Paper Trading",
    trading_mode  = TradingMode.PAPER,
    priority      = 90,
    markets       = [BrokerMarket.NSE, BrokerMarket.BSE],
    capabilities  = BrokerCapabilities(
        historical_data = True,
        live_quotes     = True,
        order_placement = True,
        order_cancel    = True,
        portfolio       = True,
        holdings        = True,
        paper_trading   = True,
    ),
)

_ANGEL_ONE_PROFILE = BrokerProfile(
    name             = "angel_one",
    display_name     = "Angel One",
    plugin_class     = "app.brokers.angel_one.AngelOneProvider",
    trading_mode     = TradingMode.PAPER,   # default safe; override to LIVE in .env
    priority         = 10,
    credentials_key  = "ANGEL",
    markets          = [BrokerMarket.NSE, BrokerMarket.BSE,
                        BrokerMarket.NFO, BrokerMarket.MCX],
    capabilities     = BrokerCapabilities(
        historical_data  = True,
        live_quotes      = True,
        websocket_feed   = True,
        order_placement  = True,
        order_cancel     = True,
        portfolio        = True,
        holdings         = True,
        options_chain    = True,
        margin_trading   = True,
        gtt_orders       = True,
        market_depth     = True,
    ),
)


# ── Factory ───────────────────────────────────────────────────

def build_broker_settings(overrides: Optional[dict] = None) -> BrokerSettings:
    """
    Construct BrokerSettings from environment variables + optional overrides.

    Environment variables:
      ACTIVE_BROKER          -- profile name (default: "paper")
      BROKER_FALLBACK_CHAIN  -- comma-separated names (default: "paper")
      PAPER_CAPITAL          -- float (default: 100000.0)
      ANGEL_TRADING_MODE     -- read_only|paper|live (default: "paper")
      ANGEL_ENABLED          -- true|false (default: "true")
    """
    active = os.getenv("ACTIVE_BROKER", "paper").strip()
    fallback_raw = os.getenv("BROKER_FALLBACK_CHAIN", "paper").strip()
    fallback = [n.strip() for n in fallback_raw.split(",") if n.strip()]
    capital = float(os.getenv("PAPER_CAPITAL", "100000.0"))

    # Angel One profile -- mode and enabled state from env
    angel_mode_raw = os.getenv("ANGEL_TRADING_MODE", "paper").strip().lower()
    try:
        angel_mode = TradingMode(angel_mode_raw)
    except ValueError:
        angel_mode = TradingMode.PAPER

    angel_enabled = os.getenv("ANGEL_ENABLED", "true").strip().lower() == "true"

    angel_profile = BrokerProfile(
        **{**_ANGEL_ONE_PROFILE.dict(), "trading_mode": angel_mode, "enabled": angel_enabled}
    )

    profiles: Dict[str, BrokerProfile] = {
        "angel_one": angel_profile,
        "paper":     _PAPER_PROFILE,
    }

    values: dict = {
        "profiles":       profiles,
        "active_broker":  active,
        "fallback_chain": fallback,
        "paper_capital":  capital,
    }

    if overrides:
        values.update(overrides)

    return BrokerSettings(**values)
