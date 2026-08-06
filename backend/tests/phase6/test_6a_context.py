"""
tests/phase6/test_6a_context.py
================================
Unit tests for ExecutionContext (Task 6A.1).

All tests are pure -- no network, no I/O, no LLM calls.
"""
import time
import pytest

from app.ai.runtime.context import (
    ExecutionContext,
    RequestState,
    ConversationTurn,
    SkillResult,
    ToolResult,
    ThoughtStep,
)


# ── Construction ──────────────────────────────────────────────────────────────

class TestExecutionContextConstruction:

    def test_default_state_is_created(self):
        ctx = ExecutionContext()
        assert ctx.state == RequestState.CREATED

    def test_request_id_auto_generated(self):
        ctx = ExecutionContext()
        assert len(ctx.request_id) == 36  # UUID4 format

    def test_two_contexts_have_different_request_ids(self):
        a = ExecutionContext()
        b = ExecutionContext()
        assert a.request_id != b.request_id

    def test_fields_default_to_empty(self):
        ctx = ExecutionContext()
        assert ctx.session_id == ""
        assert ctx.user_input == ""
        assert ctx.active_goal == ""
        assert ctx.intent_type == ""
        assert ctx.selected_agent == ""
        assert ctx.response == ""
        assert ctx.explanation == ""
        assert ctx.critique == ""
        assert ctx.error is None
        assert ctx.confidence == 0.0
        assert ctx.retry_count == 0

    def test_collections_default_to_empty(self):
        ctx = ExecutionContext()
        assert ctx.history == []
        assert ctx.memory_context == []
        assert ctx.skill_results == {}
        assert ctx.tool_results == {}
        assert ctx.thought_chain == []
        assert ctx.timings == {}
        assert ctx.metadata == {}

    def test_explicit_fields_set_correctly(self):
        ctx = ExecutionContext(
            session_id="sess-1",
            user_input="hello",
            active_goal="greet user",
        )
        assert ctx.session_id == "sess-1"
        assert ctx.user_input == "hello"
        assert ctx.active_goal == "greet user"


# ── State Machine ─────────────────────────────────────────────────────────────

class TestStateMachine:

    def test_transition_changes_state(self):
        ctx = ExecutionContext()
        ctx.transition(RequestState.PLANNING)
        assert ctx.state == RequestState.PLANNING

    def test_transition_records_timing_for_previous_state(self):
        ctx = ExecutionContext()
        ctx.transition(RequestState.PLANNING)
        assert RequestState.CREATED.value in ctx.timings
        assert ctx.timings[RequestState.CREATED.value] >= 0.0

    def test_multiple_transitions_record_all_timings(self):
        ctx = ExecutionContext()
        ctx.transition(RequestState.PLANNING)
        ctx.transition(RequestState.MEMORY_LOADING)
        ctx.transition(RequestState.REASONING)
        assert RequestState.CREATED.value in ctx.timings
        assert RequestState.PLANNING.value in ctx.timings
        assert RequestState.MEMORY_LOADING.value in ctx.timings

    def test_fail_sets_failed_state(self):
        ctx = ExecutionContext()
        ctx.fail("something went wrong")
        assert ctx.state == RequestState.FAILED
        assert ctx.error == "something went wrong"

    def test_fail_records_timing(self):
        ctx = ExecutionContext()
        ctx.fail("error")
        assert RequestState.CREATED.value in ctx.timings

    def test_is_failed_true_after_fail(self):
        ctx = ExecutionContext()
        ctx.fail("err")
        assert ctx.is_failed() is True

    def test_is_failed_false_on_fresh_context(self):
        ctx = ExecutionContext()
        assert ctx.is_failed() is False

    def test_is_complete_true_when_completed(self):
        ctx = ExecutionContext()
        ctx.transition(RequestState.COMPLETED)
        assert ctx.is_complete() is True

    def test_is_complete_true_when_failed(self):
        ctx = ExecutionContext()
        ctx.fail("err")
        assert ctx.is_complete() is True

    def test_is_complete_false_mid_pipeline(self):
        ctx = ExecutionContext()
        ctx.transition(RequestState.REASONING)
        assert ctx.is_complete() is False

    def test_full_pipeline_transition_sequence(self):
        ctx = ExecutionContext()
        states = [
            RequestState.PLANNING,
            RequestState.MEMORY_LOADING,
            RequestState.SKILL_SELECTION,
            RequestState.TOOL_EXECUTION,
            RequestState.REASONING,
            RequestState.VERIFICATION,
            RequestState.RESPONSE_GENERATION,
            RequestState.COMPLETED,
        ]
        for s in states:
            ctx.transition(s)
        assert ctx.state == RequestState.COMPLETED
        assert len(ctx.timings) == len(states)  # one timing per completed stage


# ── Timings ───────────────────────────────────────────────────────────────────

class TestTimings:

    def test_total_elapsed_ms_sums_timings(self):
        ctx = ExecutionContext()
        ctx.timings = {"created": 10.0, "planning": 20.0, "reasoning": 30.0}
        assert ctx.total_elapsed_ms() == 60.0

    def test_total_elapsed_ms_zero_on_fresh_context(self):
        ctx = ExecutionContext()
        assert ctx.total_elapsed_ms() == 0.0

    def test_timing_values_are_non_negative(self):
        ctx = ExecutionContext()
        time.sleep(0.001)
        ctx.transition(RequestState.PLANNING)
        assert ctx.timings[RequestState.CREATED.value] >= 0.0


# ── Conversation History ──────────────────────────────────────────────────────

class TestConversationHistory:

    def test_add_history_appends_turn(self):
        ctx = ExecutionContext()
        ctx.add_history("user", "hello")
        assert len(ctx.history) == 1
        assert ctx.history[0].role == "user"
        assert ctx.history[0].content == "hello"

    def test_add_history_multiple_turns(self):
        ctx = ExecutionContext()
        ctx.add_history("user", "hello")
        ctx.add_history("assistant", "hi there")
        assert len(ctx.history) == 2

    def test_recent_history_returns_last_n(self):
        ctx = ExecutionContext()
        for i in range(15):
            ctx.add_history("user", f"msg {i}")
        recent = ctx.recent_history(5)
        assert len(recent) == 5
        assert recent[-1].content == "msg 14"

    def test_recent_history_returns_all_if_fewer_than_n(self):
        ctx = ExecutionContext()
        ctx.add_history("user", "only one")
        assert len(ctx.recent_history(10)) == 1

    def test_conversation_turn_has_timestamp(self):
        turn = ConversationTurn(role="user", content="test")
        assert turn.timestamp > 0


# ── Skill and Tool Results ────────────────────────────────────────────────────

class TestSkillAndToolResults:

    def test_skill_result_stored_by_name(self):
        ctx = ExecutionContext()
        ctx.skill_results["my_skill"] = SkillResult(
            skill_name="my_skill", success=True, output={"score": 0.9}
        )
        assert ctx.skill_results["my_skill"].success is True
        assert ctx.skill_results["my_skill"].output["score"] == 0.9

    def test_tool_result_stored_by_name(self):
        ctx = ExecutionContext()
        ctx.tool_results["web_search"] = ToolResult(
            tool_name="web_search", success=True, output=["result1"]
        )
        assert ctx.tool_results["web_search"].success is True

    def test_failed_skill_result(self):
        result = SkillResult(skill_name="bad_skill", success=False, output=None, error="timeout")
        assert result.success is False
        assert result.error == "timeout"

    def test_failed_tool_result(self):
        result = ToolResult(tool_name="bad_tool", success=False, output=None, error="404")
        assert result.success is False
        assert result.error == "404"


# ── Thought Chain ─────────────────────────────────────────────────────────────

class TestThoughtChain:

    def test_thought_step_fields(self):
        step = ThoughtStep(content="I should check memory first", confidence=0.8, step_index=0)
        assert step.content == "I should check memory first"
        assert step.confidence == 0.8
        assert step.step_index == 0

    def test_thought_chain_appended_to_context(self):
        ctx = ExecutionContext()
        ctx.thought_chain.append(ThoughtStep("step 1", 0.7, 0))
        ctx.thought_chain.append(ThoughtStep("step 2", 0.9, 1))
        assert len(ctx.thought_chain) == 2
        assert ctx.thought_chain[1].confidence == 0.9


# ── Summary ───────────────────────────────────────────────────────────────────

class TestSummary:

    def test_summary_contains_required_keys(self):
        ctx = ExecutionContext(session_id="s1", user_input="test")
        s = ctx.summary()
        for key in ("request_id", "session_id", "state", "selected_agent",
                    "intent_type", "confidence", "retry_count", "total_ms",
                    "timings", "error"):
            assert key in s

    def test_summary_reflects_current_state(self):
        ctx = ExecutionContext()
        ctx.transition(RequestState.REASONING)
        ctx.confidence = 0.75
        ctx.selected_agent = "analyst"
        s = ctx.summary()
        assert s["state"] == "reasoning"
        assert s["confidence"] == 0.75
        assert s["selected_agent"] == "analyst"

    def test_summary_error_none_by_default(self):
        ctx = ExecutionContext()
        assert ctx.summary()["error"] is None

    def test_summary_error_set_after_fail(self):
        ctx = ExecutionContext()
        ctx.fail("boom")
        assert ctx.summary()["error"] == "boom"


# ── Domain Agnosticism ────────────────────────────────────────────────────────

class TestDomainAgnosticism:
    """Verify ExecutionContext contains no domain-specific fields."""

    def test_no_trading_fields(self):
        ctx = ExecutionContext()
        trading_fields = [
            "symbol", "stock", "candle", "rsi", "macd", "broker",
            "portfolio", "trade", "price", "market", "nifty",
        ]
        ctx_fields = vars(ctx).keys()
        for field_name in trading_fields:
            assert field_name not in ctx_fields, (
                f"Domain field '{field_name}' found in ExecutionContext"
            )

    def test_metadata_can_carry_domain_data(self):
        """Domain data belongs in metadata, not as first-class fields."""
        ctx = ExecutionContext()
        ctx.metadata["symbol"] = "RELIANCE"
        ctx.metadata["signal"] = "BUY"
        assert ctx.metadata["symbol"] == "RELIANCE"
