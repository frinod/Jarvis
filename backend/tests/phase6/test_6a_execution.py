"""
tests/phase6/test_6a_execution.py
===================================
Unit tests for ExecutionEngine (Task 6A.3).

All collaborators (planner, memory, reasoner, etc.) are mocked.
No network, no LLM calls, no file I/O.
"""
import asyncio
import pytest

from app.core.llm import LLMMessage
from app.core.llm import LLMResponse as CoreLLMResponse
from app.ai.runtime.context import ExecutionContext, RequestState
from app.ai.runtime.llm_gateway import LLMGateway, LLMRequest, LLMResponse
from app.ai.runtime.execution import (
    ExecutionEngine,
    ExecutionResult,
    ExecutionTrace,
    StageRecord,
    PipelinePlanner,
    PipelineMemoryProvider,
    PipelineSkillRunner,
    PipelineToolRunner,
    PipelineReasoner,
    PipelineVerifier,
    PipelineResponder,
    ExecutionEventEmitter,
    _NoOpEmitter,
)
from app.resilience.retry import RetryPolicy, RetryStrategy


# ── Mock collaborators ────────────────────────────────────────────────────────

class MockProvider:
    """Minimal LLMProvider mock."""
    async def generate(self, messages, **kwargs):
        return CoreLLMResponse(content="mock response", model="mock", tokens_used=10)

    async def stream(self, messages, **kwargs):
        for t in ["hello", " ", "world"]:
            yield t


def _no_retry():
    return RetryPolicy(max_attempts=1, strategy=RetryStrategy.FIXED, base_delay_s=0.0)


def _make_gateway() -> LLMGateway:
    gw = LLMGateway(retry_policy=_no_retry())
    gw.register("mock", MockProvider())
    return gw


class RecordingPlanner(PipelinePlanner):
    def __init__(self, intent="general", goal="test goal", agent="analyst"):
        self.called = False
        self._intent = intent
        self._goal   = goal
        self._agent  = agent

    async def plan(self, ctx: ExecutionContext) -> None:
        self.called = True
        ctx.intent_type    = self._intent
        ctx.active_goal    = self._goal
        ctx.selected_agent = self._agent


class FailingPlanner(PipelinePlanner):
    async def plan(self, ctx: ExecutionContext) -> None:
        raise RuntimeError("planner exploded")


class RecordingMemory(PipelineMemoryProvider):
    def __init__(self, entries=None):
        self.called  = False
        self._entries = entries or ["memory_entry_1"]

    async def load(self, ctx: ExecutionContext) -> None:
        self.called = True
        ctx.memory_context = self._entries


class FailingMemory(PipelineMemoryProvider):
    async def load(self, ctx: ExecutionContext) -> None:
        raise RuntimeError("memory exploded")


class RecordingSkillRunner(PipelineSkillRunner):
    def __init__(self):
        self.called = False

    async def run(self, ctx: ExecutionContext) -> None:
        self.called = True
        from app.ai.runtime.context import SkillResult
        ctx.skill_results["test_skill"] = SkillResult("test_skill", True, {"score": 0.9})


class RecordingToolRunner(PipelineToolRunner):
    def __init__(self):
        self.called = False

    async def run(self, ctx: ExecutionContext) -> None:
        self.called = True
        from app.ai.runtime.context import ToolResult
        ctx.tool_results["test_tool"] = ToolResult("test_tool", True, {"data": "ok"})


class RecordingReasoner(PipelineReasoner):
    def __init__(self, confidence=0.85):
        self.call_count  = 0
        self._confidence = confidence

    async def reason(self, ctx: ExecutionContext) -> None:
        self.call_count += 1
        from app.ai.runtime.context import ThoughtStep
        ctx.thought_chain.append(ThoughtStep("I should answer this", self._confidence, 0))
        ctx.confidence = self._confidence


class FailingReasoner(PipelineReasoner):
    async def reason(self, ctx: ExecutionContext) -> None:
        raise RuntimeError("reasoner exploded")


class AlwaysRetryVerifier(PipelineVerifier):
    """Always requests a retry."""
    async def verify(self, ctx: ExecutionContext) -> bool:
        ctx.critique = "not good enough"
        return True


class PassVerifier(PipelineVerifier):
    async def verify(self, ctx: ExecutionContext) -> bool:
        ctx.critique = "looks good"
        return False


class RecordingResponder(PipelineResponder):
    def __init__(self, response="final answer"):
        self.called    = False
        self._response = response

    async def respond(self, ctx: ExecutionContext) -> None:
        self.called    = True
        ctx.response    = self._response
        ctx.explanation = "because I said so"


class FailingResponder(PipelineResponder):
    async def respond(self, ctx: ExecutionContext) -> None:
        raise RuntimeError("responder exploded")


class CapturingEmitter(ExecutionEventEmitter):
    def __init__(self):
        self.events: list = []

    async def emit(self, event_name: str, payload: dict) -> None:
        self.events.append(event_name)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _engine(**kwargs) -> ExecutionEngine:
    return ExecutionEngine(gateway=_make_gateway(), **kwargs)


# ── Basic execution ───────────────────────────────────────────────────────────

class TestBasicExecution:

    @pytest.mark.asyncio
    async def test_run_returns_execution_result(self):
        engine = _engine()
        result = await engine.run("hello")
        assert isinstance(result, ExecutionResult)

    @pytest.mark.asyncio
    async def test_result_has_trace(self):
        engine = _engine()
        result = await engine.run("hello")
        assert isinstance(result.trace, ExecutionTrace)

    @pytest.mark.asyncio
    async def test_result_has_context(self):
        engine = _engine()
        result = await engine.run("hello")
        assert isinstance(result.context, ExecutionContext)

    @pytest.mark.asyncio
    async def test_session_id_propagated(self):
        engine = _engine()
        result = await engine.run("hello", session_id="sess-42")
        assert result.context.session_id == "sess-42"

    @pytest.mark.asyncio
    async def test_user_input_propagated(self):
        engine = _engine()
        result = await engine.run("what is the weather?")
        assert result.context.user_input == "what is the weather?"

    @pytest.mark.asyncio
    async def test_successful_run_trace_success_true(self):
        engine = _engine(responder=RecordingResponder())
        result = await engine.run("hello")
        assert result.trace.success is True

    @pytest.mark.asyncio
    async def test_no_collaborators_still_returns_result(self):
        """Engine with only a gateway should not crash."""
        engine = _engine()
        result = await engine.run("hello")
        assert result.response != ""


# ── Planner stage ─────────────────────────────────────────────────────────────

class TestPlannerStage:

    @pytest.mark.asyncio
    async def test_planner_called(self):
        planner = RecordingPlanner()
        engine  = _engine(planner=planner)
        await engine.run("hello")
        assert planner.called is True

    @pytest.mark.asyncio
    async def test_planner_sets_intent_and_goal(self):
        planner = RecordingPlanner(intent="trading", goal="analyse RELIANCE")
        engine  = _engine(planner=planner)
        result  = await engine.run("hello")
        assert result.context.intent_type    == "trading"
        assert result.context.active_goal    == "analyse RELIANCE"

    @pytest.mark.asyncio
    async def test_planner_sets_selected_agent(self):
        planner = RecordingPlanner(agent="trader")
        engine  = _engine(planner=planner)
        result  = await engine.run("hello")
        assert result.context.selected_agent == "trader"
        assert result.trace.agent_name       == "trader"

    @pytest.mark.asyncio
    async def test_planner_failure_marks_context_failed(self):
        engine = _engine(planner=FailingPlanner())
        result = await engine.run("hello")
        assert result.trace.success is False
        assert "Planning failed" in result.trace.error

    @pytest.mark.asyncio
    async def test_planner_failure_skips_remaining_stages(self):
        memory  = RecordingMemory()
        engine  = _engine(planner=FailingPlanner(), memory=memory)
        await engine.run("hello")
        assert memory.called is False

    @pytest.mark.asyncio
    async def test_no_planner_uses_user_input_as_goal(self):
        engine = _engine()
        result = await engine.run("my question")
        assert result.context.active_goal == "my question"
        assert result.context.intent_type == "general"


# ── Memory stage ──────────────────────────────────────────────────────────────

class TestMemoryStage:

    @pytest.mark.asyncio
    async def test_memory_called(self):
        memory = RecordingMemory()
        engine = _engine(memory=memory)
        await engine.run("hello")
        assert memory.called is True

    @pytest.mark.asyncio
    async def test_memory_populates_context(self):
        memory = RecordingMemory(entries=["fact_1", "fact_2"])
        engine = _engine(memory=memory)
        result = await engine.run("hello")
        assert result.context.memory_context == ["fact_1", "fact_2"]

    @pytest.mark.asyncio
    async def test_memory_failure_is_non_fatal(self):
        """Memory failure should not abort the pipeline."""
        responder = RecordingResponder()
        engine    = _engine(memory=FailingMemory(), responder=responder)
        result    = await engine.run("hello")
        assert result.trace.success is True
        assert responder.called is True

    @pytest.mark.asyncio
    async def test_memory_failure_recorded_in_trace(self):
        engine = _engine(memory=FailingMemory())
        result = await engine.run("hello")
        memory_stage = next(s for s in result.trace.stages if s.stage == "memory_loading")
        assert memory_stage.error is not None


# ── Skill and Tool stages ─────────────────────────────────────────────────────

class TestSkillAndToolStages:

    @pytest.mark.asyncio
    async def test_skill_runner_called(self):
        runner = RecordingSkillRunner()
        engine = _engine(skill_runner=runner)
        await engine.run("hello")
        assert runner.called is True

    @pytest.mark.asyncio
    async def test_tool_runner_called(self):
        runner = RecordingToolRunner()
        engine = _engine(tool_runner=runner)
        await engine.run("hello")
        assert runner.called is True

    @pytest.mark.asyncio
    async def test_skill_results_in_trace(self):
        engine = _engine(skill_runner=RecordingSkillRunner())
        result = await engine.run("hello")
        assert "test_skill" in result.trace.skills_used

    @pytest.mark.asyncio
    async def test_tool_results_in_trace(self):
        engine = _engine(tool_runner=RecordingToolRunner())
        result = await engine.run("hello")
        assert "test_tool" in result.trace.tools_used

    @pytest.mark.asyncio
    async def test_skill_failure_is_non_fatal(self):
        class FailSkill(PipelineSkillRunner):
            async def run(self, ctx): raise RuntimeError("skill boom")
        responder = RecordingResponder()
        engine    = _engine(skill_runner=FailSkill(), responder=responder)
        result    = await engine.run("hello")
        assert result.trace.success is True

    @pytest.mark.asyncio
    async def test_tool_failure_is_non_fatal(self):
        class FailTool(PipelineToolRunner):
            async def run(self, ctx): raise RuntimeError("tool boom")
        responder = RecordingResponder()
        engine    = _engine(tool_runner=FailTool(), responder=responder)
        result    = await engine.run("hello")
        assert result.trace.success is True


# ── Reasoning stage ───────────────────────────────────────────────────────────

class TestReasoningStage:

    @pytest.mark.asyncio
    async def test_reasoner_called(self):
        reasoner = RecordingReasoner()
        engine   = _engine(reasoner=reasoner)
        await engine.run("hello")
        assert reasoner.call_count >= 1

    @pytest.mark.asyncio
    async def test_confidence_set_by_reasoner(self):
        engine = _engine(reasoner=RecordingReasoner(confidence=0.92))
        result = await engine.run("hello")
        assert result.confidence == 0.92

    @pytest.mark.asyncio
    async def test_thought_chain_populated(self):
        engine = _engine(reasoner=RecordingReasoner())
        result = await engine.run("hello")
        assert len(result.context.thought_chain) >= 1

    @pytest.mark.asyncio
    async def test_reasoner_failure_marks_failed(self):
        engine = _engine(reasoner=FailingReasoner())
        result = await engine.run("hello")
        assert result.trace.success is False
        assert "Reasoning failed" in result.trace.error

    @pytest.mark.asyncio
    async def test_verifier_pass_no_retry(self):
        reasoner = RecordingReasoner()
        engine   = _engine(reasoner=reasoner, verifier=PassVerifier())
        await engine.run("hello")
        assert reasoner.call_count == 1

    @pytest.mark.asyncio
    async def test_verifier_retry_capped_at_max(self):
        reasoner = RecordingReasoner()
        engine   = _engine(reasoner=reasoner, verifier=AlwaysRetryVerifier())
        result   = await engine.run("hello")
        # MAX_REASONING_RETRIES=2 means 3 total calls (1 initial + 2 retries)
        assert reasoner.call_count == ExecutionEngine.MAX_REASONING_RETRIES + 1

    @pytest.mark.asyncio
    async def test_retry_count_recorded_in_context(self):
        engine = _engine(
            reasoner=RecordingReasoner(),
            verifier=AlwaysRetryVerifier(),
        )
        result = await engine.run("hello")
        assert result.context.retry_count == ExecutionEngine.MAX_REASONING_RETRIES

    @pytest.mark.asyncio
    async def test_critique_set_by_verifier(self):
        engine = _engine(reasoner=RecordingReasoner(), verifier=PassVerifier())
        result = await engine.run("hello")
        assert result.context.critique == "looks good"


# ── Response stage ────────────────────────────────────────────────────────────

class TestResponseStage:

    @pytest.mark.asyncio
    async def test_responder_called(self):
        responder = RecordingResponder("the answer")
        engine    = _engine(responder=responder)
        await engine.run("hello")
        assert responder.called is True

    @pytest.mark.asyncio
    async def test_response_from_responder(self):
        engine = _engine(responder=RecordingResponder("the answer"))
        result = await engine.run("hello")
        assert result.response == "the answer"

    @pytest.mark.asyncio
    async def test_explanation_from_responder(self):
        engine = _engine(responder=RecordingResponder())
        result = await engine.run("hello")
        assert result.explanation == "because I said so"

    @pytest.mark.asyncio
    async def test_responder_failure_marks_failed(self):
        engine = _engine(responder=FailingResponder())
        result = await engine.run("hello")
        assert result.trace.success is False

    @pytest.mark.asyncio
    async def test_no_responder_uses_fallback(self):
        engine = _engine(planner=RecordingPlanner(goal="my goal"))
        result = await engine.run("hello")
        assert result.response == "my goal"


# ── Event emission ────────────────────────────────────────────────────────────

class TestEventEmission:

    @pytest.mark.asyncio
    async def test_request_started_emitted(self):
        emitter = CapturingEmitter()
        engine  = _engine(emitter=emitter)
        await engine.run("hello")
        assert "RequestStarted" in emitter.events

    @pytest.mark.asyncio
    async def test_request_finished_emitted(self):
        emitter = CapturingEmitter()
        engine  = _engine(emitter=emitter)
        await engine.run("hello")
        assert "RequestFinished" in emitter.events

    @pytest.mark.asyncio
    async def test_planning_events_emitted(self):
        emitter = CapturingEmitter()
        engine  = _engine(emitter=emitter, planner=RecordingPlanner())
        await engine.run("hello")
        assert "PlanningStarted"    in emitter.events
        assert "PlanningCompleted"  in emitter.events

    @pytest.mark.asyncio
    async def test_reasoning_events_emitted(self):
        emitter = CapturingEmitter()
        engine  = _engine(emitter=emitter, reasoner=RecordingReasoner())
        await engine.run("hello")
        assert "ReasoningStarted"   in emitter.events
        assert "ReasoningCompleted" in emitter.events

    @pytest.mark.asyncio
    async def test_verification_events_emitted_when_verifier_present(self):
        emitter = CapturingEmitter()
        engine  = _engine(
            emitter=emitter,
            reasoner=RecordingReasoner(),
            verifier=PassVerifier(),
        )
        await engine.run("hello")
        assert "VerificationStarted"   in emitter.events
        assert "VerificationCompleted" in emitter.events

    @pytest.mark.asyncio
    async def test_emitter_failure_does_not_crash_pipeline(self):
        class BrokenEmitter(ExecutionEventEmitter):
            async def emit(self, name, payload):
                raise RuntimeError("emitter broken")
        engine = _engine(emitter=BrokenEmitter())
        result = await engine.run("hello")
        # Pipeline should complete despite broken emitter
        assert result is not None


# ── Execution trace ───────────────────────────────────────────────────────────

class TestExecutionTrace:

    @pytest.mark.asyncio
    async def test_trace_has_all_stages(self):
        engine = _engine(
            planner=RecordingPlanner(),
            memory=RecordingMemory(),
            skill_runner=RecordingSkillRunner(),
            tool_runner=RecordingToolRunner(),
            reasoner=RecordingReasoner(),
            responder=RecordingResponder(),
        )
        result = await engine.run("hello")
        stage_names = [s.stage for s in result.trace.stages]
        assert "planning"          in stage_names
        assert "memory_loading"    in stage_names
        assert "skill_selection"   in stage_names
        assert "tool_execution"    in stage_names
        assert "reasoning"         in stage_names
        assert "response_generation" in stage_names

    @pytest.mark.asyncio
    async def test_trace_total_ms_positive(self):
        engine = _engine()
        result = await engine.run("hello")
        assert result.trace.total_ms >= 0.0

    @pytest.mark.asyncio
    async def test_stage_durations_non_negative(self):
        engine = _engine(planner=RecordingPlanner())
        result = await engine.run("hello")
        for stage in result.trace.stages:
            assert stage.duration_ms >= 0.0

    @pytest.mark.asyncio
    async def test_trace_request_id_matches_context(self):
        engine = _engine()
        result = await engine.run("hello")
        assert result.trace.request_id == result.context.request_id

    @pytest.mark.asyncio
    async def test_timing_report_contains_stage_names(self):
        engine = _engine(planner=RecordingPlanner())
        result = await engine.run("hello")
        report = result.trace.timing_report()
        assert "planning" in report
        assert "Total"    in report

    @pytest.mark.asyncio
    async def test_retry_count_in_trace(self):
        engine = _engine(
            reasoner=RecordingReasoner(),
            verifier=AlwaysRetryVerifier(),
        )
        result = await engine.run("hello")
        assert result.trace.retry_count == ExecutionEngine.MAX_REASONING_RETRIES


# ── Streaming ─────────────────────────────────────────────────────────────────

class TestStreaming:

    @pytest.mark.asyncio
    async def test_stream_yields_tokens(self):
        engine = _engine(planner=RecordingPlanner())
        tokens = []
        async for token in engine.stream("hello"):
            tokens.append(token)
        assert len(tokens) > 0

    @pytest.mark.asyncio
    async def test_stream_yields_error_on_pipeline_failure(self):
        engine = _engine(planner=FailingPlanner())
        tokens = []
        async for token in engine.stream("hello"):
            tokens.append(token)
        assert len(tokens) == 1
        assert "Planning failed" in tokens[0] or "failed" in tokens[0].lower()


# ── Domain agnosticism ────────────────────────────────────────────────────────

class TestDomainAgnosticism:

    def test_engine_has_no_trading_fields(self):
        engine = _engine()
        trading = ["symbol", "stock", "candle", "broker", "portfolio",
                   "market", "nifty", "rsi", "macd"]
        for attr in trading:
            assert not hasattr(engine, attr), (
                f"Domain attribute '{attr}' found on ExecutionEngine"
            )

    def test_trace_has_no_trading_fields(self):
        trace = ExecutionTrace(request_id="r", session_id="s")
        trading = ["symbol", "stock", "candle", "broker", "portfolio"]
        for attr in trading:
            assert not hasattr(trace, attr), (
                f"Domain attribute '{attr}' found on ExecutionTrace"
            )

    @pytest.mark.asyncio
    async def test_metadata_carries_domain_context(self):
        engine = _engine()
        result = await engine.run("hello", metadata={"domain": "trading"})
        assert result.context.metadata["domain"] == "trading"
