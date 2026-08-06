"""
app/ai/runtime/context.py
=========================
ExecutionContext -- the single state object for one AI request.

Travels through every stage of the Thinking Pipeline.
Each stage reads from it and writes its results back into it.
Completely domain-agnostic: no trading, market, or stock knowledge.

State machine transitions are tracked via the RequestState enum.
Timings are recorded per stage for observability.
"""
from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class RequestState(str, Enum):
    """Every request moves through these states in order."""
    CREATED             = "created"
    PLANNING            = "planning"
    MEMORY_LOADING      = "memory_loading"
    SKILL_SELECTION     = "skill_selection"
    TOOL_EXECUTION      = "tool_execution"
    REASONING           = "reasoning"
    VERIFICATION        = "verification"
    RESPONSE_GENERATION = "response_generation"
    COMPLETED           = "completed"
    FAILED              = "failed"


@dataclass
class ConversationTurn:
    """One turn in the conversation history."""
    role: str       # "user" or "assistant"
    content: str
    timestamp: float = field(default_factory=time.time)


@dataclass
class SkillResult:
    """Output from one skill execution."""
    skill_name: str
    success: bool
    output: Any
    error: Optional[str] = None
    elapsed_ms: float = 0.0


@dataclass
class ToolResult:
    """Output from one tool execution."""
    tool_name: str
    success: bool
    output: Any
    error: Optional[str] = None
    elapsed_ms: float = 0.0


@dataclass
class ThoughtStep:
    """One step in the chain-of-thought reasoning trace."""
    content: str
    confidence: float       # 0.0 - 1.0
    step_index: int = 0


@dataclass
class ExecutionContext:
    """
    Carries all state for one AI request through the Thinking Pipeline.

    Created by ExecutionEngine at request start.
    Discarded after the response is returned -- never persisted.

    Fields are grouped by the pipeline stage that populates them.
    """

    # ── Identity ──────────────────────────────────────────────────────
    request_id:     str = field(default_factory=lambda: str(uuid.uuid4()))
    session_id:     str = ""
    user_input:     str = ""

    # ── Conversation ──────────────────────────────────────────────────
    history:        List[ConversationTurn] = field(default_factory=list)

    # ── State machine ─────────────────────────────────────────────────
    state:          RequestState = RequestState.CREATED
    error:          Optional[str] = None

    # ── Planning stage ────────────────────────────────────────────────
    active_goal:    str = ""
    intent_type:    str = ""
    selected_agent: str = ""

    # ── Memory stage ──────────────────────────────────────────────────
    memory_context: List[Any] = field(default_factory=list)

    # ── Skill / Tool stage ────────────────────────────────────────────
    skill_results:  Dict[str, SkillResult] = field(default_factory=dict)
    tool_results:   Dict[str, ToolResult]  = field(default_factory=dict)

    # ── Reasoning stage ───────────────────────────────────────────────
    thought_chain:  List[ThoughtStep] = field(default_factory=list)
    critique:       str = ""
    retry_count:    int = 0

    # ── Confidence stage ──────────────────────────────────────────────
    confidence:     float = 0.0

    # ── Response stage ────────────────────────────────────────────────
    response:       str = ""
    explanation:    str = ""

    # ── Observability ─────────────────────────────────────────────────
    timings:        Dict[str, float] = field(default_factory=dict)
    metadata:       Dict[str, Any]   = field(default_factory=dict)

    # ── Internal ──────────────────────────────────────────────────────
    _stage_start:   float = field(default_factory=time.time, repr=False)

    # ── State transitions ─────────────────────────────────────────────

    def transition(self, new_state: RequestState) -> None:
        """Advance to the next state and record elapsed time for the current stage."""
        elapsed = (time.time() - self._stage_start) * 1000
        self.timings[self.state.value] = round(elapsed, 2)
        self.state = new_state
        self._stage_start = time.time()

    def fail(self, error: str) -> None:
        """Transition to FAILED and record the error."""
        elapsed = (time.time() - self._stage_start) * 1000
        self.timings[self.state.value] = round(elapsed, 2)
        self.error = error
        self.state = RequestState.FAILED
        self._stage_start = time.time()

    # ── Convenience ───────────────────────────────────────────────────

    def is_failed(self) -> bool:
        return self.state == RequestState.FAILED

    def is_complete(self) -> bool:
        return self.state in (RequestState.COMPLETED, RequestState.FAILED)

    def total_elapsed_ms(self) -> float:
        """Sum of all recorded stage timings."""
        return round(sum(self.timings.values()), 2)

    def add_history(self, role: str, content: str) -> None:
        self.history.append(ConversationTurn(role=role, content=content))

    def recent_history(self, n: int = 10) -> List[ConversationTurn]:
        return self.history[-n:]

    def summary(self) -> dict:
        """Compact dict for logging and metrics."""
        return {
            "request_id":     self.request_id,
            "session_id":     self.session_id,
            "state":          self.state.value,
            "selected_agent": self.selected_agent,
            "intent_type":    self.intent_type,
            "confidence":     self.confidence,
            "retry_count":    self.retry_count,
            "total_ms":       self.total_elapsed_ms(),
            "timings":        self.timings,
            "error":          self.error,
        }
