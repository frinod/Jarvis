"""
app/ai/learning/retraining_trigger.py
=======================================
RetrainingTrigger -- fires a retraining LearningEvent when model quality
degrades below acceptable thresholds.

Design
------
  Four-condition guard (all must be true to fire):
    1. accuracy < accuracy_threshold
    2. sample_count >= min_samples        (avoid overreacting to small batches)
    3. elapsed seconds since last trigger >= cooldown_seconds  (avoid thrashing)
    4. performance_trend <= 0             (accuracy is flat or declining)

  Emits a LearningEvent(event_type="retrain_requested") when all four
  conditions are met. The LearningEngine (or an external orchestrator)
  consumes this event and schedules the actual retraining job.

  The trigger is strictly advisory — it never modifies the Brain,
  DecisionTree, or the frozen trading engine.

Resilience (Rule 11b):
  check() never raises. Returns None on failure.
"""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import List, Optional

from app.ai.learning.learning_event import LearningEvent
from app.ai.learning.model_evaluator import EvaluationResult

logger = logging.getLogger(__name__)

_DEFAULT_ACCURACY_THRESHOLD = 0.60
_DEFAULT_MIN_SAMPLES        = 10
_DEFAULT_COOLDOWN_SECONDS   = 3600   # 1 hour between triggers
_DEFAULT_TREND_WINDOW       = 3      # number of recent evaluations for trend


# ── TriggerConfig ─────────────────────────────────────────────────────────────

@dataclass
class TriggerConfig:
    accuracy_threshold: float = _DEFAULT_ACCURACY_THRESHOLD
    min_samples:        int   = _DEFAULT_MIN_SAMPLES
    cooldown_seconds:   float = _DEFAULT_COOLDOWN_SECONDS
    trend_window:       int   = _DEFAULT_TREND_WINDOW


# ── TriggerResult ─────────────────────────────────────────────────────────────

@dataclass
class TriggerResult:
    """Outcome of one RetrainingTrigger.check() call."""
    fired:          bool
    reason:         str
    event:          Optional[LearningEvent] = None
    conditions_met: dict = field(default_factory=dict)


# ── RetrainingTrigger ─────────────────────────────────────────────────────────

class RetrainingTrigger:
    """
    Evaluates whether retraining should be requested.

    Usage
    -----
        trigger = RetrainingTrigger()
        result  = trigger.check(evaluation_result, model_version="v1.3")
        if result.fired:
            # consume result.event
    """

    def __init__(self, config: Optional[TriggerConfig] = None) -> None:
        self._cfg              = config or TriggerConfig()
        self._last_trigger_at: float       = 0.0
        self._history:         List[float] = []   # recent accuracy values

    def check(
        self,
        result:        EvaluationResult,
        model_version: str = "",
        agent_name:    str = "",
    ) -> TriggerResult:
        """
        Evaluate all four conditions. Returns TriggerResult.
        Never raises.
        """
        try:
            cfg = self._cfg
            now = time.time()

            # Record accuracy for trend analysis
            self._history.append(result.accuracy)
            if len(self._history) > cfg.trend_window * 2:
                self._history = self._history[-(cfg.trend_window * 2):]

            # ── Condition 1: accuracy below threshold ─────────────────
            c1 = result.accuracy < cfg.accuracy_threshold

            # ── Condition 2: enough samples ───────────────────────────
            c2 = result.sample_count >= cfg.min_samples

            # ── Condition 3: cooldown elapsed ─────────────────────────
            c3 = (now - self._last_trigger_at) >= cfg.cooldown_seconds

            # ── Condition 4: trend is flat or declining ───────────────
            c4 = _trend_is_flat_or_declining(self._history, cfg.trend_window)

            conditions = {
                "accuracy_below_threshold": c1,
                "enough_samples":           c2,
                "cooldown_elapsed":         c3,
                "trend_flat_or_declining":  c4,
            }

            if c1 and c2 and c3 and c4:
                self._last_trigger_at = now
                reason = (
                    f"accuracy={result.accuracy:.2%} < threshold={cfg.accuracy_threshold:.2%}, "
                    f"samples={result.sample_count}, trend declining"
                )
                event = LearningEvent(
                    event_type=    "retrain_requested",
                    agent_name=    agent_name,
                    model_version= model_version,
                    outcome=       "retrain_requested",
                    confidence=    result.accuracy,
                    metadata={
                        "accuracy":   result.accuracy,
                        "f1":         result.f1,
                        "ece":        result.ece,
                        "samples":    result.sample_count,
                    },
                )
                return TriggerResult(fired=True, reason=reason, event=event, conditions_met=conditions)

            # Build reason for why it did NOT fire
            unmet = [k for k, v in conditions.items() if not v]
            reason = f"Not triggered — unmet: {', '.join(unmet)}" if unmet else "All conditions met but no trigger"
            return TriggerResult(fired=False, reason=reason, conditions_met=conditions)

        except Exception as exc:
            logger.debug("RetrainingTrigger.check failed: %s", exc)
            return TriggerResult(fired=False, reason=f"error: {exc}")

    def reset_cooldown(self) -> None:
        """Reset the cooldown timer (useful for testing)."""
        self._last_trigger_at = 0.0

    def reset_history(self) -> None:
        """Clear accuracy history (useful for testing)."""
        self._history.clear()


# ── Trend helper ──────────────────────────────────────────────────────────────

def _trend_is_flat_or_declining(history: List[float], window: int) -> bool:
    """
    True if the recent `window` accuracy values show no improvement.
    Returns True (conservative) when there is insufficient history.
    """
    if len(history) < window:
        return True   # not enough data — assume declining (conservative)
    recent = history[-window:]
    # Declining: last value <= first value in the window
    return recent[-1] <= recent[0]
