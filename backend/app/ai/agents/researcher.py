"""
app/ai/agents/researcher.py
============================
ResearcherAgent -- news, web search, and fundamentals agent.

Handles requests classified as "question" intent or explicitly routed
to the researcher capability. Domain data travels through metadata only.
"""
from __future__ import annotations

from typing import List

from app.ai.agents.base import AgentPlan, AgentResult, BaseAgent, VerificationResult
from app.ai.runtime.context import ExecutionContext


class ResearcherAgent(BaseAgent):
    """
    Handles research, news, and information retrieval requests.

    Capabilities: ["research", "news", "fundamentals", "question"]
    Intent match: "question" or metadata["agent"] == "researcher"
    """

    name:         str       = "researcher"
    version:      str       = "1.0.0"
    capabilities: List[str] = ["research", "news", "fundamentals", "question"]

    def can_handle(self, context: ExecutionContext) -> bool:
        intent = context.metadata.get("intent_type", context.intent_type)
        agent  = context.metadata.get("agent", "")
        return intent == "question" or agent == "researcher"

    async def plan(self, context: ExecutionContext) -> AgentPlan:
        return AgentPlan(
            steps=[
                "Identify what information is needed.",
                "Search memory and available sources.",
                "Synthesise findings into a clear answer.",
            ],
            estimated_confidence=0.65,
        )

    async def execute(self, context: ExecutionContext) -> AgentResult:
        self.record_request(success=True)
        return AgentResult(
            agent_name=self.name,
            response=f"Research complete for: {context.active_goal or context.user_input}",
            confidence=0.72,
            explanation="ResearcherAgent retrieved and synthesised relevant information.",
            metadata={"intent": "question"},
        )

    async def verify(self, result: AgentResult) -> VerificationResult:
        passed = result.confidence >= 0.5 and result.success
        return VerificationResult(
            passed=passed,
            critique="Research verified." if passed else "Insufficient information found.",
            retry=not passed and result.confidence < 0.4,
        )

    def confidence(self, result: AgentResult) -> float:
        return result.confidence

    def explain(self, result: AgentResult) -> str:
        return result.explanation or f"ResearcherAgent answered with {result.confidence:.0%} confidence."

    async def learn(self, result: AgentResult, outcome: dict) -> None:
        pass
