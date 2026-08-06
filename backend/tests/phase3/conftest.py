"""
Phase 3 Validation — Shared Fixtures
======================================
All test files in tests/phase3/ import from here.
Handles one-time service initialisation and shared test data.

Rule: This file must stay under 300 lines.
"""
from __future__ import annotations
import asyncio
import os
import sys
import time
from typing import Dict, Any

import pytest
import pytest_asyncio

# ── Path bootstrap ────────────────────────────────────────────
# Ensure backend/app is importable regardless of working directory
_BACKEND = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _BACKEND not in sys.path:
    sys.path.insert(0, _BACKEND)

# Load .env before any app imports
from dotenv import load_dotenv
load_dotenv(os.path.join(_BACKEND, ".env"))


# ── Test symbols ──────────────────────────────────────────────
PRIMARY_SYMBOL   = "RELIANCE.NS"   # large-cap, always liquid
SECONDARY_SYMBOL = "TCS.NS"        # second symbol for consistency tests
INDEX_SYMBOL     = "^NSEI"         # NIFTY 50 — used by market_regime
MIN_CANDLES      = 26              # minimum usable candle count


# ── Event loop (Python 3.7 compatible) ───────────────────────
@pytest.fixture(scope="session")
def event_loop():
    """Single event loop for the entire test session."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


# ── Service initialisation (once per session) ─────────────────
@pytest_asyncio.fixture(scope="session")
async def service():
    """
    Initialise market_data.service once for the whole session.
    Returns the service module so tests can call fetch_candles etc.
    """
    from app.market_data import service as svc
    await svc.initialise()
    return svc


# ── Provider status (once per session) ───────────────────────
@pytest_asyncio.fixture(scope="session")
async def provider_status(service):
    """
    Fetch provider health status once.
    Tests use this to know which provider is active.
    """
    status = await service.get_provider_status()
    return status


# ── Pre-fetched candles (once per session) ────────────────────
@pytest_asyncio.fixture(scope="session")
async def candles_5m(service):
    """
    5-minute candles for PRIMARY_SYMBOL, fetched once.
    All consistency tests use this same dataset.
    """
    result = await service.fetch_candles(
        PRIMARY_SYMBOL, interval="5m", days=5, validate=True
    )
    return result


@pytest_asyncio.fixture(scope="session")
async def candles_1d(service):
    """Daily candles for PRIMARY_SYMBOL — used by regime + backtesting tests."""
    result = await service.fetch_candles(
        PRIMARY_SYMBOL, interval="1d", days=365, validate=True
    )
    return result


@pytest_asyncio.fixture(scope="session")
async def candles_15m(service):
    """15-minute candles — used by module functional tests."""
    result = await service.fetch_candles(
        PRIMARY_SYMBOL, interval="15m", days=5, validate=True
    )
    return result


# ── Active provider name helper ───────────────────────────────
@pytest.fixture(scope="session")
def active_provider(provider_status):
    """
    Returns the name of the primary active provider.
    Tests use this to assert correct provider selection.
    """
    providers = provider_status.get("providers", [])
    for p in providers:
        if p.get("available") and p.get("logged_in"):
            return p["name"]
    # Fallback: return first available
    for p in providers:
        if p.get("available"):
            return p["name"]
    return "unknown"


# ── Candle schema validator ───────────────────────────────────
@pytest.fixture(scope="session")
def assert_candle_schema():
    """
    Returns a callable that validates a single candle dict
    has all required OHLCV fields with correct types.
    """
    def _check(candle: Dict[str, Any], label: str = "candle"):
        required = {"t", "o", "h", "l", "c", "v"}
        missing = required - set(candle.keys())
        assert not missing, f"{label} missing fields: {missing}"
        assert candle["h"] >= candle["l"],      f"{label} h < l"
        assert candle["h"] >= candle["o"],      f"{label} h < o"
        assert candle["h"] >= candle["c"],      f"{label} h < c"
        assert candle["l"] <= candle["o"],      f"{label} l > o"
        assert candle["l"] <= candle["c"],      f"{label} l > c"
        assert candle["c"] > 0,                 f"{label} close <= 0"
        assert candle["v"] >= 0,                f"{label} volume < 0"
        assert candle["t"] > 0,                 f"{label} timestamp <= 0"
    return _check


# ── Timing helper ─────────────────────────────────────────────
@pytest.fixture(scope="session")
def timer():
    """Returns a context-manager-style timing dict builder."""
    class Timer:
        def __init__(self):
            self.start = time.perf_counter()
        def elapsed_ms(self) -> float:
            return round((time.perf_counter() - self.start) * 1000, 1)
    return Timer
