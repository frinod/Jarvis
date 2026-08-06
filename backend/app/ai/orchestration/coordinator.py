"""
app/ai/orchestration/coordinator.py
=====================================
AgentCoordinator -- capability-based agent selection.

Responsibilities
----------------
  - Maintain a registry of available agents (AgentRegistry)
  - Score every healthy agent against the current goal (SelectionPolicy)
  - Return the best-matched agent name and full selection rationale
  - Record every selection decision with source="Coordinator"
  - Bridge to Brain via CoordinatorAgentSelector

Non-responsibilities (enforced by design)
------------------------------------------
  - Does NOT execute the pipeline (ExecutionEngine owns that)
  - Does NOT own goals or session state (Brain owns that)
  - Does NOT know what any agent does internally
  - Does NOT contain domain knowledge of any kind

Domain agnosticism
-------------------
  All domain data belongs in AgentDescriptor.metadata only.
  Capability and intent strings are plain strings -- no enums.
  Enforced by TestDomainAgnosticism.
"""
from __future__ import annotations

import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

from app.ai.brain.brain import BrainAgentSelector, Goal


# ── Agent health ──────────────────────────────────────────────────────────────

class AgentHealth(str, Enum):
    """
    Richer than bool: DEGRADED agents are still usable.
    OFFLINE and STOPPING agents are excluded from selection.
    """
    HEALTHY  = "healthy"
    DEGRADED = "degraded"   # usable but impaired
    OFFLINE  = "offline"    # excluded from selection
    STARTING = "starting"   # excluded until ready
    STOPPING = "stopping"   # excluded from new requests

    def is_available(self) -> bool:
        return self in (AgentHealth.HEALTHY, AgentHealth.DEGRADED)


# ── Agent descriptor ──────────────────────────────────────────────────────────

@dataclass
class AgentDescriptor:
    """
    Everything the Coordinator needs to know about an agent.
    The Coordinator never touches the concrete agent class -- only this.

    capabilities and supported_intents are plain strings so the registry
    stays domain-agnostic and new capabilities never require code changes.
    """
    name:                 str
    version:              str            = "1.0"
    priority:             int            = 3          # 1 (highest) to 5 (lowest)
    capabilities:         List[str]      = field(default_factory=list)
    supported_intents:    List[str]      = field(default_factory=list)
    supports_streaming:   bool           = False
    supports_parallel:    bool           = False      # Phase 7
    estimated_latency_ms: int            = 500
    metadata:             Dict[str, Any] = field(default_factory=dict)


# ── Agent metrics ─────────────────────────────────────────────────────────────

@dataclass
class AgentMetrics:
    """
    Runtime performance record for one agent.
    Not used by SelectionPolicy today -- reserved for Phase 7+ learning.
    SelectionPolicy can incorporate success_rate and avg_latency_ms
    once enough data is collected.
    """
    agent_name:        str
    requests:          int   = 0
    successes:         int   = 0
    failures:          int   = 0
    total_latency_ms:  float = 0.0
    total_confidence:  float = 0.0
    last_used:         float = 0.0
    last_failure:      float = 0.0

    @property
    def success_rate(self) -> float:
        return (self.successes / self.requests) if self.requests > 0 else 0.0

    @property
    def avg_latency_ms(self) -> float:
        return (self.total_latency_ms / self.requests) if self.requests > 0 else 0.0

    @property
    def avg_confidence(self) -> float:
        return (self.total_confidence / self.successes) if self.successes > 0 else 0.0

    def record(self, success: bool, latency_ms: float, confidence: float = 0.0) -> None:
        self.requests        += 1
        self.total_latency_ms += latency_ms
        self.last_used        = time.time()
        if success:
            self.successes       += 1
            self.total_confidence += confidence
        else:
            self.failures    += 1
            self.last_failure = time.time()


# ── Selection weights ─────────────────────────────────────────────────────────

@dataclass
class SelectionWeights:
    """
    Configurable scoring weights for CapabilityMatchPolicy.
    intent + capability + priority must sum to <= 1.0.
    """
    intent:     float = 0.5
    capability: float = 0.4
    priority:   float = 0.1


# ── Agent score ───────────────────────────────────────────────────────────────

@dataclass
class AgentScore:
    """Score assigned to one agent for one goal."""
    agent_name:           str
    score:                float          # 0.0 – 1.0
    rationale:            str
    matched_capabilities: List[str]      = field(default_factory=list)
    matched_intents:      List[str]      = field(default_factory=list)
    estimated_latency_ms: int            = 0


# ── Selection result ──────────────────────────────────────────────────────────

@dataclass
class SelectionResult:
    """
    Full output of one selection pass.
    Explains why one agent was chosen and all others were rejected.
    Invaluable for debugging and the future HUD decision trace.
    """
    selected_agent:   str
    candidate_scores: List[AgentScore]
    selection_reason: str
    rejected_agents:  List[str]          = field(default_factory=list)
    selection_time_ms: float             = 0.0


# ── Coordinator result ────────────────────────────────────────────────────────

@dataclass
class CoordinatorResult:
    """
    Returned by Coordinator.select().
    selected_agents is empty today; populated in Phase 7 parallel execution.
    """
    agent_name:      str
    score:           AgentScore
    goal_id:         str
    selection:       SelectionResult
    selected_agents: List[str]           = field(default_factory=list)  # Phase 7
    metadata:        Dict[str, Any]      = field(default_factory=dict)


# ── No-agent error ────────────────────────────────────────────────────────────

class NoAgentAvailableError(Exception):
    """Raised when no healthy agent can handle the goal."""
    def __init__(self, goal_id: str = "", reason: str = ""):
        self.goal_id = goal_id
        self.reason  = reason
        super().__init__(f"No agent available for goal '{goal_id}': {reason}")


# ── Selection policy ──────────────────────────────────────────────────────────

class SelectionPolicy(ABC):
    """Scores one agent descriptor against one goal."""
    @abstractmethod
    def score(self, goal: Goal, descriptor: AgentDescriptor) -> AgentScore:
        pass


class CapabilityMatchPolicy(SelectionPolicy):
    """
    Default scoring policy.

    Score = intent_match * weights.intent
           + capability_overlap * weights.capability
           + priority_bonus * weights.priority

    Tie-breaking (equal scores): lower estimated_latency_ms wins.
    All weights are configurable via SelectionWeights.
    """

    def __init__(self, weights: Optional[SelectionWeights] = None):
        self._w = weights or SelectionWeights()

    def score(self, goal: Goal, descriptor: AgentDescriptor) -> AgentScore:
        intent_type          = goal.metadata.get("intent_type", "")
        required_caps: List[str] = goal.metadata.get("required_capabilities", [])

        # Intent match
        matched_intents = [intent_type] if intent_type in descriptor.supported_intents else []
        intent_score    = self._w.intent if matched_intents else 0.0

        # Capability overlap
        if required_caps and descriptor.capabilities:
            overlap      = set(required_caps) & set(descriptor.capabilities)
            cap_score    = (len(overlap) / len(required_caps)) * self._w.capability
            matched_caps = list(overlap)
        else:
            cap_score    = 0.0
            matched_caps = []

        # Priority bonus: priority 1 → 0.10, priority 5 → 0.02
        priority_score = ((6 - descriptor.priority) / 5) * self._w.priority

        total = round(intent_score + cap_score + priority_score, 4)

        rationale = (
            f"intent={'matched' if matched_intents else 'no match'} "
            f"({intent_score:.2f}), "
            f"caps={len(matched_caps)}/{len(required_caps) if required_caps else 0} "
            f"({cap_score:.2f}), "
            f"priority={descriptor.priority} ({priority_score:.2f})"
        )

        return AgentScore(
            agent_name=descriptor.name,
            score=total,
            rationale=rationale,
            matched_capabilities=matched_caps,
            matched_intents=matched_intents,
            estimated_latency_ms=descriptor.estimated_latency_ms,
        )


# ── Agent registry ────────────────────────────────────────────────────────────

class AgentRegistry:
    """
    Single source of truth for registered agents.

    Coordinator reads from it. Agents write to it at startup.
    Registry is the only place that knows which agents exist.
    Brain and Coordinator never hold agent references directly.
    """

    def __init__(self) -> None:
        self._descriptors: Dict[str, AgentDescriptor] = {}
        self._health:      Dict[str, AgentHealth]     = {}
        self._metrics:     Dict[str, AgentMetrics]    = {}

    def register(self, descriptor: AgentDescriptor) -> None:
        """Register an agent. Overwrites any existing registration."""
        self._descriptors[descriptor.name] = descriptor
        if descriptor.name not in self._health:
            self._health[descriptor.name]  = AgentHealth.HEALTHY
        if descriptor.name not in self._metrics:
            self._metrics[descriptor.name] = AgentMetrics(agent_name=descriptor.name)

    def deregister(self, name: str) -> None:
        self._descriptors.pop(name, None)
        self._health.pop(name, None)
        self._metrics.pop(name, None)

    def set_health(self, name: str, health: AgentHealth) -> None:
        if name in self._descriptors:
            self._health[name] = health

    def get_health(self, name: str) -> Optional[AgentHealth]:
        return self._health.get(name)

    def get(self, name: str) -> Optional[AgentDescriptor]:
        return self._descriptors.get(name)

    def available(self) -> List[AgentDescriptor]:
        """Return only agents whose health allows selection."""
        return [
            d for name, d in self._descriptors.items()
            if self._health.get(name, AgentHealth.OFFLINE).is_available()
        ]

    def find(self, capability: str) -> List[AgentDescriptor]:
        """Return all available agents that declare the given capability."""
        return [d for d in self.available() if capability in d.capabilities]

    def all_names(self) -> List[str]:
        return list(self._descriptors.keys())

    def metrics(self, name: str) -> Optional[AgentMetrics]:
        return self._metrics.get(name)

    def record(self, name: str, success: bool, latency_ms: float, confidence: float = 0.0) -> None:
        if name in self._metrics:
            self._metrics[name].record(success, latency_ms, confidence)


# ── Coordinator ───────────────────────────────────────────────────────────────

class Coordinator:
    """
    Routes a Goal to the best available agent.

    Selection process
    -----------------
      1. Ask registry for all healthy/degraded agents
      2. Score each against the goal using SelectionPolicy
      3. Pick highest score; break ties by estimated_latency_ms (lower wins)
      4. Return CoordinatorResult with full SelectionResult for audit trail

    The Coordinator never executes the pipeline and never knows what
    any agent does internally.
    """

    def __init__(
        self,
        registry: AgentRegistry,
        policy:   Optional[SelectionPolicy] = None,
    ):
        self._registry = registry
        self._policy   = policy or CapabilityMatchPolicy()

    def select(self, goal: Goal) -> CoordinatorResult:
        """
        Select the best agent for the goal.
        Raises NoAgentAvailableError if no healthy agent exists.
        """
        t_start    = time.monotonic()
        candidates = self._registry.available()

        if not candidates:
            raise NoAgentAvailableError(
                goal_id=goal.id,
                reason="registry is empty or all agents are offline",
            )

        scores = [self._policy.score(goal, d) for d in candidates]

        # Sort: highest score first; tie-break by lowest latency
        scores.sort(key=lambda s: (-s.score, s.estimated_latency_ms))
        best      = scores[0]
        rejected  = [s.agent_name for s in scores[1:]]

        selection = SelectionResult(
            selected_agent=best.agent_name,
            candidate_scores=scores,
            selection_reason=best.rationale,
            rejected_agents=rejected,
            selection_time_ms=round((time.monotonic() - t_start) * 1000, 3),
        )

        return CoordinatorResult(
            agent_name=best.agent_name,
            score=best,
            goal_id=goal.id,
            selection=selection,
        )

    @property
    def registry(self) -> AgentRegistry:
        return self._registry


# ── Brain bridge ──────────────────────────────────────────────────────────────

class CoordinatorAgentSelector(BrainAgentSelector):
    """
    Bridges Coordinator to Brain's BrainAgentSelector ABC.

    Brain calls selector.select(goal, available_agents) -> str.
    This adapter delegates to Coordinator.select(goal) and returns
    the agent name, keeping Brain's interface unchanged.

    available_agents is ignored -- the Coordinator's registry is
    the authoritative source of available agents.
    """

    def __init__(self, coordinator: Coordinator):
        self._coordinator = coordinator

    def select(self, goal: Goal, available_agents: List[str]) -> str:
        result = self._coordinator.select(goal)
        return result.agent_name
