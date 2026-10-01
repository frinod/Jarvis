"""
tests/phase7/test_session2_forecasting_integration.py
=======================================================
Session 2 regression tests — Real Forecasting Integration.

Verifies that TraderAgent and AnalystAgent consume the real XGBoost
forecast result (via ctx.metadata["_forecast"]) and never use
MockForecastingEngine or hardcoded confidence as the production signal.

All tests are pure unit tests — no network, no model files, no XGBoost.
Forecast results are injected via ctx.metadata["_forecast"].
"""
import pytest

from app.ai.runtime.context import ExecutionContext
from app.ai.agents.trader import TraderAgent, SignalDirection
from app.ai.agents.analyst import AnalystAgent
from app.ai.agents.collaboration import CollaborationContext
from app.ai.prediction.forecasting import (
    ForecastResult, XGBoostForecastingEngine, MockForecastingEngine,
)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _ctx(user_input: str = "analyse RELIANCE") -> ExecutionContext:
    ctx = ExecutionContext(user_input=user_input, session_id="s2_test")
    ctx.active_goal = user_input
    return ctx


def _forecast(direction="UP", confidence=72.5, regime="bull_trend",
              ta_signal="BUY", prob_up=72.5, prob_down=15.0, prob_flat=12.5,
              wfv_accuracy=58.3, mtf_confluence="strong") -> ForecastResult:
    """Build a valid ForecastResult for injection into ctx.metadata."""
    return ForecastResult(
        symbol="RELIANCE.NS",
        direction=direction,
        confidence=confidence,
        prob_up=prob_up,
        prob_down=prob_down,
        prob_flat=prob_flat,
        regime=regime,
        regime_label="Bull Trend",
        regime_adjusted=False,
        regime_warning=None,
        mtf_confluence=mtf_confluence,
        mtf_score=0.75,
        ta_signal=ta_signal,
        ta_confidence=68.0,
        ta_score=3.5,
        trend="uptrend",
        entry_price=2850.0,
        stop_loss=2810.0,
        target1=2920.0,
        target2=2980.0,
        atr=18.5,
        rsi=58.2,
        wfv_accuracy=wfv_accuracy,
        model_name="XGBoost",
        error=None,
    )


def _inject(ctx: ExecutionContext, fr: ForecastResult) -> ExecutionContext:
    ctx.metadata["_forecast"] = fr
    return ctx


# ═══════════════════════════════════════════════════════════════════════════════
# 1. TraderAgent receives real forecast result
# ═══════════════════════════════════════════════════════════════════════════════

class TestTraderAgentRealForecast:

    @pytest.mark.asyncio
    async def test_trader_receives_forecast_result(self):
        agent = TraderAgent()
        ctx   = _inject(_ctx(), _forecast(direction="UP", confidence=72.5))
        result = await agent.execute(ctx)
        signal = result.metadata["trade_signal"]
        assert signal is not None
        assert signal.direction == SignalDirection.BUY

    @pytest.mark.asyncio
    async def test_model_direction_up_maps_to_buy(self):
        agent = TraderAgent()
        ctx   = _inject(_ctx(), _forecast(direction="UP"))
        result = await agent.execute(ctx)
        assert result.metadata["trade_signal"].direction == SignalDirection.BUY

    @pytest.mark.asyncio
    async def test_model_direction_down_maps_to_sell(self):
        agent = TraderAgent()
        ctx   = _inject(_ctx(), _forecast(direction="DOWN", confidence=68.0,
                                          prob_up=15.0, prob_down=68.0, prob_flat=17.0))
        result = await agent.execute(ctx)
        assert result.metadata["trade_signal"].direction == SignalDirection.SELL

    @pytest.mark.asyncio
    async def test_model_direction_flat_maps_to_hold(self):
        agent = TraderAgent()
        ctx   = _inject(_ctx(), _forecast(direction="FLAT", confidence=55.0,
                                          prob_up=20.0, prob_down=25.0, prob_flat=55.0))
        result = await agent.execute(ctx)
        assert result.metadata["trade_signal"].direction == SignalDirection.HOLD

    @pytest.mark.asyncio
    async def test_model_confidence_propagates(self):
        agent = TraderAgent()
        ctx   = _inject(_ctx(), _forecast(confidence=72.5))
        result = await agent.execute(ctx)
        # confidence normalised 0-100 -> 0-1
        assert abs(result.confidence - 0.725) < 0.001

    @pytest.mark.asyncio
    async def test_regime_propagates_to_signal_metadata(self):
        agent = TraderAgent()
        ctx   = _inject(_ctx(), _forecast(regime="high_volatility"))
        result = await agent.execute(ctx)
        signal = result.metadata["trade_signal"]
        assert signal.metadata.get("regime") == "high_volatility"

    @pytest.mark.asyncio
    async def test_mtf_propagates_to_signal_metadata(self):
        agent = TraderAgent()
        ctx   = _inject(_ctx(), _forecast(mtf_confluence="strong"))
        result = await agent.execute(ctx)
        signal = result.metadata["trade_signal"]
        assert signal.metadata.get("mtf_confluence") == "strong"

    @pytest.mark.asyncio
    async def test_rationale_mentions_xgboost(self):
        agent = TraderAgent()
        ctx   = _inject(_ctx(), _forecast())
        result = await agent.execute(ctx)
        assert "XGBoost" in result.metadata["trade_signal"].rationale

    @pytest.mark.asyncio
    async def test_no_hardcoded_confidence(self):
        """Confidence must come from the forecast, not a fixed value."""
        agent = TraderAgent()
        # Two different confidence values must produce two different results
        ctx1 = _inject(_ctx(), _forecast(confidence=80.0))
        ctx2 = _inject(_ctx(), _forecast(confidence=51.0))
        r1 = await agent.execute(ctx1)
        r2 = await agent.execute(ctx2)
        assert r1.confidence != r2.confidence


# ═══════════════════════════════════════════════════════════════════════════════
# 2. AnalystAgent receives real forecast result
# ═══════════════════════════════════════════════════════════════════════════════

class TestAnalystAgentRealForecast:

    @pytest.mark.asyncio
    async def test_analyst_receives_forecast_result(self):
        agent  = AnalystAgent()
        ctx    = _inject(_ctx(), _forecast())
        result = await agent.execute(ctx)
        assert result.agent_name == "analyst"
        assert "XGBoost" in result.explanation

    @pytest.mark.asyncio
    async def test_analyst_confidence_from_forecast(self):
        agent  = AnalystAgent()
        ctx    = _inject(_ctx(), _forecast(confidence=72.5))
        result = await agent.execute(ctx)
        assert abs(result.confidence - 0.725) < 0.001

    @pytest.mark.asyncio
    async def test_analyst_no_hardcoded_07_confidence(self):
        """AnalystAgent must never return exactly 0.7 when a forecast is present."""
        agent  = AnalystAgent()
        ctx    = _inject(_ctx(), _forecast(confidence=80.0))
        result = await agent.execute(ctx)
        assert result.confidence != 0.7

    @pytest.mark.asyncio
    async def test_analyst_explanation_contains_direction(self):
        agent  = AnalystAgent()
        ctx    = _inject(_ctx(), _forecast(direction="UP"))
        result = await agent.execute(ctx)
        assert "UP" in result.explanation

    @pytest.mark.asyncio
    async def test_analyst_explanation_contains_regime(self):
        agent  = AnalystAgent()
        ctx    = _inject(_ctx(), _forecast(regime="bull_trend"))
        result = await agent.execute(ctx)
        assert "Bull Trend" in result.explanation or "bull_trend" in result.explanation

    @pytest.mark.asyncio
    async def test_analyst_explanation_contains_wfv(self):
        agent  = AnalystAgent()
        ctx    = _inject(_ctx(), _forecast(wfv_accuracy=58.3))
        result = await agent.execute(ctx)
        assert "58.3" in result.explanation

    @pytest.mark.asyncio
    async def test_analyst_explanation_contains_mtf(self):
        agent  = AnalystAgent()
        ctx    = _inject(_ctx(), _forecast(mtf_confluence="strong"))
        result = await agent.execute(ctx)
        assert "strong" in result.explanation


# ═══════════════════════════════════════════════════════════════════════════════
# 3. Failure / safe no-trade behaviour
# ═══════════════════════════════════════════════════════════════════════════════

class TestFailureSafeNoTrade:

    @pytest.mark.asyncio
    async def test_no_forecast_trader_returns_hold(self):
        """No _forecast in metadata -> HOLD, not a fabricated signal."""
        agent  = TraderAgent()
        ctx    = _ctx()  # no _forecast injected
        result = await agent.execute(ctx)
        signal = result.metadata["trade_signal"]
        assert signal.direction == SignalDirection.HOLD
        assert result.confidence == 0.0

    @pytest.mark.asyncio
    async def test_no_forecast_analyst_returns_neutral_confidence(self):
        agent  = AnalystAgent()
        ctx    = _ctx()
        result = await agent.execute(ctx)
        assert result.confidence == 0.5

    @pytest.mark.asyncio
    async def test_forecast_error_trader_returns_hold(self):
        agent  = TraderAgent()
        ctx    = _ctx()
        ctx.metadata["_forecast"] = ForecastResult.unavailable("model_not_found")
        result = await agent.execute(ctx)
        signal = result.metadata["trade_signal"]
        assert signal.direction == SignalDirection.HOLD
        assert result.confidence == 0.0

    @pytest.mark.asyncio
    async def test_forecast_error_analyst_returns_neutral(self):
        agent  = AnalystAgent()
        ctx    = _ctx()
        ctx.metadata["_forecast"] = ForecastResult.unavailable("insufficient_data")
        result = await agent.execute(ctx)
        assert result.confidence == 0.5

    @pytest.mark.asyncio
    async def test_raw_dict_forecast_accepted(self):
        """Agents must accept a raw dict (as returned by forecast()) as well as ForecastResult."""
        agent = TraderAgent()
        ctx   = _ctx()
        # Simulate the raw dict structure returned by forecaster.forecast()
        ctx.metadata["_forecast"] = {
            "symbol": "RELIANCE.NS",
            "forecast": {
                "direction": "UP", "confidence": 65.0,
                "prob_up": 65.0, "prob_down": 20.0, "prob_flat": 15.0,
                "model": "XGBoost", "current_price": 2850.0,
                "estimated_target": 2920.0, "estimated_low": 2810.0,
            },
            "regime":  {"regime": "bull_trend", "label": "Bull Trend", "adjusted": False, "warning": None},
            "mtf":     {"confluence": "moderate", "score": 0.6, "htf_signal": "BUY"},
            "context": {"overall_signal": "BUY", "ta_confidence": 68.0, "ta_score": 3.5,
                        "trend": "uptrend", "atr": 18.5, "rsi": 58.2, "supertrend": "bullish"},
            "validation": {"wfv_accuracy": 57.1, "wfv_useful": True, "test_samples": 42},
        }
        result = await agent.execute(ctx)
        signal = result.metadata["trade_signal"]
        assert signal.direction == SignalDirection.BUY

    @pytest.mark.asyncio
    async def test_forecast_not_silently_overwritten(self):
        """The forecast result injected must be the one used — not replaced by a default."""
        agent = TraderAgent()
        ctx   = _inject(_ctx(), _forecast(direction="DOWN", confidence=68.0,
                                          prob_up=15.0, prob_down=68.0, prob_flat=17.0))
        result = await agent.execute(ctx)
        # Must be SELL (from DOWN), not BUY or HOLD
        assert result.metadata["trade_signal"].direction == SignalDirection.SELL


# ═══════════════════════════════════════════════════════════════════════════════
# 4. MockForecastingEngine not used in production path
# ═══════════════════════════════════════════════════════════════════════════════

class TestMockNotInProductionPath:

    def test_mock_engine_is_not_default_in_trader(self):
        """TraderAgent must not instantiate MockForecastingEngine internally."""
        import inspect
        source = inspect.getsource(TraderAgent._generate_signal)
        assert "MockForecastingEngine" not in source

    def test_mock_engine_is_not_default_in_analyst(self):
        import inspect
        source = inspect.getsource(AnalystAgent._build_explanation)
        assert "MockForecastingEngine" not in source

    def test_xgboost_engine_is_importable(self):
        from app.ai.prediction.forecasting import XGBoostForecastingEngine
        assert XGBoostForecastingEngine is not None

    def test_forecast_result_is_importable(self):
        from app.ai.prediction.forecasting import ForecastResult
        assert ForecastResult is not None

    def test_mock_engine_still_works_for_tests(self):
        """MockForecastingEngine must still be usable for unit tests via DI."""
        from app.ai.prediction.feature_store import FeatureVector
        engine = MockForecastingEngine(confidence=0.8)
        fv     = FeatureVector(features={"price": 100.0})
        result = engine.predict(fv)
        assert result.confidence == 0.8


# ═══════════════════════════════════════════════════════════════════════════════
# 5. ForecastResult contract
# ═══════════════════════════════════════════════════════════════════════════════

class TestForecastResult:

    def test_is_valid_true_for_real_directions(self):
        for d in ("UP", "DOWN", "FLAT"):
            fr = ForecastResult(direction=d, confidence=60.0)
            assert fr.is_valid, f"Expected is_valid for direction={d}"

    def test_is_valid_false_for_unavailable(self):
        fr = ForecastResult.unavailable("model_not_found")
        assert not fr.is_valid

    def test_trade_signal_up_is_buy(self):
        fr = ForecastResult(direction="UP", confidence=70.0)
        assert fr.trade_signal == "BUY"

    def test_trade_signal_down_is_sell(self):
        fr = ForecastResult(direction="DOWN", confidence=65.0)
        assert fr.trade_signal == "SELL"

    def test_trade_signal_flat_is_hold(self):
        fr = ForecastResult(direction="FLAT", confidence=55.0)
        assert fr.trade_signal == "HOLD"

    def test_trade_signal_unavailable_is_hold(self):
        fr = ForecastResult.unavailable()
        assert fr.trade_signal == "HOLD"

    def test_from_dict_valid_forecast(self):
        d = {
            "symbol": "TCS.NS",
            "forecast": {
                "direction": "UP", "confidence": 71.0,
                "prob_up": 71.0, "prob_down": 18.0, "prob_flat": 11.0,
                "model": "XGBoost", "current_price": 3500.0,
                "estimated_target": 3580.0, "estimated_low": 3450.0,
            },
            "regime":  {"regime": "bull_trend", "label": "Bull", "adjusted": False, "warning": None},
            "mtf":     {"confluence": "strong", "score": 0.8, "htf_signal": "BUY"},
            "context": {"overall_signal": "BUY", "ta_confidence": 70.0, "ta_score": 4.0,
                        "trend": "strong_uptrend", "atr": 22.0, "rsi": 61.0},
            "validation": {"wfv_accuracy": 60.2, "wfv_useful": True, "test_samples": 50},
        }
        fr = ForecastResult.from_dict(d)
        assert fr.is_valid
        assert fr.direction == "UP"
        assert fr.confidence == 71.0
        assert fr.regime == "bull_trend"
        assert fr.wfv_accuracy == 60.2

    def test_from_dict_error_response(self):
        fr = ForecastResult.from_dict({"error": "insufficient_data"})
        assert not fr.is_valid
        assert fr.error == "insufficient_data"

    def test_from_dict_none_returns_unavailable(self):
        fr = ForecastResult.from_dict(None)
        assert not fr.is_valid

    def test_from_dict_empty_dict_returns_unavailable(self):
        fr = ForecastResult.from_dict({})
        assert not fr.is_valid


# ═══════════════════════════════════════════════════════════════════════════════
# 6. Multi-session isolation
# ═══════════════════════════════════════════════════════════════════════════════

class TestMultiSessionIsolation:

    @pytest.mark.asyncio
    async def test_two_contexts_independent(self):
        """Two concurrent contexts must not share forecast state."""
        agent = TraderAgent()
        ctx1  = _inject(_ctx(), _forecast(direction="UP",   confidence=75.0))
        ctx2  = _inject(_ctx(), _forecast(direction="DOWN", confidence=68.0,
                                          prob_up=15.0, prob_down=68.0, prob_flat=17.0))
        r1 = await agent.execute(ctx1)
        r2 = await agent.execute(ctx2)
        assert r1.metadata["trade_signal"].direction == SignalDirection.BUY
        assert r2.metadata["trade_signal"].direction == SignalDirection.SELL

    @pytest.mark.asyncio
    async def test_rag_enrichment_still_works_with_forecast(self):
        """RAG context enrichment must still work when _forecast is also present."""
        from app.ai.rag.context_builder import ContextAssembly, ContextBlock
        agent = TraderAgent()
        ctx   = _inject(_ctx(), _forecast())
        blocks = [
            ContextBlock(block_type="market",   content="RELIANCE broke out above 2800", importance=0.9),
            ContextBlock(block_type="strategy",  content="RSI at 58, bullish momentum",  importance=0.7),
        ]
        ctx.metadata["_rag_context"] = ContextAssembly(
            blocks=blocks, total_tokens=50, entries_used=2,
            prompt_text="[market] RELIANCE broke out above 2800",
        )
        result = await agent.execute(ctx)
        # Both forecast and RAG context should be present
        assert "XGBoost" in result.metadata["trade_signal"].rationale
        assert "Context:" in result.explanation

    @pytest.mark.asyncio
    async def test_collaboration_bus_still_works_with_forecast(self):
        """Collaboration bus must still publish signal when forecast is present."""
        agent = TraderAgent()
        ctx   = _inject(_ctx(), _forecast(direction="UP"))
        bus   = CollaborationContext.attach(ctx)
        await agent.execute(ctx)
        msgs = bus.get_messages(message_type="trade_signal")
        assert len(msgs) == 1
        assert msgs[0].payload["direction"] == "buy"

    @pytest.mark.asyncio
    async def test_reasoning_log_still_works_with_forecast(self):
        """Reasoning log must still capture context when forecast is present."""
        from app.ai.reasoning.reasoning_log import ReasoningLogger
        from app.ai.memory.long_term import InMemoryLongTermMemory
        ltm    = InMemoryLongTermMemory()
        logger = ReasoningLogger(ltm=ltm)
        ctx    = _inject(_ctx(), _forecast(confidence=72.5))
        ctx.confidence = 0.725
        trace  = await logger.log(ctx, outcome="success")
        assert trace is not None
        assert trace.confidence == 0.725
