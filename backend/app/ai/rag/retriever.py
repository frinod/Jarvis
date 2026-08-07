"""
app/ai/rag/retriever.py
========================
Retriever -- pluggable retrieval strategies for the RAG pipeline.

Architecture (per review):
    Retriever (facade)
        └── RetrievalStrategy (ABC)
                ├── DenseRetriever      -- vector similarity
                ├── KeywordRetriever    -- BM25-style keyword
                └── HybridRetriever    -- RRF merge of dense + keyword (default)

Future strategies (Phase 8+) plug in without changing any caller:
    GraphRetriever, WebRetriever, etc.

Resilience (Rule 11b):
    All strategies catch their own exceptions and return [] on failure.

Retrieval metrics:
    Every retrieve() returns a RetrievalResult with counts for
    debugging, optimisation, and explainability (Phase 7D).
"""
from __future__ import annotations

import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List, Optional

from app.ai.memory.long_term import LongTermMemory
from app.ai.memory.short_term import MemoryEntry
from app.ai.memory.embeddings import EmbeddingService


# ── Retrieval result ──────────────────────────────────────────────────────────

@dataclass
class RetrievalResult:
    """
    Output of one retrieve() call with entries and pipeline metrics.
    Metrics are used for debugging and XAI — never exposed to the trading engine.
    """
    entries:       List[MemoryEntry]
    strategy:      str   = ""
    dense_count:   int   = 0
    keyword_count: int   = 0
    merged_count:  int   = 0
    final_count:   int   = 0
    cache_hit:     bool  = False
    latency_ms:    float = 0.0

    def __post_init__(self):
        self.final_count = len(self.entries)


# ── RetrievalStrategy ABC ─────────────────────────────────────────────────────

class RetrievalStrategy(ABC):
    """
    Interface for all retrieval strategies. Implementations are swappable
    without changing Retriever callers. All must catch their own exceptions
    and return RetrievalResult(entries=[]) on failure (Rule 11b).
    """

    @abstractmethod
    async def retrieve(
        self,
        query:   str,
        top_k:   int = 5,
        filters: Optional[dict] = None,
    ) -> RetrievalResult:
        """
        Retrieve up to top_k entries relevant to query.
        filters: optional metadata dict, e.g. {"entry_type": "market_snapshot"}.
        Never raises.
        """


# ── DenseRetriever ────────────────────────────────────────────────────────────

class DenseRetriever(RetrievalStrategy):
    """
    Vector similarity retrieval via LTM.search_by_vector().
    Falls back to LTM.search() when embeddings are unavailable.
    """

    def __init__(self, ltm: LongTermMemory, embeddings: Optional[EmbeddingService] = None) -> None:
        self._ltm = ltm
        self._emb = embeddings

    async def retrieve(self, query: str, top_k: int = 5, filters: Optional[dict] = None) -> RetrievalResult:
        t0 = time.monotonic()
        try:
            if self._emb is not None and hasattr(self._ltm, "search_by_vector"):
                vec     = self._emb.encode(query)
                entries = await self._ltm.search_by_vector(vector=vec, top_k=top_k, score_threshold=0.0)  # type: ignore[attr-defined]
            else:
                entries = await self._ltm.search(query, top_k=top_k)
            entries = _apply_filters(entries, filters)
            return RetrievalResult(entries=entries[:top_k], strategy="dense", dense_count=len(entries), latency_ms=_ms(t0))
        except Exception:
            return RetrievalResult(entries=[], strategy="dense", latency_ms=_ms(t0))


# ── KeywordRetriever ──────────────────────────────────────────────────────────

class KeywordRetriever(RetrievalStrategy):
    """BM25-style keyword retrieval via LongTermMemory.search(). No embedding required."""

    def __init__(self, ltm: LongTermMemory) -> None:
        self._ltm = ltm

    async def retrieve(self, query: str, top_k: int = 5, filters: Optional[dict] = None) -> RetrievalResult:
        t0 = time.monotonic()
        try:
            entries = await self._ltm.search(query, top_k=top_k * 2)
            entries = _apply_filters(entries, filters)
            return RetrievalResult(entries=entries[:top_k], strategy="keyword", keyword_count=len(entries), latency_ms=_ms(t0))
        except Exception:
            return RetrievalResult(entries=[], strategy="keyword", latency_ms=_ms(t0))


# ── HybridRetriever ───────────────────────────────────────────────────────────

class HybridRetriever(RetrievalStrategy):
    """
    Hybrid retrieval: dense + keyword merged with Reciprocal Rank Fusion (RRF).

    RRF formula: score(d) = Σ 1 / (k + rank(d))  where k=60 (standard).
    Entries in both result sets receive a higher combined score.
    Default strategy for Phase 7B (ADR-003).
    """

    RRF_K = 60

    def __init__(
        self,
        ltm:        LongTermMemory,
        embeddings: Optional[EmbeddingService] = None,
        fetch_k:    int = 20,
    ) -> None:
        self._dense   = DenseRetriever(ltm, embeddings)
        self._keyword = KeywordRetriever(ltm)
        self._fetch_k = fetch_k

    async def retrieve(self, query: str, top_k: int = 5, filters: Optional[dict] = None) -> RetrievalResult:
        t0 = time.monotonic()
        dense_res   = await self._dense.retrieve(query, top_k=self._fetch_k, filters=filters)
        keyword_res = await self._keyword.retrieve(query, top_k=self._fetch_k, filters=filters)
        merged = _rrf_merge(dense_res.entries, keyword_res.entries, k=self.RRF_K)
        return RetrievalResult(
            entries=merged[:top_k],
            strategy="hybrid",
            dense_count=len(dense_res.entries),
            keyword_count=len(keyword_res.entries),
            merged_count=len(merged),
            latency_ms=_ms(t0),
        )


# ── Retriever (facade) ────────────────────────────────────────────────────────

class Retriever:
    """
    Facade over a pluggable RetrievalStrategy.

    Brain and MemoryPipelineProvider call Retriever.retrieve().
    Swap strategies without changing any caller.

    Usage
    -----
        retriever = Retriever(HybridRetriever(ltm=qdrant_ltm, embeddings=st_emb))
        result = await retriever.retrieve("RELIANCE breakout", top_k=5)
        # result.entries, result.dense_count, result.latency_ms
    """

    def __init__(self, strategy: RetrievalStrategy) -> None:
        self._strategy = strategy

    async def retrieve(self, query: str, top_k: int = 5, filters: Optional[dict] = None) -> RetrievalResult:
        """Retrieve entries. Never raises (Rule 11b)."""
        try:
            return await self._strategy.retrieve(query, top_k=top_k, filters=filters)
        except Exception:
            return RetrievalResult(entries=[], strategy="error")

    @property
    def strategy_name(self) -> str:
        return type(self._strategy).__name__


# ── RRF merge ─────────────────────────────────────────────────────────────────

def _rrf_merge(list_a: List[MemoryEntry], list_b: List[MemoryEntry], k: int = 60) -> List[MemoryEntry]:
    """Reciprocal Rank Fusion of two ranked lists. Deduplicated by entry id."""
    scores: dict = {}
    order:  dict = {}
    for rank, entry in enumerate(list_a):
        scores[entry.id] = scores.get(entry.id, 0.0) + 1.0 / (k + rank + 1)
        order.setdefault(entry.id, entry)
    for rank, entry in enumerate(list_b):
        scores[entry.id] = scores.get(entry.id, 0.0) + 1.0 / (k + rank + 1)
        order.setdefault(entry.id, entry)
    return [order[eid] for eid in sorted(scores, key=lambda eid: scores[eid], reverse=True)]


# ── Metadata filter ───────────────────────────────────────────────────────────

def _apply_filters(entries: List[MemoryEntry], filters: Optional[dict]) -> List[MemoryEntry]:
    """Apply metadata filters. Supported: entry_type (str or list). Unknown keys ignored."""
    if not filters:
        return entries
    entry_type = filters.get("entry_type")
    if entry_type is not None:
        allowed = {entry_type} if isinstance(entry_type, str) else set(entry_type)
        entries = [e for e in entries if e.metadata.get("entry_type") in allowed]
    return entries


def _ms(t0: float) -> float:
    return round((time.monotonic() - t0) * 1000, 2)
