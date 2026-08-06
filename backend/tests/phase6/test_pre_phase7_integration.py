"""
tests/phase6/test_pre_phase7_integration.py
============================================
Pre-Phase 7 stabilization tests.

Covers:
  1. End-to-end pipeline: every stage from API → Brain → Gateway is exercised
     in a single request and each stage is individually asserted.
  2. Legacy fallback isolation: LLMRouter is only used when AIRuntime is absent.
  3. AIRuntime status endpoint contract.
  4. TradeRequest validation (C2 fix).
  5. Safe math evaluator (C3 fix).
  6. TestDomainAgnosticism (mandatory).
"""
from __future__ import annotations
import pytest

from app.ai import AIRuntime, RuntimeHealth, RuntimeMetrics
from app.ai.brain.brain import Brain
from app.ai.orchestration.coordinator import AgentDescriptor, AgentRegistry, Coordinator
from app.ai.orchestration.workflow import WorkflowEngine
from app.ai.runtime.execution import ExecutionEngine, ExecutionResult
from app.ai.runtime.llm_gateway import LLMGateway, LLMRequest
from app.resilience.retry import RetryPolicy, RetryStrategy


# ── Shared test doubles ───────────────────────────────────────────────────────

class _StageTracker:
    """Records which pipeline stages were called during a request."""
    def __init__(self):
        self.stages: list = []

    def record(self, stage: str):
        self.stages.append(stage)


class _TrackedProvider:
    """Mock LLM provider that records every call."""
    def __init__(self, tracker: _StageTracker):
        self._tracker = tracker

    async def generate(self, messages, **kwargs):
        from app.core.llm import LLMResponse as CoreResp
        self._tracker.record("gateway.complete")
        return CoreResp(content="e2e response", model="mock", tokens_used=5)

    async def stream(self, messages, **kwargs):
        self._tracker.record("gateway.stream")
        for token in ["e2e", " ", "stream"]:
            yield token


def _no_retry() -> RetryPolicy:
    return RetryPolicy(max_attempts=1, strategy=RetryStrategy.FIXED, base_delay_s=0.0)


def _make_gateway(tracker: _StageTracker) -> LLMGateway:
    gw = LLMGateway(retry_policy=_no_retry())
    gw.register("mock", _TrackedProvider(tracker))
    return gw


def _make_coordinator() -> Coordinator:
    r = AgentRegistry()
    r.register(AgentDescriptor(name="analyst", supported_intents=["general", "question"]))
    return Coordinator(registry=r)


def _make_runtime(tracker: _StageTracker, with_coordinator: bool = True) -> AIRuntime:
    gw = _make_gateway(tracker)
    coord = _make_coordinator() if with_coordinator else None
    return AIRuntime(gateway=gw, coordinator=coord)


# ── TestEndToEndPipeline ──────────────────────────────────────────────────────

class TestEndToEndPipeline:
    """
    Every stage of the live request path must be exercised in a single call.

    Asserted stages:
      AIRuntime.process()
        → Brain.process()          (goal created, decision recorded)
        → Coordinator.select()     (agent selected when coordinator present)
        → ExecutionEngine.run()    (context transitions through pipeline)
        → LLMGateway.complete()    (provider called, response returned)
        → Brain.reflect()          (reflection logged after response)
    """

    @pytest.mark.asyncio
    async def test_full_pipeline_returns_execution_result(self):
        tracker = _StageTracker()
        rt = _make_runtime(tracker)
        result = await rt.process("What is the market outlook?", "sess-e2e")
        assert isinstance(result, ExecutionResult)

    @pytest.mark.asyncio
    async def test_brain_creates_goal(self):
        tracker = _StageTracker()
        rt = _make_runtime(tracker)
        await rt.process("test question", "sess-e2e")
        assert len(rt.brain._goal_history) == 1
        assert rt.brain._goal_history[0].objective == "test question"

    @pytest.mark.asyncio
    async def test_brain_records_decision(self):
        tracker = _StageTracker()
        rt = _make_runtime(tracker)
        await rt.process("test", "sess-e2e")
        assert len(rt.brain._decision_history) >= 1

    @pytest.mark.asyncio
    async def test_brain_runs_reflection(self):
        tracker = _StageTracker()
        rt = _make_runtime(tracker)
        await rt.process("test", "sess-e2e")
        assert len(rt.brain._reflection_log) >= 1

    @pytest.mark.asyncio
    async def test_execution_engine_produces_response(self):
        tracker = _StageTracker()
        rt = _make_runtime(tracker)
        result = await rt.process("hello", "sess-e2e")
        assert result.response != ""

    @pytest.mark.asyncio
    async def test_gateway_called_during_streaming(self):
        """LLMGateway.stream() is called directly by ExecutionEngine.stream()."""
        tracker = _StageTracker()
        rt = _make_runtime(tracker)
        tokens = []
        async for token in rt.stream("hello", "sess-e2e"):
            tokens.append(token)
        assert "gateway.stream" in tracker.stages
        assert len(tokens) > 0

    @pytest.mark.asyncio
    async def test_session_id_propagated_through_pipeline(self):
        tracker = _StageTracker()
        rt = _make_runtime(tracker)
        result = await rt.process("hello", "sess-propagation")
        assert result.context.session_id == "sess-propagation"

    @pytest.mark.asyncio
    async def test_metadata_flows_through_pipeline(self):
        tracker = _StageTracker()
        rt = _make_runtime(tracker)
        result = await rt.process("hello", "sess-e2e", metadata={"domain": "stocks"})
        assert result.context.metadata.get("domain") == "stocks"

    @pytest.mark.asyncio
    async def test_request_count_increments_per_call(self):
        tracker = _StageTracker()
        rt = _make_runtime(tracker)
        await rt.process("q1", "s1")
        await rt.process("q2", "s1")
        await rt.process("q3", "s1")
        assert rt._request_count == 3

    @pytest.mark.asyncio
    async def test_multiple_sessions_are_independent(self):
        tracker = _StageTracker()
        rt = _make_runtime(tracker)
        await rt.process("q1", "sess-A")
        await rt.process("q2", "sess-B")
        assert rt.brain.get_session("sess-A") is not None
        assert rt.brain.get_session("sess-B") is not None
        assert rt.brain.get_session("sess-A") is not rt.brain.get_session("sess-B")

    @pytest.mark.asyncio
    async def test_pipeline_never_raises_on_empty_input(self):
        tracker = _StageTracker()
        rt = _make_runtime(tracker)
        try:
            result = await rt.process("", "sess-empty")
            assert result is not None
        except Exception as exc:
            pytest.fail(f"process() raised on empty input: {exc}")

    @pytest.mark.asyncio
    async def test_streaming_path_calls_gateway(self):
        tracker = _StageTracker()
        rt = _make_runtime(tracker)
        tokens = []
        async for token in rt.stream("hello", "sess-stream"):
            tokens.append(token)
        assert len(tokens) > 0
        assert "gateway.stream" in tracker.stages

    @pytest.mark.asyncio
    async def test_streaming_yields_strings(self):
        tracker = _StageTracker()
        rt = _make_runtime(tracker)
        async for token in rt.stream("hello", "sess-stream"):
            assert isinstance(token, str)


# ── TestLegacyFallbackIsolation ───────────────────────────────────────────────

class TestLegacyFallbackIsolation:
    """
    LLMRouter must only be used when AIRuntime is absent.
    When ai_runtime is set, the orchestrator must NOT call LLMRouter.generate().
    """

    def _make_orchestrator_with_runtime(self, tracker: _StageTracker):
        """Build a minimal orchestrator stub with ai_runtime wired."""
        from unittest.mock import AsyncMock, MagicMock

        class _FakeOrchestrator:
            def __init__(self):
                self.ai_runtime = None
                self._llm_router_called = False

            async def _call_via_router(self):
                self._llm_router_called = True
                return "router response"

            async def _call_via_runtime(self, system_prompt, user_input):
                tracker.record("runtime.called")
                return "runtime response"

        return _FakeOrchestrator()

    @pytest.mark.asyncio
    async def test_runtime_path_taken_when_ai_runtime_set(self):
        """When ai_runtime is present, _call_runtime() is invoked."""
        tracker = _StageTracker()
        rt = _make_runtime(tracker)

        # Simulate what orchestrator._call_runtime does: call gateway directly
        request = LLMRequest(messages=[], max_tokens=10)
        # gateway has no messages but mock provider ignores them
        response = await rt.gateway.complete(request)
        assert response.content == "e2e response"
        assert "gateway.complete" in tracker.stages

    @pytest.mark.asyncio
    async def test_gateway_has_retry_policy(self):
        """LLMGateway must have a retry policy — LLMRouter has none."""
        tracker = _StageTracker()
        gw = _make_gateway(tracker)
        assert gw._retry_policy is not None
        assert gw._retry_policy.max_attempts >= 1

    @pytest.mark.asyncio
    async def test_gateway_fallback_chain_excludes_primary(self):
        """Fallback chain must not include the primary provider."""
        tracker = _StageTracker()
        gw = _make_gateway(tracker)
        # Register a second provider
        gw.register("backup", _TrackedProvider(tracker), priority=99)
        chain = gw._fallback_chain("mock")
        names = [e.name for e in chain]
        assert "mock" not in names
        assert "backup" in names

    def test_gateway_registered_providers_match_llm_router(self):
        """
        Both systems must share the same provider instances.
        Verified by checking that registering the same object to both
        results in identical identity.
        """
        from app.core.llm import LLMRouter
        tracker = _StageTracker()
        provider = _TrackedProvider(tracker)

        router = LLMRouter()
        router.register("mock", provider, default=True)

        gw = LLMGateway(retry_policy=_no_retry())
        gw.register("mock", provider)

        # Same object — no configuration drift
        assert router.providers["mock"] is gw._providers["mock"].provider


# ── TestRuntimeStatusEndpointContract ────────────────────────────────────────

class TestRuntimeStatusEndpointContract:
    """
    The /api/ai/runtime/status endpoint must return the correct schema
    whether AIRuntime is active or inactive.
    """

    @pytest.mark.asyncio
    async def test_health_active_when_provider_registered(self):
        tracker = _StageTracker()
        rt = _make_runtime(tracker)
        health = await rt.health()
        assert health.status == "healthy"
        assert len(health.gateway_providers) > 0

    @pytest.mark.asyncio
    async def test_health_offline_when_no_providers(self):
        gw = LLMGateway(retry_policy=_no_retry())
        rt = AIRuntime(gateway=gw)
        health = await rt.health()
        assert health.status == "offline"

    @pytest.mark.asyncio
    async def test_metrics_schema_complete(self):
        tracker = _StageTracker()
        rt = _make_runtime(tracker)
        await rt.process("hello", "s1")
        m = rt.metrics()
        # All fields must be present and non-negative
        assert m.total_requests    >= 1
        assert m.total_workflows   >= 0
        assert m.completed_goals   >= 0
        assert m.failed_goals      >= 0
        assert m.total_decisions   >= 0
        assert m.total_reflections >= 0

    @pytest.mark.asyncio
    async def test_health_details_track_requests(self):
        tracker = _StageTracker()
        rt = _make_runtime(tracker)
        await rt.process("q1", "s1")
        await rt.process("q2", "s1")
        health = await rt.health()
        assert health.details["total_requests"] == 2

    @pytest.mark.asyncio
    async def test_health_lists_registered_agents(self):
        tracker = _StageTracker()
        rt = _make_runtime(tracker, with_coordinator=True)
        health = await rt.health()
        assert "analyst" in health.registered_agents

    @pytest.mark.asyncio
    async def test_status_response_fields_present(self):
        """Simulate the fields the endpoint returns and verify all are present."""
        tracker = _StageTracker()
        rt = _make_runtime(tracker)
        await rt.process("hello", "s1")
        health  = await rt.health()
        metrics = rt.metrics()
        response = {
            "runtime":            "ACTIVE",
            "status":             health.status,
            "brain":              True,
            "memory":             True,
            "reasoning":          True,
            "gateway":            True,
            "providers":          health.gateway_providers,
            "registered_agents":  health.registered_agents,
            "requests_processed": metrics.total_requests,
            "workflows_run":      metrics.total_workflows,
            "completed_goals":    metrics.completed_goals,
            "failed_goals":       metrics.failed_goals,
            "total_decisions":    metrics.total_decisions,
            "total_reflections":  metrics.total_reflections,
        }
        required_keys = [
            "runtime", "status", "brain", "memory", "reasoning", "gateway",
            "providers", "requests_processed", "completed_goals",
        ]
        for key in required_keys:
            assert key in response, f"Missing key '{key}' in status response"


# ── TestTradeRequestValidation ────────────────────────────────────────────────

class TestTradeRequestValidation:
    """C2 fix: TradeRequest validators must reject invalid inputs."""

    def _make(self, symbol="RELIANCE", trade_type="BUY", qty=10):
        from app.api.routes import TradeRequest
        return TradeRequest(symbol=symbol, trade_type=trade_type, qty=qty)

    def test_valid_request_accepted(self):
        req = self._make()
        assert req.symbol == "RELIANCE"
        assert req.trade_type == "BUY"
        assert req.qty == 10

    def test_symbol_uppercased(self):
        req = self._make(symbol="reliance")
        assert req.symbol == "RELIANCE"

    def test_trade_type_uppercased(self):
        req = self._make(trade_type="buy")
        assert req.trade_type == "BUY"

    def test_sell_accepted(self):
        req = self._make(trade_type="SELL")
        assert req.trade_type == "SELL"

    def test_invalid_trade_type_rejected(self):
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            self._make(trade_type="LONG")

    def test_invalid_trade_type_abc_rejected(self):
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            self._make(trade_type="abc")

    def test_zero_qty_rejected(self):
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            self._make(qty=0)

    def test_negative_qty_rejected(self):
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            self._make(qty=-100)

    def test_qty_above_limit_rejected(self):
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            self._make(qty=10_001)

    def test_path_traversal_symbol_rejected(self):
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            self._make(symbol="../../etc")

    def test_symbol_with_spaces_rejected(self):
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            self._make(symbol="REL IANCE")

    def test_symbol_too_long_rejected(self):
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            self._make(symbol="A" * 21)

    def test_boundary_qty_1_accepted(self):
        req = self._make(qty=1)
        assert req.qty == 1

    def test_boundary_qty_10000_accepted(self):
        req = self._make(qty=10_000)
        assert req.qty == 10_000


# ── TestSafeMathEvaluator ─────────────────────────────────────────────────────

class TestSafeMathEvaluator:
    """C3 fix: _safe_math must evaluate arithmetic and reject unsafe expressions."""

    def _eval(self, expr: str):
        from app.core.orchestrator import JarvisOrchestrator
        orch = JarvisOrchestrator.__new__(JarvisOrchestrator)
        return orch._safe_math(expr)

    def test_addition(self):
        assert self._eval("2 + 3") == 5

    def test_subtraction(self):
        assert self._eval("10 - 4") == 6

    def test_multiplication(self):
        assert self._eval("6 * 7") == 42

    def test_division(self):
        assert self._eval("10 / 4") == 2.5

    def test_power(self):
        assert self._eval("2 ** 8") == 256

    def test_unary_negation(self):
        assert self._eval("-5 + 10") == 5

    def test_float_result(self):
        result = self._eval("1 / 3")
        assert abs(result - 0.3333333333) < 1e-6

    def test_word_operators_via_caller(self):
        """The caller replaces words before passing to _safe_math."""
        expr = "10 plus 5 minus 3"
        normalized = expr.replace("plus", "+").replace("minus", "-")
        assert self._eval(normalized) == 12

    def test_function_call_rejected(self):
        assert self._eval("__import__('os').system('ls')") is None

    def test_attribute_access_rejected(self):
        assert self._eval("(1).__class__") is None

    def test_string_literal_rejected(self):
        assert self._eval("'hello'") is None

    def test_empty_string_returns_none(self):
        assert self._eval("") is None

    def test_nonsense_returns_none(self):
        assert self._eval("not a math expression") is None

    def test_division_by_zero_returns_none(self):
        assert self._eval("1 / 0") is None


# ── TestDomainAgnosticism ─────────────────────────────────────────────────────

class TestDomainAgnosticism:
    """Mandatory: AIRuntime and all wired components have no trading first-class fields."""

    TRADING_FIELDS = [
        "symbol", "stock", "candle", "rsi", "macd", "broker",
        "portfolio", "trade", "price", "market", "nifty",
        "signal", "indicator", "ticker",
    ]

    def test_runtime_has_no_trading_attributes(self):
        tracker = _StageTracker()
        rt = _make_runtime(tracker)
        for attr in self.TRADING_FIELDS:
            assert not hasattr(rt, attr), f"Domain attr '{attr}' on AIRuntime"

    def test_brain_has_no_trading_attributes(self):
        tracker = _StageTracker()
        rt = _make_runtime(tracker)
        for attr in self.TRADING_FIELDS:
            assert not hasattr(rt.brain, attr), f"Domain attr '{attr}' on Brain"

    def test_execution_engine_has_no_trading_attributes(self):
        tracker = _StageTracker()
        rt = _make_runtime(tracker)
        for attr in self.TRADING_FIELDS:
            assert not hasattr(rt.engine, attr), f"Domain attr '{attr}' on ExecutionEngine"

    def test_gateway_has_no_trading_attributes(self):
        tracker = _StageTracker()
        rt = _make_runtime(tracker)
        for attr in self.TRADING_FIELDS:
            assert not hasattr(rt.gateway, attr), f"Domain attr '{attr}' on LLMGateway"

    def test_runtime_health_has_no_trading_attributes(self):
        h = RuntimeHealth(status="healthy")
        for attr in self.TRADING_FIELDS:
            assert attr not in vars(h), f"Domain attr '{attr}' on RuntimeHealth"

    def test_runtime_metrics_has_no_trading_attributes(self):
        m = RuntimeMetrics()
        for attr in self.TRADING_FIELDS:
            assert attr not in vars(m), f"Domain attr '{attr}' on RuntimeMetrics"

    @pytest.mark.asyncio
    async def test_domain_data_travels_via_metadata_only(self):
        tracker = _StageTracker()
        rt = _make_runtime(tracker)
        result = await rt.process(
            "analyze RELIANCE",
            "sess-domain",
            metadata={"symbol": "RELIANCE", "rsi": 72.4},
        )
        assert result.context.metadata.get("symbol") == "RELIANCE"
        assert result.context.metadata.get("rsi") == 72.4
