"""
tests/phase6/test_6d_integration.py
======================================
Integration tests for Phase 6D + mandatory TestDomainAgnosticism.

Covers:
  - Agent → SkillRegistry wiring
  - Agent → AIToolRegistry wiring
  - Perception → FeatureStore → ForecastingEngine → ConfidenceScorer pipeline
  - TraderAgent produces a signal end-to-end (Phase 6D milestone)
  - TestDomainAgnosticism (mandatory for every Phase 6 test file)
"""
import pytest

from app.ai.agents.analyst import AnalystAgent
from app.ai.agents.researcher import ResearcherAgent
from app.ai.agents.trader import TraderAgent, SignalDirection
from app.ai.agents.planner import PlannerAgent
from app.ai.agents.base import BaseAgent
from app.ai.skills import BaseSkill, SkillResult, SkillRegistry
from app.ai.tools.registry import AIToolRegistry, BaseTool
from app.ai.perception.market import InMemoryMarketPerception
from app.ai.perception.news import InMemoryNewsPerception, NewsItem
from app.ai.perception.sentiment import InMemorySentimentPerception
from app.ai.prediction.feature_store import FeatureStore
from app.ai.prediction.forecasting import MockForecastingEngine, PredictionDirection
from app.ai.prediction.confidence import ConfidenceScorer
from app.ai.runtime.context import ExecutionContext


# ── Helpers ───────────────────────────────────────────────────────────────────

def _ctx(user_input="hello", agent="", intent="general"):
    ctx = ExecutionContext(user_input=user_input)
    ctx.active_goal = user_input
    ctx.intent_type = intent
    if intent:
        ctx.metadata["intent_type"] = intent
    if agent:
        ctx.metadata["agent"] = agent
    return ctx


# ── TestAgentSkillIntegration ─────────────────────────────────────────────────

class TestAgentSkillIntegration:
    """Agents can discover and run skills via SkillRegistry."""

    class _SummarySkill(BaseSkill):
        name = "summarise"
        def run(self, data):
            text = data.get("text", "")
            return SkillResult(skill_name=self.name, success=True,
                               output=text[:50], confidence=0.8)

    def test_skill_registry_used_by_agent(self):
        registry = SkillRegistry()
        registry.register(self._SummarySkill())
        result = registry.run("summarise", {"text": "a long piece of text here"})
        assert result.success is True
        assert len(result.output) <= 50

    def test_agent_can_use_skill_result(self):
        registry = SkillRegistry()
        registry.register(self._SummarySkill())
        result = registry.run("summarise", {"text": "hello world"})
        # Skill result can be stored in ExecutionContext.skill_results
        ctx = _ctx()
        from app.ai.runtime.context import SkillResult as CtxSkillResult
        ctx.skill_results["summarise"] = CtxSkillResult(
            skill_name="summarise",
            success=result.success,
            output=result.output,
        )
        assert ctx.skill_results["summarise"].success is True


# ── TestAgentToolIntegration ──────────────────────────────────────────────────

class TestAgentToolIntegration:
    """Agents can call tools via AIToolRegistry."""

    class _LookupTool(BaseTool):
        name = "lookup"
        async def call(self, params):
            return {"result": f"looked up {params.get('query', '')}"}

    @pytest.mark.asyncio
    async def test_tool_called_by_agent_role(self):
        registry = AIToolRegistry()
        registry.register(self._LookupTool(), allowed_roles={"researcher"})
        result = await registry.call("lookup", {"query": "test"}, agent_role="researcher")
        assert result.success is True
        assert "looked up test" in result.output["result"]

    @pytest.mark.asyncio
    async def test_tool_denied_for_wrong_role(self):
        registry = AIToolRegistry()
        registry.register(self._LookupTool(), allowed_roles={"researcher"})
        result = await registry.call("lookup", {}, agent_role="trader")
        assert result.success is False


# ── TestPerceptionPredictionPipeline ─────────────────────────────────────────

class TestPerceptionPredictionPipeline:
    """Full perception → features → forecast → confidence pipeline."""

    @pytest.mark.asyncio
    async def test_market_to_feature_vector(self):
        perception = InMemoryMarketPerception(mock_data={"price": 100.0, "volume": 5000.0})
        bundle     = await perception.fetch({})
        store      = FeatureStore()
        fv         = store.build(bundle.data)
        assert "price"  in fv.features
        assert "volume" in fv.features

    @pytest.mark.asyncio
    async def test_feature_vector_to_prediction(self):
        perception = InMemoryMarketPerception(mock_data={"price": 100.0})
        bundle     = await perception.fetch({})
        store      = FeatureStore()
        fv         = store.build(bundle.data)
        engine     = MockForecastingEngine(direction=PredictionDirection.UP, confidence=0.8)
        result     = engine.predict(fv)
        assert result.direction  == PredictionDirection.UP
        assert result.confidence == 0.8

    @pytest.mark.asyncio
    async def test_prediction_to_confidence_score(self):
        engine  = MockForecastingEngine(confidence=0.75)
        fv      = FeatureStore().build({"price": 100.0})
        pred    = engine.predict(fv)
        scorer  = ConfidenceScorer()
        scored  = scorer.score(prediction=pred, ta_signal=0.7)
        assert 0.0 < scored.confidence < 1.0

    @pytest.mark.asyncio
    async def test_sentiment_feeds_confidence_scorer(self):
        news_items = [
            NewsItem(title="positive news", sentiment=0.8),
            NewsItem(title="more good news", sentiment=0.7),
        ]
        sentiment_p = InMemorySentimentPerception(news_items=news_items)
        sent_score  = await sentiment_p.score({})
        scorer      = ConfidenceScorer()
        result      = scorer.score(sentiment=sent_score.score)
        assert result.confidence > 0.5   # positive sentiment → above neutral


# ── TestTraderAgentMilestone ──────────────────────────────────────────────────

class TestTraderAgentMilestone:
    """
    Phase 6D milestone: TraderAgent produces a trade signal end-to-end.
    Architecture §23: 'TraderAgent produces a signal.'
    """

    @pytest.mark.asyncio
    async def test_trader_produces_buy_signal(self):
        agent = TraderAgent()
        ctx   = _ctx(agent="trader")
        ctx.metadata["signal_confidence"] = 0.85
        result = await agent.execute(ctx)
        signal = result.metadata.get("trade_signal")
        assert signal is not None
        assert signal.direction == SignalDirection.BUY

    @pytest.mark.asyncio
    async def test_trader_produces_sell_signal(self):
        agent = TraderAgent()
        ctx   = _ctx(agent="trader")
        ctx.metadata["signal_confidence"] = 0.15
        result = await agent.execute(ctx)
        signal = result.metadata["trade_signal"]
        assert signal.direction == SignalDirection.SELL

    @pytest.mark.asyncio
    async def test_trader_signal_has_rationale(self):
        agent = TraderAgent()
        ctx   = _ctx(agent="trader")
        result = await agent.execute(ctx)
        signal = result.metadata["trade_signal"]
        assert signal.rationale != ""

    @pytest.mark.asyncio
    async def test_trader_signal_confidence_in_range(self):
        agent = TraderAgent()
        ctx   = _ctx(agent="trader")
        result = await agent.execute(ctx)
        signal = result.metadata["trade_signal"]
        assert 0.0 <= signal.confidence <= 1.0

    @pytest.mark.asyncio
    async def test_all_four_agents_pass_contract(self):
        """All four domain agents implement the full BaseAgent contract."""
        agents = [AnalystAgent(), ResearcherAgent(), TraderAgent(), PlannerAgent()]
        for agent in agents:
            assert isinstance(agent, BaseAgent), f"{agent.name} is not a BaseAgent"
            assert hasattr(agent, "can_handle")
            assert hasattr(agent, "plan")
            assert hasattr(agent, "execute")
            assert hasattr(agent, "verify")
            assert hasattr(agent, "confidence")
            assert hasattr(agent, "explain")
            assert hasattr(agent, "learn")


# ── TestDomainAgnosticism ─────────────────────────────────────────────────────

class TestDomainAgnosticism:
    """
    All Phase 6D components must contain zero domain-specific first-class fields.
    Mandatory in every Phase 6 test file.
    """

    TRADING_FIELDS = [
        "symbol", "stock", "candle", "rsi", "macd", "broker",
        "portfolio", "price", "market", "nifty",
        "indicator", "ticker",
    ]

    def test_base_agent_has_no_trading_attributes(self):
        class _A(BaseAgent):
            def can_handle(self, c): return True
            async def plan(self, c): pass
            async def execute(self, c): pass
            async def verify(self, r): pass
            def confidence(self, r): return 0.0
            def explain(self, r): return ""
            async def learn(self, r, o): pass
        a = _A()
        for attr in self.TRADING_FIELDS:
            assert not hasattr(a, attr), f"Domain attribute '{attr}' on BaseAgent"

    def test_analyst_agent_has_no_trading_attributes(self):
        a = AnalystAgent()
        for attr in self.TRADING_FIELDS:
            assert not hasattr(a, attr), f"Domain attribute '{attr}' on AnalystAgent"

    def test_trader_agent_has_no_trading_first_class_fields(self):
        a = TraderAgent()
        # TraderAgent may have 'trade' in capabilities but not as a data field
        for attr in ["symbol", "stock", "candle", "rsi", "macd", "broker",
                     "portfolio", "price", "market", "nifty", "indicator", "ticker"]:
            assert not hasattr(a, attr), f"Domain attribute '{attr}' on TraderAgent"

    def test_feature_store_has_no_trading_attributes(self):
        s = FeatureStore()
        for attr in self.TRADING_FIELDS:
            assert not hasattr(s, attr), f"Domain attribute '{attr}' on FeatureStore"

    def test_confidence_scorer_has_no_trading_attributes(self):
        s = ConfidenceScorer()
        for attr in self.TRADING_FIELDS:
            assert not hasattr(s, attr), f"Domain attribute '{attr}' on ConfidenceScorer"

    def test_market_perception_has_no_trading_attributes(self):
        p = InMemoryMarketPerception()
        for attr in self.TRADING_FIELDS:
            assert not hasattr(p, attr), f"Domain attribute '{attr}' on MarketPerception"

    def test_metadata_carries_domain_data(self):
        """Domain data belongs in metadata, never as first-class fields."""
        from app.ai.agents.base import AgentResult
        r = AgentResult(agent_name="trader", response="x", confidence=0.8)
        r.metadata["symbol"]    = "RELIANCE"
        r.metadata["rsi_value"] = 72.4
        assert r.metadata["symbol"]    == "RELIANCE"
        assert r.metadata["rsi_value"] == 72.4
