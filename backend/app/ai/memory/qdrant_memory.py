"""
app/ai/memory/qdrant_memory.py
===============================
QdrantLongTermMemory -- Phase 7A persistent memory implementation.

Drop-in replacement for InMemoryLongTermMemory. Implements the same
LongTermMemory ABC. No caller changes required.

Resilience contract (ADR-002):
  MR-1: Memory is optional. Trading engine never knows this exists.
  MR-2: store()/search()/get()/delete() never raise to caller.
        All failures return safe fallback values.
  MR-3: store() is best-effort. Failure logs and continues.
  MR-4: 200 ms read timeout. Exceeded → return empty result immediately.

Health integration:
  - Every operation reports success/failure to MemoryHealthMonitor.
  - Brain reads monitor.state to adjust retrieval strategy.
  - This class never reads the health state — it only reports to it.

Collections:
  - One Qdrant collection per instance (collection_name parameter).
  - Vectors: cosine distance, 384 dims (all-MiniLM-L6-v2).
  - Payload: all MemoryEntry fields except embedding.

Fallback:
  - If Qdrant is unavailable at construction, falls back to
    InMemoryLongTermMemory silently. Callers never see the difference.
"""
from __future__ import annotations

import asyncio
import logging
import time
import uuid
from typing import Any, Dict, List, Optional

from app.ai.memory.long_term import InMemoryLongTermMemory, LongTermMemory
from app.ai.memory.memory_health import MemoryHealthMonitor, MemoryHealthState
from app.ai.memory.short_term import MemoryEntry, MemoryRole

logger = logging.getLogger(__name__)

_VECTOR_DIM     = 384
_READ_TIMEOUT_S = 0.200   # ADR-002 MR-4: 200 ms


class QdrantLongTermMemory(LongTermMemory):
    """
    Qdrant-backed persistent long-term memory.

    Falls back to InMemoryLongTermMemory if Qdrant is unavailable.
    All public methods satisfy ADR-002 MR-2: they never raise.

    Usage
    -----
        monitor = MemoryHealthMonitor()
        ltm = QdrantLongTermMemory(
            url="http://localhost:6333",
            collection_name="trade_memory",
            health_monitor=monitor,
        )
        entry = MemoryEntry(content="RELIANCE breakout confirmed", importance=0.9)
        await ltm.store(entry)
        results = await ltm.search("RELIANCE breakout")
    """

    def __init__(
        self,
        url:             str                          = "http://localhost:6333",
        api_key:         Optional[str]                = None,
        collection_name: str                          = "jarvis_memory",
        vector_dim:      int                          = _VECTOR_DIM,
        health_monitor:  Optional[MemoryHealthMonitor] = None,
        importance_threshold: float                   = 0.6,
    ) -> None:
        self._url             = url
        self._api_key         = api_key
        self._collection      = collection_name
        self._vector_dim      = vector_dim
        self._monitor         = health_monitor or MemoryHealthMonitor()
        self._threshold       = importance_threshold
        self._client          = None
        self._fallback:       Optional[InMemoryLongTermMemory] = None
        self._using_fallback  = False
        self._size_cache      = 0

        self._init_client()

    # ── Initialisation ────────────────────────────────────────────────

    def _init_client(self) -> None:
        """Connect to Qdrant and ensure collection exists. Falls back on failure."""
        try:
            from qdrant_client import QdrantClient                          # type: ignore
            from qdrant_client.models import Distance, VectorParams        # type: ignore

            kwargs: Dict[str, Any] = {"url": self._url, "timeout": 5}
            if self._api_key:
                kwargs["api_key"] = self._api_key

            self._client = QdrantClient(**kwargs)

            # Create collection if it doesn't exist
            existing = [c.name for c in self._client.get_collections().collections]
            if self._collection not in existing:
                self._client.create_collection(
                    collection_name=self._collection,
                    vectors_config=VectorParams(
                        size=self._vector_dim,
                        distance=Distance.COSINE,
                    ),
                )
                logger.info("QdrantLongTermMemory: created collection '%s'", self._collection)
            else:
                logger.info("QdrantLongTermMemory: connected to collection '%s'", self._collection)

        except Exception as exc:
            logger.warning(
                "QdrantLongTermMemory: Qdrant unavailable (%s), using in-memory fallback",
                exc,
            )
            self._fallback      = InMemoryLongTermMemory(self._threshold)
            self._using_fallback = True
            self._monitor.record_failure("init failed")

    # ── LongTermMemory ABC ────────────────────────────────────────────

    async def store(self, entry: MemoryEntry) -> str:
        """
        Persist entry to Qdrant. Best-effort (MR-3): failure logs and returns id.
        Entries below importance_threshold are silently skipped.
        """
        if entry.importance < self._threshold:
            return entry.id

        if self._using_fallback:
            return await self._fallback.store(entry)  # type: ignore[union-attr]

        try:
            from qdrant_client.models import PointStruct  # type: ignore

            vector = entry.embedding or ([0.0] * self._vector_dim)
            payload = _entry_to_payload(entry)

            await asyncio.wait_for(
                asyncio.get_event_loop().run_in_executor(
                    None,
                    lambda: self._client.upsert(
                        collection_name=self._collection,
                        points=[PointStruct(id=_uuid_to_int(entry.id), vector=vector, payload=payload)],
                    ),
                ),
                timeout=_READ_TIMEOUT_S * 2,   # writes get double the read budget
            )
            self._size_cache += 1
            self._monitor.record_success()
            return entry.id

        except Exception as exc:
            logger.warning("QdrantLongTermMemory.store failed: %s", exc)
            self._monitor.record_failure(str(exc))
            return entry.id   # MR-3: never fail the caller

    async def search(self, query: str, top_k: int = 5) -> List[MemoryEntry]:
        """
        Keyword search (fallback) or vector search (when embedding provided).
        Returns [] on timeout or error (MR-2, MR-4).
        """
        if self._using_fallback:
            return await self._fallback.search(query, top_k)  # type: ignore[union-attr]

        try:
            # Keyword search via scroll + filter (no embedding available here)
            results = await asyncio.wait_for(
                asyncio.get_event_loop().run_in_executor(
                    None,
                    lambda: self._client.scroll(
                        collection_name=self._collection,
                        limit=top_k * 4,   # over-fetch then filter
                        with_payload=True,
                        with_vectors=False,
                    ),
                ),
                timeout=_READ_TIMEOUT_S,
            )
            points, _ = results
            q = query.lower()
            hits = [
                _payload_to_entry(p.payload)
                for p in points
                if q in (p.payload or {}).get("content", "").lower()
            ]
            hits.sort(key=lambda e: (e.importance, e.timestamp), reverse=True)
            self._monitor.record_success()
            return hits[:top_k]

        except asyncio.TimeoutError:
            logger.warning("QdrantLongTermMemory.search timed out (>%dms)", int(_READ_TIMEOUT_S * 1000))
            self._monitor.record_failure("read timeout")
            return []
        except Exception as exc:
            logger.warning("QdrantLongTermMemory.search failed: %s", exc)
            self._monitor.record_failure(str(exc))
            return []

    async def search_by_vector(
        self,
        vector: List[float],
        top_k:  int   = 5,
        score_threshold: float = 0.0,
    ) -> List[MemoryEntry]:
        """
        Semantic vector search. Returns [] on timeout or error (MR-2, MR-4).
        Called by MemoryPipelineProvider when embeddings are available.
        """
        if self._using_fallback:
            return []

        try:
            results = await asyncio.wait_for(
                asyncio.get_event_loop().run_in_executor(
                    None,
                    lambda: self._client.search(
                        collection_name=self._collection,
                        query_vector=vector,
                        limit=top_k,
                        score_threshold=score_threshold,
                        with_payload=True,
                    ),
                ),
                timeout=_READ_TIMEOUT_S,
            )
            self._monitor.record_success()
            return [_payload_to_entry(r.payload) for r in results if r.payload]

        except asyncio.TimeoutError:
            logger.warning("QdrantLongTermMemory.search_by_vector timed out")
            self._monitor.record_failure("read timeout")
            return []
        except Exception as exc:
            logger.warning("QdrantLongTermMemory.search_by_vector failed: %s", exc)
            self._monitor.record_failure(str(exc))
            return []

    async def get(self, entry_id: str) -> Optional[MemoryEntry]:
        """Retrieve one entry by id. Returns None on failure (MR-2)."""
        if self._using_fallback:
            return await self._fallback.get(entry_id)  # type: ignore[union-attr]

        try:
            results = await asyncio.wait_for(
                asyncio.get_event_loop().run_in_executor(
                    None,
                    lambda: self._client.retrieve(
                        collection_name=self._collection,
                        ids=[_uuid_to_int(entry_id)],
                        with_payload=True,
                    ),
                ),
                timeout=_READ_TIMEOUT_S,
            )
            if results and results[0].payload:
                self._monitor.record_success()
                return _payload_to_entry(results[0].payload)
            return None

        except Exception as exc:
            logger.warning("QdrantLongTermMemory.get failed: %s", exc)
            self._monitor.record_failure(str(exc))
            return None

    async def delete(self, entry_id: str) -> bool:
        """Delete one entry. Returns False on failure (MR-2)."""
        if self._using_fallback:
            return await self._fallback.delete(entry_id)  # type: ignore[union-attr]

        try:
            from qdrant_client.models import PointIdsList  # type: ignore

            await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: self._client.delete(
                    collection_name=self._collection,
                    points_selector=PointIdsList(points=[_uuid_to_int(entry_id)]),
                ),
            )
            self._size_cache = max(0, self._size_cache - 1)
            self._monitor.record_success()
            return True

        except Exception as exc:
            logger.warning("QdrantLongTermMemory.delete failed: %s", exc)
            self._monitor.record_failure(str(exc))
            return False

    async def all_entries(self) -> List[MemoryEntry]:
        """Return all stored entries. Returns [] on failure (MR-2)."""
        if self._using_fallback:
            return await self._fallback.all_entries()  # type: ignore[union-attr]

        try:
            results = await asyncio.wait_for(
                asyncio.get_event_loop().run_in_executor(
                    None,
                    lambda: self._client.scroll(
                        collection_name=self._collection,
                        limit=10_000,
                        with_payload=True,
                        with_vectors=False,
                    ),
                ),
                timeout=_READ_TIMEOUT_S,
            )
            points, _ = results
            self._monitor.record_success()
            return [_payload_to_entry(p.payload) for p in points if p.payload]

        except Exception as exc:
            logger.warning("QdrantLongTermMemory.all_entries failed: %s", exc)
            self._monitor.record_failure(str(exc))
            return []

    def size(self) -> int:
        """Approximate size. Uses cached count to avoid a network call."""
        if self._using_fallback:
            return self._fallback.size()  # type: ignore[union-attr]
        return self._size_cache

    # ── Introspection ─────────────────────────────────────────────────

    @property
    def health_monitor(self) -> MemoryHealthMonitor:
        return self._monitor

    @property
    def is_using_fallback(self) -> bool:
        return self._using_fallback

    @property
    def collection_name(self) -> str:
        return self._collection


# ── Payload helpers ───────────────────────────────────────────────────────────

def _entry_to_payload(entry: MemoryEntry) -> Dict[str, Any]:
    return {
        "entry_id":   entry.id,
        "content":    entry.content,
        "role":       entry.role.value,
        "importance": entry.importance,
        "timestamp":  entry.timestamp,
        "session_id": entry.session_id,
        "metadata":   entry.metadata,
    }


def _payload_to_entry(payload: Dict[str, Any]) -> MemoryEntry:
    return MemoryEntry(
        id         = payload.get("entry_id", str(uuid.uuid4())),
        content    = payload.get("content", ""),
        role       = MemoryRole(payload.get("role", "user")),
        importance = float(payload.get("importance", 0.5)),
        timestamp  = float(payload.get("timestamp", time.time())),
        session_id = payload.get("session_id", ""),
        metadata   = payload.get("metadata", {}),
    )


def _uuid_to_int(uid: str) -> int:
    """Convert UUID string to a positive integer for Qdrant point id."""
    return uuid.UUID(uid).int % (2 ** 63)
