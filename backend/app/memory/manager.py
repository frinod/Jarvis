"""JARVIS OS - Memory Subsystem"""
from __future__ import annotations
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any, List, Optional
from uuid import uuid4


class MemoryType(str, Enum):
    EPISODIC = "episodic"
    SEMANTIC = "semantic"
    PROCEDURAL = "procedural"
    EMOTIONAL = "emotional"


@dataclass
class MemoryEntry:
    id: str
    type: MemoryType
    content: str
    metadata: dict
    importance: float  # 0-1
    timestamp: datetime
    embedding: Optional[list] = None
    tags: Optional[List[str]] = None

    def __post_init__(self):
        if self.tags is None:
            self.tags = []


class MemoryStore(ABC):
    @abstractmethod
    async def store(self, entry: MemoryEntry) -> str:
        pass

    @abstractmethod
    async def retrieve(self, query: str, top_k: int = 5) -> "List[MemoryEntry]":
        pass

    @abstractmethod
    async def search_by_type(self, mem_type: MemoryType, limit: int = 10) -> "List[MemoryEntry]":
        pass


class MemoryManager:
    """Orchestrates all memory subsystems."""

    def __init__(self, vector_store=None, db_session=None):
        self.vector_store = vector_store
        self.db_session = db_session
        self._short_term: List[MemoryEntry] = []
        self._max_short_term = 50

    async def remember(self, content: str, mem_type: MemoryType,
                       importance: float = 0.5, metadata: dict = None) -> str:
        entry = MemoryEntry(
            id=str(uuid4()),
            type=mem_type,
            content=content,
            metadata=metadata or {},
            importance=importance,
            timestamp=datetime.utcnow()
        )
        self._short_term.append(entry)
        if len(self._short_term) > self._max_short_term:
            self._short_term.pop(0)

        if self.vector_store:
            await self.vector_store.store(entry)
        return entry.id

    async def recall(self, query: str, top_k: int = 5) -> List[MemoryEntry]:
        if self.vector_store:
            return await self.vector_store.retrieve(query, top_k)
        # Fallback: search short-term memory
        return [m for m in self._short_term if query.lower() in m.content.lower()][:top_k]

    async def get_conversation_context(self, last_n: int = 10) -> List[MemoryEntry]:
        episodic = [m for m in self._short_term if m.type == MemoryType.EPISODIC]
        return episodic[-last_n:]

    async def get_user_preferences(self) -> List[MemoryEntry]:
        return [m for m in self._short_term if m.type == MemoryType.PROCEDURAL]

    def get_short_term_summary(self) -> dict:
        return {
            "total": len(self._short_term),
            "by_type": {t.value: sum(1 for m in self._short_term if m.type == t)
                        for t in MemoryType}
        }
