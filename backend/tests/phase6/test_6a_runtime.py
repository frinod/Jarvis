"""
tests/phase6/test_6a_runtime.py
================================
Unit tests for AIRuntime facade (Task 6A.7).

All tests are pure -- no network, no I/O, no real LLM calls.
This is the Phase 6A milestone test: AIRuntime.process() routes a request
through Brain → Coordinator → ExecutionEngine.
"""
import pytest

from app.ai import AIRuntime, RuntimeHealth, RuntimeMetrics
from app.ai.orchestration.coordinator import (
    AgentDescriptor, AgentRegistry, Coordinator,
)
from app.ai.orchestration.workflow import Workflow, WorkflowNode, WorkflowResult, WorkflowStatus
from app.ai.runtime.execution import ExecutionResult
from app.ai.runtime.llm_gateway import LLMGateway
from app.resilience.retry import RetryPolicy, RetryStrategy


# ── Shared helpers ────────────────────────────────────────────────────────────

class MockProvider:
    async def generate(self, messages, **kwargs):
        from app.core.llm import LLMResponse as CoreResp
        return CoreResp(content="runtime response", model="mock", tokens_used=10)

    async def stream(self, messages, **kwargs):
        for t in ["hello", " ", "world"]:
            yield t


def _no_retry():
    return RetryPolicy(max_attempts=1, strategy=RetryStrategy.FIXED, base_delay_s=0.0)


def _make_gateway() -> LLMGateway:
    gw = LLMGateway(retry_policy=_no_retry())
    gw.register("mock", MockProvider())
    return gw


def _make_coordinator(agent_name: str = "analyst") -> Coordinator:
    r = AgentRegistry()
    r.register(AgentDescriptor(name=agent_name, supported_intents=["general"]))
    return Coordinator(registry=r)


def _make_runtime(with_coordinator: bool = False) -> AIRuntime:
    gw = _make_gateway()
    coord = _make_coordinator() if with_coordinator else None
    return AIRuntime(gateway=gw, coordinator=coord)


# ── TestAIRuntimeConstruction ─────────────────────────────────────────────────

class TestAIRuntimeConstruction:

    def test_constructs_with_gateway_only(self):
        rt = _make_runtime()
        assert rt is not None

    def test_constructs_with_coordinator(self):
        rt = _make_runtime(with_coordinator=True)
        assert rt is not None

    def test_brain_property(self):
        from app.ai.brain.brain import Brain
        rt = _make_runtime()
        assert isinstance(rt.brain, Brain)

    def test_engine_property(self):
        from app.ai.runtime.execution import ExecutionEngine
        rt = _make_runtime()
        assert isinstance(rt.engine, ExecutionEngine)

    def test_gateway_property(self):
        rt = _make_runtime()
        assert isinstance(rt.gateway, LLMGateway)

    def test_workflow_engine_property(self):
        from app.ai.orchestration.workflow import WorkflowEngine
        rt = _make_runtime()
        assert isinstance(rt.workflow_engine, WorkflowEngine)

    def test_initial_request_count_zero(self):
        rt = _make_runtime()
        assert rt._request_count == 0

    def test_initial_workflow_count_zero(self):
        rt = _make_runtime()
        assert rt._workflow_count == 0


# ── TestAIRuntimeProcess ──────────────────────────────────────────────────────

class TestAIRuntimeProcess:

    @pytest.mark.asyncio
    async def test_process_returns_execution_result(self):
        rt     = _make_runtime()
        result = await rt.process("hello", "sess-1")
        assert isinstance(result, ExecutionResult)

    @pytest.mark.asyncio
    async def test_process_increments_request_count(self):
        rt = _make_runtime()
        await rt.process("hello", "sess-1")
        await rt.process("world", "sess-1")
        assert rt._request_count == 2

    @pytest.mark.asyncio
    async def test_process_with_coordinator_routes_to_agent(self):
        rt     = _make_runtime(with_coordinator=True)
        result = await rt.process("analyze something", "sess-1")
        assert isinstance(result, ExecutionResult)

    @pytest.mark.asyncio
    async def test_process_with_metadata(self):
        rt     = _make_runtime()
        result = await rt.process("hello", "sess-1", metadata={"domain": "research"})
        assert result.context.metadata.get("domain") == "research"

    @pytest.mark.asyncio
    async def test_process_never_raises(self):
        """AIRuntime.process() must never raise -- failures are in the result."""
        rt = _make_runtime()
        try:
            result = await rt.process("", "")
            assert result is not None
        except Exception as exc:
            pytest.fail(f"process() raised unexpectedly: {exc}")

    @pytest.mark.asyncio
    async def test_process_session_id_propagated(self):
        rt     = _make_runtime()
        result = await rt.process("hello", "sess-42")
        assert result.context.session_id == "sess-42"

    @pytest.mark.asyncio
    async def test_process_creates_brain_goal(self):
        rt = _make_runtime()
        await rt.process("test question", "sess-1")
        assert len(rt.brain._goal_history) == 1
        assert rt.brain._goal_history[0].objective == "test question"


# ── TestAIRuntimeStream ───────────────────────────────────────────────────────

class TestAIRuntimeStream:

    @pytest.mark.asyncio
    async def test_stream_yields_tokens(self):
        rt     = _make_runtime()
        tokens = []
        async for token in rt.stream("hello", "sess-1"):
            tokens.append(token)
        assert len(tokens) > 0

    @pytest.mark.asyncio
    async def test_stream_increments_request_count(self):
        rt = _make_runtime()
        async for _ in rt.stream("hello", "sess-1"):
            pass
        assert rt._request_count == 1

    @pytest.mark.asyncio
    async def test_stream_yields_strings(self):
        rt = _make_runtime()
        async for token in rt.stream("hello", "sess-1"):
            assert isinstance(token, str)


# ── TestAIRuntimeWorkflow ─────────────────────────────────────────────────────

class TestAIRuntimeWorkflow:

    def _make_workflow(self, agent: str = "analyst") -> Workflow:
        wf = Workflow(name="test_workflow")
        n  = WorkflowNode(name="step1")
        n.assigned_agent = agent
        wf.add_node(n)
        return wf

    @pytest.mark.asyncio
    async def test_run_workflow_returns_result(self):
        rt     = _make_runtime()
        result = await rt.run_workflow(self._make_workflow())
        assert isinstance(result, WorkflowResult)

    @pytest.mark.asyncio
    async def test_run_workflow_increments_count(self):
        rt = _make_runtime()
        await rt.run_workflow(self._make_workflow())
        await rt.run_workflow(self._make_workflow())
        assert rt._workflow_count == 2

    @pytest.mark.asyncio
    async def test_run_workflow_completes_successfully(self):
        rt     = _make_runtime()
        result = await rt.run_workflow(self._make_workflow())
        assert result.workflow.status == WorkflowStatus.COMPLETED

    @pytest.mark.asyncio
    async def test_run_workflow_with_coordinator(self):
        rt = _make_runtime(with_coordinator=True)
        wf = Workflow(name="coord_wf")
        n  = WorkflowNode(name="step1")  # no assigned_agent -- coordinator assigns
        wf.add_node(n)
        result = await rt.run_workflow(wf)
        assert isinstance(result, WorkflowResult)


# ── TestAIRuntimeHealth ───────────────────────────────────────────────────────

class TestAIRuntimeHealth:

    @pytest.mark.asyncio
    async def test_health_returns_runtime_health(self):
        rt     = _make_runtime()
        health = await rt.health()
        assert isinstance(health, RuntimeHealth)

    @pytest.mark.asyncio
    async def test_health_status_healthy_with_provider(self):
        rt     = _make_runtime()
        health = await rt.health()
        assert health.status == "healthy"

    @pytest.mark.asyncio
    async def test_health_lists_gateway_providers(self):
        rt     = _make_runtime()
        health = await rt.health()
        assert "mock" in health.gateway_providers

    @pytest.mark.asyncio
    async def test_health_offline_when_no_providers(self):
        gw = LLMGateway(retry_policy=_no_retry())  # no providers registered
        rt = AIRuntime(gateway=gw)
        health = await rt.health()
        assert health.status == "offline"

    @pytest.mark.asyncio
    async def test_health_lists_registered_agents(self):
        rt     = _make_runtime(with_coordinator=True)
        health = await rt.health()
        assert "analyst" in health.registered_agents

    @pytest.mark.asyncio
    async def test_health_details_include_request_count(self):
        rt = _make_runtime()
        await rt.process("hello", "s1")
        health = await rt.health()
        assert health.details["total_requests"] == 1


# ── TestAIRuntimeMetrics ──────────────────────────────────────────────────────

class TestAIRuntimeMetrics:

    def test_metrics_returns_runtime_metrics(self):
        rt = _make_runtime()
        assert isinstance(rt.metrics(), RuntimeMetrics)

    @pytest.mark.asyncio
    async def test_metrics_counts_requests(self):
        rt = _make_runtime()
        await rt.process("q1", "s1")
        await rt.process("q2", "s1")
        m = rt.metrics()
        assert m.total_requests == 2

    @pytest.mark.asyncio
    async def test_metrics_counts_workflows(self):
        rt = _make_runtime()
        wf = Workflow(name="wf")
        n  = WorkflowNode(name="step1")
        n.assigned_agent = "analyst"
        wf.add_node(n)
        await rt.run_workflow(wf)
        assert rt.metrics().total_workflows == 1

    @pytest.mark.asyncio
    async def test_metrics_completed_goals_after_process(self):
        rt = _make_runtime()
        await rt.process("hello", "s1")
        m = rt.metrics()
        assert m.completed_goals >= 1

    def test_metrics_zero_on_fresh_runtime(self):
        rt = _make_runtime()
        m  = rt.metrics()
        assert m.total_requests    == 0
        assert m.total_workflows   == 0
        assert m.completed_goals   == 0


# ── TestPhase6AMilestone ──────────────────────────────────────────────────────

class TestPhase6AMilestone:
    """
    Milestone test: AIRuntime.process() routes a request through
    Brain → Coordinator → ExecutionEngine end-to-end.
    This is the Phase 6A completion criterion from the architecture doc.
    """

    @pytest.mark.asyncio
    async def test_full_pipeline_brain_to_engine(self):
        rt     = _make_runtime(with_coordinator=True)
        result = await rt.process("What should I focus on today?", "sess-milestone")
        assert isinstance(result, ExecutionResult)
        assert result.context.session_id == "sess-milestone"

    @pytest.mark.asyncio
    async def test_brain_records_decision_for_request(self):
        rt = _make_runtime(with_coordinator=True)
        await rt.process("test", "sess-1")
        assert len(rt.brain._decision_history) >= 1

    @pytest.mark.asyncio
    async def test_brain_reflection_runs_after_process(self):
        rt = _make_runtime()
        await rt.process("test", "sess-1")
        assert len(rt.brain._reflection_log) >= 1

    @pytest.mark.asyncio
    async def test_multiple_sessions_independent(self):
        rt = _make_runtime()
        await rt.process("q1", "sess-A")
        await rt.process("q2", "sess-B")
        assert rt.brain.get_session("sess-A") is not None
        assert rt.brain.get_session("sess-B") is not None
        assert rt.brain.get_session("sess-A") is not rt.brain.get_session("sess-B")


# ── TestDomainAgnosticism ─────────────────────────────────────────────────────

class TestDomainAgnosticism:

    TRADING_FIELDS = [
        "symbol", "stock", "candle", "rsi", "macd", "broker",
        "portfolio", "trade", "price", "market", "nifty",
        "signal", "indicator", "ticker",
    ]

    def test_runtime_has_no_trading_attributes(self):
        rt = _make_runtime()
        for attr in self.TRADING_FIELDS:
            assert not hasattr(rt, attr), f"Domain attr '{attr}' on AIRuntime"

    def test_runtime_health_has_no_trading_attributes(self):
        h = RuntimeHealth(status="healthy")
        for attr in self.TRADING_FIELDS:
            assert attr not in vars(h), f"Domain attr '{attr}' on RuntimeHealth"

    def test_runtime_metrics_has_no_trading_attributes(self):
        m = RuntimeMetrics()
        for attr in self.TRADING_FIELDS:
            assert attr not in vars(m), f"Domain attr '{attr}' on RuntimeMetrics"

    @pytest.mark.asyncio
    async def test_metadata_carries_domain_context(self):
        rt     = _make_runtime()
        result = await rt.process("hello", "s1", metadata={"symbol": "RELIANCE"})
        assert result.context.metadata.get("symbol") == "RELIANCE"
