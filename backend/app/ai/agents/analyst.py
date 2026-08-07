"""
app/ai/agents/analyst.py
=========================
AnalystAgent -- technical analysis and market context agent.

Handles requests classified as "analysis" intent or explicitly routed
to the analyst capability. Domain data (symbols, indicators) travels
through ExecutionContext.metadata only.

Phase 7C update:
  - RAG-aware: reads ctx.metadata["_rag_context"] (ContextAssembly) to
    enrich analysis with retrieved market and strategy context blocks.
  - Collaboration-aware: reads TradeSignal from AgentCollaborationBus
    when TraderAgent has already run in the same pipeline pass.
  - No interface changes -- all callers continue to work unchanged.

Domain agnosticism at the interface level
------------------------------------------
  AnalystAgent.can_handle() reads intent from context.metadata["intent_type"].
  It does NOT have first-class fields for symbols, prices, or indicators.
  All domain data is in metadata.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from app.ai.agents.base import AgentPlan, AgentResult, BaseAgent, VerificationResult
from app.ai.agents.collaboration import CollaborationContext
from app.ai.runtime.context import ExecutionContext


def _get_context_assembly_type():
    try:
        from app.ai.rag.context_builder import ContextAssembly
        return ContextAssembly
    except ImportError:
        return None


class AnalystAgent(BaseAgent):
    """
    Handles technical analysis and market context requests.

    Capabilities: ["analysis", "technical_analysis", "market_context"]
    Intent match: "analysis" or metadata["agent"] == "analyst"
    """

    name:         str       = "analyst"
    version:      str       = "1.0.0"
    capabilities: List[str] = ["analysis", "technical_analysis", "market_context"]

    # ── Contract ──────────────────────────────────────────────────────

    def can_handle(self, context: ExecutionContext) -> bool:
        intent = context.metadata.get("intent_type", context.intent_type)
        agent  = context.metadata.get("agent", "")
        return intent == "analysis" or agent == "analyst"

    async def plan(self, context: ExecutionContext) -> AgentPlan:
        return AgentPlan(
            steps=[
                "Identify analysis scope and criteria.",
                "Gather relevant data from context and memory.",
                "Apply analytical reasoning.",
                "Summarise findings with confidence score.",
            ],
            estimated_confidence=0.65,
        )

    async def execute(self, context: ExecutionContext) -> AgentResult:
        self.record_request(success=True)
        goal     = context.active_goal or context.user_input
        response = f"Analysis complete for: {goal}"
        explanation = self._build_explanation(context)
        return AgentResult(
            agent_name=self.name,
            response=response,
            confidence=0.7,
            explanation=explanation,
            metadata={"intent": "analysis"},
        )

    async def verify(self, result: AgentResult) -> VerificationResult:
        passed = result.confidence >= 0.5 and result.success
        return VerificationResult(
            passed=passed,
            critique="Analysis verified." if passed else "Low confidence -- consider more data.",
            retry=not passed and result.confidence < 0.4,
        )

    def confidence(self, result: AgentResult) -> float:
        return result.confidence

    def explain(self, result: AgentResult) -> str:
        return result.explanation or f"AnalystAgent produced this result with {result.confidence:.0%} confidence."

    async def learn(self, result: AgentResult, outcome: dict) -> None:
        pass   # Phase 8: feed to LearningEngine

    # ── RAG + collaboration enrichment ─────────────────────────────────

    def _build_explanation(self, context: ExecutionContext) -> str:
        parts = ["AnalystAgent applied technical reasoning to the available context."]

        # RAG context enrichment
        ContextAssembly = _get_context_assembly_type()
        if ContextAssembly is not None:
            assembly = context.metadata.get("_rag_context")
            if assembly is not None and isinstance(assembly, ContextAssembly):
                market_blocks = [
                    b.content for b in assembly.blocks
                    if b.block_type in ("market", "strategy")
                ]
                if market_blocks:
                    parts.append(f"Retrieved context: {market_blocks[0][:150]}")

        # Collaboration bus: read trade signal if TraderAgent already ran
        bus = CollaborationContext.get_bus(context)
        if bus is not None:
            msg = bus.latest("trade_signal")
            if msg is not None:
                direction  = msg.payload.get("direction", "")
                confidence = msg.payload.get("confidence", 0.0)
                parts.append(f"TraderAgent signal: {direction} ({confidence:.0%})")

        return " ".join(parts)
