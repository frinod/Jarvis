"""
config/settings/__init__.py
============================
Settings assembler for JARVIS OS.

Provides a single import point for all configuration domains.
Consumers import from here, not from individual domain modules.

Usage
-----
    from app.config.settings import get_settings, JarvisSettings

    settings = get_settings()
    settings.app.port
    settings.broker.get_active()
    settings.ai.inference.temperature
    settings.risk.is_trading_halted()
    settings.cache.ttl_for("market_quotes")
    settings.logging.level_for("httpx")

Design principles
-----------------
  Single assembly point -- one call builds everything
  Lazy singleton -- built once, cached, thread-safe for reads
  Environment-aware -- testing profile applies TTL overrides
  Explicit over implicit -- no magic attribute injection
  Immutable after build -- all domain objects are frozen
"""
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel

from app.config.settings.app      import AppSettings,      build_app_settings
from app.config.settings.broker   import BrokerSettings,   build_broker_settings
from app.config.settings.market   import MarketSettings,   build_market_settings
from app.config.settings.ai       import AISettings,       build_ai_settings
from app.config.settings.risk     import RiskSettings,     build_risk_settings
from app.config.settings.cache    import CacheSettings,    build_cache_settings
from app.config.settings.logging  import LoggingSettings,  build_logging_settings
from app.config.settings.provider import ProviderSettings


class JarvisSettings(BaseModel):
    """
    Unified settings container for JARVIS OS.
    All domain settings are assembled here and frozen after build.
    """
    app:     AppSettings
    broker:  BrokerSettings
    market:  MarketSettings
    ai:      AISettings
    risk:    RiskSettings
    cache:   CacheSettings
    logging: LoggingSettings

    class Config:
        allow_mutation = False
        extra          = "ignore"
        # Allow arbitrary types (nested Pydantic models with custom Config)
        arbitrary_types_allowed = True

    def to_dict(self) -> dict:
        """Safe serialisation of all domains. Credentials always redacted."""
        return {
            "app":     self.app.to_dict(),
            "broker":  self.broker.get_active().to_safe_dict() if self.broker.get_active() else {},
            "market":  self.market.to_dict(),
            "ai":      self.ai.to_dict(),
            "risk":    self.risk.to_dict(),
            "cache":   self.cache.to_dict(),
            "logging": self.logging.to_dict(),
        }


# ── Singleton ─────────────────────────────────────────────────

_settings: Optional[JarvisSettings] = None


def build_settings(overrides: Optional[dict] = None) -> JarvisSettings:
    """
    Build a fresh JarvisSettings from environment + optional overrides.
    overrides: dict with keys matching JarvisSettings field names.
    Each value should be a pre-built domain settings object.

    Example:
        build_settings(overrides={"risk": my_risk_settings})
    """
    values: dict = {
        "app":     build_app_settings(),
        "broker":  build_broker_settings(),
        "market":  build_market_settings(),
        "ai":      build_ai_settings(),
        "risk":    build_risk_settings(),
        "cache":   build_cache_settings(),
        "logging": build_logging_settings(),
    }
    if overrides:
        values.update(overrides)
    return JarvisSettings(**values)


def get_settings() -> JarvisSettings:
    """
    Return the singleton JarvisSettings, building it on first call.
    Subsequent calls return the cached instance.
    Call reset_settings() in tests to force a rebuild.
    """
    global _settings
    if _settings is None:
        _settings = build_settings()
    return _settings


def reset_settings() -> None:
    """
    Clear the singleton. Used in tests and on config reload.
    After calling this, the next get_settings() call rebuilds from env.
    """
    global _settings
    _settings = None


# ── Public API ────────────────────────────────────────────────

__all__ = [
    # Assembler
    "JarvisSettings",
    "build_settings",
    "get_settings",
    "reset_settings",
    # Domain types (re-exported for convenience)
    "AppSettings",
    "BrokerSettings",
    "MarketSettings",
    "AISettings",
    "RiskSettings",
    "CacheSettings",
    "LoggingSettings",
    "ProviderSettings",
]
