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

# Phase 7B RAG components (optional — degrade gracefully if absent)
try:
    from app.ai.rag.retriever import Retriever, HybridRetriever, RetrievalResult
    from app.ai.rag.reranker import BaseReranker, NoOpReranker
    from app.ai.rag.context_builder import ContextBuilder, ContextAssembly
    from app.ai.rag.semantic_cache import SemanticCache
    _RAG_AVAILABLE = True
except ImportError:
    _RAG_AVAILABLE = False


class MemoryPipelineProvider(PipelineMemoryProvider):
    """
    Full memory provider: ShortTermMemory + LongTermMemory + EmbeddingService.
    Phase 7B: optionally wired with Retriever, Reranker, ContextBuilder, SemanticCache.

    When RAG components are present:
      - SemanticCache is checked first (exact then semantic)
      - Retriever (HybridRetriever by default) fetches candidates
      - Reranker re-scores candidates
      - ContextBuilder assembles token-budgeted ContextAssembly
      - ContextAssembly stored in ctx.metadata["_rag_context"] for SystemPromptBuilder

    When RAG components are absent (or LTM is Offline):
      - Falls back to Phase 6 STM-only behaviour

    Usage
    -----
        provider = MemoryPipelineProvider(
            short_term=stm, long_term=qdrant_ltm, embeddings=st_emb,
            retriever=Retriever(HybridRetriever(qdrant_ltm, st_emb)),
            reranker=NoOpReranker(),
            context_builder=ContextBuilder(),
            semantic_cache=SemanticCache(st_emb),
        )
    """

    def __init__(
        self,
        short_term:      Optional[ShortTermMemory]    = None,
        long_term:       Optional[LongTermMemory]     = None,
        embeddings:      Optional[EmbeddingService]   = None,
        max_turns:       int                          = 10,
        ltm_top_k:       int                          = 5,
        ltm_min_score:   float                        = 0.3,
        # Phase 7B RAG components
        retriever:       Optional[object]             = None,
        reranker:        Optional[object]             = None,
        context_builder: Optional[object]             = None,
        semantic_cache:  Optional[object]             = None,
    ):
        self._stm            = short_term or ShortTermMemory()
        self._ltm            = long_term
        self._emb            = embeddings
        self._max_turns      = max_turns
        self._ltm_top_k      = ltm_top_k
        self._ltm_min_score  = ltm_min_score
        self._retriever      = retriever
        self._reranker       = reranker
        self._context_builder = context_builder
        self._semantic_cache = semantic_cache

    async def load(self, ctx: ExecutionContext) -> None:
        """
        1. Record user turn in ShortTermMemory.
        2. Load recent turns from ShortTermMemory.
        3. RAG path (Phase 7B): cache → retriever → reranker → context builder.
           Falls back to Phase 6 path when RAG components absent or LTM offline.
        4. Merge into ctx.memory_context; store ContextAssembly in ctx.metadata.
        """
        # 1. Record current user turn
        self._stm.add(content=ctx.user_input, role=MemoryRole.USER, session_id=ctx.session_id)

        # 2. Recent short-term turns
        recent: List[MemoryEntry] = self._stm.recent(n=self._max_turns, session_id=ctx.session_id or None)

        # 3. LTM retrieval
        ltm_hits: List[MemoryEntry] = []
        if self._ltm is not None and self._health_available():
            try:
                if _RAG_AVAILABLE and self._retriever is not None:
                    ltm_hits = await self._rag_retrieve(ctx)
                else:
                    ltm_hits = await self._legacy_retrieve(ctx)
            except Exception:
                ltm_hits = []

        # 4. Merge STM + LTM (deduplicated)
        seen   = {e.id for e in recent}
        merged = list(recent)
        for entry in ltm_hits:
            if isinstance(entry, MemoryEntry) and entry.id not in seen:
                merged.append(entry)
                seen.add(entry.id)

        ctx.memory_context = merged

    async def _rag_retrieve(self, ctx: ExecutionContext) -> List[MemoryEntry]:
        """Full Phase 7B RAG path: cache → retriever → reranker → context builder."""
        query = ctx.user_input

        # Semantic cache check
        if self._semantic_cache is not None:
            cached = self._semantic_cache.get(query)
            if cached is not None:
                if self._context_builder is not None:
                    assembly = self._context_builder.build(
                        cached.entries, query=query,
                        metrics={**vars(cached), "cache_hit": True},
                    )
                    ctx.metadata["_rag_context"] = assembly
                return cached.entries

        # Retrieval
        result = await self._retriever.retrieve(query, top_k=self._ltm_top_k * 2)  # type: ignore[union-attr]

        # Reranking
        entries = result.entries
        if self._reranker is not None and entries:
            entries = self._reranker.rerank(query, entries, top_k=self._ltm_top_k)

        # Context assembly
        if self._context_builder is not None:
            metrics = {
                "dense_count":   result.dense_count,
                "keyword_count": result.keyword_count,
                "merged_count":  result.merged_count,
                "cache_hit":     False,
                "latency_ms":    result.latency_ms,
            }
            assembly = self._context_builder.build(entries, query=query, metrics=metrics)
            ctx.metadata["_rag_context"] = assembly

        # Cache the result
        if self._semantic_cache is not None:
            is_market = any(
                e.metadata.get("entry_type") in ("market_snapshot", "news")
                for e in entries if isinstance(e, MemoryEntry)
            )
            self._semantic_cache.put(query, result, is_market=is_market)

        return entries

    async def _legacy_retrieve(self, ctx: ExecutionContext) -> List[MemoryEntry]:
        """Phase 6 retrieval path — used when RAG components are absent."""
        if self._emb is not None:
            if hasattr(self._ltm, "search_by_vector"):
                q_vec = self._emb.encode(ctx.user_input)
                return await self._ltm.search_by_vector(vector=q_vec, top_k=self._ltm_top_k, score_threshold=self._ltm_min_score)  # type: ignore[union-attr]
            all_ltm = await self._ltm.all_entries()  # type: ignore[union-attr]
            if all_ltm:
                scored = self._emb.top_k(query=ctx.user_input, entries=all_ltm, k=self._ltm_top_k, min_score=self._ltm_min_score)
                return [e for e, _ in scored]
        return await self._ltm.search(ctx.user_input, top_k=self._ltm_top_k)  # type: ignore[union-attr]

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
