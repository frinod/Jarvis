"""
app/ai/perception/sentiment.py
================================
SentimentPerception -- aggregate sentiment scoring from news and other sources.

Design
------
  - SentimentScore is a plain dataclass with a -1.0 to +1.0 score.
  - SentimentPerception ABC + InMemorySentimentPerception stub.
  - Aggregation logic: mean of news item sentiments, clamped to [-1, 1].
"""
from __future__ import annotations

import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from app.ai.perception.news import NewsItem


# ── SentimentScore ────────────────────────────────────────────────────────────

@dataclass
class SentimentScore:
    """Aggregate sentiment for a topic or query."""
    score:      float          # -1.0 (very negative) to +1.0 (very positive)
    label:      str            # "positive", "neutral", "negative"
    confidence: float          = 0.5
    sample_size: int           = 0
    timestamp:  float          = field(default_factory=time.time)
    metadata:   Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_score(cls, score: float, sample_size: int = 0) -> "SentimentScore":
        label = "positive" if score > 0.1 else "negative" if score < -0.1 else "neutral"
        return cls(score=round(score, 3), label=label, sample_size=sample_size)


# ── SentimentPerception ABC ───────────────────────────────────────────────────

class SentimentPerception(ABC):
    """Interface for sentiment scoring."""

    @abstractmethod
    async def score(self, params: Dict[str, Any]) -> SentimentScore:
        """Compute aggregate sentiment for the given params."""

    @abstractmethod
    async def is_available(self) -> bool:
        pass


# ── InMemorySentimentPerception ───────────────────────────────────────────────

class InMemorySentimentPerception(SentimentPerception):
    """
    Computes sentiment by averaging NewsItem.sentiment values.
    Phase 7+: replace with a real NLP sentiment model.
    """

    def __init__(self, news_items: Optional[List[NewsItem]] = None):
        self._items     = news_items or []
        self._available = True

    async def score(self, params: Dict[str, Any]) -> SentimentScore:
        if not self._items:
            return SentimentScore.from_score(0.0, sample_size=0)
        scores = [item.sentiment for item in self._items]
        avg    = sum(scores) / len(scores)
        avg    = max(-1.0, min(1.0, avg))
        return SentimentScore.from_score(avg, sample_size=len(scores))

    async def is_available(self) -> bool:
        return self._available

    def set_items(self, items: List[NewsItem]) -> None:
        self._items = items
