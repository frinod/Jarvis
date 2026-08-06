"""
app/ai/agents/planner.py
=========================
PlannerAgent -- goal decomposition and multi-step planning agent.

Handles requests classified as "task" intent or explicitly routed
to the planner capability. Produces a structured plan in metadata.
"""
from __future__ import annotations

from typing import List

from app.ai.agents.base import AgentPlan, AgentResult, BaseAgent, VerificationResult
from app.ai.runtime.context import ExecutionContext


class PlannerAgent(BaseAgent):
    """
    Decomposes goals into multi-step execution plans.

    Capabilities: ["planning", "task", "decomposition"]
    Intent match: "task" or metadata["agent"] == "planner"
    """

    name:         str       = "planner"
    version:      str       = "1.0.0"
    capabilities: List[str] = ["planning", "task", "decomposition"]

    def can_handle(self, context: ExecutionContext) -> bool:
        intent = context.metadata.get("intent_type", context.intent_type)
        agent  = context.metadata.get("agent", "")
        return intent == "task" or agent == "planner"

    async def plan(self, context: ExecutionContext) -> AgentPlan:
        return AgentPlan(
            steps=[
                "Clarify the task requirements.",
                "Identify sub-goals and dependencies.",
                "Order steps by priority and dependency.",
                "Estimate effort and confidence per step.",
            ],
            estimated_confidence=0.70,
        )

    async def execute(self, context: ExecutionContext) -> AgentResult:
        self.record_request(success=True)
        goal  = context.active_goal or context.user_input
        steps = self._decompose(goal)
        return AgentResult(
            agent_name=self.name,
            response=f"Plan created with {len(steps)} steps for: {goal}",
            confidence=0.75,
            explanation="PlannerAgent decomposed the goal into actionable steps.",
            metadata={"plan_steps": steps},
        )

    async def verify(self, result: AgentResult) -> VerificationResult:
        steps  = result.metadata.get("plan_steps", [])
        passed = len(steps) >= 1 and result.confidence >= 0.5
        return VerificationResult(
            passed=passed,
            critique=f"Plan with {len(steps)} steps verified." if passed else "Plan is empty or low confidence.",
            retry=not passed,
        )

    def confidence(self, result: AgentResult) -> float:
        return result.confidence

    def explain(self, result: AgentResult) -> str:
        steps = result.metadata.get("plan_steps", [])
        return f"PlannerAgent created {len(steps)}-step plan with {result.confidence:.0%} confidence."

    async def learn(self, result: AgentResult, outcome: dict) -> None:
        pass

    def _decompose(self, goal: str) -> List[str]:
        """Simple keyword-based decomposition. Phase 6D+: use ReasoningPlanner."""
        words = goal.lower().split()
        if len(words) <= 3:
            return [f"Execute: {goal}"]
        return [
            f"Understand: {goal[:60]}",
            "Gather required resources.",
            "Execute the primary action.",
            "Verify the outcome.",
        ]
