"""
app/ai/memory/__init__.py
=========================
Memory package public API.

Exports
-------
  MemoryEntry, MemoryRole          -- shared data model
  ShortTermMemory                  -- ring buffer
  ShortTermMemoryAdapter           -- PipelineMemoryProvider for short-term only
  LongTermMemory                   -- ABC
  InMemoryLongTermMemory           -- Phase 6 implementation (testing / fallback)
  QdrantLongTermMemory             -- Phase 7A implementation (persistent)
  SearchResult                     -- search result with score
  EmbeddingService                 -- ABC
  SimpleEmbeddingService           -- Phase 6 implementation (testing / fallback)
  SentenceTransformerEmbeddingService -- Phase 7A implementation (semantic)
  MemoryHealthMonitor              -- health state machine (ADR-002)
  MemoryHealthState                -- Healthy/Degraded/Offline/Recovering
  MemoryPipelineProvider           -- full provider: STM + LTM + embeddings

MemoryPipelineProvider
-----------------------
  Wires ShortTermMemory + LongTermMemory + EmbeddingService into one
  PipelineMemoryProvider. Injected into ExecutionEngine as the memory
  collaborator.

  On every request:
    1. Records user turn in ShortTermMemory.
    2. Retrieves recent turns from ShortTermMemory.
    3. Performs semantic search in LongTermMemory (if embeddings enabled).
       Uses search_by_vector() when QdrantLongTermMemory is present.
    4. Merges results into ctx.memory_context (STM first, then LTM hits).
    5. Respects MemoryHealthMonitor state: skips LTM when Offline.
"""
from __future__ import annotations

from typing import List, Optional

from app.ai.memory.short_term import MemoryEntry, MemoryRole, ShortTermMemory, ShortTermMemoryAdapter
from app.ai.memory.long_term import InMemoryLongTermMemory, LongTermMemory, SearchResult
from app.ai.memory.embeddings import EmbeddingService, SimpleEmbeddingService
from app.ai.memory.memory_health import MemoryHealthMonitor, MemoryHealthState
from app.ai.memory.qdrant_memory import QdrantLongTermMemory
from app.ai.memory.sentence_transformer_embeddings import SentenceTransformerEmbeddingService
from app.ai.runtime.context import ExecutionContext
from app.ai.runtime.execution import PipelineMemoryProvider


class MemoryPipelineProvider(PipelineMemoryProvider):
    """
    Full memory provider: ShortTermMemory + LongTermMemory + EmbeddingService.

    Injected into ExecutionEngine as the memory collaborator.
    All three components are optional -- the provider degrades gracefully
    when only some are present.

    Usage
    -----
        stm = ShortTermMemory()
        ltm = InMemoryLongTermMemory()
        emb = SimpleEmbeddingService()
        provider = MemoryPipelineProvider(stm, ltm, emb)
        engine   = ExecutionEngine(gateway=gw, memory=provider)
    """

    def __init__(
        self,
        short_term:  Optional[ShortTermMemory]    = None,
        long_term:   Optional[LongTermMemory]     = None,
        embeddings:  Optional[EmbeddingService]   = None,
        max_turns:   int                          = 10,
        ltm_top_k:   int                          = 5,
        ltm_min_score: float                      = 0.3,
    ):
        self._stm          = short_term or ShortTermMemory()
        self._ltm          = long_term
        self._emb          = embeddings
        self._max_turns    = max_turns
        self._ltm_top_k    = ltm_top_k
        self._ltm_min_score = ltm_min_score

    async def load(self, ctx: ExecutionContext) -> None:
        """
        1. Record user turn in ShortTermMemory.
        2. Load recent turns from ShortTermMemory.
        3. Semantic or keyword search in LongTermMemory.
           - Skipped entirely when health state is Offline.
           - Uses search_by_vector() for QdrantLongTermMemory + embeddings.
           - Falls back to keyword search when no embeddings.
        4. Merge into ctx.memory_context (STM first, then LTM hits).
        """
        # 1. Record current user turn
        self._stm.add(
            content=ctx.user_input,
            role=MemoryRole.USER,
            session_id=ctx.session_id,
        )

        # 2. Recent short-term turns
        recent: List[MemoryEntry] = self._stm.recent(
            n=self._max_turns,
            session_id=ctx.session_id or None,
        )

        # 3. Long-term search — respect health state
        ltm_hits: List[MemoryEntry] = []
        if self._ltm is not None and self._health_available():
            try:
                if self._emb is not None:
                    # Semantic path: encode query, use vector search if Qdrant
                    q_vec = self._emb.encode(ctx.user_input)
                    if hasattr(self._ltm, "search_by_vector"):
                        ltm_hits = await self._ltm.search_by_vector(  # type: ignore[attr-defined]
                            vector=q_vec,
                            top_k=self._ltm_top_k,
                            score_threshold=self._ltm_min_score,
                        )
                    else:
                        all_ltm = await self._ltm.all_entries()
                        if all_ltm:
                            scored = self._emb.top_k(
                                query=ctx.user_input,
                                entries=all_ltm,
                                k=self._ltm_top_k,
                                min_score=self._ltm_min_score,
                            )
                            ltm_hits = [entry for entry, _ in scored]
                else:
                    # Keyword fallback
                    ltm_hits = await self._ltm.search(ctx.user_input, top_k=self._ltm_top_k)
            except Exception:
                ltm_hits = []   # MR-2: never propagate

        # 4. Merge: recent STM turns + LTM hits (deduplicated by id)
        seen = {e.id for e in recent}
        merged = list(recent)
        for entry in ltm_hits:
            if entry.id not in seen:
                merged.append(entry)
                seen.add(entry.id)

        ctx.memory_context = merged

    def _health_available(self) -> bool:
        """Return True when LTM should be queried based on health state."""
        if self._ltm is None:
            return False
        monitor = getattr(self._ltm, "health_monitor", None)
        if monitor is None:
            return True   # non-Qdrant LTM has no health monitor, always available
        return monitor.is_available

    # ── Accessors (for Brain and tests) ──────────────────────────────

    @property
    def short_term(self) -> ShortTermMemory:
        return self._stm

    @property
    def long_term(self) -> Optional[LongTermMemory]:
        return self._ltm

    @property
    def embeddings(self) -> Optional[EmbeddingService]:
        return self._emb


__all__ = [
    "MemoryEntry",
    "MemoryRole",
    "ShortTermMemory",
    "ShortTermMemoryAdapter",
    "LongTermMemory",
    "InMemoryLongTermMemory",
    "QdrantLongTermMemory",
    "SearchResult",
    "EmbeddingService",
    "SimpleEmbeddingService",
    "SentenceTransformerEmbeddingService",
    "MemoryHealthMonitor",
    "MemoryHealthState",
    "MemoryPipelineProvider",
]
