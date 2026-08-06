"""
app/ai/prediction/forecasting.py
==================================
ForecastingEngine -- ML model wrapper for inference.

Design
------
  - ForecastingEngine wraps existing XGBoost .pkl models in backend/models/.
  - No new ML training in Phase 6 -- inference only (architecture §15).
  - ForecastingEngine is an ABC. XGBoostForecastingEngine is the impl.
  - MockForecastingEngine is provided for testing (no model files needed).
  - PredictionResult carries direction, magnitude, and confidence.

Domain agnosticism at the interface level
------------------------------------------
  ForecastingEngine.predict() accepts a FeatureVector.
  PredictionResult.metadata carries domain-specific data.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

from app.ai.prediction.feature_store import FeatureVector


# ── PredictionResult ──────────────────────────────────────────────────────────

class PredictionDirection(str, Enum):
    UP      = "up"
    DOWN    = "down"
    NEUTRAL = "neutral"


@dataclass
class PredictionResult:
    """Output of ForecastingEngine.predict()."""
    direction:     PredictionDirection
    magnitude:     float          # 0.0 to 1.0 (strength of the prediction)
    confidence:    float          # 0.0 to 1.0
    model_name:    str            = ""
    features_used: List[str]      = field(default_factory=list)
    metadata:      Dict[str, Any] = field(default_factory=dict)


# ── ForecastingEngine ABC ─────────────────────────────────────────────────────

class ForecastingEngine(ABC):
    """
    Interface for ML model inference.
    Phase 6: MockForecastingEngine.
    Phase 7+: XGBoostForecastingEngine wrapping backend/models/*.pkl.
    """

    @abstractmethod
    def predict(self, features: FeatureVector, model_name: str = "default") -> PredictionResult:
        """Run inference. Returns PredictionResult. Never raises."""

    @abstractmethod
    def is_model_available(self, model_name: str) -> bool:
        """Return True if the named model is loaded and ready."""


# ── MockForecastingEngine ─────────────────────────────────────────────────────

class MockForecastingEngine(ForecastingEngine):
    """
    Mock engine for Phase 6 testing.
    Returns configurable predictions without loading any model files.
    """

    def __init__(
        self,
        direction:  PredictionDirection = PredictionDirection.NEUTRAL,
        magnitude:  float               = 0.5,
        confidence: float               = 0.5,
    ):
        self._direction  = direction
        self._magnitude  = magnitude
        self._confidence = confidence

    def predict(self, features: FeatureVector, model_name: str = "default") -> PredictionResult:
        return PredictionResult(
            direction=self._direction,
            magnitude=self._magnitude,
            confidence=self._confidence,
            model_name=model_name,
            features_used=features.source_keys,
        )

    def is_model_available(self, model_name: str) -> bool:
        return True   # mock always available

    def set_prediction(
        self,
        direction:  PredictionDirection,
        magnitude:  float,
        confidence: float,
    ) -> None:
        self._direction  = direction
        self._magnitude  = magnitude
        self._confidence = confidence
