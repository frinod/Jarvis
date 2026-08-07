"""
app/ai/learning/learning_event.py
===================================
LearningEvent + ExperienceRecord — the stable boundary between the
reasoning package and the learning package.

Design
------
  LearningEvent
    Describes *what happened* in one reasoning episode.
    Built from a ReasoningTrace. The LearningEngine never imports
    ReasoningTrace directly — it only sees LearningEvent.

  ExperienceRecord
    Describes *what should be remembered* from a LearningEvent.
    Produced by the LearningEngine after evaluating a LearningEvent.
    Stored in LTM with importance=1.0 so it is never dropped.

  This two-step boundary means:
    - ReasoningTrace format can change without touching LearningEngine.
    - ExperienceRecord format can change without touching ReasoningLogger.

Event types
-----------
  "prediction_outcome"  — a prediction was made and the outcome is known
  "retrain_requested"   — retraining trigger fired
  "model_registered"    — a new model version was registered
  "model_rolled_back"   — rollback to a previous version
  "feedback_recorded"   — raw feedback stored (no outcome yet)
"""
from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, Optional


# ── LearningEvent ─────────────────────────────────────────────────────────────

@dataclass
class LearningEvent:
    """
    Describes what happened in one reasoning or trading episode.

    Built from a ReasoningTrace (via from_trace()) or constructed directly
    for non-reasoning events (retrain_requested, model_registered, etc.).

    The LearningEngine consumes LearningEvents — it never imports
    ReasoningTrace. This is the stable boundary.
    """
    event_id:      str            = field(default_factory=lambda: str(uuid.uuid4()))
    event_type:    str            = "prediction_outcome"   # see module docstring
    session_id:    str            = ""
    request_id:    str            = ""
    agent_name:    str            = ""
    intent_type:   str            = ""
    prediction:    str            = ""    # what was predicted / decided
    outcome:       str            = ""    # "success" | "failure" | "partial" | ""
    confidence:    float          = 0.0
    model_version: str            = ""
    market_regime: str            = ""    # e.g. "trending", "sideways", "volatile"
    reasoning_path: str           = ""    # step_summary from ReasoningTrace
    retry_count:   int            = 0
    timestamp:     float          = field(default_factory=time.time)
    metadata:      Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_trace(cls, trace: Any, model_version: str = "") -> "LearningEvent":
        """
        Build a LearningEvent from a ReasoningTrace.

        Accepts Any to avoid importing ReasoningTrace here (boundary rule).
        Callers that have a ReasoningTrace pass it directly.
        """
        return cls(
            event_type=    "prediction_outcome",
            session_id=    getattr(trace, "session_id",   ""),
            request_id=    getattr(trace, "request_id",   ""),
            agent_name=    getattr(trace, "agent_name",   ""),
            intent_type=   getattr(trace, "intent_type",  ""),
            prediction=    getattr(trace, "goal",         ""),
            outcome=       getattr(trace, "outcome",      ""),
            confidence=    getattr(trace, "confidence",   0.0),
            model_version= model_version,
            market_regime= getattr(trace, "metadata", {}).get("market_regime", ""),
            reasoning_path=getattr(trace, "step_summary", ""),
            retry_count=   getattr(trace, "retry_count",  0),
        )

    def to_dict(self) -> dict:
        return {
            "event_id":      self.event_id,
            "event_type":    self.event_type,
            "session_id":    self.session_id,
            "request_id":    self.request_id,
            "agent_name":    self.agent_name,
            "intent_type":   self.intent_type,
            "prediction":    self.prediction,
            "outcome":       self.outcome,
            "confidence":    self.confidence,
            "model_version": self.model_version,
            "market_regime": self.market_regime,
            "reasoning_path":self.reasoning_path,
            "retry_count":   self.retry_count,
            "timestamp":     self.timestamp,
            **self.metadata,
        }


# ── ExperienceRecord ──────────────────────────────────────────────────────────

@dataclass
class ExperienceRecord:
    """
    Describes what should be remembered from a LearningEvent.

    Produced by the LearningEngine after evaluating a LearningEvent.
    Stored in LTM so future retrieval can surface relevant lessons.

    lesson:               human-readable summary of what was learned
    confidence_adjustment: suggested delta to apply to future confidence
                           scores for similar contexts (negative = reduce)
    source_event_id:      links back to the originating LearningEvent
    """
    record_id:             str            = field(default_factory=lambda: str(uuid.uuid4()))
    source_event_id:       str            = ""
    agent_name:            str            = ""
    intent_type:           str            = ""
    market_regime:         str            = ""
    outcome:               str            = ""
    lesson:                str            = ""
    confidence_adjustment: float          = 0.0
    model_version:         str            = ""
    timestamp:             float          = field(default_factory=time.time)
    metadata:              Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "record_id":              self.record_id,
            "source_event_id":        self.source_event_id,
            "agent_name":             self.agent_name,
            "intent_type":            self.intent_type,
            "market_regime":          self.market_regime,
            "outcome":                self.outcome,
            "lesson":                 self.lesson,
            "confidence_adjustment":  self.confidence_adjustment,
            "model_version":          self.model_version,
            "timestamp":              self.timestamp,
            **self.metadata,
        }

    @classmethod
    def from_event(cls, event: LearningEvent, lesson: str, confidence_adjustment: float = 0.0) -> "ExperienceRecord":
        """Build an ExperienceRecord from a LearningEvent + derived lesson."""
        return cls(
            source_event_id=      event.event_id,
            agent_name=           event.agent_name,
            intent_type=          event.intent_type,
            market_regime=        event.market_regime,
            outcome=              event.outcome,
            lesson=               lesson,
            confidence_adjustment=confidence_adjustment,
            model_version=        event.model_version,
        )
