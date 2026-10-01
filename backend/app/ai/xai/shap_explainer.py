"""
app/ai/xai/shap_explainer.py
==============================
BaseExplainer ABC + ShapExplainer + FallbackExplainer.

Design
------
  - BaseExplainer is the public interface. Callers never import SHAP directly.
  - ShapExplainer wraps shap.Explainer (lazy import). Falls back to
    FallbackExplainer if shap is not installed.
  - FallbackExplainer returns uniform importance (1/n per feature).
  - FeatureImportance is the output type: ordered list of (name, score) pairs.

Resilience (Rule 11b):
  explain() never raises. Returns empty FeatureImportance on any failure.

Extensibility:
  Later implementations (LIME, Integrated Gradients, Attention) implement
  BaseExplainer without changing any caller.
"""
from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from app.ai.prediction.feature_store import FeatureVector

logger = logging.getLogger(__name__)


# ── FeatureImportance ─────────────────────────────────────────────────────────

@dataclass
class FeatureImportance:
    """
    Output of BaseExplainer.explain().

    scores: list of (feature_name, importance_score) sorted descending.
    model_name: which model produced this explanation.
    method: 'shap' | 'uniform' | other.
    metadata: arbitrary extra data for downstream consumers.
    """
    scores:     List[Tuple[str, float]]
    model_name: str                  = ""
    method:     str                  = "unknown"
    metadata:   Dict[str, Any]       = field(default_factory=dict)

    def top(self, n: int = 5) -> List[Tuple[str, float]]:
        """Return the n highest-importance features."""
        return self.scores[:n]

    def as_dict(self) -> Dict[str, float]:
        return dict(self.scores)


# ── BaseExplainer ABC ─────────────────────────────────────────────────────────

class BaseExplainer(ABC):
    """
    Interface for feature-importance explainers.

    Implementations: ShapExplainer, FallbackExplainer.
    Future: LimeExplainer, IntegratedGradientsExplainer.
    """

    @abstractmethod
    def explain(
        self,
        features:   FeatureVector,
        model_name: str = "default",
        model:      Optional[Any] = None,
    ) -> FeatureImportance:
        """
        Compute feature importance for the given FeatureVector.
        Never raises — returns empty FeatureImportance on failure.
        """

    @abstractmethod
    def is_available(self) -> bool:
        """Return True if the underlying library is installed and ready."""


# ── FallbackExplainer ─────────────────────────────────────────────────────────

class FallbackExplainer(BaseExplainer):
    """
    Returns uniform importance (1/n per feature).
    Used when shap is not installed or ShapExplainer fails.
    """

    def explain(
        self,
        features:   FeatureVector,
        model_name: str = "default",
        model:      Optional[Any] = None,
    ) -> FeatureImportance:
        n = len(features.features)
        if n == 0:
            return FeatureImportance(scores=[], model_name=model_name, method="uniform")
        score = round(1.0 / n, 6)
        scores = sorted(
            [(name, score) for name in features.features],
            key=lambda x: x[0],
        )
        return FeatureImportance(scores=scores, model_name=model_name, method="uniform")

    def is_available(self) -> bool:
        return True


# ── ShapExplainer ─────────────────────────────────────────────────────────────

class ShapExplainer(BaseExplainer):
    """
    SHAP-based feature importance explainer.

    Lazy-imports shap at first use. Falls back to FallbackExplainer if
    shap is not installed or if the model type is unsupported.

    Usage
    -----
        explainer = ShapExplainer()
        importance = explainer.explain(feature_vector, model=xgb_model)
        print(importance.top(5))
    """

    def __init__(self) -> None:
        self._fallback = FallbackExplainer()
        self._shap_available: Optional[bool] = None   # None = not yet checked

    def is_available(self) -> bool:
        if self._shap_available is None:
            try:
                import shap  # noqa: F401
                self._shap_available = True
            except ImportError:
                self._shap_available = False
                logger.warning(
                    "shap not installed — ShapExplainer will use uniform fallback. "
                    "Install with: pip install shap==0.41.*"
                )
        return self._shap_available

    def explain(
        self,
        features:   FeatureVector,
        model_name: str = "default",
        model:      Optional[Any] = None,
    ) -> FeatureImportance:
        """
        Compute SHAP values for features.
        Falls back to FallbackExplainer if shap unavailable or model is None.
        Never raises.
        """
        if not self.is_available() or model is None:
            result = self._fallback.explain(features, model_name=model_name)
            result.method = "uniform_fallback"
            return result

        try:
            import shap
            import numpy as np

            feature_names = list(features.features.keys())
            values = np.array([features.to_list(feature_names)], dtype=float)

            explainer   = shap.Explainer(model, feature_names=feature_names)
            shap_values = explainer(values)

            # shap_values.values shape: (1, n_features) for single-output models
            raw = shap_values.values[0]
            abs_scores = [abs(float(v)) for v in raw]
            total = sum(abs_scores) or 1.0
            normalised = [s / total for s in abs_scores]

            scores = sorted(
                zip(feature_names, normalised),
                key=lambda x: x[1],
                reverse=True,
            )
            return FeatureImportance(
                scores=list(scores),
                model_name=model_name,
                method="shap",
            )
        except Exception as exc:
            logger.debug("ShapExplainer.explain failed: %s — using fallback", exc)
            result = self._fallback.explain(features, model_name=model_name)
            result.method = "uniform_fallback"
            return result
