"""
app/ai/memory/sentence_transformer_embeddings.py
=================================================
SentenceTransformerEmbeddingService -- Phase 7A embedding implementation.

Drop-in replacement for SimpleEmbeddingService. Implements the same
EmbeddingService ABC. No caller changes required.

Model: all-MiniLM-L6-v2
  - 384-dimensional vectors
  - ~80 MB download on first run, cached locally
  - Fully offline after first download
  - Python 3.7 compatible
  - Cosine similarity via normalised dot product

Resilience (ADR-002 MR-2, MR-3):
  - Model load failure → falls back to SimpleEmbeddingService silently
  - encode() failure  → returns zero vector of correct dimension
  - Never raises to caller

Lazy loading:
  - Model is loaded on first encode() call, not at import time
  - Subsequent calls reuse the loaded model (process-level singleton)
"""
from __future__ import annotations

import logging
from typing import List, Optional

from app.ai.memory.embeddings import EmbeddingService, SimpleEmbeddingService

logger = logging.getLogger(__name__)

_MODEL_NAME = "all-MiniLM-L6-v2"
_VECTOR_DIM = 384


class SentenceTransformerEmbeddingService(EmbeddingService):
    """
    Sentence-transformer embedding service using all-MiniLM-L6-v2.

    Falls back to SimpleEmbeddingService if sentence-transformers is
    unavailable or the model fails to load. Callers never see the
    difference — the ABC contract is always satisfied.

    Usage
    -----
        svc = SentenceTransformerEmbeddingService()
        vec = svc.encode("RELIANCE showing bullish breakout")
        # vec is a list of 384 floats, L2-normalised
    """

    def __init__(self, model_name: str = _MODEL_NAME) -> None:
        self._model_name = model_name
        self._model      = None          # loaded lazily
        self._fallback:  Optional[SimpleEmbeddingService] = None
        self._using_fallback = False

    # ── Model loading ─────────────────────────────────────────────────

    def _load_model(self) -> None:
        """Load the sentence-transformer model once. Thread-safe for reads."""
        if self._model is not None or self._using_fallback:
            return
        try:
            from sentence_transformers import SentenceTransformer  # type: ignore
            self._model = SentenceTransformer(self._model_name)
            logger.info("SentenceTransformerEmbeddingService: loaded %s", self._model_name)
        except Exception as exc:
            logger.warning(
                "SentenceTransformerEmbeddingService: model load failed (%s), "
                "falling back to SimpleEmbeddingService",
                exc,
            )
            self._fallback       = SimpleEmbeddingService()
            self._using_fallback = True

    # ── EmbeddingService ABC ──────────────────────────────────────────

    def encode(self, text: str) -> List[float]:
        """
        Encode text to a 384-dim L2-normalised float vector.
        Returns a zero vector on any failure (MR-2: never raises).
        """
        self._load_model()

        if self._using_fallback:
            return self._fallback.encode(text)  # type: ignore[union-attr]

        if not text or not text.strip():
            return [0.0] * _VECTOR_DIM

        try:
            vec = self._model.encode(text, normalize_embeddings=True)
            return vec.tolist()
        except Exception as exc:
            logger.warning("SentenceTransformerEmbeddingService.encode failed: %s", exc)
            return [0.0] * _VECTOR_DIM

    def similarity(self, a: List[float], b: List[float]) -> float:
        """
        Cosine similarity between two L2-normalised vectors (dot product).
        Handles empty or mismatched lengths safely.
        """
        if not a or not b:
            return 0.0
        # Vectors from this service are always 384-dim and normalised.
        # Pad shorter vector if comparing against fallback vectors.
        len_a, len_b = len(a), len(b)
        if len_a < len_b:
            a = a + [0.0] * (len_b - len_a)
        elif len_b < len_a:
            b = b + [0.0] * (len_a - len_b)
        return round(sum(x * y for x, y in zip(a, b)), 6)

    # ── Introspection ─────────────────────────────────────────────────

    @property
    def vector_dim(self) -> int:
        return _VECTOR_DIM

    @property
    def model_name(self) -> str:
        return self._model_name

    @property
    def is_using_fallback(self) -> bool:
        return self._using_fallback
