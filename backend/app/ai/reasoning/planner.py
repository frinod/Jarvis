"""
app/ai/reasoning/planner.py
============================
ReasoningPlanner -- decomposes a goal into ordered reasoning steps.

Design
------
  - ReasoningPlanner.decompose() takes a goal string and returns a
    ReasoningPlan (ordered list of ReasoningSteps).
  - Pure logic -- no LLM calls, no I/O.
  - PipelinePlannerAdapter bridges ReasoningPlanner to PipelinePlanner ABC
    so ExecutionEngine can inject it without knowing the concrete class.
  - Intent classification is keyword-based in Phase 6.
    Phase 6C+ can replace with an LLM classifier without changing callers.

Domain agnosticism
-------------------
  Intent types are generic: "question", "task", "analysis", "general".
  No trading, market, or domain-specific intent types.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional

from app.ai.runtime.context import ExecutionContext
from app.ai.runtime.execution import PipelinePlanner


# ── ReasoningStep ─────────────────────────────────────────────────────────────

@dataclass
class ReasoningStep:
    """One step in a decomposed reasoning plan."""
    index:       int
    description: str
    requires:    List[str] = field(default_factory=list)   # step names this depends on
    metadata:    dict      = field(default_factory=dict)


# ── ReasoningPlan ─────────────────────────────────────────────────────────────

@dataclass
class ReasoningPlan:
    """
    Ordered sequence of steps to achieve a goal.
    estimated_confidence is the planner's prior before any evidence.
    """
    goal:                 str
    intent_type:          str
    steps:                List[ReasoningStep]
    estimated_confidence: float = 0.6
    metadata:             dict  = field(default_factory=dict)

    def step_count(self) -> int:
        return len(self.steps)

    def descriptions(self) -> List[str]:
        return [s.description for s in self.steps]


# ── ReasoningPlanner ──────────────────────────────────────────────────────────

class ReasoningPlanner:
    """
    Decomposes a goal into an ordered ReasoningPlan.

    Intent classification (keyword-based, Phase 6):
      "question"  -- starts with who/what/when/where/why/how/is/are/can/does
      "task"      -- starts with do/make/create/build/write/run/execute/find
      "analysis"  -- starts with analyse/analyze/compare/evaluate/assess/review
      "general"   -- everything else

    Each intent type maps to a standard step template.
    Phase 6C+: replace _classify_intent() with an LLM call.

    Usage
    -----
        planner = ReasoningPlanner()
        plan    = planner.decompose("What is the best approach?")
        for step in plan.steps:
            print(step.description)
    """

    _QUESTION_WORDS = {"who", "what", "when", "where", "why", "how", "is", "are", "can", "does", "will"}
    _TASK_WORDS     = {"do", "make", "create", "build", "write", "run", "execute", "find", "get", "set"}
    _ANALYSIS_WORDS = {"analyse", "analyze", "compare", "evaluate", "assess", "review", "check", "audit"}

    def decompose(self, goal: str, context: Optional[ExecutionContext] = None) -> ReasoningPlan:
        """
        Decompose a goal string into a ReasoningPlan.
        If context is provided, intent_type from context.metadata is preferred.
        """
        intent = (
            context.metadata.get("intent_type", "")
            if context else ""
        ) or self._classify_intent(goal)

        steps = self._build_steps(goal, intent)

        return ReasoningPlan(
            goal=goal,
            intent_type=intent,
            steps=steps,
            estimated_confidence=self._prior_confidence(intent),
        )

    def _classify_intent(self, goal: str) -> str:
        first_word = goal.strip().lower().split()[0] if goal.strip() else ""
        if first_word in self._QUESTION_WORDS:
            return "question"
        if first_word in self._TASK_WORDS:
            return "task"
        if first_word in self._ANALYSIS_WORDS:
            return "analysis"
        return "general"

    def _build_steps(self, goal: str, intent: str) -> List[ReasoningStep]:
        templates = {
            "question": [
                "Identify what information is needed to answer the question.",
                "Retrieve relevant context from memory and tools.",
                "Formulate a direct, accurate answer.",
            ],
            "task": [
                "Clarify the task requirements and constraints.",
                "Identify the resources and tools needed.",
                "Execute the task step by step.",
                "Verify the result meets the requirements.",
            ],
            "analysis": [
                "Define the scope and criteria for analysis.",
                "Gather relevant data and evidence.",
                "Apply analytical reasoning to the evidence.",
                "Summarise findings and conclusions.",
            ],
            "general": [
                "Understand the intent of the request.",
                "Gather relevant context.",
                "Formulate a response.",
            ],
        }
        descriptions = templates.get(intent, templates["general"])
        return [
            ReasoningStep(index=i, description=desc)
            for i, desc in enumerate(descriptions)
        ]

    def _prior_confidence(self, intent: str) -> float:
        """Prior confidence before any evidence, by intent type."""
        return {
            "question": 0.65,
            "task":     0.60,
            "analysis": 0.55,
            "general":  0.60,
        }.get(intent, 0.60)


# ── PipelinePlannerAdapter ────────────────────────────────────────────────────

class PipelinePlannerAdapter(PipelinePlanner):
    """
    Bridges ReasoningPlanner to the PipelinePlanner ABC.
    Injected into ExecutionEngine as the planner collaborator.

    Sets ctx.active_goal, ctx.intent_type from the plan.
    """

    def __init__(self, planner: Optional[ReasoningPlanner] = None):
        self._planner = planner or ReasoningPlanner()

    async def plan(self, ctx: ExecutionContext) -> None:
        plan = self._planner.decompose(ctx.user_input, context=ctx)
        ctx.active_goal = plan.goal
        ctx.intent_type = plan.intent_type
        ctx.metadata["_reasoning_plan"] = {
            "intent_type":  plan.intent_type,
            "step_count":   plan.step_count(),
            "steps":        plan.descriptions(),
            "est_confidence": plan.estimated_confidence,
        }
