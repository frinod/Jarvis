"""
app/ai/xai/xai_cache.py
=========================
XaiCache -- TTL + LRU cache for FeatureImportance results.

Design
------
  - Keyed by (model_version, feature_hash) where feature_hash is a
    deterministic hash of the FeatureVector's feature names and values.
  - TTL: 1 hour by default (configurable).
  - LRU capacity: 128 entries by default (configurable).
  - Thread-safe for single-process use (no async needed — pure CPU).
  - Never raises (Rule 11b).

Why cache explanations?
  SHAP is O(n_features * n_samples) per call. For repeated requests with
  the same model + features, caching avoids redundant computation.
"""
from __future__ import annotations

import hashlib
import logging
import time
from collections import OrderedDict
from typing import Optional, Tuple

from app.ai.prediction.feature_store import FeatureVector
from app.ai.xai.shap_explainer import FeatureImportance

logger = logging.getLogger(__name__)

_DEFAULT_TTL_SECONDS = 3600   # 1 hour
_DEFAULT_CAPACITY    = 128


def _feature_hash(features: FeatureVector) -> str:
    """Deterministic hash of feature names + values (order-independent)."""
    items = sorted(features.features.items())
    raw   = str(items).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()[:16]


class XaiCache:
    """
    TTL + LRU cache for FeatureImportance results.

    Usage
    -----
        cache = XaiCache(ttl_seconds=3600, capacity=128)
        key   = cache.make_key(model_version="v1.2", features=fv)
        hit   = cache.get(key)
        if hit is None:
            result = explainer.explain(fv)
            cache.put(key, result)
    """

    def __init__(
        self,
        ttl_seconds: float = _DEFAULT_TTL_SECONDS,
        capacity:    int   = _DEFAULT_CAPACITY,
    ) -> None:
        self._ttl      = ttl_seconds
        self._capacity = max(1, capacity)
        # OrderedDict used as LRU: most-recently-used at the end
        self._store: OrderedDict[str, Tuple[FeatureImportance, float]] = OrderedDict()

    # ── Public API ────────────────────────────────────────────────────

    def make_key(self, model_version: str, features: FeatureVector) -> str:
        """Build a cache key from model version + feature hash."""
        return f"{model_version}:{_feature_hash(features)}"

    def get(self, key: str) -> Optional[FeatureImportance]:
        """
        Return cached FeatureImportance if present and not expired.
        Returns None on miss or expiry. Never raises.
        """
        try:
            if key not in self._store:
                return None
            importance, stored_at = self._store[key]
            if time.time() - stored_at > self._ttl:
                del self._store[key]
                return None
            # Move to end (most recently used)
            self._store.move_to_end(key)
            return importance
        except Exception as exc:
            logger.debug("XaiCache.get failed: %s", exc)
            return None

    def put(self, key: str, importance: FeatureImportance) -> None:
        """
        Store a FeatureImportance result. Evicts LRU entry if at capacity.
        Never raises.
        """
        try:
            if key in self._store:
                self._store.move_to_end(key)
            self._store[key] = (importance, time.time())
            if len(self._store) > self._capacity:
                self._store.popitem(last=False)   # evict LRU (first item)
        except Exception as exc:
            logger.debug("XaiCache.put failed: %s", exc)

    def invalidate(self, key: str) -> bool:
        """Remove one entry. Returns True if it existed."""
        return bool(self._store.pop(key, None))

    def clear(self) -> None:
        """Remove all entries."""
        self._store.clear()

    # ── Introspection ─────────────────────────────────────────────────

    @property
    def size(self) -> int:
        return len(self._store)

    def stats(self) -> dict:
        now    = time.time()
        live   = sum(1 for _, (_, ts) in self._store.items() if now - ts <= self._ttl)
        return {
            "size":     len(self._store),
            "live":     live,
            "expired":  len(self._store) - live,
            "capacity": self._capacity,
            "ttl":      self._ttl,
        }
