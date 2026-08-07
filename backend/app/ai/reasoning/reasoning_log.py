"""
app/ai/reasoning/reasoning_log.py
===================================
ReasoningLog -- persists reasoning traces to LongTermMemory.

Design
------
  - ReasoningTrace: structured record of one reasoning episode.
    Captures: goal, intent, thought chain summary, confidence, outcome,
    agent name, retry count, and arbitrary metadata.
  - ReasoningLogger: serialises a ReasoningTrace to a MemoryEntry and
    stores it in LongTermMemory. Best-effort -- never raises (Rule 11b).
  - ReasoningLogReader: retrieves past traces from LTM for XAI and
    learning (Phase 7D). Returns [] on any failure.

Purpose
-------
  JARVIS learns from its own reasoning history. By persisting traces,
  Phase 7D's LearningEngine can:
    - Identify which reasoning patterns lead to high-confidence outcomes
    - Detect recurring failure modes
    - Adjust ChainConfig weights based on empirical evidence

Resilience (Rule 11b):
  log() and read() never raise. Failures are logged at DEBUG level.

Domain agnosticism:
  ReasoningTrace contains no domain fields.
  Domain data travels through metadata only.
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from app.ai.memory.long_term import LongTermMemory
from app.ai.memory.short_term import MemoryEntry, MemoryRole
from app.ai.runtime.context import ExecutionContext, ThoughtStep

logger = logging.getLogger(__name__)


# ── ReasoningTrace ────────────────────────────────────────────────────────────

@dataclass
class ReasoningTrace:
    """
    Structured record of one reasoning episode.

    Stored as a MemoryEntry in LTM with entry_type="reasoning_trace".
    Retrieved by ReasoningLogReader for XAI and learning.
    """
    request_id:    str
    session_id:    str
    goal:          str
    intent_type:   str
    agent_name:    str
    confidence:    float
    retry_count:   int
    step_count:    int
    step_summary:  str          # one-line summary of the thought chain
    outcome:       str          # "success" | "failure" | "partial"
    critique:      str          = ""
    metadata:      Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_context(cls, ctx: ExecutionContext, outcome: str = "success") -> "ReasoningTrace":
        """Build a ReasoningTrace from a completed ExecutionContext."""
        step_summary = _summarise_chain(ctx.thought_chain)
        return cls(
            request_id=ctx.request_id,
            session_id=ctx.session_id,
            goal=ctx.active_goal or ctx.user_input,
            intent_type=ctx.intent_type,
            agent_name=ctx.selected_agent,
            confidence=ctx.confidence,
            retry_count=ctx.retry_count,
            step_count=len(ctx.thought_chain),
            step_summary=step_summary,
            outcome=outcome,
            critique=ctx.critique,
        )

    def to_dict(self) -> dict:
        return {
            "request_id":   self.request_id,
            "session_id":   self.session_id,
            "goal":         self.goal,
            "intent_type":  self.intent_type,
            "agent_name":   self.agent_name,
            "confidence":   self.confidence,
            "retry_count":  self.retry_count,
            "step_count":   self.step_count,
            "step_summary": self.step_summary,
            "outcome":      self.outcome,
            "critique":     self.critique,
            **self.metadata,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "ReasoningTrace":
        known = {
            "request_id", "session_id", "goal", "intent_type", "agent_name",
            "confidence", "retry_count", "step_count", "step_summary",
            "outcome", "critique",
        }
        meta = {k: v for k, v in d.items() if k not in known}
        return cls(
            request_id=d.get("request_id", ""),
            session_id=d.get("session_id", ""),
            goal=d.get("goal", ""),
            intent_type=d.get("intent_type", ""),
            agent_name=d.get("agent_name", ""),
            confidence=float(d.get("confidence", 0.0)),
            retry_count=int(d.get("retry_count", 0)),
            step_count=int(d.get("step_count", 0)),
            step_summary=d.get("step_summary", ""),
            outcome=d.get("outcome", ""),
            critique=d.get("critique", ""),
            metadata=meta,
        )


# ── ReasoningLogger ───────────────────────────────────────────────────────────

class ReasoningLogger:
    """
    Serialises a ReasoningTrace to a MemoryEntry and stores it in LTM.

    Best-effort: log() never raises. If LTM is unavailable, the trace
    is silently discarded (Rule 11b — intelligence layer must not affect
    trading engine stability).

    Usage
    -----
        logger = ReasoningLogger(ltm=qdrant_ltm)
        await logger.log(ctx, outcome="success")
    """

    def __init__(self, ltm: Optional[LongTermMemory] = None) -> None:
        self._ltm = ltm

    async def log(
        self,
        ctx:     ExecutionContext,
        outcome: str = "success",
    ) -> Optional[ReasoningTrace]:
        """
        Build a ReasoningTrace from ctx and store it in LTM.
        Returns the trace on success, None on failure.
        Never raises.
        """
        if self._ltm is None:
            return None
        try:
            trace   = ReasoningTrace.from_context(ctx, outcome=outcome)
            entry   = _trace_to_entry(trace)
            await self._ltm.store(entry)
            return trace
        except Exception as exc:
            logger.debug("ReasoningLogger.log failed: %s", exc)
            return None

    async def log_trace(self, trace: ReasoningTrace) -> bool:
        """Store a pre-built ReasoningTrace. Returns True on success."""
        if self._ltm is None:
            return False
        try:
            entry = _trace_to_entry(trace)
            await self._ltm.store(entry)
            return True
        except Exception as exc:
            logger.debug("ReasoningLogger.log_trace failed: %s", exc)
            return False


# ── ReasoningLogReader ────────────────────────────────────────────────────────

class ReasoningLogReader:
    """
    Retrieves past ReasoningTraces from LTM.

    Used by Phase 7D LearningEngine to analyse reasoning patterns.
    Returns [] on any failure (Rule 11b).

    Usage
    -----
        reader = ReasoningLogReader(ltm=qdrant_ltm)
        traces = await reader.recent(n=20)
        high_conf = [t for t in traces if t.confidence >= 0.8]
    """

    def __init__(self, ltm: Optional[LongTermMemory] = None) -> None:
        self._ltm = ltm

    async def recent(self, n: int = 20) -> List[ReasoningTrace]:
        """
        Return up to n recent reasoning traces from LTM.
        Returns [] if LTM is unavailable or no traces exist.
        Uses all_entries() + metadata filter so JSON content is not searched.
        """
        if self._ltm is None:
            return []
        try:
            # Prefer all_entries() so we can filter by metadata entry_type.
            # Falls back to search() for LTM implementations that lack all_entries().
            if hasattr(self._ltm, "all_entries"):
                all_e = await self._ltm.all_entries()
            else:
                all_e = await self._ltm.search("reasoning_trace", top_k=n * 5)
            traces = []
            for e in all_e:
                t = _entry_to_trace(e)
                if t is not None:
                    traces.append(t)
            return traces[:n]
        except Exception as exc:
            logger.debug("ReasoningLogReader.recent failed: %s", exc)
            return []

    async def by_outcome(self, outcome: str, n: int = 20) -> List[ReasoningTrace]:
        """Return traces filtered by outcome ('success', 'failure', 'partial')."""
        all_traces = await self.recent(n=n * 3)
        return [t for t in all_traces if t.outcome == outcome][:n]

    async def by_agent(self, agent_name: str, n: int = 20) -> List[ReasoningTrace]:
        """Return traces for a specific agent."""
        all_traces = await self.recent(n=n * 3)
        return [t for t in all_traces if t.agent_name == agent_name][:n]


# ── Helpers ───────────────────────────────────────────────────────────────────

def _summarise_chain(chain: List[ThoughtStep]) -> str:
    """One-line summary of a thought chain."""
    if not chain:
        return "no reasoning steps"
    final = chain[-1]
    return f"{len(chain)} steps, final confidence {final.confidence:.0%}: {final.content[:100]}"


def _trace_to_entry(trace: ReasoningTrace) -> MemoryEntry:
    """Serialise a ReasoningTrace to a MemoryEntry for LTM storage.

    importance is always 1.0 so the entry is stored regardless of the LTM
    importance_threshold. Low-confidence traces are exactly what the
    LearningEngine needs — they must never be silently dropped.
    """
    content = json.dumps(trace.to_dict(), ensure_ascii=False)
    return MemoryEntry(
        content=content,
        role=MemoryRole.ASSISTANT,
        session_id=trace.session_id,
        importance=1.0,   # always store — LearningEngine needs failure traces too
        metadata={
            "entry_type":  "reasoning_trace",
            "outcome":     trace.outcome,
            "agent_name":  trace.agent_name,
            "intent_type": trace.intent_type,
            "confidence":  trace.confidence,
        },
    )


def _entry_to_trace(entry: MemoryEntry) -> Optional[ReasoningTrace]:
    """Deserialise a MemoryEntry back to a ReasoningTrace. Returns None on failure."""
    try:
        if entry.metadata.get("entry_type") != "reasoning_trace":
            return None
        d = json.loads(entry.content)
        return ReasoningTrace.from_dict(d)
    except Exception:
        return None
