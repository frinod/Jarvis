"""
config/environment.py
=====================
Environment profile detection for JARVIS OS.

Controlled by a single env var: JARVIS_ENV
  development  (default) -- verbose logging, all features on, Angel One live
  testing      -- paper_only broker, yahoo data only, short cache TTLs
  staging      -- json logging, Angel One live, moderate retries
  production   -- json logging, WARNING level, all retries maxed, strict validation

Zero dependencies -- importable before any other config module.
"""
from __future__ import annotations

import os
from enum import Enum
from typing import Dict, Any


class Environment(str, Enum):
    DEVELOPMENT = "development"
    TESTING     = "testing"
    STAGING     = "staging"
    PRODUCTION  = "production"


# ── Profile overrides ─────────────────────────────────────────
# Each profile overrides only the values that differ from defaults.
# Keys must match field names in the Settings domain classes.

_PROFILES: Dict[Environment, Dict[str, Any]] = {
    Environment.DEVELOPMENT: {
        # All defaults apply -- nothing overridden
    },
    Environment.TESTING: {
        "active_broker":          "paper_only",
        "active_data_provider":   "yahoo",
        "log_level":              "WARNING",
        "log_format":             "console",
        "ai_max_retries":         1,
        "ttl_quote_live_s":       1,
        "ttl_quote_poll_s":       1,
        "ttl_candle_1m_s":        1,
        "ttl_candle_5m_s":        1,
        "ttl_candle_15m_s":       1,
        "ttl_candle_1h_s":        1,
        "ttl_candle_1d_s":        1,
        "ttl_fundamentals_s":     5,
        "ttl_instruments_s":      5,
        "ttl_regime_s":           1,
        # Safety: never allow live trading in tests
        "live_trading_enabled":   False,
        "angel_one_ws_enabled":   False,
    },
    Environment.STAGING: {
        "log_format":             "json",
        "log_level":              "INFO",
        "ai_max_retries":         2,
    },
    Environment.PRODUCTION: {
        "log_format":             "json",
        "log_level":              "WARNING",
        "ai_max_retries":         3,
        "provider_max_retries":   3,
    },
}


def get_env() -> Environment:
    """
    Return the active Environment profile.
    Reads JARVIS_ENV env var. Unknown values default to DEVELOPMENT.
    """
    raw = os.environ.get("JARVIS_ENV", "development").strip().lower()
    try:
        return Environment(raw)
    except ValueError:
        return Environment.DEVELOPMENT


def is_production() -> bool:
    return get_env() == Environment.PRODUCTION


def is_staging() -> bool:
    return get_env() == Environment.STAGING


def is_testing() -> bool:
    return get_env() == Environment.TESTING


def is_development() -> bool:
    return get_env() == Environment.DEVELOPMENT


def profile_overrides() -> Dict[str, Any]:
    """
    Return the settings overrides for the current environment profile.
    Settings loader applies these after loading base .env values.
    """
    return dict(_PROFILES.get(get_env(), {}))


def require_strict_security() -> bool:
    """
    True in staging and production -- triggers SECRET_KEY validation,
    live trading guards, and credential completeness checks at startup.
    """
    return get_env() in (Environment.STAGING, Environment.PRODUCTION)
