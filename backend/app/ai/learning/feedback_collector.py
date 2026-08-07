"""
app/ai/learning/feedback_collector.py
=======================================
FeedbackCollector -- records actual trade outcomes vs predicted.

Design
------
  - FeedbackRecord carries: prediction, actual outcome, confidence,
    model version, agent, market regime, and reasoning path.
    These fields are exactly what ModelEvaluator needs for accuracy
    and calibration metrics.
  - Stored in LTM as MemoryEntry with entry_type="feedback_record"
    and importance=1.0 (never dropped).
  - FeedbackReader retrieves records for ModelEvaluator.

Resilience (Rule 11b):
  record() and recent() never raise. Return None / [] on failure.
"""
from __future__ import annotations

import json
import logging
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from app.ai.memory.long_term import LongTermMemory
from app.ai.memory.short_term import MemoryEntry, MemoryRole

logger = logging.getLogger(__name__)


# ── FeedbackRecord ────────────────────────────────────────────────────────────

@dataclass
class FeedbackRecord:
    """
    One feedback entry: what was predicted vs what actually happened.

    Fields
    ------
    trade_id:       unique identifier for the trade / request
    prediction:     what the model predicted ("BUY", "SELL", "HOLD", etc.)
    actual:         what actually happened ("profit", "loss", "neutral", etc.)
    correct:        True if prediction matched actual direction
    confidence:     model confidence at prediction time
    model_version:  which model version made the prediction
    agent_name:     which agent produced the signal
    market_regime:  market context at prediction time
    reasoning_path: step_summary from the ReasoningTrace
    """
    trade_id:       str            = field(default_factory=lambda: str(uuid.uuid4()))
    prediction:     str            = ""
    actual:         str            = ""
    correct:        bool           = False
    confidence:     float          = 0.0
    model_version:  str            = ""
    agent_name:     str            = ""
    market_regime:  str            = ""
    reasoning_path: str            = ""
    timestamp:      float          = field(default_factory=time.time)
    metadata:       Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "trade_id":       self.trade_id,
            "prediction":     self.prediction,
            "actual":         self.actual,
            "correct":        self.correct,
            "confidence":     self.confidence,
            "model_version":  self.model_version,
            "agent_name":     self.agent_name,
            "market_regime":  self.market_regime,
            "reasoning_path": self.reasoning_path,
            "timestamp":      self.timestamp,
            **self.metadata,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "FeedbackRecord":
        known = {
            "trade_id", "prediction", "actual", "correct", "confidence",
            "model_version", "agent_name", "market_regime", "reasoning_path", "timestamp",
        }
        meta = {k: v for k, v in d.items() if k not in known}
        return cls(
            trade_id=      d.get("trade_id",       str(uuid.uuid4())),
            prediction=    d.get("prediction",     ""),
            actual=        d.get("actual",         ""),
            correct=       bool(d.get("correct",   False)),
            confidence=    float(d.get("confidence", 0.0)),
            model_version= d.get("model_version",  ""),
            agent_name=    d.get("agent_name",     ""),
            market_regime= d.get("market_regime",  ""),
            reasoning_path=d.get("reasoning_path", ""),
            timestamp=     float(d.get("timestamp", time.time())),
            metadata=      meta,
        )


# ── FeedbackCollector ─────────────────────────────────────────────────────────

class FeedbackCollector:
    """
    Records FeedbackRecords to LTM.

    Usage
    -----
        collector = FeedbackCollector(ltm=qdrant_ltm)
        record = await collector.record(
            prediction="BUY", actual="profit", correct=True,
            confidence=0.82, model_version="v1.3",
            agent_name="TraderAgent", market_regime="trending",
        )
    """

    def __init__(self, ltm: Optional[LongTermMemory] = None) -> None:
        self._ltm = ltm

    async def record(
        self,
        prediction:     str,
        actual:         str,
        correct:        bool,
        confidence:     float          = 0.0,
        model_version:  str            = "",
        agent_name:     str            = "",
        market_regime:  str            = "",
        reasoning_path: str            = "",
        trade_id:       Optional[str]  = None,
        metadata:       Optional[Dict[str, Any]] = None,
    ) -> Optional[FeedbackRecord]:
        """
        Build and store a FeedbackRecord. Returns the record on success,
        None if LTM is unavailable or storage fails. Never raises.
        """
        if self._ltm is None:
            return None
        try:
            fb = FeedbackRecord(
                trade_id=      trade_id or str(uuid.uuid4()),
                prediction=    prediction,
                actual=        actual,
                correct=       correct,
                confidence=    confidence,
                model_version= model_version,
                agent_name=    agent_name,
                market_regime= market_regime,
                reasoning_path=reasoning_path,
                metadata=      metadata or {},
            )
            entry = _record_to_entry(fb)
            await self._ltm.store(entry)
            return fb
        except Exception as exc:
            logger.debug("FeedbackCollector.record failed: %s", exc)
            return None

    async def record_feedback(self, fb: FeedbackRecord) -> bool:
        """Store a pre-built FeedbackRecord. Returns True on success."""
        if self._ltm is None:
            return False
        try:
            entry = _record_to_entry(fb)
            await self._ltm.store(entry)
            return True
        except Exception as exc:
            logger.debug("FeedbackCollector.record_feedback failed: %s", exc)
            return False


# ── FeedbackReader ────────────────────────────────────────────────────────────

class FeedbackReader:
    """
    Retrieves FeedbackRecords from LTM for ModelEvaluator.

    Returns [] on any failure (Rule 11b).
    """

    def __init__(self, ltm: Optional[LongTermMemory] = None) -> None:
        self._ltm = ltm

    async def recent(self, n: int = 50) -> List[FeedbackRecord]:
        """Return up to n recent FeedbackRecords."""
        if self._ltm is None:
            return []
        try:
            if hasattr(self._ltm, "all_entries"):
                all_e = await self._ltm.all_entries()
            else:
                all_e = await self._ltm.search("feedback_record", top_k=n * 5)
            records = []
            for e in all_e:
                r = _entry_to_record(e)
                if r is not None:
                    records.append(r)
            return records[:n]
        except Exception as exc:
            logger.debug("FeedbackReader.recent failed: %s", exc)
            return []

    async def by_model(self, model_version: str, n: int = 50) -> List[FeedbackRecord]:
        """Return records for a specific model version."""
        all_r = await self.recent(n=n * 3)
        return [r for r in all_r if r.model_version == model_version][:n]

    async def by_agent(self, agent_name: str, n: int = 50) -> List[FeedbackRecord]:
        """Return records for a specific agent."""
        all_r = await self.recent(n=n * 3)
        return [r for r in all_r if r.agent_name == agent_name][:n]


# ── Helpers ───────────────────────────────────────────────────────────────────

def _record_to_entry(fb: FeedbackRecord) -> MemoryEntry:
    content = json.dumps(fb.to_dict(), ensure_ascii=False)
    return MemoryEntry(
        content=content,
        role=MemoryRole.ASSISTANT,
        session_id="",
        importance=1.0,
        metadata={
            "entry_type":    "feedback_record",
            "correct":       fb.correct,
            "model_version": fb.model_version,
            "agent_name":    fb.agent_name,
        },
    )


def _entry_to_record(entry: MemoryEntry) -> Optional[FeedbackRecord]:
    try:
        if entry.metadata.get("entry_type") != "feedback_record":
            return None
        d = json.loads(entry.content)
        return FeedbackRecord.from_dict(d)
    except Exception:
        return None
