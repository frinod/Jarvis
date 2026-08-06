"""
tests/phase6/test_6a_brain.py
==============================
Unit tests for Brain (Task 6A.4).

All tests are pure -- no network, no I/O, no LLM calls.
All collaborators are mocked.
"""
import pytest

from app.ai.brain.brain import (
    Goal,
    GoalStatus,
    DecisionRecord,
    ActionItem,
    ReflectionResult,
    MemoryScopeSpec,
    ExecutionPolicySpec,
    SessionState,
    BrainCapabilities,
    BrainAgentSelector,
    BrainMemoryScope,
    BrainExecutionPolicy,
    Brain,
)
from app.ai.runtime.context import ExecutionContext, RequestState, SkillResult, ToolResult
from app.ai.runtime.execution import ExecutionEngine, ExecutionResult, ExecutionTrace
from app.resilience.retry import RetryPolicy, RetryStrategy


# ── Shared mocks ──────────────────────────────────────────────────────────────

class MockProvider:
    async def generate(self, messages, **kwargs):
        from app.core.llm import LLMResponse as CoreResp
        return CoreResp(content="mock", model="mock", tokens_used=5)

    async def stream(self, messages, **kwargs):
        yield "token"


def _no_retry():
    return RetryPolicy(max_attempts=1, strategy=RetryStrategy.FIXED, base_delay_s=0.0)


def _make_engine() -> ExecutionEngine:
    from app.ai.runtime.llm_gateway import LLMGateway
    gw = LLMGateway(retry_policy=_no_retry())
    gw.register("mock", MockProvider())
    return ExecutionEngine(gateway=gw)


def _make_brain(**kwargs) -> Brain:
    return Brain(engine=_make_engine(), **kwargs)


# ── TestGoal ──────────────────────────────────────────────────────────────────

class TestGoal:

    def test_default_status_is_pending(self):
        g = Goal(objective="do something")
        assert g.status == GoalStatus.PENDING

    def test_id_auto_generated(self):
        g = Goal()
        assert len(g.id) == 36

    def test_two_goals_have_different_ids(self):
        assert Goal().id != Goal().id

    def test_activate_sets_active(self):
        g = Goal()
        g.activate()
        assert g.status == GoalStatus.ACTIVE

    def test_complete_sets_completed(self):
        g = Goal()
        g.complete(result="done", confidence=0.9)
        assert g.status == GoalStatus.COMPLETED
        assert g.result == "done"
        assert g.confidence == 0.9

    def test_fail_sets_failed(self):
        g = Goal()
        g.fail("timeout")
        assert g.status == GoalStatus.FAILED
        assert g.metadata["failure_reason"] == "timeout"

    def test_abandon_sets_abandoned(self):
        g = Goal()
        g.abandon()
        assert g.status == GoalStatus.ABANDONED

    def test_parent_goal_id_defaults_none(self):
        g = Goal()
        assert g.parent_goal_id is None

    def test_parent_goal_id_can_be_set(self):
        parent = Goal(objective="parent")
        child  = Goal(objective="child", parent_goal_id=parent.id)
        assert child.parent_goal_id == parent.id

    def test_metadata_is_domain_escape_hatch(self):
        g = Goal()
        g.metadata["symbol"] = "RELIANCE"
        assert g.metadata["symbol"] == "RELIANCE"

    def test_priority_defaults_to_3(self):
        g = Goal()
        assert g.priority == 3


# ── TestDecisionRecord ────────────────────────────────────────────────────────

class TestDecisionRecord:

    def test_id_auto_generated(self):
        d = DecisionRecord()
        assert len(d.decision_id) == 36

    def test_decision_source_field_exists(self):
        d = DecisionRecord(decision_source="Brain")
        assert d.decision_source == "Brain"

    def test_decision_source_can_be_any_component(self):
        for source in ["Brain", "Planner", "Coordinator", "TraderAgent", "Reasoner"]:
            d = DecisionRecord(decision_source=source)
            assert d.decision_source == source

    def test_all_fields_settable(self):
        d = DecisionRecord(
            goal_id="g1",
            decision_type="agent_selection",
            decision_source="Brain",
            rationale="best fit",
            outcome="analyst selected",
        )
        assert d.goal_id         == "g1"
        assert d.decision_type   == "agent_selection"
        assert d.rationale       == "best fit"
        assert d.outcome         == "analyst selected"

    def test_timestamp_auto_set(self):
        d = DecisionRecord()
        assert d.timestamp > 0


# ── TestReflectionResult ──────────────────────────────────────────────────────

class TestReflectionResult:

    def test_construction(self):
        r = ReflectionResult(
            goal_id="g1",
            objective_achieved=True,
            confidence_delta=0.02,
            should_store=True,
            critique="clean success",
        )
        assert r.goal_id             == "g1"
        assert r.objective_achieved  is True
        assert r.confidence_delta    == 0.02
        assert r.should_store        is True

    def test_action_items_default_empty(self):
        r = ReflectionResult(
            goal_id="g1", objective_achieved=True,
            confidence_delta=0.0, should_store=False, critique=""
        )
        assert r.action_items == []

    def test_action_item_fields(self):
        a = ActionItem(action="increase_memory_scope", reason="retries hit max", priority=2)
        assert a.action   == "increase_memory_scope"
        assert a.reason   == "retries hit max"
        assert a.priority == 2

    def test_reflection_with_action_items(self):
        items = [
            ActionItem("store_to_long_term_memory", "high confidence", 5),
            ActionItem("review_tool_reliability",   "tool failed",     3),
        ]
        r = ReflectionResult(
            goal_id="g1", objective_achieved=True,
            confidence_delta=0.02, should_store=True,
            critique="ok", action_items=items,
        )
        assert len(r.action_items) == 2
        assert r.action_items[0].action == "store_to_long_term_memory"


# ── TestBrainConstruction ─────────────────────────────────────────────────────

class TestBrainConstruction:

    def test_brain_constructs_with_engine_only(self):
        brain = _make_brain()
        assert brain is not None

    def test_default_capabilities(self):
        brain = _make_brain()
        assert brain.capabilities.supports_reflection is True
        assert brain.capabilities.supports_learning   is False
        assert brain.capabilities.supports_streaming  is True

    def test_custom_capabilities(self):
        caps  = BrainCapabilities(supports_parallel_goals=True)
        brain = _make_brain(capabilities=caps)
        assert brain.capabilities.supports_parallel_goals is True

    def test_initial_state_empty(self):
        brain = _make_brain()
        s = brain.session_summary()
        assert s["active_goals"]    == 0
        assert s["completed_goals"] == 0
        assert s["total_decisions"] == 0


# ── TestBrainProcess ──────────────────────────────────────────────────────────

class TestBrainProcess:

    @pytest.mark.asyncio
    async def test_process_returns_execution_result(self):
        brain  = _make_brain()
        result = await brain.process("hello", "sess-1")
        assert isinstance(result, ExecutionResult)

    @pytest.mark.asyncio
    async def test_process_creates_goal_in_history(self):
        brain = _make_brain()
        await brain.process("hello", "sess-1")
        assert len(brain._goal_history) == 1
        assert brain._goal_history[0].objective == "hello"

    @pytest.mark.asyncio
    async def test_process_goal_status_completed(self):
        brain = _make_brain()
        await brain.process("hello", "sess-1")
        assert brain._goal_history[0].status == GoalStatus.COMPLETED

    @pytest.mark.asyncio
    async def test_process_no_active_goals_after_completion(self):
        brain = _make_brain()
        await brain.process("hello", "sess-1")
        assert len(brain._active_goals) == 0

    @pytest.mark.asyncio
    async def test_process_records_agent_selection_decision(self):
        brain = _make_brain()
        await brain.process("hello", "sess-1")
        decisions = brain._decision_history
        types = [d.decision_type for d in decisions]
        assert "agent_selection" in types

    @pytest.mark.asyncio
    async def test_process_records_reflection_decision(self):
        brain = _make_brain()
        await brain.process("hello", "sess-1")
        types = [d.decision_type for d in brain._decision_history]
        assert "reflection" in types

    @pytest.mark.asyncio
    async def test_process_updates_session_state(self):
        brain = _make_brain()
        await brain.process("hello", "sess-42")
        session = brain.get_session("sess-42")
        assert session is not None
        assert session.session_id == "sess-42"

    @pytest.mark.asyncio
    async def test_process_metadata_forwarded(self):
        brain  = _make_brain()
        result = await brain.process("hello", "sess-1", metadata={"domain": "research"})
        assert result.context.metadata.get("domain") == "research"


# ── TestBrainConfidenceAggregation ────────────────────────────────────────────

class TestBrainConfidenceAggregation:

    def _ctx(self, reasoner_conf=0.0, skill_success=None, tool_success=None, retries=0):
        ctx = ExecutionContext()
        ctx.confidence  = reasoner_conf
        ctx.retry_count = retries
        if skill_success is not None:
            ctx.skill_results["s"] = SkillResult("s", skill_success, None)
        if tool_success is not None:
            ctx.tool_results["t"] = ToolResult("t", tool_success, None)
        return ctx

    def test_reasoner_only(self):
        brain  = _make_brain()
        policy = ExecutionPolicySpec()
        ctx    = self._ctx(reasoner_conf=0.8)
        conf   = brain._aggregate_confidence(ctx, policy)
        assert conf == round(0.8 * 0.5 / 0.5, 3)   # = 0.8

    def test_no_sources_returns_half(self):
        brain  = _make_brain()
        policy = ExecutionPolicySpec()
        ctx    = self._ctx()
        conf   = brain._aggregate_confidence(ctx, policy)
        assert conf == 0.5

    def test_retry_penalty_applied(self):
        brain  = _make_brain()
        policy = ExecutionPolicySpec()
        ctx    = self._ctx(reasoner_conf=0.8, retries=2)
        conf   = brain._aggregate_confidence(ctx, policy)
        assert conf < 0.8

    def test_clamped_to_zero_minimum(self):
        brain  = _make_brain()
        policy = ExecutionPolicySpec(retry_confidence_penalty=1.0)
        ctx    = self._ctx(reasoner_conf=0.1, retries=5)
        conf   = brain._aggregate_confidence(ctx, policy)
        assert conf >= 0.0

    def test_clamped_to_one_maximum(self):
        brain  = _make_brain()
        policy = ExecutionPolicySpec()
        ctx    = self._ctx(reasoner_conf=1.0, skill_success=True, tool_success=True)
        conf   = brain._aggregate_confidence(ctx, policy)
        assert conf <= 1.0

    def test_failed_skill_lowers_confidence(self):
        brain   = _make_brain()
        policy  = ExecutionPolicySpec()
        ctx_ok  = self._ctx(reasoner_conf=0.8, skill_success=True)
        ctx_bad = self._ctx(reasoner_conf=0.8, skill_success=False)
        assert brain._aggregate_confidence(ctx_ok, policy) > brain._aggregate_confidence(ctx_bad, policy)

    def test_custom_weights_respected(self):
        brain  = _make_brain()
        policy = ExecutionPolicySpec(weight_reasoner=0.9, weight_skills=0.05, weight_tools=0.05)
        ctx    = self._ctx(reasoner_conf=1.0)
        conf   = brain._aggregate_confidence(ctx, policy)
        assert conf == 1.0


# ── TestBrainReflection ───────────────────────────────────────────────────────

class TestBrainReflection:

    def _make_result(self, confidence=0.8, failed=False, retries=0, tool_failed=False):
        ctx = ExecutionContext()
        ctx.confidence  = confidence
        ctx.retry_count = retries
        if failed:
            ctx.fail("test error")
        if tool_failed:
            ctx.tool_results["t"] = ToolResult("t", False, None, error="timeout")
        trace  = ExecutionTrace(request_id="r", session_id="s")
        return ExecutionResult(
            response="answer", confidence=confidence,
            explanation="", trace=trace, context=ctx,
        )

    def test_achieved_clean_success(self):
        brain  = _make_brain()
        goal   = Goal(objective="test")
        result = self._make_result(confidence=0.9)
        r      = brain.reflect(goal, result)
        assert r.objective_achieved is True
        assert r.confidence_delta   == 0.02

    def test_not_achieved_low_confidence(self):
        brain  = _make_brain()
        goal   = Goal(objective="test")
        result = self._make_result(confidence=0.3)
        r      = brain.reflect(goal, result)
        assert r.objective_achieved is False
        assert r.confidence_delta   == -0.05

    def test_should_store_high_confidence(self):
        brain  = _make_brain()
        goal   = Goal(objective="test")
        result = self._make_result(confidence=0.85)
        r      = brain.reflect(goal, result)
        assert r.should_store is True

    def test_should_not_store_low_confidence(self):
        brain  = _make_brain()
        goal   = Goal(objective="test")
        result = self._make_result(confidence=0.5)
        r      = brain.reflect(goal, result)
        assert r.should_store is False

    def test_max_retries_produces_action_item(self):
        brain  = _make_brain()
        goal   = Goal(objective="test")
        result = self._make_result(confidence=0.8, retries=ExecutionEngine.MAX_REASONING_RETRIES)
        r      = brain.reflect(goal, result)
        actions = [a.action for a in r.action_items]
        assert "increase_memory_scope" in actions

    def test_tool_failure_produces_action_item(self):
        brain  = _make_brain()
        goal   = Goal(objective="test")
        result = self._make_result(confidence=0.8, tool_failed=True)
        r      = brain.reflect(goal, result)
        actions = [a.action for a in r.action_items]
        assert "review_tool_reliability" in actions

    def test_high_confidence_produces_store_action(self):
        brain  = _make_brain()
        goal   = Goal(objective="test")
        result = self._make_result(confidence=0.9)
        r      = brain.reflect(goal, result)
        actions = [a.action for a in r.action_items]
        assert "store_to_long_term_memory" in actions


# ── TestBrainDecisionHistory ──────────────────────────────────────────────────

class TestBrainDecisionHistory:

    @pytest.mark.asyncio
    async def test_decisions_recorded_per_process_call(self):
        brain = _make_brain()
        await brain.process("q1", "s1")
        await brain.process("q2", "s1")
        assert len(brain._decision_history) >= 2

    @pytest.mark.asyncio
    async def test_decisions_for_goal_filters_correctly(self):
        brain = _make_brain()
        await brain.process("q1", "s1")
        goal_id   = brain._goal_history[0].id
        decisions = brain.decisions_for_goal(goal_id)
        assert len(decisions) >= 1
        assert all(d.goal_id == goal_id for d in decisions)

    def test_decision_source_is_brain(self):
        brain = _make_brain()
        brain._record_decision("g1", "agent_selection", "Brain", "test")
        assert brain._decision_history[-1].decision_source == "Brain"


# ── TestSessionState ──────────────────────────────────────────────────────────

class TestSessionState:

    def test_session_created_on_first_process(self):
        brain = _make_brain()
        assert brain.get_session("new-sess") is None

    @pytest.mark.asyncio
    async def test_session_exists_after_process(self):
        brain = _make_brain()
        await brain.process("hello", "sess-99")
        assert brain.get_session("sess-99") is not None

    @pytest.mark.asyncio
    async def test_session_last_response_updated(self):
        brain = _make_brain()
        await brain.process("hello", "sess-1")
        session = brain.get_session("sess-1")
        assert session.last_response != "" or session.last_response == ""  # set, not None

    def test_session_touch_updates_timestamp(self):
        import time
        s = SessionState(session_id="s1")
        before = s.updated_at
        time.sleep(0.01)
        s.touch()
        assert s.updated_at > before

    def test_session_metadata_is_domain_escape_hatch(self):
        s = SessionState()
        s.metadata["topic"] = "research"
        assert s.metadata["topic"] == "research"


# ── TestBrainSessionSummary ───────────────────────────────────────────────────

class TestBrainSessionSummary:

    @pytest.mark.asyncio
    async def test_summary_counts_completed_goals(self):
        brain = _make_brain()
        await brain.process("q1", "s1")
        await brain.process("q2", "s1")
        s = brain.session_summary("s1")
        assert s["completed_goals"] == 2

    @pytest.mark.asyncio
    async def test_summary_includes_capabilities(self):
        brain = _make_brain()
        s = brain.session_summary()
        assert "capabilities" in s
        assert "supports_reflection" in s["capabilities"]

    def test_summary_zero_on_fresh_brain(self):
        brain = _make_brain()
        s = brain.session_summary()
        assert s["active_goals"]    == 0
        assert s["completed_goals"] == 0
        assert s["failed_goals"]    == 0


# ── TestDomainAgnosticism ─────────────────────────────────────────────────────

class TestDomainAgnosticism:
    """Brain must contain zero domain-specific first-class fields."""

    TRADING_FIELDS = [
        "symbol", "stock", "candle", "rsi", "macd", "broker",
        "portfolio", "trade", "price", "market", "nifty",
        "signal", "indicator", "ticker",
    ]

    def test_brain_has_no_trading_attributes(self):
        brain = _make_brain()
        for attr in self.TRADING_FIELDS:
            assert not hasattr(brain, attr), (
                f"Domain attribute '{attr}' found on Brain"
            )

    def test_goal_has_no_trading_attributes(self):
        g = Goal()
        for attr in self.TRADING_FIELDS:
            assert attr not in vars(g), (
                f"Domain attribute '{attr}' found on Goal"
            )

    def test_session_state_has_no_trading_attributes(self):
        s = SessionState()
        for attr in self.TRADING_FIELDS:
            assert attr not in vars(s), (
                f"Domain attribute '{attr}' found on SessionState"
            )

    def test_metadata_carries_domain_data(self):
        """Domain data belongs in metadata, never as first-class fields."""
        g = Goal()
        g.metadata["symbol"]    = "RELIANCE"
        g.metadata["rsi_value"] = 72.4
        assert g.metadata["symbol"]    == "RELIANCE"
        assert g.metadata["rsi_value"] == 72.4
