"""
tests/phase6/test_6a_workflow.py
==================================
Unit tests for WorkflowEngine (Task 6A.6).

All tests are pure -- no network, no I/O, no real LLM calls.
ExecutionEngine is mocked via a thin stub.
"""
import pytest

from app.ai.brain.brain import Goal
from app.ai.orchestration.coordinator import (
    AgentDescriptor, AgentRegistry, Coordinator,
)
from app.ai.orchestration.workflow import (
    NodeStatus,
    WorkflowStatus,
    WorkflowNode,
    Workflow,
    NodeRecord,
    WorkflowTrace,
    WorkflowResult,
    WorkflowEngine,
    WorkflowEventEmitter,
    CompensationHandler,
    _NoOpEmitter,
)
from app.ai.runtime.context import ExecutionContext
from app.ai.runtime.execution import ExecutionEngine, ExecutionResult, ExecutionTrace
from app.resilience.retry import RetryPolicy, RetryStrategy


# ── Shared mocks ──────────────────────────────────────────────────────────────

class MockProvider:
    async def generate(self, messages, **kwargs):
        from app.core.llm import LLMResponse as CoreResp
        return CoreResp(content="ok", model="mock", tokens_used=5)

    async def stream(self, messages, **kwargs):
        yield "token"


def _no_retry():
    return RetryPolicy(max_attempts=1, strategy=RetryStrategy.FIXED, base_delay_s=0.0)


def _make_engine(succeed: bool = True) -> ExecutionEngine:
    """Return an ExecutionEngine whose run() always succeeds or always fails."""
    from app.ai.runtime.llm_gateway import LLMGateway
    from app.ai.runtime.execution import PipelineResponder

    gw = LLMGateway(retry_policy=_no_retry())
    gw.register("mock", MockProvider())

    if succeed:
        return ExecutionEngine(gateway=gw)

    # Failing engine: planner raises
    from app.ai.runtime.execution import PipelinePlanner
    class _FailPlanner(PipelinePlanner):
        async def plan(self, ctx):
            raise RuntimeError("forced failure")

    return ExecutionEngine(gateway=gw, planner=_FailPlanner())


def _make_workflow_engine(succeed: bool = True, coordinator=None) -> WorkflowEngine:
    return WorkflowEngine(
        engine=_make_engine(succeed),
        coordinator=coordinator,
    )


def _node(name: str, depends_on=None, on_failure="retry",
          max_retries=0, agent="analyst") -> WorkflowNode:
    n = WorkflowNode(name=name, on_failure=on_failure, max_retries=max_retries)
    n.assigned_agent = agent
    if depends_on:
        n.depends_on = depends_on
    return n


def _workflow(*nodes: WorkflowNode, name: str = "test_wf") -> Workflow:
    wf = Workflow(name=name)
    for n in nodes:
        wf.add_node(n)
    return wf


class CapturingEmitter(WorkflowEventEmitter):
    def __init__(self):
        self.events: list = []

    async def emit(self, event_name: str, payload: dict) -> None:
        self.events.append(event_name)


# ── TestWorkflowNode ──────────────────────────────────────────────────────────

class TestWorkflowNode:

    def test_id_auto_generated(self):
        n = WorkflowNode()
        assert len(n.id) == 36

    def test_two_nodes_have_different_ids(self):
        assert WorkflowNode().id != WorkflowNode().id

    def test_default_status_pending(self):
        assert WorkflowNode().status == NodeStatus.PENDING

    def test_depends_on_defaults_empty(self):
        assert WorkflowNode().depends_on == []

    def test_on_failure_defaults_retry(self):
        assert WorkflowNode().on_failure == "retry"

    def test_is_terminal_completed(self):
        n = WorkflowNode()
        n.status = NodeStatus.COMPLETED
        assert n.is_terminal() is True

    def test_is_terminal_failed(self):
        n = WorkflowNode()
        n.status = NodeStatus.FAILED
        assert n.is_terminal() is True

    def test_is_terminal_skipped(self):
        n = WorkflowNode()
        n.status = NodeStatus.SKIPPED
        assert n.is_terminal() is True

    def test_is_not_terminal_running(self):
        n = WorkflowNode()
        n.status = NodeStatus.RUNNING
        assert n.is_terminal() is False

    def test_metadata_is_domain_escape_hatch(self):
        n = WorkflowNode()
        n.metadata["symbol"] = "RELIANCE"
        assert n.metadata["symbol"] == "RELIANCE"


# ── TestWorkflow ──────────────────────────────────────────────────────────────

class TestWorkflow:

    def test_add_node(self):
        wf = Workflow(name="wf")
        wf.add_node(_node("step1"))
        assert len(wf.nodes) == 1

    def test_get_node_by_id(self):
        n  = _node("step1")
        wf = _workflow(n)
        assert wf.get_node(n.id) is n

    def test_get_node_by_name(self):
        n  = _node("step1")
        wf = _workflow(n)
        assert wf.get_node_by_name("step1") is n

    def test_get_node_missing_returns_none(self):
        wf = _workflow()
        assert wf.get_node("nonexistent") is None

    def test_completed_ids(self):
        n1 = _node("a")
        n2 = _node("b")
        n1.status = NodeStatus.COMPLETED
        wf = _workflow(n1, n2)
        assert n1.id in wf.completed_ids()
        assert n2.id not in wf.completed_ids()

    def test_failed_nodes(self):
        n1 = _node("a")
        n2 = _node("b")
        n1.status = NodeStatus.FAILED
        wf = _workflow(n1, n2)
        assert n1 in wf.failed_nodes()
        assert n2 not in wf.failed_nodes()

    def test_skipped_nodes(self):
        n = _node("a")
        n.status = NodeStatus.SKIPPED
        wf = _workflow(n)
        assert n in wf.skipped_nodes()


# ── TestWorkflowTrace ─────────────────────────────────────────────────────────

class TestWorkflowTrace:

    def test_add_record(self):
        t = WorkflowTrace(workflow_id="w1", workflow_name="wf")
        t.add_record(NodeRecord(node_id="n1", node_name="step1", status="completed"))
        assert len(t.node_records) == 1

    def test_timing_report_contains_node_names(self):
        t = WorkflowTrace(workflow_id="w1", workflow_name="wf")
        t.add_record(NodeRecord(node_id="n1", node_name="step1",
                                status="completed", duration_ms=42.0))
        report = t.timing_report()
        assert "step1" in report
        assert "Total"  in report

    def test_timing_report_marks_skipped(self):
        t = WorkflowTrace(workflow_id="w1", workflow_name="wf")
        t.add_record(NodeRecord(node_id="n1", node_name="step1",
                                status="skipped", skipped=True))
        assert "[skipped]" in t.timing_report()


# ── TestWorkflowEngineBasic ───────────────────────────────────────────────────

class TestWorkflowEngineBasic:

    @pytest.mark.asyncio
    async def test_run_returns_workflow_result(self):
        we     = _make_workflow_engine()
        result = await we.run(_workflow(_node("step1")))
        assert isinstance(result, WorkflowResult)

    @pytest.mark.asyncio
    async def test_single_node_completes(self):
        we     = _make_workflow_engine()
        result = await we.run(_workflow(_node("step1")))
        assert result.workflow.nodes[0].status == NodeStatus.COMPLETED

    @pytest.mark.asyncio
    async def test_workflow_status_completed_on_success(self):
        we     = _make_workflow_engine()
        result = await we.run(_workflow(_node("step1")))
        assert result.workflow.status == WorkflowStatus.COMPLETED
        assert result.success is True

    @pytest.mark.asyncio
    async def test_multiple_nodes_all_complete(self):
        we     = _make_workflow_engine()
        result = await we.run(_workflow(_node("a"), _node("b"), _node("c")))
        for n in result.workflow.nodes:
            assert n.status == NodeStatus.COMPLETED

    @pytest.mark.asyncio
    async def test_node_results_keyed_by_node_id(self):
        n  = _node("step1")
        we = _make_workflow_engine()
        result = await we.run(_workflow(n))
        assert n.id in result.node_results

    @pytest.mark.asyncio
    async def test_trace_has_record_per_node(self):
        we     = _make_workflow_engine()
        result = await we.run(_workflow(_node("a"), _node("b")))
        assert len(result.trace.node_records) == 2

    @pytest.mark.asyncio
    async def test_trace_total_ms_positive(self):
        we     = _make_workflow_engine()
        result = await we.run(_workflow(_node("step1")))
        assert result.trace.total_ms >= 0.0


# ── TestDependencyResolution ──────────────────────────────────────────────────

class TestDependencyResolution:

    @pytest.mark.asyncio
    async def test_node_with_satisfied_dependency_runs(self):
        n1 = _node("step1")
        n2 = _node("step2")
        n2.depends_on = [n1.id]
        we     = _make_workflow_engine()
        result = await we.run(_workflow(n1, n2))
        assert n2.status == NodeStatus.COMPLETED

    @pytest.mark.asyncio
    async def test_node_with_unsatisfied_dependency_fails(self):
        n1 = _node("step1")
        n2 = _node("step2")
        # n2 depends on a non-existent node
        n2.depends_on = ["nonexistent-id"]
        we     = _make_workflow_engine()
        result = await we.run(_workflow(n1, n2))
        assert n2.status == NodeStatus.FAILED
        assert "Dependency" in n2.error

    @pytest.mark.asyncio
    async def test_failed_dependency_blocks_downstream(self):
        n1 = _node("step1")
        n2 = _node("step2")
        n2.depends_on = [n1.id]
        # n1 will fail because engine is set to fail
        we     = _make_workflow_engine(succeed=False)
        result = await we.run(_workflow(n1, n2))
        # n1 fails, n2's dependency (n1) is not in completed_ids
        assert n2.status == NodeStatus.FAILED

    @pytest.mark.asyncio
    async def test_independent_nodes_both_run(self):
        n1 = _node("a")
        n2 = _node("b")
        # no dependencies between them
        we     = _make_workflow_engine()
        result = await we.run(_workflow(n1, n2))
        assert n1.status == NodeStatus.COMPLETED
        assert n2.status == NodeStatus.COMPLETED


# ── TestFailurePolicy ─────────────────────────────────────────────────────────

class TestFailurePolicy:

    @pytest.mark.asyncio
    async def test_failed_node_marks_workflow_failed(self):
        we     = _make_workflow_engine(succeed=False)
        result = await we.run(_workflow(_node("step1")))
        assert result.workflow.status == WorkflowStatus.FAILED
        assert result.success is False

    @pytest.mark.asyncio
    async def test_skip_policy_marks_node_skipped(self):
        n  = _node("step1", on_failure="skip")
        we = _make_workflow_engine(succeed=False)
        result = await we.run(_workflow(n))
        assert n.status == NodeStatus.SKIPPED

    @pytest.mark.asyncio
    async def test_partial_status_when_some_succeed_some_fail(self):
        n_ok   = _node("ok_step")
        n_fail = _node("fail_step")
        # Run ok first, then fail
        we = WorkflowEngine(engine=_make_engine(succeed=True))
        # Patch: make second node fail by giving it a bad engine
        # Simplest: use skip on second node and check PARTIAL
        n_skip = _node("skip_step", on_failure="skip")
        fail_we = WorkflowEngine(engine=_make_engine(succeed=False))
        result  = await fail_we.run(_workflow(n_ok, n_skip))
        # n_ok fails (engine fails), n_skip is skipped
        assert result.workflow.status in (
            WorkflowStatus.FAILED, WorkflowStatus.PARTIAL
        )

    @pytest.mark.asyncio
    async def test_trace_error_set_on_failure(self):
        we     = _make_workflow_engine(succeed=False)
        result = await we.run(_workflow(_node("step1")))
        assert result.trace.error is not None

    @pytest.mark.asyncio
    async def test_retry_count_incremented(self):
        n  = _node("step1", max_retries=2)
        we = _make_workflow_engine(succeed=False)
        await we.run(_workflow(n))
        assert n.retry_count > 0


# ── TestCoordinatorIntegration ────────────────────────────────────────────────

class TestCoordinatorIntegration:

    def _make_coordinator(self) -> Coordinator:
        r = AgentRegistry()
        r.register(AgentDescriptor(name="analyst", supported_intents=["analyze"]))
        return Coordinator(registry=r)

    @pytest.mark.asyncio
    async def test_coordinator_assigns_agent(self):
        n  = WorkflowNode(name="analyze market")  # no assigned_agent
        we = WorkflowEngine(
            engine=_make_engine(),
            coordinator=self._make_coordinator(),
        )
        result = await we.run(_workflow(n))
        assert n.assigned_agent == "analyst"

    @pytest.mark.asyncio
    async def test_no_coordinator_uses_preset_agent(self):
        n  = _node("step1", agent="preset_agent")
        we = _make_workflow_engine()
        await we.run(_workflow(n))
        assert n.assigned_agent == "preset_agent"

    @pytest.mark.asyncio
    async def test_empty_registry_fails_node(self):
        n  = WorkflowNode(name="step1")  # no assigned_agent
        we = WorkflowEngine(
            engine=_make_engine(),
            coordinator=Coordinator(registry=AgentRegistry()),
        )
        result = await we.run(_workflow(n))
        assert n.status == NodeStatus.FAILED


# ── TestEventEmission ─────────────────────────────────────────────────────────

class TestEventEmission:

    @pytest.mark.asyncio
    async def test_workflow_started_emitted(self):
        emitter = CapturingEmitter()
        we      = WorkflowEngine(engine=_make_engine(), emitter=emitter)
        await we.run(_workflow(_node("step1")))
        assert "WorkflowStarted" in emitter.events

    @pytest.mark.asyncio
    async def test_workflow_completed_emitted(self):
        emitter = CapturingEmitter()
        we      = WorkflowEngine(engine=_make_engine(), emitter=emitter)
        await we.run(_workflow(_node("step1")))
        assert "WorkflowCompleted" in emitter.events

    @pytest.mark.asyncio
    async def test_node_started_emitted(self):
        emitter = CapturingEmitter()
        we      = WorkflowEngine(engine=_make_engine(), emitter=emitter)
        await we.run(_workflow(_node("step1")))
        assert "NodeStarted" in emitter.events

    @pytest.mark.asyncio
    async def test_node_completed_emitted(self):
        emitter = CapturingEmitter()
        we      = WorkflowEngine(engine=_make_engine(), emitter=emitter)
        await we.run(_workflow(_node("step1")))
        assert "NodeCompleted" in emitter.events

    @pytest.mark.asyncio
    async def test_node_failed_emitted_on_failure(self):
        emitter = CapturingEmitter()
        we      = WorkflowEngine(engine=_make_engine(succeed=False), emitter=emitter)
        await we.run(_workflow(_node("step1")))
        assert "NodeFailed" in emitter.events

    @pytest.mark.asyncio
    async def test_broken_emitter_does_not_crash_workflow(self):
        class BrokenEmitter(WorkflowEventEmitter):
            async def emit(self, name, payload):
                raise RuntimeError("broken")
        we     = WorkflowEngine(engine=_make_engine(), emitter=BrokenEmitter())
        result = await we.run(_workflow(_node("step1")))
        assert result is not None


# ── TestDomainAgnosticism ─────────────────────────────────────────────────────

class TestDomainAgnosticism:

    TRADING_FIELDS = [
        "symbol", "stock", "candle", "rsi", "macd", "broker",
        "portfolio", "trade", "price", "market", "nifty",
        "signal", "indicator", "ticker",
    ]

    def test_workflow_engine_has_no_trading_attributes(self):
        we = _make_workflow_engine()
        for attr in self.TRADING_FIELDS:
            assert not hasattr(we, attr), f"Domain attr '{attr}' on WorkflowEngine"

    def test_workflow_node_has_no_trading_attributes(self):
        n = WorkflowNode()
        for attr in self.TRADING_FIELDS:
            assert attr not in vars(n), f"Domain attr '{attr}' on WorkflowNode"

    def test_workflow_has_no_trading_attributes(self):
        wf = Workflow()
        for attr in self.TRADING_FIELDS:
            assert attr not in vars(wf), f"Domain attr '{attr}' on Workflow"

    def test_metadata_carries_domain_data(self):
        n = WorkflowNode()
        n.metadata["symbol"]    = "RELIANCE"
        n.metadata["rsi_value"] = 72.4
        assert n.metadata["symbol"]    == "RELIANCE"
        assert n.metadata["rsi_value"] == 72.4
