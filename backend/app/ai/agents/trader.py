"""
app/ai/agents/trader.py
========================
TraderAgent -- trade signal generation and execution decision agent.

Handles requests explicitly routed to the trader capability.
Produces a TradeSignal in metadata -- never as a first-class field.

Phase 7C update:
  - RAG-aware: reads ctx.metadata["_rag_context"] (ContextAssembly) to
    enrich signal rationale with retrieved market context blocks.
  - Collaboration-aware: publishes TradeSignal to AgentCollaborationBus
    so AnalystAgent and PlannerAgent can read it within the same run.
  - No interface changes -- all callers continue to work unchanged.

Domain agnosticism at the interface level
------------------------------------------
  TraderAgent.can_handle() reads from metadata["agent"] only.
  TradeSignal is stored in AgentResult.metadata["trade_signal"].
  No first-class fields for symbols, prices, or positions.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

from app.ai.agents.base import AgentPlan, AgentResult, BaseAgent, VerificationResult
from app.ai.agents.collaboration import AgentCollaborationBus, AgentMessage, CollaborationContext
from app.ai.runtime.context import ExecutionContext

# Lazy import to avoid circular dependency
def _get_context_assembly_type():
    try:
        from app.ai.rag.context_builder import ContextAssembly
        return ContextAssembly
    except ImportError:
        return None


# ── TradeSignal ───────────────────────────────────────────────────────────────

class SignalDirection(str, Enum):
    BUY     = "buy"
    SELL    = "sell"
    HOLD    = "hold"
    NEUTRAL = "neutral"


@dataclass
class TradeSignal:
    """
    A trade signal produced by TraderAgent.
    Stored in AgentResult.metadata["trade_signal"] -- never as a first-class field.
    """
    direction:  SignalDirection
    confidence: float
    rationale:  str
    metadata:   Dict[str, Any] = field(default_factory=dict)


# ── TraderAgent ───────────────────────────────────────────────────────────────

class TraderAgent(BaseAgent):
    """
    Generates trade signals and execution decisions.

    Capabilities: ["trading", "signal_generation", "execution"]
    Intent match: metadata["agent"] == "trader"

    Signal generation
    -----------------
    In Phase 6, signals are derived from context confidence and metadata.
    Phase 6D+: integrate with FeatureStore + ForecastingEngine + ConfidenceScorer.
    """

    name:         str       = "trader"
    version:      str       = "1.0.0"
    capabilities: List[str] = ["trading", "signal_generation", "execution"]

    # Confidence thresholds for signal direction
    BUY_THRESHOLD:  float = 0.70
    SELL_THRESHOLD: float = 0.30

    def can_handle(self, context: ExecutionContext) -> bool:
        agent  = context.metadata.get("agent", "")
        intent = context.metadata.get("intent_type", context.intent_type)
        return agent == "trader" or intent == "trading"

    async def plan(self, context: ExecutionContext) -> AgentPlan:
        return AgentPlan(
            steps=[
                "Assess market context from available data.",
                "Apply signal generation logic.",
                "Compute confidence score.",
                "Produce trade signal with rationale.",
            ],
            estimated_confidence=0.60,
        )

    async def execute(self, context: ExecutionContext) -> AgentResult:
        self.record_request(success=True)
        signal = self._generate_signal(context)
        rationale = self._enrich_rationale(signal, context)

        # Publish to collaboration bus so other agents can read the signal
        bus = CollaborationContext.get_bus(context)
        if bus is not None:
            bus.publish(AgentMessage(
                sender=self.name,
                message_type="trade_signal",
                payload={
                    "direction":  signal.direction.value,
                    "confidence": signal.confidence,
                    "rationale":  rationale,
                },
            ))

        return AgentResult(
            agent_name=self.name,
            response=f"Signal: {signal.direction.value.upper()} (confidence {signal.confidence:.0%})",
            confidence=signal.confidence,
            explanation=rationale,
            metadata={"trade_signal": signal},
        )

    async def verify(self, result: AgentResult) -> VerificationResult:
        signal = result.metadata.get("trade_signal")
        if signal is None:
            return VerificationResult(passed=False, critique="No trade signal produced.", retry=True)
        passed = result.confidence >= 0.5
        return VerificationResult(
            passed=passed,
            critique=f"Signal {signal.direction.value} verified." if passed else "Low confidence signal.",
            retry=not passed and result.confidence < 0.35,
        )

    def confidence(self, result: AgentResult) -> float:
        return result.confidence

    def explain(self, result: AgentResult) -> str:
        signal = result.metadata.get("trade_signal")
        if signal:
            return f"TraderAgent generated {signal.direction.value} signal: {signal.rationale}"
        return result.explanation

    async def learn(self, result: AgentResult, outcome: dict) -> None:
        pass

    # ── RAG enrichment ────────────────────────────────────────────────

    def _enrich_rationale(self, signal: TradeSignal, context: ExecutionContext) -> str:
        """
        Enrich signal rationale with retrieved market context from RAG pipeline.
        Falls back to signal.rationale when no ContextAssembly is present.
        """
        ContextAssembly = _get_context_assembly_type()
        if ContextAssembly is None:
            return signal.rationale
        assembly = context.metadata.get("_rag_context")
        if assembly is None or not isinstance(assembly, ContextAssembly):
            return signal.rationale
        # Extract market and strategy blocks only
        market_blocks = [
            b.content for b in assembly.blocks
            if b.block_type in ("market", "strategy")
        ]
        if not market_blocks:
            return signal.rationale
        context_summary = " | ".join(market_blocks[:2])  # top 2 blocks
        return f"{signal.rationale} Context: {context_summary[:200]}"

    # ── Signal generation ─────────────────────────────────────────────

    def _generate_signal(self, context: ExecutionContext) -> TradeSignal:
        """
        Derive a signal from context confidence and metadata.
        Phase 6D+: replace with FeatureStore + ForecastingEngine.
        """
        # Use context confidence as the signal strength proxy
        base_conf = context.confidence if context.confidence > 0.0 else 0.5

        # Allow metadata override for testing
        override = context.metadata.get("signal_confidence")
        if override is not None:
            base_conf = float(override)

        if base_conf >= self.BUY_THRESHOLD:
            direction = SignalDirection.BUY
            rationale = f"High confidence ({base_conf:.0%}) supports a buy signal."
        elif base_conf <= self.SELL_THRESHOLD:
            direction = SignalDirection.SELL
            rationale = f"Low confidence ({base_conf:.0%}) supports a sell signal."
        else:
            direction = SignalDirection.HOLD
            rationale = f"Neutral confidence ({base_conf:.0%}) -- hold position."

        return TradeSignal(
            direction=direction,
            confidence=round(base_conf, 3),
            rationale=rationale,
        )
