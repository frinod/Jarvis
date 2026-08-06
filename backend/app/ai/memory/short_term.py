"""
app/ai/memory/short_term.py
============================
ShortTermMemory -- in-process ring buffer for recent conversation turns
and transient facts.

Design
------
  - Fixed-capacity ring buffer backed by collections.deque(maxlen=50).
  - Entries are evicted oldest-first when capacity is reached.
  - Keyword search over content (no embeddings -- that is EmbeddingService).
  - MemoryPipelineAdapter bridges to PipelineMemoryProvider so
    ExecutionEngine can inject short-term context without knowing the
    concrete implementation.

Domain agnosticism
-------------------
  No domain fields. All domain data lives in MemoryEntry.metadata.
"""
from __future__ import annotations

import time
import uuid
from collections import deque
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

from app.ai.runtime.context import ExecutionContext
from app.ai.runtime.execution import PipelineMemoryProvider


# ── Memory entry ──────────────────────────────────────────────────────────────

class MemoryRole(str, Enum):
    USER      = "user"
    ASSISTANT = "assistant"
    SYSTEM    = "system"
    TOOL      = "tool"


@dataclass
class MemoryEntry:
    """
    One item stored in memory.

    content    -- the text to remember
    role       -- who produced this content
    importance -- 0.0 (ephemeral) to 1.0 (critical); used by LongTermMemory
                  to decide whether to persist
    embedding  -- populated by EmbeddingService when similarity search is needed
    metadata   -- domain escape hatch; never add domain fields here
    """
    id:         str            = field(default_factory=lambda: str(uuid.uuid4()))
    content:    str            = ""
    role:       MemoryRole     = MemoryRole.USER
    importance: float          = 0.5
    timestamp:  float          = field(default_factory=time.time)
    session_id: str            = ""
    embedding:  Optional[List[float]] = None
    metadata:   Dict[str, Any] = field(default_factory=dict)

    def age_seconds(self) -> float:
        return time.time() - self.timestamp


# ── ShortTermMemory ───────────────────────────────────────────────────────────

class ShortTermMemory:
    """
    Fixed-capacity ring buffer for recent conversation turns.

    Capacity defaults to 50 entries (architecture §7).
    When full, the oldest entry is silently evicted.

    Usage
    -----
        stm = ShortTermMemory()
        stm.add("What is the weather?", role=MemoryRole.USER, session_id="s1")
        stm.add("It is sunny.",         role=MemoryRole.ASSISTANT, session_id="s1")
        recent = stm.recent(n=5)
        hits   = stm.search("weather")
    """

    MAX_CAPACITY = 50

    def __init__(self, capacity: int = MAX_CAPACITY):
        if capacity < 1:
            raise ValueError(f"capacity must be >= 1, got {capacity}")
        self._capacity = capacity
        self._buffer: deque[MemoryEntry] = deque(maxlen=capacity)

    # ── Write ─────────────────────────────────────────────────────────

    def add(
        self,
        content:    str,
        role:       MemoryRole     = MemoryRole.USER,
        session_id: str            = "",
        importance: float          = 0.5,
        metadata:   Optional[Dict[str, Any]] = None,
    ) -> MemoryEntry:
        """Add one entry. Returns the stored MemoryEntry."""
        entry = MemoryEntry(
            content=content,
            role=role,
            session_id=session_id,
            importance=importance,
            metadata=metadata or {},
        )
        self._buffer.append(entry)
        return entry

    def add_entry(self, entry: MemoryEntry) -> None:
        """Add a pre-built MemoryEntry directly."""
        self._buffer.append(entry)

    def clear(self, session_id: Optional[str] = None) -> int:
        """
        Clear entries. If session_id given, remove only that session's entries.
        Returns number of entries removed.
        """
        if session_id is None:
            count = len(self._buffer)
            self._buffer.clear()
            return count

        before = len(self._buffer)
        kept = [e for e in self._buffer if e.session_id != session_id]
        self._buffer.clear()
        self._buffer.extend(kept)
        return before - len(self._buffer)

    # ── Read ──────────────────────────────────────────────────────────

    def recent(self, n: int = 10, session_id: Optional[str] = None) -> List[MemoryEntry]:
        """Return the n most recent entries, optionally filtered by session."""
        entries = list(self._buffer)
        if session_id is not None:
            entries = [e for e in entries if e.session_id == session_id]
        return entries[-n:]

    def search(
        self,
        query:      str,
        session_id: Optional[str] = None,
        top_k:      int           = 5,
    ) -> List[MemoryEntry]:
        """
        Keyword search over content (case-insensitive substring match).
        Returns up to top_k most recent matches.
        For semantic search, use EmbeddingService.
        """
        q = query.lower()
        entries = list(self._buffer)
        if session_id is not None:
            entries = [e for e in entries if e.session_id == session_id]
        hits = [e for e in entries if q in e.content.lower()]
        return hits[-top_k:]

    def all_entries(self, session_id: Optional[str] = None) -> List[MemoryEntry]:
        """Return all entries, optionally filtered by session."""
        entries = list(self._buffer)
        if session_id is not None:
            return [e for e in entries if e.session_id == session_id]
        return entries

    # ── Introspection ─────────────────────────────────────────────────

    @property
    def size(self) -> int:
        return len(self._buffer)

    @property
    def capacity(self) -> int:
        return self._capacity

    @property
    def is_full(self) -> bool:
        return len(self._buffer) == self._capacity

    def stats(self) -> Dict[str, Any]:
        entries = list(self._buffer)
        by_role = {}
        for e in entries:
            by_role[e.role.value] = by_role.get(e.role.value, 0) + 1
        return {
            "size":     len(entries),
            "capacity": self._capacity,
            "is_full":  self.is_full,
            "by_role":  by_role,
        }


# ── PipelineMemoryProvider adapter ───────────────────────────────────────────

class ShortTermMemoryAdapter(PipelineMemoryProvider):
    """
    Bridges ShortTermMemory to the PipelineMemoryProvider ABC so
    ExecutionEngine can load memory context without knowing the
    concrete implementation.

    Injects ctx.memory_context with recent entries for the session.
    Also records the user turn into short-term memory.
    """

    def __init__(self, memory: ShortTermMemory, max_turns: int = 10):
        self._memory    = memory
        self._max_turns = max_turns

    async def load(self, ctx: ExecutionContext) -> None:
        # Store the current user turn
        self._memory.add(
            content=ctx.user_input,
            role=MemoryRole.USER,
            session_id=ctx.session_id,
        )
        # Inject recent turns as memory context
        ctx.memory_context = self._memory.recent(
            n=self._max_turns,
            session_id=ctx.session_id or None,
        )
