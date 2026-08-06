"""
app/ai/prediction/feature_store.py
=====================================
FeatureStore -- builds feature vectors from raw perception data.

Design
------
  - FeatureStore.build() accepts a plain dict of raw data and returns
    a FeatureVector (also a plain dict + metadata).
  - No ML model calls here -- pure feature engineering.
  - Phase 7+: extend with more sophisticated feature extractors.
  - Architecture §15: FeatureStore feeds ForecastingEngine.

Domain agnosticism at the interface level
------------------------------------------
  FeatureStore.build() accepts any dict. Feature names are generic.
  Domain-specific feature names live in the returned FeatureVector.features dict.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


# ── FeatureVector ─────────────────────────────────────────────────────────────

@dataclass
class FeatureVector:
    """
    Output of FeatureStore.build().
    features is a plain dict of name -> float value.
    """
    features:   Dict[str, float]
    source_keys: List[str]        = field(default_factory=list)
    metadata:   Dict[str, Any]   = field(default_factory=dict)

    def to_list(self, keys: Optional[List[str]] = None) -> List[float]:
        """Return feature values as an ordered list (for model input)."""
        if keys:
            return [self.features.get(k, 0.0) for k in keys]
        return list(self.features.values())

    def __len__(self) -> int:
        return len(self.features)


# ── FeatureStore ──────────────────────────────────────────────────────────────

class FeatureStore:
    """
    Builds feature vectors from raw perception data.

    Supported features (Phase 6):
      - Numeric values from the raw data dict are included as-is.
      - Boolean values are converted to 1.0/0.0.
      - Non-numeric values are skipped.

    Phase 7+: add RSI, MACD, EMA, BB, ATR, volume_ratio extractors.

    Usage
    -----
        store  = FeatureStore()
        vector = store.build({"price": 100.0, "volume": 5000, "change_pct": 1.5})
        values = vector.to_list()
    """

    def build(self, raw_data: Dict[str, Any]) -> FeatureVector:
        """
        Extract numeric features from raw_data.
        Non-numeric values are silently skipped.
        """
        features: Dict[str, float] = {}
        source_keys: List[str]     = []

        for key, value in raw_data.items():
            if isinstance(value, bool):
                features[key] = 1.0 if value else 0.0
                source_keys.append(key)
            elif isinstance(value, (int, float)):
                features[key] = float(value)
                source_keys.append(key)
            # Non-numeric: skip

        return FeatureVector(features=features, source_keys=source_keys)

    def build_from_bundles(self, bundles: list) -> FeatureVector:
        """
        Build a feature vector by merging multiple PerceptionBundle.data dicts.
        Later bundles override earlier ones on key collision.
        """
        merged: Dict[str, Any] = {}
        for bundle in bundles:
            data = getattr(bundle, "data", {})
            merged.update(data)
        return self.build(merged)
