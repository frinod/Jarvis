"""
app/ai/learning/model_evaluator.py
=====================================
ModelEvaluator -- computes rolling model quality metrics from FeedbackRecords.

Design
------
  - Pure computation: no I/O, no LTM access. Accepts a list of
    FeedbackRecords and returns an EvaluationResult.
  - Metrics: accuracy, precision, recall, F1, ECE (calibration error),
    false positive rate, false negative rate, confidence vs accuracy.
  - EvaluationResult.is_degraded() is the signal RetrainingTrigger reads.
  - Domain-agnostic: treats "correct=True" as positive, "correct=False"
    as negative. No trading-specific logic.

Why ECE?
  Confidence calibration matters as much as correctness for a trading AI.
  A model that says 90% confidence but is right only 60% of the time is
  miscalibrated and dangerous. ECE measures this gap.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from app.ai.learning.feedback_collector import FeedbackRecord


# ── EvaluationResult ──────────────────────────────────────────────────────────

@dataclass
class EvaluationResult:
    """
    Output of ModelEvaluator.evaluate().

    All metrics are in [0.0, 1.0] unless noted.
    sample_count: number of FeedbackRecords used.
    """
    sample_count:        int   = 0
    accuracy:            float = 0.0
    precision:           float = 0.0
    recall:              float = 0.0
    f1:                  float = 0.0
    false_positive_rate: float = 0.0
    false_negative_rate: float = 0.0
    ece:                 float = 0.0   # Expected Calibration Error (lower = better)
    avg_confidence:      float = 0.0
    metadata:            Dict[str, Any] = field(default_factory=dict)

    def is_degraded(self, accuracy_threshold: float = 0.6) -> bool:
        """True if accuracy is below threshold AND we have enough samples."""
        return self.sample_count >= 10 and self.accuracy < accuracy_threshold

    def to_dict(self) -> dict:
        return {
            "sample_count":        self.sample_count,
            "accuracy":            round(self.accuracy, 4),
            "precision":           round(self.precision, 4),
            "recall":              round(self.recall, 4),
            "f1":                  round(self.f1, 4),
            "false_positive_rate": round(self.false_positive_rate, 4),
            "false_negative_rate": round(self.false_negative_rate, 4),
            "ece":                 round(self.ece, 4),
            "avg_confidence":      round(self.avg_confidence, 4),
        }


# ── ModelEvaluator ────────────────────────────────────────────────────────────

class ModelEvaluator:
    """
    Computes rolling model quality metrics from a list of FeedbackRecords.

    Usage
    -----
        evaluator = ModelEvaluator()
        records   = await reader.recent(n=100)
        result    = evaluator.evaluate(records)
        if result.is_degraded():
            trigger.check(result)
    """

    def evaluate(self, records: List[FeedbackRecord]) -> EvaluationResult:
        """
        Compute all metrics from records.
        Returns a zero-filled EvaluationResult if records is empty.
        Never raises.
        """
        if not records:
            return EvaluationResult()

        try:
            n = len(records)

            # ── Basic counts ──────────────────────────────────────────
            tp = sum(1 for r in records if r.correct and r.prediction != "HOLD")
            fp = sum(1 for r in records if not r.correct and r.prediction != "HOLD")
            fn = sum(1 for r in records if r.correct and r.prediction == "HOLD")
            tn = sum(1 for r in records if not r.correct and r.prediction == "HOLD")

            correct_count = sum(1 for r in records if r.correct)
            accuracy      = correct_count / n

            precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
            recall    = tp / (tp + fn) if (tp + fn) > 0 else 0.0
            f1        = (
                2 * precision * recall / (precision + recall)
                if (precision + recall) > 0 else 0.0
            )
            fpr = fp / (fp + tn) if (fp + tn) > 0 else 0.0
            fnr = fn / (fn + tp) if (fn + tp) > 0 else 0.0

            avg_conf = sum(r.confidence for r in records) / n

            # ── ECE (Expected Calibration Error) ──────────────────────
            ece = _compute_ece(records, n_bins=10)

            return EvaluationResult(
                sample_count=        n,
                accuracy=            accuracy,
                precision=           precision,
                recall=              recall,
                f1=                  f1,
                false_positive_rate= fpr,
                false_negative_rate= fnr,
                ece=                 ece,
                avg_confidence=      avg_conf,
            )
        except Exception:
            return EvaluationResult(sample_count=len(records))


# ── ECE helper ────────────────────────────────────────────────────────────────

def _compute_ece(records: List[FeedbackRecord], n_bins: int = 10) -> float:
    """
    Expected Calibration Error.

    Bins predictions by confidence, computes |avg_confidence - accuracy|
    per bin, weighted by bin size.
    """
    if not records:
        return 0.0

    bin_size = 1.0 / n_bins
    bins: List[List[FeedbackRecord]] = [[] for _ in range(n_bins)]

    for r in records:
        idx = min(int(r.confidence / bin_size), n_bins - 1)
        bins[idx].append(r)

    ece = 0.0
    n   = len(records)
    for b in bins:
        if not b:
            continue
        avg_conf = sum(r.confidence for r in b) / len(b)
        acc      = sum(1 for r in b if r.correct) / len(b)
        ece     += (len(b) / n) * abs(avg_conf - acc)

    return ece
