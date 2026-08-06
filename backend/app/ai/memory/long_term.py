"""
app/ai/memory/long_term.py
===========================
LongTermMemory -- persistent memory store interface and in-memory implementation.

Design
------
  - LongTermMemory is an ABC. InMemoryLongTermMemory is the Phase 6 impl.
  - Phase 7+: swap InMemoryLongTermMemory for QdrantLongTermMemory without
    changing any caller -- the ABC is the contract.
  - Entries are stored with an importance score (0.0–1.0).
  - Only entries above importance_threshold are persisted (default 0.6).
  - Keyword search is provided by InMemoryLongTermMemory.
  - Semantic search (embedding-based) is wired in by MemoryPipelineProvider
    in __init__.py when EmbeddingService is available.

Domain agnosticism
-------------------
  No domain fields. All domain data lives in MemoryEntry.metadata.
"""
from __future__ import annotations

import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from app.ai.memory.short_term import MemoryEntry, MemoryRole


# ── LongTermMemory ABC ────────────────────────────────────────────────────────

class LongTermMemory(ABC):
    """
    Interface for persistent memory storage.

    Implementations must be swappable without changing callers.
    Phase 6: InMemoryLongTermMemory.
    Phase 7+: QdrantLongTermMemory (vector DB).
    """

    @abstractmethod
    async def store(self, entry: MemoryEntry) -> str:
        """Persist one entry. Returns its id."""

    @abstractmethod
    async def search(self, query: str, top_k: int = 5) -> List[MemoryEntry]:
        """Keyword or semantic search. Returns up to top_k entries."""

    @abstractmethod
    async def get(self, entry_id: str) -> Optional[MemoryEntry]:
        """Retrieve one entry by id. Returns None if not found."""

    @abstractmethod
    async def delete(self, entry_id: str) -> bool:
        """Delete one entry. Returns True if it existed."""

    @abstractmethod
    async def all_entries(self) -> List[MemoryEntry]:
        """Return all stored entries (for testing and export)."""

    @abstractmethod
    def size(self) -> int:
        """Number of stored entries."""


# ── SearchResult ──────────────────────────────────────────────────────────────

@dataclass
class SearchResult:
    """One result from a memory search, with relevance score."""
    entry:   MemoryEntry
    score:   float          # 0.0 (irrelevant) to 1.0 (exact match)
    matched: str            = ""   # which field matched (for debugging)


# ── InMemoryLongTermMemory ────────────────────────────────────────────────────

class InMemoryLongTermMemory(LongTermMemory):
    """
    In-memory dict-backed LongTermMemory.

    Suitable for Phase 6 and testing. Replace with QdrantLongTermMemory
    in Phase 7 without changing any caller.

    Importance threshold
    --------------------
    Only entries with importance >= importance_threshold are stored.
    Callers below the threshold receive the entry id but nothing is persisted.
    This prevents low-value ephemeral data from polluting long-term memory.

    Usage
    -----
        ltm = InMemoryLongTermMemory(importance_threshold=0.6)
        entry = MemoryEntry(content="User prefers concise answers", importance=0.8)
        await ltm.store(entry)
        results = await ltm.search("concise")
    """

    def __init__(self, importance_threshold: float = 0.6):
        if not (0.0 <= importance_threshold <= 1.0):
            raise ValueError("importance_threshold must be in [0.0, 1.0]")
        self._threshold = importance_threshold
        self._store: Dict[str, MemoryEntry] = {}

    # ── Write ─────────────────────────────────────────────────────────

    async def store(self, entry: MemoryEntry) -> str:
        """
        Store entry if importance >= threshold.
        Always returns entry.id so callers don't need to branch.
        """
        if entry.importance >= self._threshold:
            self._store[entry.id] = entry
        return entry.id

    async def delete(self, entry_id: str) -> bool:
        if entry_id in self._store:
            del self._store[entry_id]
            return True
        return False

    # ── Read ──────────────────────────────────────────────────────────

    async def search(self, query: str, top_k: int = 5) -> List[MemoryEntry]:
        """
        Case-insensitive keyword search over content.
        Results are sorted by importance (descending), then recency.
        For semantic search, use EmbeddingService.top_k() directly.
        """
        q = query.lower()
        hits = [
            e for e in self._store.values()
            if q in e.content.lower()
        ]
        hits.sort(key=lambda e: (e.importance, e.timestamp), reverse=True)
        return hits[:top_k]

    async def get(self, entry_id: str) -> Optional[MemoryEntry]:
        return self._store.get(entry_id)

    async def all_entries(self) -> List[MemoryEntry]:
        return list(self._store.values())

    def size(self) -> int:
        return len(self._store)

    # ── Introspection ─────────────────────────────────────────────────

    @property
    def importance_threshold(self) -> float:
        return self._threshold

    def stats(self) -> Dict[str, Any]:
        entries = list(self._store.values())
        if not entries:
            return {"size": 0, "avg_importance": 0.0, "threshold": self._threshold}
        avg_imp = sum(e.importance for e in entries) / len(entries)
        return {
            "size":           len(entries),
            "avg_importance": round(avg_imp, 3),
            "threshold":      self._threshold,
        }
