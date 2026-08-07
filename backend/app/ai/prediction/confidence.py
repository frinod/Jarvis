"""
app/ai/prediction/confidence.py
=================================
ConfidenceScorer -- aggregates confidence from prediction, TA signals, and sentiment.

Design
------
  - ConfidenceScorer.score() accepts a PredictionResult + optional signals
    and returns a final 0.0–1.0 confidence score with reasoning.
  - Weights are configurable via ScorerConfig.
  - Returns 0.5 (neutral) when no inputs are available (architecture §18).

Domain agnosticism
-------------------
  ConfidenceScorer operates on numeric scores only.
  No domain-specific fields. Domain data lives in ScoredResult.metadata.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from app.ai.prediction.forecasting import PredictionResult


# ── ScorerConfig ──────────────────────────────────────────────────────────────

@dataclass
class ScorerConfig:
    """Weights for confidence aggregation. Must sum to <= 1.0."""
    weight_prediction: float = 0.50
    weight_ta_signal:  float = 0.30
    weight_sentiment:  float = 0.20
    neutral_fallback:  float = 0.50   # returned when no inputs available


# ── ScoredResult ──────────────────────────────────────────────────────────────

@dataclass
class ScoredResult:
    """Output of ConfidenceScorer.score()."""
    confidence: float
    reasoning:  str
    components: Dict[str, float] = field(default_factory=dict)
    metadata:   Dict[str, Any]   = field(default_factory=dict)


# ── ConfidenceScorer ──────────────────────────────────────────────────────────

class ConfidenceScorer:
    """
    Aggregates confidence from multiple signal sources.

    Sources (all optional):
      - prediction: PredictionResult.confidence from ForecastingEngine
      - ta_signal:  float from technical analysis (0.0–1.0)
      - sentiment:  float from SentimentPerception (-1.0 to +1.0, normalised)

    Usage
    -----
        scorer = ConfidenceScorer()
        result = scorer.score(prediction=pred, ta_signal=0.7, sentiment=0.3)
        print(result.confidence)   # 0.0 to 1.0
    """

    def __init__(self, config: Optional[ScorerConfig] = None):
        self._cfg = config or ScorerConfig()

    def score(
        self,
        prediction: Optional[PredictionResult] = None,
        ta_signal:  Optional[float]            = None,
        sentiment:  Optional[float]            = None,
    ) -> ScoredResult:
        """
        Aggregate confidence from available sources.
        Returns neutral_fallback (0.5) when no sources are provided.
        """
        cfg        = self._cfg
        weighted   = 0.0
        total_w    = 0.0
        components: Dict[str, float] = {}
        parts:      List[str]        = []

        if prediction is not None:
            # Normalise to [0,1] — guard against callers passing percentage (0-100)
            pred_conf = prediction.confidence if prediction.confidence <= 1.0 else prediction.confidence / 100.0
            pred_conf = max(0.0, min(1.0, pred_conf))
            weighted  += pred_conf * cfg.weight_prediction
            total_w   += cfg.weight_prediction
            components["prediction"] = pred_conf
            parts.append(f"prediction={pred_conf:.2f}")

        if ta_signal is not None:
            ta = max(0.0, min(1.0, float(ta_signal)))
            weighted  += ta * cfg.weight_ta_signal
            total_w   += cfg.weight_ta_signal
            components["ta_signal"] = ta
            parts.append(f"ta={ta:.2f}")

        if sentiment is not None:
            # Normalise sentiment from [-1, 1] to [0, 1]
            norm_sent = (float(sentiment) + 1.0) / 2.0
            norm_sent = max(0.0, min(1.0, norm_sent))
            weighted  += norm_sent * cfg.weight_sentiment
            total_w   += cfg.weight_sentiment
            components["sentiment"] = norm_sent
            parts.append(f"sentiment={norm_sent:.2f}")

        if total_w == 0.0:
            return ScoredResult(
                confidence=cfg.neutral_fallback,
                reasoning="No signal sources available -- returning neutral confidence.",
                components={},
            )

        final = round(weighted / total_w, 3)
        reasoning = "Aggregated from: " + ", ".join(parts) + f" → {final:.0%}"

        return ScoredResult(
            confidence=final,
            reasoning=reasoning,
            components=components,
        )
