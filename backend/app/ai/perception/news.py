"""
app/ai/perception/news.py
==========================
NewsPerception -- news and sentiment data provider interface and stub.

Design
------
  - NewsPerception is an ABC. InMemoryNewsPerception is the Phase 6 stub.
  - Phase 7+: swap for a real news provider (NewsAPI, RSS, etc.)
  - NewsItem is a plain dataclass -- no domain-specific fields beyond
    what any news item would have.
"""
from __future__ import annotations

import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


# ── NewsItem ──────────────────────────────────────────────────────────────────

@dataclass
class NewsItem:
    """One news article or headline."""
    title:     str
    summary:   str            = ""
    source:    str            = ""
    url:       str            = ""
    timestamp: float          = field(default_factory=time.time)
    sentiment: float          = 0.0   # -1.0 (negative) to +1.0 (positive)
    metadata:  Dict[str, Any] = field(default_factory=dict)


# ── NewsPerception ABC ────────────────────────────────────────────────────────

class NewsPerception(ABC):
    """
    Interface for news data retrieval.
    Phase 6: InMemoryNewsPerception (stub).
    Phase 7+: real provider.
    """

    @abstractmethod
    async def fetch(self, params: Dict[str, Any]) -> List[NewsItem]:
        """
        Fetch news items for the given params.
        params may contain: query, limit, from_date, etc.
        """

    @abstractmethod
    async def is_available(self) -> bool:
        """Return True if the news source is reachable."""


# ── InMemoryNewsPerception ────────────────────────────────────────────────────

class InMemoryNewsPerception(NewsPerception):
    """
    In-memory stub for Phase 6 testing.
    Returns configurable mock news items.
    """

    def __init__(self, mock_items: Optional[List[NewsItem]] = None):
        self._items     = mock_items or []
        self._available = True

    async def fetch(self, params: Dict[str, Any]) -> List[NewsItem]:
        if not self._available:
            return []
        limit = params.get("limit", 10)
        return self._items[:limit]

    async def is_available(self) -> bool:
        return self._available

    def set_available(self, available: bool) -> None:
        self._available = available

    def add_item(self, item: NewsItem) -> None:
        self._items.append(item)
