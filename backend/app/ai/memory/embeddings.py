"""
app/ai/memory/embeddings.py
============================
EmbeddingService -- text-to-vector encoding and cosine similarity search.

Design
------
  - EmbeddingService is an ABC. SimpleEmbeddingService is the Phase 6 impl.
  - Phase 7+: swap for a real embedding model (sentence-transformers, OpenAI
    embeddings, etc.) without changing any caller.
  - SimpleEmbeddingService uses a bag-of-words TF vector with cosine similarity.
    It is deterministic, dependency-free, and fast enough for unit tests and
    small memory stores.
  - No external dependencies. No network calls. No model files.

Domain agnosticism
-------------------
  No domain fields. Operates on plain text strings only.
"""
from __future__ import annotations

import math
from abc import ABC, abstractmethod
from typing import List, Optional, Tuple

from app.ai.memory.short_term import MemoryEntry


# ── EmbeddingService ABC ──────────────────────────────────────────────────────

class EmbeddingService(ABC):
    """
    Interface for text-to-vector encoding.

    Implementations must be swappable without changing callers.
    Phase 6: SimpleEmbeddingService (bag-of-words).
    Phase 7+: SentenceTransformerEmbeddingService or OpenAIEmbeddingService.
    """

    @abstractmethod
    def encode(self, text: str) -> List[float]:
        """Convert text to a float vector. Deterministic for the same text."""

    @abstractmethod
    def similarity(self, a: List[float], b: List[float]) -> float:
        """Cosine similarity between two vectors. Returns value in [-1.0, 1.0]."""

    def top_k(
        self,
        query:   str,
        entries: List[MemoryEntry],
        k:       int   = 5,
        min_score: float = 0.0,
    ) -> List[Tuple[MemoryEntry, float]]:
        """
        Return the top-k most similar entries to query, with scores.
        Entries without embeddings are encoded on the fly.
        Results are sorted by score descending.
        Entries with score < min_score are excluded.
        """
        q_vec = self.encode(query)
        scored: List[Tuple[MemoryEntry, float]] = []
        for entry in entries:
            vec = entry.embedding if entry.embedding else self.encode(entry.content)
            score = self.similarity(q_vec, vec)
            if score >= min_score:
                scored.append((entry, round(score, 4)))
        scored.sort(key=lambda x: x[1], reverse=True)
        return scored[:k]


# ── SimpleEmbeddingService ────────────────────────────────────────────────────

class SimpleEmbeddingService(EmbeddingService):
    """
    Bag-of-words TF embedding with cosine similarity.

    Vocabulary is built lazily from all encoded texts.
    Vectors are L2-normalised so cosine similarity = dot product.

    Suitable for Phase 6 (no external deps, deterministic, fast).
    Replace with a real model in Phase 7 without changing callers.

    Usage
    -----
        svc = SimpleEmbeddingService()
        v1  = svc.encode("the quick brown fox")
        v2  = svc.encode("a fast brown dog")
        sim = svc.similarity(v1, v2)   # ~0.5
    """

    def __init__(self) -> None:
        self._vocab: dict[str, int] = {}   # word -> index

    # ── Vocabulary ────────────────────────────────────────────────────

    def _tokenize(self, text: str) -> List[str]:
        """Lowercase, split on whitespace and punctuation."""
        import re
        return re.findall(r"[a-z0-9]+", text.lower())

    def _get_or_add(self, word: str) -> int:
        if word not in self._vocab:
            self._vocab[word] = len(self._vocab)
        return self._vocab[word]

    def vocab_size(self) -> int:
        return len(self._vocab)

    # ── Encoding ──────────────────────────────────────────────────────

    def encode(self, text: str) -> List[float]:
        """
        Produce a TF bag-of-words vector, L2-normalised.
        Vocabulary grows as new words are seen.
        Returns a zero vector for empty text.
        """
        tokens = self._tokenize(text)
        if not tokens:
            return []

        # Build term-frequency dict
        tf: dict[int, float] = {}
        for token in tokens:
            idx = self._get_or_add(token)
            tf[idx] = tf.get(idx, 0.0) + 1.0

        # Build dense vector (current vocab size)
        size = len(self._vocab)
        vec = [0.0] * size
        for idx, count in tf.items():
            vec[idx] = count

        return _l2_normalise(vec)

    # ── Similarity ────────────────────────────────────────────────────

    def similarity(self, a: List[float], b: List[float]) -> float:
        """
        Cosine similarity between two L2-normalised vectors.
        Handles vectors of different lengths (vocab may have grown).
        Returns 0.0 for empty vectors.
        """
        if not a or not b:
            return 0.0
        # Pad shorter vector with zeros
        len_a, len_b = len(a), len(b)
        if len_a < len_b:
            a = a + [0.0] * (len_b - len_a)
        elif len_b < len_a:
            b = b + [0.0] * (len_a - len_b)
        return round(_dot(a, b), 6)

    # ── Batch encode ──────────────────────────────────────────────────

    def encode_entries(self, entries: List[MemoryEntry]) -> None:
        """
        Encode all entries in-place, populating entry.embedding.
        Call this after adding a batch of entries to enable semantic search.
        """
        for entry in entries:
            entry.embedding = self.encode(entry.content)


# ── Math helpers ──────────────────────────────────────────────────────────────

def _dot(a: List[float], b: List[float]) -> float:
    return sum(x * y for x, y in zip(a, b))


def _l2_norm(v: List[float]) -> float:
    return math.sqrt(sum(x * x for x in v))


def _l2_normalise(v: List[float]) -> List[float]:
    norm = _l2_norm(v)
    if norm == 0.0:
        return v
    return [x / norm for x in v]
