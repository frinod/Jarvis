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
        Derive a trade signal from the real XGBoost forecast result.

        The forecast result is injected into context.metadata["_forecast"]
        by the caller (AI Discovery, paper trading, or any orchestration layer)
        before the agent runs.  If no forecast is present the agent returns
        HOLD — it never fabricates a directional signal.
        """
        from app.ai.prediction.forecasting import ForecastResult

        raw_forecast = context.metadata.get("_forecast")

        # ── No forecast injected ──────────────────────────────────────
        if raw_forecast is None:
            return TradeSignal(
                direction=SignalDirection.HOLD,
                confidence=0.0,
                rationale="No forecast available — holding. Inject _forecast into context.metadata to enable signal generation.",
                metadata={"source": "no_forecast"},
            )

        # ── Normalise: accept both ForecastResult and raw dict ────────
        if isinstance(raw_forecast, dict):
            fr = ForecastResult.from_dict(raw_forecast)
        elif isinstance(raw_forecast, ForecastResult):
            fr = raw_forecast
        else:
            return TradeSignal(
                direction=SignalDirection.HOLD,
                confidence=0.0,
                rationale="Forecast result has unexpected type — holding.",
                metadata={"source": "bad_forecast_type"},
            )

        # ── Forecasting failure → safe no-trade ───────────────────────
        if not fr.is_valid:
            return TradeSignal(
                direction=SignalDirection.HOLD,
                confidence=0.0,
                rationale=f"Forecast unavailable ({fr.error or 'unknown'}) — holding.",
                metadata={"source": "forecast_error", "error": fr.error},
            )

        # ── Map real model direction to trade signal ───────────────────
        direction_map = {
            "BUY":  SignalDirection.BUY,
            "SELL": SignalDirection.SELL,
            "HOLD": SignalDirection.HOLD,
        }
        direction  = direction_map.get(fr.trade_signal, SignalDirection.HOLD)
        confidence = round(fr.confidence / 100.0, 3)   # normalise 0-100 → 0-1

        regime_note = f" Regime: {fr.regime_label or fr.regime}." if fr.regime != "unknown" else ""
        mtf_note    = f" MTF: {fr.mtf_confluence}." if fr.mtf_confluence else ""
        wfv_note    = f" WFV accuracy: {fr.wfv_accuracy:.1f}%." if fr.wfv_accuracy is not None else ""

        rationale = (
            f"XGBoost model: {fr.direction} ({fr.confidence:.1f}% confidence). "
            f"TA signal: {fr.ta_signal}.{regime_note}{mtf_note}{wfv_note}"
        )

        return TradeSignal(
            direction=direction,
            confidence=confidence,
            rationale=rationale,
            metadata={
                "source":        "xgboost",
                "model_name":    fr.model_name,
                "direction":     fr.direction,
                "prob_up":       fr.prob_up,
                "prob_down":     fr.prob_down,
                "prob_flat":     fr.prob_flat,
                "regime":        fr.regime,
                "regime_adjusted": fr.regime_adjusted,
                "mtf_confluence": fr.mtf_confluence,
                "entry_price":   fr.entry_price,
                "stop_loss":     fr.stop_loss,
                "target1":       fr.target1,
                "wfv_accuracy":  fr.wfv_accuracy,
            },
        )
