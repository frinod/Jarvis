"""
tests/phase6/test_6d_agents_domain.py
=======================================
Unit tests for domain agents (Tasks 6D.2–6D.5).

Covers: AnalystAgent, ResearcherAgent, TraderAgent (+ TradeSignal),
        PlannerAgent — can_handle, plan, execute, verify, confidence, explain.
"""
import pytest

from app.ai.agents.analyst import AnalystAgent
from app.ai.agents.researcher import ResearcherAgent
from app.ai.agents.trader import TraderAgent, TradeSignal, SignalDirection
from app.ai.agents.planner import PlannerAgent
from app.ai.agents.base import AgentPlan, AgentResult, VerificationResult
from app.ai.runtime.context import ExecutionContext


# ── Helpers ───────────────────────────────────────────────────────────────────

def _ctx(user_input="hello", intent="general", agent=""):
    ctx = ExecutionContext(user_input=user_input)
    ctx.active_goal = user_input
    ctx.intent_type = intent
    if intent:
        ctx.metadata["intent_type"] = intent
    if agent:
        ctx.metadata["agent"] = agent
    return ctx


# ── TestAnalystAgent ──────────────────────────────────────────────────────────

class TestAnalystAgent:

    def test_can_handle_analysis_intent(self):
        agent = AnalystAgent()
        assert agent.can_handle(_ctx(intent="analysis")) is True

    def test_can_handle_agent_override(self):
        agent = AnalystAgent()
        assert agent.can_handle(_ctx(agent="analyst")) is True

    def test_cannot_handle_question_intent(self):
        agent = AnalystAgent()
        assert agent.can_handle(_ctx(intent="question")) is False

    def test_capabilities_include_analysis(self):
        agent = AnalystAgent()
        assert "analysis" in agent.capabilities

    @pytest.mark.asyncio
    async def test_plan_returns_agent_plan(self):
        agent = AnalystAgent()
        plan  = await agent.plan(_ctx(intent="analysis"))
        assert isinstance(plan, AgentPlan)
        assert len(plan.steps) >= 2

    @pytest.mark.asyncio
    async def test_execute_returns_result(self):
        agent  = AnalystAgent()
        result = await agent.execute(_ctx(intent="analysis"))
        assert isinstance(result, AgentResult)
        assert result.agent_name == "analyst"
        assert result.confidence > 0.0

    @pytest.mark.asyncio
    async def test_verify_passes_on_good_result(self):
        agent  = AnalystAgent()
        result = await agent.execute(_ctx(intent="analysis"))
        vr     = await agent.verify(result)
        assert isinstance(vr, VerificationResult)
        assert vr.passed is True

    def test_confidence_returns_result_confidence(self):
        agent  = AnalystAgent()
        result = AgentResult(agent_name="analyst", response="x", confidence=0.7)
        assert agent.confidence(result) == 0.7

    def test_explain_returns_string(self):
        agent  = AnalystAgent()
        result = AgentResult(agent_name="analyst", response="x", confidence=0.7)
        assert isinstance(agent.explain(result), str)
        assert len(agent.explain(result)) > 0

    def test_name_and_version(self):
        agent = AnalystAgent()
        assert agent.name    == "analyst"
        assert agent.version == "1.0.0"


# ── TestResearcherAgent ───────────────────────────────────────────────────────

class TestResearcherAgent:

    def test_can_handle_question_intent(self):
        agent = ResearcherAgent()
        assert agent.can_handle(_ctx(intent="question")) is True

    def test_can_handle_agent_override(self):
        agent = ResearcherAgent()
        assert agent.can_handle(_ctx(agent="researcher")) is True

    def test_cannot_handle_analysis_intent(self):
        agent = ResearcherAgent()
        assert agent.can_handle(_ctx(intent="analysis")) is False

    def test_capabilities_include_research(self):
        agent = ResearcherAgent()
        assert "research" in agent.capabilities

    @pytest.mark.asyncio
    async def test_execute_returns_result(self):
        agent  = ResearcherAgent()
        result = await agent.execute(_ctx(intent="question"))
        assert isinstance(result, AgentResult)
        assert result.agent_name == "researcher"

    @pytest.mark.asyncio
    async def test_verify_passes_on_good_result(self):
        agent  = ResearcherAgent()
        result = await agent.execute(_ctx(intent="question"))
        vr     = await agent.verify(result)
        assert vr.passed is True

    def test_name_and_version(self):
        agent = ResearcherAgent()
        assert agent.name    == "researcher"
        assert agent.version == "1.0.0"


# ── TestTraderAgent ───────────────────────────────────────────────────────────

class TestTraderAgent:

    def test_can_handle_trader_agent_override(self):
        agent = TraderAgent()
        assert agent.can_handle(_ctx(agent="trader")) is True

    def test_can_handle_trading_intent(self):
        agent = TraderAgent()
        ctx   = _ctx()
        ctx.metadata["intent_type"] = "trading"
        assert agent.can_handle(ctx) is True

    def test_cannot_handle_question_intent(self):
        agent = TraderAgent()
        assert agent.can_handle(_ctx(intent="question")) is False

    def test_capabilities_include_trading(self):
        agent = TraderAgent()
        assert "trading" in agent.capabilities

    @pytest.mark.asyncio
    async def test_execute_returns_result_with_signal(self):
        agent  = TraderAgent()
        ctx    = _ctx(agent="trader")
        ctx.confidence = 0.8
        result = await agent.execute(ctx)
        assert isinstance(result, AgentResult)
        assert "trade_signal" in result.metadata

    @pytest.mark.asyncio
    async def test_high_confidence_produces_buy_signal(self):
        """With real forecast injected (UP direction), signal must be BUY."""
        from app.ai.prediction.forecasting import ForecastResult
        agent = TraderAgent()
        ctx   = _ctx(agent="trader")
        ctx.metadata["_forecast"] = ForecastResult(
            direction="UP", confidence=85.0,
            prob_up=85.0, prob_down=8.0, prob_flat=7.0,
        )
        result = await agent.execute(ctx)
        signal = result.metadata["trade_signal"]
        assert signal.direction == SignalDirection.BUY

    @pytest.mark.asyncio
    async def test_low_confidence_produces_sell_signal(self):
        """With real forecast injected (DOWN direction), signal must be SELL."""
        from app.ai.prediction.forecasting import ForecastResult
        agent = TraderAgent()
        ctx   = _ctx(agent="trader")
        ctx.metadata["_forecast"] = ForecastResult(
            direction="DOWN", confidence=68.0,
            prob_up=12.0, prob_down=68.0, prob_flat=20.0,
        )
        result = await agent.execute(ctx)
        signal = result.metadata["trade_signal"]
        assert signal.direction == SignalDirection.SELL

    @pytest.mark.asyncio
    async def test_mid_confidence_produces_hold_signal(self):
        agent = TraderAgent()
        ctx   = _ctx(agent="trader")
        ctx.metadata["signal_confidence"] = 0.5
        result = await agent.execute(ctx)
        signal = result.metadata["trade_signal"]
        assert signal.direction == SignalDirection.HOLD

    @pytest.mark.asyncio
    async def test_verify_passes_on_good_signal(self):
        """Verify passes when a real forecast produces a valid signal."""
        from app.ai.prediction.forecasting import ForecastResult
        agent  = TraderAgent()
        ctx    = _ctx(agent="trader")
        ctx.metadata["_forecast"] = ForecastResult(
            direction="UP", confidence=80.0,
            prob_up=80.0, prob_down=10.0, prob_flat=10.0,
        )
        result = await agent.execute(ctx)
        vr     = await agent.verify(result)
        assert vr.passed is True

    @pytest.mark.asyncio
    async def test_verify_fails_on_missing_signal(self):
        agent  = TraderAgent()
        result = AgentResult(agent_name="trader", response="x", confidence=0.8)
        vr     = await agent.verify(result)
        assert vr.passed is False
        assert vr.retry  is True

    def test_trade_signal_dataclass(self):
        s = TradeSignal(direction=SignalDirection.BUY, confidence=0.8, rationale="test")
        assert s.direction  == SignalDirection.BUY
        assert s.confidence == 0.8
        assert s.rationale  == "test"

    def test_signal_direction_values(self):
        assert SignalDirection.BUY.value     == "buy"
        assert SignalDirection.SELL.value    == "sell"
        assert SignalDirection.HOLD.value    == "hold"
        assert SignalDirection.NEUTRAL.value == "neutral"

    def test_explain_includes_signal_direction(self):
        agent  = TraderAgent()
        signal = TradeSignal(SignalDirection.BUY, 0.8, "strong uptrend")
        result = AgentResult(agent_name="trader", response="x", confidence=0.8,
                             metadata={"trade_signal": signal})
        explanation = agent.explain(result)
        assert "buy" in explanation.lower()

    def test_name_and_version(self):
        agent = TraderAgent()
        assert agent.name    == "trader"
        assert agent.version == "1.0.0"


# ── TestPlannerAgent ──────────────────────────────────────────────────────────

class TestPlannerAgent:

    def test_can_handle_task_intent(self):
        agent = PlannerAgent()
        assert agent.can_handle(_ctx(intent="task")) is True

    def test_can_handle_agent_override(self):
        agent = PlannerAgent()
        assert agent.can_handle(_ctx(agent="planner")) is True

    def test_cannot_handle_question_intent(self):
        agent = PlannerAgent()
        assert agent.can_handle(_ctx(intent="question")) is False

    def test_capabilities_include_planning(self):
        agent = PlannerAgent()
        assert "planning" in agent.capabilities

    @pytest.mark.asyncio
    async def test_execute_returns_result_with_plan_steps(self):
        agent  = PlannerAgent()
        result = await agent.execute(_ctx(intent="task"))
        assert isinstance(result, AgentResult)
        assert "plan_steps" in result.metadata
        assert len(result.metadata["plan_steps"]) >= 1

    @pytest.mark.asyncio
    async def test_execute_short_goal_produces_single_step(self):
        agent  = PlannerAgent()
        result = await agent.execute(_ctx("do it"))
        steps  = result.metadata.get("plan_steps", [])
        assert len(steps) == 1

    @pytest.mark.asyncio
    async def test_execute_long_goal_produces_multiple_steps(self):
        agent  = PlannerAgent()
        result = await agent.execute(_ctx("create a comprehensive analysis report for the project"))
        steps  = result.metadata.get("plan_steps", [])
        assert len(steps) > 1

    @pytest.mark.asyncio
    async def test_verify_passes_on_good_plan(self):
        agent  = PlannerAgent()
        result = await agent.execute(_ctx(intent="task"))
        vr     = await agent.verify(result)
        assert vr.passed is True

    def test_explain_mentions_step_count(self):
        agent  = PlannerAgent()
        result = AgentResult(agent_name="planner", response="x", confidence=0.75,
                             metadata={"plan_steps": ["a", "b", "c"]})
        explanation = agent.explain(result)
        assert "3" in explanation

    def test_name_and_version(self):
        agent = PlannerAgent()
        assert agent.name    == "planner"
        assert agent.version == "1.0.0"
