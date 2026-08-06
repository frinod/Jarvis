"""
tests/phase6/test_6c_reasoning.py
===================================
Unit tests for Phase 6C -- Reasoning Engine.

Covers:
  - ChainOfThought (6C.1)
  - PipelineReasonerAdapter (6C.1)
  - Reflection + VerificationResult (6C.2)
  - PipelineVerifierAdapter (6C.2)
  - ReasoningPlanner + ReasoningPlan (6C.3)
  - PipelinePlannerAdapter (6C.3)
  - PromptTemplate + TemplateRegistry (6C.4)
  - SystemPromptBuilder + PipelineResponderAdapter (6C.5)
  - TestDomainAgnosticism (mandatory)

All tests are pure -- no network, no I/O, no real LLM calls.
"""
import pytest

from app.ai.reasoning.chain import ChainOfThought, ChainConfig, PipelineReasonerAdapter
from app.ai.reasoning.reflection import Reflection, ReflectionConfig, VerificationResult, PipelineVerifierAdapter
from app.ai.reasoning.planner import ReasoningPlanner, ReasoningPlan, ReasoningStep, PipelinePlannerAdapter
from app.ai.prompts.templates import PromptTemplate, TemplateRegistry
from app.ai.prompts.system import SystemPromptBuilder, BuilderConfig, PipelineResponderAdapter
from app.ai.runtime.context import ExecutionContext, ThoughtStep, SkillResult, ToolResult
from app.core.llm import LLMMessage


# ── Helpers ───────────────────────────────────────────────────────────────────

def _ctx(user_input: str = "hello", session_id: str = "s1") -> ExecutionContext:
    ctx = ExecutionContext(user_input=user_input, session_id=session_id)
    ctx.active_goal = user_input
    return ctx


def _ctx_with_evidence(
    user_input: str = "analyse this",
    mem_count: int = 3,
    skill_ok: int = 2,
    skill_bad: int = 0,
    tool_ok: int = 1,
    tool_bad: int = 0,
) -> ExecutionContext:
    ctx = _ctx(user_input)
    from app.ai.memory.short_term import MemoryEntry
    ctx.memory_context = [MemoryEntry(content=f"mem {i}") for i in range(mem_count)]
    for i in range(skill_ok):
        ctx.skill_results[f"skill_ok_{i}"] = SkillResult(f"skill_ok_{i}", True, "result")
    for i in range(skill_bad):
        ctx.skill_results[f"skill_bad_{i}"] = SkillResult(f"skill_bad_{i}", False, None, error="err")
    for i in range(tool_ok):
        ctx.tool_results[f"tool_ok_{i}"] = ToolResult(f"tool_ok_{i}", True, "result")
    for i in range(tool_bad):
        ctx.tool_results[f"tool_bad_{i}"] = ToolResult(f"tool_bad_{i}", False, None, error="err")
    return ctx


def _make_gateway():
    from app.ai.runtime.llm_gateway import LLMGateway
    from app.resilience.retry import RetryPolicy, RetryStrategy

    class MockProvider:
        async def generate(self, messages, **kwargs):
            from app.core.llm import LLMResponse as CoreResp
            return CoreResp(content="mock response", model="mock", tokens_used=10)
        async def stream(self, messages, **kwargs):
            yield "token"

    policy = RetryPolicy(max_attempts=1, strategy=RetryStrategy.FIXED, base_delay_s=0.0)
    gw = LLMGateway(retry_policy=policy)
    gw.register("mock", MockProvider())
    return gw


# ── TestChainOfThought ────────────────────────────────────────────────────────

class TestChainOfThought:

    def test_think_returns_list_of_thought_steps(self):
        cot   = ChainOfThought()
        ctx   = _ctx("what is the weather?")
        chain = cot.think(ctx)
        assert isinstance(chain, list)
        assert all(isinstance(s, ThoughtStep) for s in chain)

    def test_think_produces_at_least_two_steps(self):
        cot   = ChainOfThought()
        chain = cot.think(_ctx("hello"))
        assert len(chain) >= 2

    def test_think_populates_ctx_thought_chain(self):
        cot = ChainOfThought()
        ctx = _ctx("hello")
        cot.think(ctx)
        assert len(ctx.thought_chain) >= 2

    def test_think_sets_ctx_confidence(self):
        cot = ChainOfThought()
        ctx = _ctx("hello")
        cot.think(ctx)
        assert 0.0 <= ctx.confidence <= 1.0

    def test_steps_have_increasing_indices(self):
        cot   = ChainOfThought()
        chain = cot.think(_ctx("hello"))
        for i, step in enumerate(chain):
            assert step.step_index == i

    def test_memory_boosts_confidence(self):
        cot      = ChainOfThought()
        ctx_no   = _ctx("hello")
        ctx_mem  = _ctx_with_evidence(mem_count=5)
        cot.think(ctx_no)
        cot.think(ctx_mem)
        assert ctx_mem.confidence >= ctx_no.confidence

    def test_successful_tools_boost_confidence(self):
        cot       = ChainOfThought()
        ctx_plain = _ctx("hello")
        ctx_tools = _ctx_with_evidence(tool_ok=3)
        cot.think(ctx_plain)
        cot.think(ctx_tools)
        assert ctx_tools.confidence >= ctx_plain.confidence

    def test_failed_tools_lower_confidence(self):
        cot      = ChainOfThought()
        ctx_ok   = _ctx_with_evidence(tool_ok=2, tool_bad=0)
        ctx_bad  = _ctx_with_evidence(tool_ok=2, tool_bad=3)
        cot.think(ctx_ok)
        cot.think(ctx_bad)
        assert ctx_ok.confidence >= ctx_bad.confidence

    def test_confidence_clamped_to_one(self):
        cot = ChainOfThought()
        ctx = _ctx_with_evidence(mem_count=50, skill_ok=20, tool_ok=20)
        cot.think(ctx)
        assert ctx.confidence <= 1.0

    def test_confidence_clamped_to_zero(self):
        cot = ChainOfThought(ChainConfig(base_confidence=0.0, failure_penalty=1.0))
        ctx = _ctx_with_evidence(skill_bad=10, tool_bad=10)
        cot.think(ctx)
        assert ctx.confidence >= 0.0

    def test_final_confidence_helper(self):
        cot   = ChainOfThought()
        chain = cot.think(_ctx("hello"))
        assert cot.final_confidence(chain) == chain[-1].confidence

    def test_final_confidence_empty_chain(self):
        cot = ChainOfThought()
        assert cot.final_confidence([]) == 0.5

    def test_custom_config_respected(self):
        cfg = ChainConfig(base_confidence=0.9)
        cot = ChainOfThought(cfg)
        ctx = _ctx("hello")
        cot.think(ctx)
        assert ctx.confidence >= 0.8   # high base should yield high confidence


# ── TestPipelineReasonerAdapter ───────────────────────────────────────────────

class TestPipelineReasonerAdapter:

    @pytest.mark.asyncio
    async def test_reason_populates_thought_chain(self):
        adapter = PipelineReasonerAdapter()
        ctx     = _ctx("hello")
        await adapter.reason(ctx)
        assert len(ctx.thought_chain) >= 2

    @pytest.mark.asyncio
    async def test_reason_sets_confidence(self):
        adapter = PipelineReasonerAdapter()
        ctx     = _ctx("hello")
        await adapter.reason(ctx)
        assert 0.0 <= ctx.confidence <= 1.0

    @pytest.mark.asyncio
    async def test_reason_with_custom_cot(self):
        cot     = ChainOfThought(ChainConfig(base_confidence=0.8))
        adapter = PipelineReasonerAdapter(cot)
        ctx     = _ctx("hello")
        await adapter.reason(ctx)
        assert ctx.confidence >= 0.7


# ── TestReflection ────────────────────────────────────────────────────────────

class TestReflection:

    def _chain(self, confidences):
        return [
            ThoughtStep(content=f"step {i}", confidence=c, step_index=i)
            for i, c in enumerate(confidences)
        ]

    def test_evaluate_returns_verification_result(self):
        ref = Reflection()
        ctx = _ctx("hello")
        ctx.thought_chain = self._chain([0.6, 0.7, 0.75])
        result = ref.evaluate(ctx)
        assert isinstance(result, VerificationResult)

    def test_high_confidence_chain_passes(self):
        ref = Reflection()
        ctx = _ctx("hello")
        ctx.thought_chain = self._chain([0.7, 0.75, 0.8])
        result = ref.evaluate(ctx)
        assert result.passed is True
        assert result.should_retry is False

    def test_low_confidence_triggers_retry(self):
        ref = Reflection()
        ctx = _ctx("hello")
        ctx.thought_chain = self._chain([0.3, 0.25, 0.2])
        result = ref.evaluate(ctx)
        assert result.should_retry is True

    def test_empty_chain_fails(self):
        ref = Reflection()
        ctx = _ctx("hello")
        ctx.thought_chain = []
        result = ref.evaluate(ctx)
        assert result.passed is False

    def test_large_confidence_drop_adds_issue(self):
        ref = Reflection()
        ctx = _ctx("hello")
        ctx.thought_chain = self._chain([0.8, 0.4, 0.75])   # big drop at step 1
        result = ref.evaluate(ctx)
        assert len(result.issues) >= 1

    def test_sets_ctx_critique(self):
        ref = Reflection()
        ctx = _ctx("hello")
        ctx.thought_chain = self._chain([0.7, 0.75, 0.8])
        ref.evaluate(ctx)
        assert ctx.critique != ""

    def test_critique_contains_confidence(self):
        ref = Reflection()
        ctx = _ctx("hello")
        ctx.thought_chain = self._chain([0.7, 0.75, 0.8])
        result = ref.evaluate(ctx)
        assert "%" in result.critique or "confidence" in result.critique.lower()

    def test_failed_tools_with_low_confidence_adds_issue(self):
        ref = Reflection()
        ctx = _ctx_with_evidence(tool_bad=2)
        ctx.thought_chain = self._chain([0.5, 0.5, 0.5])
        result = ref.evaluate(ctx)
        assert len(result.issues) >= 1

    def test_score_helper(self):
        ref   = Reflection()
        chain = self._chain([0.6, 0.7, 0.8])
        assert ref.score(chain) == 0.8

    def test_score_empty_chain(self):
        ref = Reflection()
        assert ref.score([]) == 0.0

    def test_custom_config(self):
        cfg = ReflectionConfig(min_confidence=0.9)
        ref = Reflection(cfg)
        ctx = _ctx("hello")
        ctx.thought_chain = self._chain([0.7, 0.75, 0.8])
        result = ref.evaluate(ctx)
        # 0.8 < 0.9 threshold, should fail
        assert result.passed is False


# ── TestPipelineVerifierAdapter ───────────────────────────────────────────────

class TestPipelineVerifierAdapter:

    @pytest.mark.asyncio
    async def test_verify_returns_bool(self):
        adapter = PipelineVerifierAdapter()
        ctx     = _ctx("hello")
        ctx.thought_chain = [ThoughtStep("step", 0.8, 0)]
        result = await adapter.verify(ctx)
        assert isinstance(result, bool)

    @pytest.mark.asyncio
    async def test_verify_false_for_good_chain(self):
        adapter = PipelineVerifierAdapter()
        ctx     = _ctx("hello")
        ctx.thought_chain = [
            ThoughtStep("s0", 0.7, 0),
            ThoughtStep("s1", 0.75, 1),
            ThoughtStep("s2", 0.8, 2),
        ]
        result = await adapter.verify(ctx)
        assert result is False

    @pytest.mark.asyncio
    async def test_verify_true_for_low_confidence(self):
        adapter = PipelineVerifierAdapter()
        ctx     = _ctx("hello")
        ctx.thought_chain = [
            ThoughtStep("s0", 0.2, 0),
            ThoughtStep("s1", 0.2, 1),
        ]
        result = await adapter.verify(ctx)
        assert result is True


# ── TestReasoningPlanner ──────────────────────────────────────────────────────

class TestReasoningPlanner:

    def test_decompose_returns_plan(self):
        planner = ReasoningPlanner()
        plan    = planner.decompose("What is the weather?")
        assert isinstance(plan, ReasoningPlan)

    def test_question_intent_detected(self):
        planner = ReasoningPlanner()
        for q in ["What is X?", "How does Y work?", "Why is Z?", "Is this correct?"]:
            plan = planner.decompose(q)
            assert plan.intent_type == "question", f"Expected question for: {q}"

    def test_task_intent_detected(self):
        planner = ReasoningPlanner()
        for q in ["Create a report", "Build a plan", "Write a summary"]:
            plan = planner.decompose(q)
            assert plan.intent_type == "task", f"Expected task for: {q}"

    def test_analysis_intent_detected(self):
        planner = ReasoningPlanner()
        for q in ["Analyse the data", "Compare these options", "Evaluate the risk"]:
            plan = planner.decompose(q)
            assert plan.intent_type == "analysis", f"Expected analysis for: {q}"

    def test_general_intent_fallback(self):
        planner = ReasoningPlanner()
        plan    = planner.decompose("Hello there")
        assert plan.intent_type == "general"

    def test_plan_has_steps(self):
        planner = ReasoningPlanner()
        plan    = planner.decompose("What is X?")
        assert plan.step_count() >= 1

    def test_steps_have_descriptions(self):
        planner = ReasoningPlanner()
        plan    = planner.decompose("What is X?")
        assert all(s.description for s in plan.steps)

    def test_steps_have_sequential_indices(self):
        planner = ReasoningPlanner()
        plan    = planner.decompose("What is X?")
        for i, step in enumerate(plan.steps):
            assert step.index == i

    def test_estimated_confidence_in_range(self):
        planner = ReasoningPlanner()
        for goal in ["What?", "Create X", "Analyse Y", "Hello"]:
            plan = planner.decompose(goal)
            assert 0.0 <= plan.estimated_confidence <= 1.0

    def test_context_intent_overrides_classification(self):
        planner = ReasoningPlanner()
        ctx     = _ctx("Hello there")
        ctx.metadata["intent_type"] = "analysis"
        plan    = planner.decompose("Hello there", context=ctx)
        assert plan.intent_type == "analysis"

    def test_descriptions_returns_list(self):
        planner = ReasoningPlanner()
        plan    = planner.decompose("What is X?")
        descs   = plan.descriptions()
        assert isinstance(descs, list)
        assert len(descs) == plan.step_count()


# ── TestPipelinePlannerAdapter ────────────────────────────────────────────────

class TestPipelinePlannerAdapter:

    @pytest.mark.asyncio
    async def test_plan_sets_active_goal(self):
        adapter = PipelinePlannerAdapter()
        ctx     = _ctx("What is the weather?")
        await adapter.plan(ctx)
        assert ctx.active_goal == "What is the weather?"

    @pytest.mark.asyncio
    async def test_plan_sets_intent_type(self):
        adapter = PipelinePlannerAdapter()
        ctx     = _ctx("What is the weather?")
        await adapter.plan(ctx)
        assert ctx.intent_type == "question"

    @pytest.mark.asyncio
    async def test_plan_stores_metadata(self):
        adapter = PipelinePlannerAdapter()
        ctx     = _ctx("What is X?")
        await adapter.plan(ctx)
        assert "_reasoning_plan" in ctx.metadata
        assert "steps" in ctx.metadata["_reasoning_plan"]


# ── TestPromptTemplate ────────────────────────────────────────────────────────

class TestPromptTemplate:

    def test_render_substitutes_variables(self):
        t = PromptTemplate(
            name="test",
            template="Hello {name}, your goal is {goal}.",
            variables=["name", "goal"],
        )
        result = t.render(name="Alice", goal="research")
        assert result == "Hello Alice, your goal is research."

    def test_render_raises_on_missing_variable(self):
        t = PromptTemplate(
            name="test",
            template="Hello {name}.",
            variables=["name"],
        )
        with pytest.raises(KeyError):
            t.render()

    def test_render_safe_leaves_missing_as_placeholder(self):
        t = PromptTemplate(
            name="test",
            template="Hello {name}.",
            variables=["name"],
        )
        result = t.render_safe()
        assert "{name}" in result

    def test_render_ignores_extra_kwargs(self):
        t = PromptTemplate(
            name="test",
            template="Hello {name}.",
            variables=["name"],
        )
        result = t.render(name="Alice", extra="ignored")
        assert result == "Hello Alice."

    def test_required_variables(self):
        t = PromptTemplate(name="t", template="", variables=["a", "b"])
        assert t.required_variables() == ["a", "b"]


# ── TestTemplateRegistry ──────────────────────────────────────────────────────

class TestTemplateRegistry:

    def test_register_and_get(self):
        registry = TemplateRegistry()
        t = PromptTemplate(name="my_template", template="Hello {name}.", variables=["name"])
        registry.register(t)
        assert registry.get("my_template") is t

    def test_get_missing_raises(self):
        registry = TemplateRegistry()
        with pytest.raises(KeyError):
            registry.get("nonexistent")

    def test_has_returns_bool(self):
        registry = TemplateRegistry()
        registry.register(PromptTemplate(name="t", template="x"))
        assert registry.has("t") is True
        assert registry.has("missing") is False

    def test_names_returns_list(self):
        registry = TemplateRegistry()
        registry.register(PromptTemplate(name="a", template=""))
        registry.register(PromptTemplate(name="b", template=""))
        assert set(registry.names()) == {"a", "b"}

    def test_len(self):
        registry = TemplateRegistry()
        registry.register(PromptTemplate(name="x", template=""))
        assert len(registry) == 1

    def test_default_registry_has_builtin_templates(self):
        registry = TemplateRegistry.default()
        assert registry.has("system_base")
        assert registry.has("system_with_memory")
        assert registry.has("reasoning_chain")
        assert registry.has("retry_with_critique")

    def test_system_base_renders(self):
        registry = TemplateRegistry.default()
        t = registry.get("system_base")
        result = t.render(agent_name="Kiro", objective="help the user")
        assert "Kiro" in result
        assert "help the user" in result


# ── TestSystemPromptBuilder ───────────────────────────────────────────────────

class TestSystemPromptBuilder:

    def test_build_returns_list_of_llm_messages(self):
        builder  = SystemPromptBuilder()
        ctx      = _ctx("hello")
        messages = builder.build(ctx)
        assert isinstance(messages, list)
        assert all(isinstance(m, LLMMessage) for m in messages)

    def test_first_message_is_system(self):
        builder  = SystemPromptBuilder()
        messages = builder.build(_ctx("hello"))
        assert messages[0].role == "system"

    def test_last_message_is_user_input(self):
        builder  = SystemPromptBuilder()
        ctx      = _ctx("my question")
        messages = builder.build(ctx)
        assert messages[-1].role == "user"
        assert messages[-1].content == "my question"

    def test_memory_context_included(self):
        from app.ai.memory.short_term import MemoryEntry
        builder = SystemPromptBuilder()
        ctx     = _ctx("hello")
        ctx.memory_context = [MemoryEntry(content="user likes dark mode")]
        messages = builder.build(ctx)
        combined = " ".join(m.content for m in messages)
        assert "dark mode" in combined

    def test_thought_chain_included_when_present(self):
        builder = SystemPromptBuilder()
        ctx     = _ctx("hello")
        ctx.thought_chain = [ThoughtStep("step 0 content", 0.7, 0)]
        messages = builder.build(ctx)
        combined = " ".join(m.content for m in messages)
        assert "step 0 content" in combined

    def test_thought_chain_excluded_when_config_off(self):
        cfg     = BuilderConfig(include_thought_chain=False)
        builder = SystemPromptBuilder(config=cfg)
        ctx     = _ctx("hello")
        ctx.thought_chain = [ThoughtStep("secret reasoning", 0.7, 0)]
        messages = builder.build(ctx)
        combined = " ".join(m.content for m in messages)
        assert "secret reasoning" not in combined

    def test_history_included(self):
        builder = SystemPromptBuilder()
        ctx     = _ctx("hello")
        ctx.add_history("user", "previous question")
        ctx.add_history("assistant", "previous answer")
        messages = builder.build(ctx)
        roles = [m.role for m in messages]
        assert "assistant" in roles

    def test_build_request_returns_llm_request(self):
        from app.ai.runtime.llm_gateway import LLMRequest
        builder = SystemPromptBuilder()
        ctx     = _ctx("hello")
        request = builder.build_request(ctx)
        assert isinstance(request, LLMRequest)
        assert len(request.messages) >= 1

    def test_custom_agent_name_in_system_prompt(self):
        cfg     = BuilderConfig(agent_name="TestBot")
        builder = SystemPromptBuilder(config=cfg)
        ctx     = _ctx("hello")
        messages = builder.build(ctx)
        assert "TestBot" in messages[0].content


# ── TestPipelineResponderAdapter ──────────────────────────────────────────────

class TestPipelineResponderAdapter:

    @pytest.mark.asyncio
    async def test_respond_sets_ctx_response(self):
        gw      = _make_gateway()
        adapter = PipelineResponderAdapter(gateway=gw)
        ctx     = _ctx("hello")
        await adapter.respond(ctx)
        assert ctx.response == "mock response"

    @pytest.mark.asyncio
    async def test_respond_sets_ctx_explanation(self):
        gw      = _make_gateway()
        adapter = PipelineResponderAdapter(gateway=gw)
        ctx     = _ctx("hello")
        await adapter.respond(ctx)
        assert ctx.explanation != ""

    @pytest.mark.asyncio
    async def test_respond_with_memory_context(self):
        from app.ai.memory.short_term import MemoryEntry
        gw      = _make_gateway()
        adapter = PipelineResponderAdapter(gateway=gw)
        ctx     = _ctx("hello")
        ctx.memory_context = [MemoryEntry(content="relevant fact")]
        await adapter.respond(ctx)
        assert ctx.response != ""


# ── TestFullPipelineIntegration ───────────────────────────────────────────────

class TestFullPipelineIntegration:
    """
    Verify that all Phase 6C components wire correctly into ExecutionEngine.
    """

    def _make_engine(self):
        from app.ai.runtime.execution import ExecutionEngine
        gw      = _make_gateway()
        planner = PipelinePlannerAdapter()
        reasoner = PipelineReasonerAdapter()
        verifier = PipelineVerifierAdapter()
        responder = PipelineResponderAdapter(gateway=gw)
        return ExecutionEngine(
            gateway=gw,
            planner=planner,
            reasoner=reasoner,
            verifier=verifier,
            responder=responder,
        )

    @pytest.mark.asyncio
    async def test_full_pipeline_completes(self):
        engine = self._make_engine()
        result = await engine.run("What is the best approach?", session_id="s1")
        assert result.response == "mock response"
        assert not result.trace.error

    @pytest.mark.asyncio
    async def test_intent_type_set_by_planner(self):
        engine = self._make_engine()
        result = await engine.run("What is X?", session_id="s1")
        assert result.context.intent_type == "question"

    @pytest.mark.asyncio
    async def test_thought_chain_populated_by_reasoner(self):
        engine = self._make_engine()
        result = await engine.run("hello", session_id="s1")
        assert len(result.context.thought_chain) >= 2

    @pytest.mark.asyncio
    async def test_confidence_set_by_reasoner(self):
        engine = self._make_engine()
        result = await engine.run("hello", session_id="s1")
        assert 0.0 <= result.confidence <= 1.0

    @pytest.mark.asyncio
    async def test_critique_set_by_verifier(self):
        engine = self._make_engine()
        result = await engine.run("hello", session_id="s1")
        assert result.context.critique != ""


# ── TestDomainAgnosticism ─────────────────────────────────────────────────────

class TestDomainAgnosticism:
    """Reasoning and prompt components must contain zero domain-specific fields."""

    TRADING_FIELDS = [
        "symbol", "stock", "candle", "rsi", "macd", "broker",
        "portfolio", "trade", "price", "market", "nifty",
        "signal", "indicator", "ticker",
    ]

    def test_chain_of_thought_has_no_trading_attributes(self):
        cot = ChainOfThought()
        for attr in self.TRADING_FIELDS:
            assert not hasattr(cot, attr), f"Domain attribute '{attr}' found on ChainOfThought"

    def test_reflection_has_no_trading_attributes(self):
        ref = Reflection()
        for attr in self.TRADING_FIELDS:
            assert not hasattr(ref, attr), f"Domain attribute '{attr}' found on Reflection"

    def test_reasoning_planner_has_no_trading_attributes(self):
        planner = ReasoningPlanner()
        for attr in self.TRADING_FIELDS:
            assert not hasattr(planner, attr), f"Domain attribute '{attr}' found on ReasoningPlanner"

    def test_reasoning_plan_has_no_trading_attributes(self):
        planner = ReasoningPlanner()
        plan    = planner.decompose("hello")
        for attr in self.TRADING_FIELDS:
            assert attr not in vars(plan), f"Domain attribute '{attr}' found on ReasoningPlan"

    def test_system_prompt_builder_has_no_trading_attributes(self):
        builder = SystemPromptBuilder()
        for attr in self.TRADING_FIELDS:
            assert not hasattr(builder, attr), f"Domain attribute '{attr}' found on SystemPromptBuilder"

    def test_template_registry_has_no_trading_content(self):
        registry = TemplateRegistry.default()
        for name in registry.names():
            t = registry.get(name)
            for field in self.TRADING_FIELDS:
                assert field not in t.template.lower(), (
                    f"Domain term '{field}' found in template '{name}'"
                )

    def test_metadata_carries_domain_data(self):
        """Domain data belongs in metadata, never as first-class fields."""
        plan = ReasoningPlan(goal="test", intent_type="general", steps=[])
        plan.metadata["symbol"]    = "RELIANCE"
        plan.metadata["rsi_value"] = 72.4
        assert plan.metadata["symbol"]    == "RELIANCE"
        assert plan.metadata["rsi_value"] == 72.4
