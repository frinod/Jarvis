"""
app/ai/brain/brain.py
=====================
Brain -- the central cognitive controller.

Responsibilities
----------------
  - Accept user input and create a Goal for every request
  - Own session state (active goals, decision history, reflection log)
  - Select execution policy, memory scope, and agent assignment
  - Delegate execution to ExecutionEngine
  - Aggregate confidence from multiple pipeline sources
  - Reflect on every completed request and produce actionable items
  - Record every significant decision for debugging and future learning

Non-responsibilities (enforced by design)
------------------------------------------
  - Does NOT execute pipeline stages (ExecutionEngine owns that)
  - Does NOT call the LLM directly
  - Does NOT contain domain knowledge of any kind
  - Does NOT store memories (MemoryProvider owns that)

Domain agnosticism
-------------------
  Brain contains zero domain knowledge.
  All domain data belongs in Goal.metadata / ExecutionContext.metadata only.
  Enforced by TestDomainAgnosticism.
"""
from __future__ import annotations

import time
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

from app.ai.runtime.context import ExecutionContext
from app.ai.runtime.execution import ExecutionEngine, ExecutionResult


# ── Goal ──────────────────────────────────────────────────────────────────────

class GoalStatus(str, Enum):
    PENDING   = "pending"
    ACTIVE    = "active"
    COMPLETED = "completed"
    FAILED    = "failed"
    ABANDONED = "abandoned"


@dataclass
class Goal:
    """
    Represents one thing the user wants to achieve.

    Brain creates one Goal per request.
    parent_goal_id enables future GoalTree decomposition without
    changing this data model.
    """
    id:             str            = field(default_factory=lambda: str(uuid.uuid4()))
    objective:      str            = ""
    priority:       int            = 3          # 1 (highest) to 5 (lowest)
    status:         GoalStatus     = GoalStatus.PENDING
    constraints:    List[str]      = field(default_factory=list)
    created_at:     float          = field(default_factory=time.time)
    owner_agent:    str            = ""
    confidence:     float          = 0.0
    result:         Any            = None
    parent_goal_id: Optional[str]  = None       # GoalTree: future sub-goal support
    metadata:       Dict[str, Any] = field(default_factory=dict)

    def activate(self) -> None:
        self.status = GoalStatus.ACTIVE

    def complete(self, result: Any = None, confidence: float = 0.0) -> None:
        self.status     = GoalStatus.COMPLETED
        self.result     = result
        self.confidence = confidence

    def fail(self, reason: str = "") -> None:
        self.status = GoalStatus.FAILED
        self.metadata["failure_reason"] = reason

    def abandon(self) -> None:
        self.status = GoalStatus.ABANDONED


# ── Decision record ───────────────────────────────────────────────────────────

@dataclass
class DecisionRecord:
    """
    Audit trail entry for one Brain decision.
    decision_source identifies which component made the decision,
    enabling per-component debugging in logs and the HUD.
    """
    decision_id:     str            = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp:       float          = field(default_factory=time.time)
    goal_id:         str            = ""
    decision_type:   str            = ""   # "agent_selection", "memory_scope", etc.
    decision_source: str            = ""   # "Brain", "Planner", "Coordinator", etc.
    rationale:       str            = ""
    outcome:         str            = ""   # populated after effect is known
    metadata:        Dict[str, Any] = field(default_factory=dict)


# ── Reflection ────────────────────────────────────────────────────────────────

@dataclass
class ActionItem:
    """One concrete action produced by Reflection."""
    action:      str   # e.g. "increase_memory_scope", "retry_reasoning"
    reason:      str
    priority:    int   = 3   # 1 (urgent) to 5 (low)


@dataclass
class ReflectionResult:
    """
    Produced after every completed request.
    Reflection is pure logic -- no LLM calls.
    action_items make lessons concrete and executable.
    """
    goal_id:            str
    objective_achieved: bool
    confidence_delta:   float        # how much to adjust future estimates
    should_store:       bool         # store to long-term memory?
    critique:           str
    action_items:       List[ActionItem] = field(default_factory=list)


# ── Execution policy and memory scope ────────────────────────────────────────

@dataclass
class MemoryScopeSpec:
    """How much memory to load for a request."""
    max_turns:            int   = 10
    include_long_term:    bool  = True
    relevance_threshold:  float = 0.6


@dataclass
class ExecutionPolicySpec:
    """
    Configures how the pipeline should run for a specific goal.
    Confidence weights are here so they can be tuned per-policy
    without touching Brain or ExecutionEngine.
    """
    max_retries:              int   = 2
    confidence_threshold:     float = 0.7
    timeout_ms:               int   = 10_000
    stream_mode:              bool  = False
    # Confidence aggregation weights (must sum to <= 1.0)
    weight_reasoner:          float = 0.5
    weight_skills:            float = 0.2
    weight_tools:             float = 0.2
    retry_confidence_penalty: float = 0.05


# ── Collaborator ABCs ─────────────────────────────────────────────────────────

class BrainAgentSelector(ABC):
    """Selects which agent should handle a goal. Pure logic, no I/O."""
    @abstractmethod
    def select(self, goal: Goal, available_agents: List[str]) -> str:
        pass


class BrainMemoryScope(ABC):
    """Determines how much memory to load for a goal."""
    @abstractmethod
    def scope(self, goal: Goal, history: List[Goal]) -> MemoryScopeSpec:
        pass


class BrainExecutionPolicy(ABC):
    """Returns the execution policy for a goal."""
    @abstractmethod
    def policy(self, goal: Goal) -> ExecutionPolicySpec:
        pass


# ── Default collaborators ─────────────────────────────────────────────────────

class _DefaultAgentSelector(BrainAgentSelector):
    def select(self, goal: Goal, available_agents: List[str]) -> str:
        return available_agents[0] if available_agents else "default"


class _DefaultMemoryScope(BrainMemoryScope):
    def scope(self, goal: Goal, history: List[Goal]) -> MemoryScopeSpec:
        return MemoryScopeSpec()


class _DefaultExecutionPolicy(BrainExecutionPolicy):
    def policy(self, goal: Goal) -> ExecutionPolicySpec:
        return ExecutionPolicySpec()


# ── Session state ─────────────────────────────────────────────────────────────

@dataclass
class SessionState:
    """
    Brain-owned session context.
    Centralises all session-level state so no separate SessionManager is needed.
    """
    session_id:          str            = ""
    active_agent:        str            = ""
    current_topic:       str            = ""
    conversation_summary: str           = ""
    last_response:       str            = ""
    context_window:      int            = 0    # turns loaded in last request
    created_at:          float          = field(default_factory=time.time)
    updated_at:          float          = field(default_factory=time.time)
    metadata:            Dict[str, Any] = field(default_factory=dict)

    def touch(self) -> None:
        self.updated_at = time.time()


# ── Brain capabilities ────────────────────────────────────────────────────────

@dataclass
class BrainCapabilities:
    """
    Feature flags for this Brain instance.
    Allows progressive capability rollout without code changes elsewhere.
    """
    supports_reflection:     bool = True
    supports_learning:       bool = False   # Phase 8
    supports_parallel_goals: bool = False   # Phase 7
    supports_goal_tree:      bool = False   # Phase 7
    supports_multi_agent:    bool = False   # Phase 6D+
    supports_memory:         bool = True
    supports_streaming:      bool = True


# ── Brain ─────────────────────────────────────────────────────────────────────

class Brain:
    """
    Central cognitive controller.

    Owns Goals, Decision History, Session State, Reflection, and
    Confidence Aggregation. Coordinates planning, memory scope selection,
    agent assignment, and execution policy. Does not execute the pipeline
    -- delegates to ExecutionEngine.

    Usage
    -----
        brain = Brain(engine=engine)
        result = await brain.process("what should I do today?", "sess-1")
    """

    def __init__(
        self,
        engine:           ExecutionEngine,
        agent_selector:   Optional[BrainAgentSelector]   = None,
        memory_scope:     Optional[BrainMemoryScope]     = None,
        execution_policy: Optional[BrainExecutionPolicy] = None,
        available_agents: Optional[List[str]]            = None,
        capabilities:     Optional[BrainCapabilities]    = None,
    ):
        self._engine           = engine
        self._agent_selector   = agent_selector   or _DefaultAgentSelector()
        self._memory_scope     = memory_scope     or _DefaultMemoryScope()
        self._execution_policy = execution_policy or _DefaultExecutionPolicy()
        self._available_agents = available_agents or []
        self.capabilities      = capabilities     or BrainCapabilities()

        self._active_goals:    List[Goal]           = []
        self._goal_history:    List[Goal]           = []
        self._decision_history: List[DecisionRecord] = []
        self._reflection_log:  List[ReflectionResult] = []
        self._sessions:        Dict[str, SessionState] = {}

    # ── Public entry point ────────────────────────────────────────────

    async def process(
        self,
        user_input: str,
        session_id: str = "",
        metadata:   Optional[Dict[str, Any]] = None,
    ) -> ExecutionResult:
        """
        Accept user input, create a Goal, configure the pipeline,
        delegate to ExecutionEngine, reflect on the outcome.
        Always returns an ExecutionResult -- never raises to the caller.
        """
        session = self._get_or_create_session(session_id)

        goal = Goal(objective=user_input, metadata=metadata or {})
        goal.activate()
        self._active_goals.append(goal)

        policy = self._execution_policy.policy(goal)
        scope  = self._memory_scope.scope(goal, self._goal_history)
        agent  = self._agent_selector.select(goal, self._available_agents)
        goal.owner_agent = agent

        self._record_decision(
            goal_id=goal.id,
            decision_type="agent_selection",
            decision_source="Brain",
            rationale=f"Selected agent '{agent}' for objective: {user_input[:80]}",
        )

        result = await self._engine.run(
            user_input=user_input,
            session_id=session_id,
            metadata={**goal.metadata, "_goal_id": goal.id, "_policy": policy},
        )

        final_confidence = self._aggregate_confidence(result.context, policy)
        result.context.confidence = final_confidence

        goal.complete(result=result.response, confidence=final_confidence)
        self._active_goals.remove(goal)
        self._goal_history.append(goal)

        if self.capabilities.supports_reflection:
            reflection = self.reflect(goal, result, policy)
            self._reflection_log.append(reflection)
            self._record_decision(
                goal_id=goal.id,
                decision_type="reflection",
                decision_source="Brain",
                rationale=reflection.critique,
                outcome="stored" if reflection.should_store else "discarded",
            )

        session.active_agent  = agent
        session.last_response = result.response
        session.context_window = scope.max_turns
        session.touch()

        return result

    # ── Confidence aggregation ────────────────────────────────────────

    def _aggregate_confidence(
        self,
        ctx:    ExecutionContext,
        policy: ExecutionPolicySpec,
    ) -> float:
        """
        Weighted confidence from reasoner + skills + tools, minus retry penalty.
        Weights are configurable via ExecutionPolicySpec.
        """
        total_weight = 0.0
        weighted_sum = 0.0

        if ctx.confidence > 0.0:
            weighted_sum  += ctx.confidence * policy.weight_reasoner
            total_weight  += policy.weight_reasoner

        if ctx.skill_results:
            skill_score = sum(
                1.0 if r.success else 0.0
                for r in ctx.skill_results.values()
            ) / len(ctx.skill_results)
            weighted_sum += skill_score * policy.weight_skills
            total_weight += policy.weight_skills

        if ctx.tool_results:
            tool_score = sum(
                1.0 if r.success else 0.0
                for r in ctx.tool_results.values()
            ) / len(ctx.tool_results)
            weighted_sum += tool_score * policy.weight_tools
            total_weight += policy.weight_tools

        base = (weighted_sum / total_weight) if total_weight > 0.0 else 0.5
        penalty = ctx.retry_count * policy.retry_confidence_penalty
        return round(max(0.0, min(1.0, base - penalty)), 3)

    # ── Reflection ────────────────────────────────────────────────────

    def reflect(
        self,
        goal:   Goal,
        result: ExecutionResult,
        policy: Optional[ExecutionPolicySpec] = None,
    ) -> ReflectionResult:
        """
        Pure logic post-execution analysis. No LLM calls.
        Produces actionable items for future improvement.
        """
        if policy is None:
            policy = ExecutionPolicySpec()

        ctx       = result.context
        achieved  = (not ctx.is_failed()) and (result.confidence >= policy.confidence_threshold)
        delta     = +0.02 if (achieved and ctx.retry_count == 0) else (-0.05 if not achieved else 0.0)
        should_store = achieved and result.confidence >= 0.7

        actions: List[ActionItem] = []

        if ctx.retry_count >= ExecutionEngine.MAX_REASONING_RETRIES:
            actions.append(ActionItem(
                action="increase_memory_scope",
                reason="Reasoning required max retries -- richer context may help",
                priority=2,
            ))

        if ctx.tool_results and any(not t.success for t in ctx.tool_results.values()):
            actions.append(ActionItem(
                action="review_tool_reliability",
                reason="One or more tools failed, reducing confidence",
                priority=3,
            ))

        if not achieved and not ctx.is_failed():
            actions.append(ActionItem(
                action="lower_confidence_threshold",
                reason="Objective not achieved at current threshold",
                priority=4,
            ))

        if should_store:
            actions.append(ActionItem(
                action="store_to_long_term_memory",
                reason="High-confidence result worth persisting",
                priority=5,
            ))

        critique = (
            "Objective achieved cleanly." if achieved and ctx.retry_count == 0
            else "Objective achieved after retries." if achieved
            else f"Objective not achieved: {ctx.error or 'low confidence'}"
        )

        return ReflectionResult(
            goal_id=goal.id,
            objective_achieved=achieved,
            confidence_delta=delta,
            should_store=should_store,
            critique=critique,
            action_items=actions,
        )

    # ── Session management ────────────────────────────────────────────

    def _get_or_create_session(self, session_id: str) -> SessionState:
        if session_id not in self._sessions:
            self._sessions[session_id] = SessionState(session_id=session_id)
        return self._sessions[session_id]

    def get_session(self, session_id: str) -> Optional[SessionState]:
        return self._sessions.get(session_id)

    # ── Decision recording ────────────────────────────────────────────

    def _record_decision(
        self,
        goal_id:         str,
        decision_type:   str,
        decision_source: str,
        rationale:       str = "",
        outcome:         str = "",
    ) -> None:
        self._decision_history.append(DecisionRecord(
            goal_id=goal_id,
            decision_type=decision_type,
            decision_source=decision_source,
            rationale=rationale,
            outcome=outcome,
        ))

    def decisions_for_goal(self, goal_id: str) -> List[DecisionRecord]:
        return [d for d in self._decision_history if d.goal_id == goal_id]

    # ── Session summary ───────────────────────────────────────────────

    def session_summary(self, session_id: str = "") -> dict:
        """Compact dict for logging and metrics."""
        return {
            "active_goals":      len(self._active_goals),
            "completed_goals":   sum(1 for g in self._goal_history if g.status == GoalStatus.COMPLETED),
            "failed_goals":      sum(1 for g in self._goal_history if g.status == GoalStatus.FAILED),
            "total_decisions":   len(self._decision_history),
            "total_reflections": len(self._reflection_log),
            "session_id":        session_id,
            "capabilities":      {
                k: v for k, v in vars(self.capabilities).items()
            },
        }
