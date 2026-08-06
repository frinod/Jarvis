"""
app/ai/perception/market.py
============================
MarketPerception -- market data provider interface and in-memory stub.

Design
------
  - MarketPerception is an ABC. InMemoryMarketPerception is the Phase 6 stub.
  - Phase 7+: swap for a real market data provider (Zerodha, Yahoo Finance, etc.)
  - All market data is returned as plain dicts -- no domain-specific dataclasses
    at the interface level. Domain data lives in the returned dict.
  - PerceptionBundle is the output: a plain dict with a "source" key.

Domain agnosticism at the interface level
------------------------------------------
  MarketPerception.fetch() accepts a plain dict of params.
  The returned PerceptionBundle.data is a plain dict.
  Callers store it in ExecutionContext.metadata["market_data"].
"""
from __future__ import annotations

import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


# ── PerceptionBundle ──────────────────────────────────────────────────────────

@dataclass
class PerceptionBundle:
    """
    Output of one perception fetch.
    data is a plain dict -- domain data lives here.
    """
    source:     str
    data:       Dict[str, Any]
    timestamp:  float          = field(default_factory=time.time)
    success:    bool           = True
    error:      Optional[str]  = None
    latency_ms: float          = 0.0


# ── MarketPerception ABC ──────────────────────────────────────────────────────

class MarketPerception(ABC):
    """
    Interface for market data retrieval.
    Phase 6: InMemoryMarketPerception (stub).
    Phase 7+: real provider (Zerodha, Yahoo Finance, etc.).
    """

    @abstractmethod
    async def fetch(self, params: Dict[str, Any]) -> PerceptionBundle:
        """
        Fetch market data for the given params.
        params may contain: symbol, interval, limit, etc.
        Returns a PerceptionBundle with data as a plain dict.
        """

    @abstractmethod
    async def is_available(self) -> bool:
        """Return True if the data source is reachable."""


# ── InMemoryMarketPerception ──────────────────────────────────────────────────

class InMemoryMarketPerception(MarketPerception):
    """
    In-memory stub for Phase 6 testing.
    Returns configurable mock data. Replace with real provider in Phase 7.

    Usage
    -----
        perception = InMemoryMarketPerception(mock_data={"price": 100.0})
        bundle     = await perception.fetch({"symbol": "TEST"})
    """

    def __init__(self, mock_data: Optional[Dict[str, Any]] = None):
        self._mock_data = mock_data or {"price": 0.0, "volume": 0, "change_pct": 0.0}
        self._available = True

    async def fetch(self, params: Dict[str, Any]) -> PerceptionBundle:
        start = time.monotonic()
        data  = {**self._mock_data, **params}   # merge params into mock data
        return PerceptionBundle(
            source="in_memory",
            data=data,
            success=self._available,
            error=None if self._available else "Source unavailable",
            latency_ms=round((time.monotonic() - start) * 1000, 2),
        )

    async def is_available(self) -> bool:
        return self._available

    def set_available(self, available: bool) -> None:
        self._available = available

    def set_mock_data(self, data: Dict[str, Any]) -> None:
        self._mock_data = data
