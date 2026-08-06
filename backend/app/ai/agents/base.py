"""
app/ai/agents/base.py
======================
BaseAgent -- the full agent contract for the JARVIS AI Runtime.

Every agent in the runtime implements this interface.
No agent may be registered with the Coordinator unless it fully
implements all methods (enforced by ABC).

Architecture §12 defines the contract. This file implements it exactly.

Domain agnosticism
-------------------
  BaseAgent contains zero domain knowledge.
  Domain logic lives in concrete agent subclasses.
  All domain data travels through ExecutionContext.metadata.
"""
from __future__ import annotations

import time
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

from app.ai.runtime.context import ExecutionContext


# ── Agent status ──────────────────────────────────────────────────────────────

class AgentStatus(str, Enum):
    INITIALISING = "initialising"
    HEALTHY      = "healthy"
    DEGRADED     = "degraded"
    OFFLINE      = "offline"


# ── Agent result ──────────────────────────────────────────────────────────────

@dataclass
class AgentPlan:
    """Decomposed execution plan from BaseAgent.plan()."""
    steps:                List[str]
    estimated_confidence: float          = 0.6
    metadata:             Dict[str, Any] = field(default_factory=dict)


@dataclass
class AgentResult:
    """
    Output of BaseAgent.execute().
    Carries the response, confidence, explanation, and any domain data
    in metadata (never as first-class fields).
    """
    agent_name:  str
    response:    str
    confidence:  float
    explanation: str            = ""
    success:     bool           = True
    error:       Optional[str]  = None
    elapsed_ms:  float          = 0.0
    metadata:    Dict[str, Any] = field(default_factory=dict)


@dataclass
class VerificationResult:
    """Output of BaseAgent.verify()."""
    passed:       bool
    critique:     str
    retry:        bool           = False
    metadata:     Dict[str, Any] = field(default_factory=dict)


# ── BaseAgent ABC ─────────────────────────────────────────────────────────────

class BaseAgent(ABC):
    """
    Full agent contract for the JARVIS AI Runtime.

    Every agent implements all seven methods.
    The Coordinator selects agents via can_handle().
    ExecutionEngine drives the lifecycle via plan() → execute() → verify().

    Usage
    -----
        class MyAgent(BaseAgent):
            name = "my_agent"
            capabilities = ["general"]

            def can_handle(self, context): ...
            async def plan(self, context): ...
            async def execute(self, context): ...
            async def verify(self, result): ...
            def confidence(self, result): ...
            def explain(self, result): ...
            async def learn(self, result, outcome): ...
    """

    name:         str  = "base_agent"
    version:      str  = "1.0.0"
    capabilities: List[str] = []

    def __init__(self) -> None:
        self._status:     AgentStatus = AgentStatus.INITIALISING
        self._created_at: float       = time.time()
        self._request_count: int      = 0
        self._error_count:   int      = 0

    # ── Contract methods ──────────────────────────────────────────────

    @abstractmethod
    def can_handle(self, context: ExecutionContext) -> bool:
        """
        Return True if this agent can handle the given context.
        Must be fast -- no I/O, no LLM calls.
        Used by Coordinator for agent selection.
        """

    @abstractmethod
    async def plan(self, context: ExecutionContext) -> AgentPlan:
        """
        Decompose the request into an ordered list of steps.
        Returns AgentPlan(steps, estimated_confidence).
        """

    @abstractmethod
    async def execute(self, context: ExecutionContext) -> AgentResult:
        """
        Run the full Thinking Pipeline for this agent.
        Returns AgentResult(response, confidence, explanation, metadata).
        """

    @abstractmethod
    async def verify(self, result: AgentResult) -> VerificationResult:
        """
        Self-check the result before returning it.
        Returns VerificationResult(passed, critique, retry).
        If retry=True, ExecutionEngine will re-run execute() with critique injected.
        """

    @abstractmethod
    def confidence(self, result: AgentResult) -> float:
        """
        Return a 0.0-1.0 confidence score for the result.
        Aggregates skill signals, reasoning confidence, and perception quality.
        """

    @abstractmethod
    def explain(self, result: AgentResult) -> str:
        """
        Return a human-readable explanation of how the result was produced.
        Injected into the final response by SystemPromptBuilder.
        """

    @abstractmethod
    async def learn(self, result: AgentResult, outcome: dict) -> None:
        """
        Called after the user receives the response and an outcome is known.
        Phase 6: stores to LongTermMemory. Phase 8: feeds Learning Engine.
        """

    # ── Lifecycle ─────────────────────────────────────────────────────

    def initialize(self) -> None:
        """Called by LifecycleManager on startup. Override to add setup logic."""
        self._status = AgentStatus.HEALTHY

    def shutdown(self) -> None:
        """Called by LifecycleManager on shutdown. Override to add teardown logic."""
        self._status = AgentStatus.OFFLINE

    def health_check(self) -> AgentStatus:
        """Return current health status. Override for custom health logic."""
        return self._status

    # ── Metrics ───────────────────────────────────────────────────────

    def record_request(self, success: bool = True) -> None:
        self._request_count += 1
        if not success:
            self._error_count += 1

    def stats(self) -> Dict[str, Any]:
        return {
            "name":          self.name,
            "version":       self.version,
            "status":        self._status.value,
            "capabilities":  self.capabilities,
            "requests":      self._request_count,
            "errors":        self._error_count,
            "error_rate":    (
                round(self._error_count / self._request_count, 3)
                if self._request_count > 0 else 0.0
            ),
        }
