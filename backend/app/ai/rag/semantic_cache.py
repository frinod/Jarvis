"""
app/ai/rag/semantic_cache.py
=============================
SemanticCache -- two-layer query cache for the RAG pipeline.

Architecture (per review):
    Layer 1: Exact cache   -- O(1) dict lookup on normalised query string
    Layer 2: Semantic cache -- embedding similarity lookup (threshold 0.92)
    Layer 3: Retriever      -- called only on cache miss

TTL:
    market queries (entry_type="market_snapshot"): 5 minutes
    general queries: 30 minutes
    Configurable via constructor.

Resilience (Rule 11b):
    get() and put() never raise. Cache miss is always a valid result.
    Embedding failures return a cache miss (safe degradation).

Usage
-----
    cache = SemanticCache(embeddings=st_emb)
    hit = cache.get("RELIANCE breakout analysis")
    if hit is None:
        result = await retriever.retrieve(query)
        cache.put(query, result)
"""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from app.ai.memory.embeddings import EmbeddingService
from app.ai.rag.retriever import RetrievalResult

logger = logging.getLogger(__name__)

_DEFAULT_THRESHOLD    = 0.92   # ADR-003
_DEFAULT_TTL_MARKET   = 300    # 5 minutes
_DEFAULT_TTL_GENERAL  = 1800   # 30 minutes
_MAX_CACHE_SIZE       = 256    # evict oldest when exceeded


# ── Cache entry ───────────────────────────────────────────────────────────────

@dataclass
class _CacheEntry:
    query:      str
    result:     RetrievalResult
    embedding:  Optional[List[float]]
    created_at: float = field(default_factory=time.time)
    ttl_s:      float = _DEFAULT_TTL_GENERAL

    def is_expired(self) -> bool:
        return (time.time() - self.created_at) > self.ttl_s


# ── SemanticCache ─────────────────────────────────────────────────────────────

class SemanticCache:
    """
    Two-layer cache: exact string match → semantic similarity → miss.

    Layer 1 (exact): normalised query string → O(1) lookup.
    Layer 2 (semantic): embedding cosine similarity ≥ threshold.

    Both layers respect TTL. Expired entries are evicted on access.

    Usage
    -----
        cache = SemanticCache(embeddings=svc, threshold=0.92)
        hit = cache.get("RELIANCE breakout")
        if hit is None:
            result = await retriever.retrieve(query)
            cache.put("RELIANCE breakout", result, is_market=True)
    """

    def __init__(
        self,
        embeddings:    Optional[EmbeddingService] = None,
        threshold:     float = _DEFAULT_THRESHOLD,
        ttl_market_s:  float = _DEFAULT_TTL_MARKET,
        ttl_general_s: float = _DEFAULT_TTL_GENERAL,
        enabled:       bool  = True,
    ) -> None:
        self._emb          = embeddings
        self._threshold    = threshold
        self._ttl_market   = ttl_market_s
        self._ttl_general  = ttl_general_s
        self.enabled       = enabled
        self._store:       Dict[str, _CacheEntry] = {}   # normalised_query → entry
        self._hits         = 0
        self._misses       = 0

    # ── Public API ────────────────────────────────────────────────────

    def get(self, query: str) -> Optional[RetrievalResult]:
        """
        Return cached RetrievalResult if a valid hit exists, else None.
        Checks exact match first, then semantic similarity.
        Never raises.
        """
        if not self.enabled:
            return None
        try:
            return self._get(query)
        except Exception:
            return None

    def put(self, query: str, result: RetrievalResult, is_market: bool = False) -> None:
        """
        Store a result in the cache. Best-effort (Rule 11b): never raises.
        is_market=True applies the shorter market TTL.
        """
        if not self.enabled:
            return
        try:
            self._put(query, result, is_market)
        except Exception:
            pass

    def invalidate(self, query: str) -> None:
        """Remove a specific query from the cache."""
        key = _normalise(query)
        self._store.pop(key, None)

    def clear(self) -> None:
        """Clear all cache entries."""
        self._store.clear()
        self._hits   = 0
        self._misses = 0

    # ── Stats ─────────────────────────────────────────────────────────

    @property
    def size(self) -> int:
        return len(self._store)

    @property
    def hit_rate(self) -> float:
        total = self._hits + self._misses
        return round(self._hits / total, 3) if total > 0 else 0.0

    def stats(self) -> dict:
        return {
            "size":     self.size,
            "hits":     self._hits,
            "misses":   self._misses,
            "hit_rate": self.hit_rate,
            "enabled":  self.enabled,
        }

    # ── Internal ──────────────────────────────────────────────────────

    def _get(self, query: str) -> Optional[RetrievalResult]:
        key = _normalise(query)

        # Layer 1: exact match
        entry = self._store.get(key)
        if entry is not None:
            if entry.is_expired():
                del self._store[key]
            else:
                self._hits += 1
                result = entry.result
                result.cache_hit = True
                return result

        # Layer 2: semantic similarity
        if self._emb is not None:
            q_vec = self._emb.encode(query)
            best_key, best_score = self._best_semantic_match(q_vec)
            if best_key is not None and best_score >= self._threshold:
                entry = self._store[best_key]
                if entry.is_expired():
                    del self._store[best_key]
                else:
                    self._hits += 1
                    result = entry.result
                    result.cache_hit = True
                    return result

        self._misses += 1
        return None

    def _put(self, query: str, result: RetrievalResult, is_market: bool) -> None:
        # Evict oldest entries if at capacity
        if len(self._store) >= _MAX_CACHE_SIZE:
            oldest_key = min(self._store, key=lambda k: self._store[k].created_at)
            del self._store[oldest_key]

        key       = _normalise(query)
        embedding = None
        if self._emb is not None:
            try:
                embedding = self._emb.encode(query)
            except Exception:
                pass

        ttl = self._ttl_market if is_market else self._ttl_general
        self._store[key] = _CacheEntry(
            query=query,
            result=result,
            embedding=embedding,
            ttl_s=ttl,
        )

    def _best_semantic_match(self, q_vec: List[float]) -> Tuple[Optional[str], float]:
        """Find the cache entry with highest cosine similarity to q_vec."""
        best_key   = None
        best_score = 0.0
        for key, entry in list(self._store.items()):
            if entry.embedding is None:
                continue
            if entry.is_expired():
                continue
            score = self._emb.similarity(q_vec, entry.embedding)  # type: ignore[union-attr]
            if score > best_score:
                best_score = score
                best_key   = key
        return best_key, best_score


# ── Helpers ───────────────────────────────────────────────────────────────────

def _normalise(query: str) -> str:
    """Normalise query for exact-match key: lowercase, strip, collapse spaces."""
    return " ".join(query.lower().split())
