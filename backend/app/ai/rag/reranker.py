"""
app/ai/rag/reranker.py
=======================
ReRanker -- post-retrieval re-scoring of candidate entries.

Architecture (per review):
    BaseReranker (ABC)
        ├── NoOpReranker          -- returns entries unchanged (default, zero overhead)
        └── CrossEncoderReranker  -- cross-encoder re-scoring, lazy model load,
                                     falls back to NoOpReranker if model absent

Resilience (Rule 11b):
    CrossEncoderReranker catches all exceptions and falls back to NoOpReranker.
    rerank() never raises.

Why reranking matters:
    Bi-encoder retrieval (dense/keyword) optimises for recall.
    Cross-encoder reranking optimises for precision by scoring each
    (query, entry) pair jointly. Typical improvement: top-5 precision
    increases 15-25% over bi-encoder alone.
"""
from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import List, Optional, Tuple

from app.ai.memory.short_term import MemoryEntry

logger = logging.getLogger(__name__)

_CROSS_ENCODER_MODEL = "cross-encoder/ms-marco-MiniLM-L-6-v2"


# ── BaseReranker ABC ──────────────────────────────────────────────────────────

class BaseReranker(ABC):
    """
    Interface for all rerankers. Implementations are swappable without
    changing callers. rerank() must never raise (Rule 11b).
    """

    @abstractmethod
    def rerank(
        self,
        query:   str,
        entries: List[MemoryEntry],
        top_k:   int = 5,
    ) -> List[MemoryEntry]:
        """
        Re-score entries against query and return top_k in descending relevance.
        Never raises.
        """


# ── NoOpReranker ──────────────────────────────────────────────────────────────

class NoOpReranker(BaseReranker):
    """
    Pass-through reranker. Returns entries unchanged, truncated to top_k.
    Default when no model is available. Zero overhead.
    """

    def rerank(self, query: str, entries: List[MemoryEntry], top_k: int = 5) -> List[MemoryEntry]:
        return entries[:top_k]


# ── CrossEncoderReranker ──────────────────────────────────────────────────────

class CrossEncoderReranker(BaseReranker):
    """
    Cross-encoder reranker using ms-marco-MiniLM-L-6-v2 (~100 MB).

    Lazy-loads the model on first rerank() call.
    Falls back to NoOpReranker silently if:
      - sentence-transformers is not installed
      - model download fails
      - any runtime error occurs

    Usage
    -----
        reranker = CrossEncoderReranker()
        top5 = reranker.rerank("RELIANCE breakout", candidates, top_k=5)
    """

    def __init__(self, model_name: str = _CROSS_ENCODER_MODEL) -> None:
        self._model_name  = model_name
        self._model       = None
        self._fallback    = NoOpReranker()
        self._using_fallback = False

    def _load_model(self) -> None:
        if self._model is not None or self._using_fallback:
            return
        try:
            from sentence_transformers import CrossEncoder  # type: ignore
            self._model = CrossEncoder(self._model_name)
            logger.info("CrossEncoderReranker: loaded %s", self._model_name)
        except Exception as exc:
            logger.warning(
                "CrossEncoderReranker: model load failed (%s), using NoOpReranker",
                exc,
            )
            self._using_fallback = True

    def rerank(self, query: str, entries: List[MemoryEntry], top_k: int = 5) -> List[MemoryEntry]:
        """Re-score entries. Falls back to NoOpReranker on any failure."""
        if not entries:
            return []

        self._load_model()

        if self._using_fallback:
            return self._fallback.rerank(query, entries, top_k)

        try:
            pairs  = [(query, e.content) for e in entries]
            scores = self._model.predict(pairs)
            ranked = sorted(zip(entries, scores), key=lambda x: x[1], reverse=True)
            return [e for e, _ in ranked[:top_k]]
        except Exception as exc:
            logger.warning("CrossEncoderReranker.rerank failed: %s", exc)
            return self._fallback.rerank(query, entries, top_k)

    @property
    def is_using_fallback(self) -> bool:
        return self._using_fallback

    @property
    def model_name(self) -> str:
        return self._model_name
