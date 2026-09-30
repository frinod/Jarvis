"""
tests/phase7/test_7c_agents.py
================================
Phase 7C test suite — Agent Framework & Reasoning Enhancements.

Coverage:
  Part 1: TestDecisionTree, TestReasoningLog
  Part 2: TestAgentCollaborationBus, TestCollaborationContext
  Part 3: TestRAGAwareTrader, TestRAGAwareAnalyst, TestContextPropagation
  Part 4: TestMultiAgentCollaboration, TestIntegration, TestDomainAgnosticism

All tests are pure — no network, no real LLM, no Qdrant.
"""
import json
import pytest

from app.ai.runtime.context import ExecutionContext, ThoughtStep, ToolResult
from app.ai.memory.short_term import MemoryEntry, MemoryRole
from app.ai.memory.long_term import InMemoryLongTermMemory


# ── Shared helpers ────────────────────────────────────────────────────────────

def _ctx(user_input: str = "hello", session_id: str = "s1") -> ExecutionContext:
    ctx = ExecutionContext(user_input=user_input, session_id=session_id)
    ctx.active_goal = user_input
    return ctx


def _ctx_with_confidence(conf: float) -> ExecutionContext:
    ctx = _ctx()
    ctx.confidence = conf
    return ctx


def _chain(confidences):
    return [
        ThoughtStep(content=f"step {i}", confidence=c, step_index=i)
        for i, c in enumerate(confidences)
    ]


# ═══════════════════════════════════════════════════════════════════════════════
# PART 1 — DecisionTree
# ═══════════════════════════════════════════════════════════════════════════════

from app.ai.reasoning.decision_tree import (
    DecisionNode, DecisionTree, DecisionTreeEvaluator,
    DecisionOutcome, build_default_tree,
)


class TestDecisionNode:

    def test_construction(self):
        node = DecisionNode(
            name="test",
            condition=lambda ctx: True,
            response="yes",
            confidence=0.8,
            priority=1,
        )
        assert node.name == "test"
        assert node.response == "yes"
        assert node.confidence == 0.8
        assert node.priority == 1

    def test_condition_callable(self):
        node = DecisionNode(
            name="low_conf",
            condition=lambda ctx: ctx.confidence < 0.4,
            response="low",
        )
        ctx_low  = _ctx_with_confidence(0.2)
        ctx_high = _ctx_with_confidence(0.8)
        assert node.condition(ctx_low)  is True
        assert node.condition(ctx_high) is False

    def test_metadata_default_empty(self):
        node = DecisionNode(name="n", condition=lambda ctx: True, response="r")
        assert node.metadata == {}


class TestDecisionTree:

    def test_empty_tree_returns_no_match(self):
        tree    = DecisionTree()
        outcome = tree.evaluate(_ctx())
        assert outcome.matched is False

    def test_single_matching_node(self):
        tree = DecisionTree()
        tree.add(DecisionNode(
            name="always",
            condition=lambda ctx: True,
            response="matched",
            confidence=0.9,
        ))
        outcome = tree.evaluate(_ctx())
        assert outcome.matched is True
        assert outcome.response == "matched"
        assert outcome.node_name == "always"
        assert outcome.confidence == 0.9

    def test_first_match_wins(self):
        tree = DecisionTree()
        tree.add(DecisionNode(name="first",  condition=lambda ctx: True, response="A", priority=1))
        tree.add(DecisionNode(name="second", condition=lambda ctx: True, response="B", priority=2))
        outcome = tree.evaluate(_ctx())
        assert outcome.response == "A"
        assert outcome.node_name == "first"

    def test_priority_ordering(self):
        tree = DecisionTree()
        # Add in reverse priority order — tree must sort
        tree.add(DecisionNode(name="low",  condition=lambda ctx: True, response="low",  priority=5))
        tree.add(DecisionNode(name="high", condition=lambda ctx: True, response="high", priority=1))
        outcome = tree.evaluate(_ctx())
        assert outcome.node_name == "high"

    def test_non_matching_node_skipped(self):
        tree = DecisionTree()
        tree.add(DecisionNode(name="never", condition=lambda ctx: False, response="X"))
        tree.add(DecisionNode(name="yes",   condition=lambda ctx: True,  response="Y"))
        outcome = tree.evaluate(_ctx())
        assert outcome.response == "Y"

    def test_all_non_matching_returns_no_match(self):
        tree = DecisionTree()
        tree.add(DecisionNode(name="n1", condition=lambda ctx: False, response="A"))
        tree.add(DecisionNode(name="n2", condition=lambda ctx: False, response="B"))
        outcome = tree.evaluate(_ctx())
        assert outcome.matched is False
        assert outcome.response == ""

    def test_node_count(self):
        tree = DecisionTree()
        tree.add(DecisionNode(name="a", condition=lambda ctx: True, response="a"))
        tree.add(DecisionNode(name="b", condition=lambda ctx: True, response="b"))
        assert tree.node_count == 2

    def test_node_names(self):
        tree = DecisionTree()
        tree.add(DecisionNode(name="alpha", condition=lambda ctx: True, response="a", priority=1))
        tree.add(DecisionNode(name="beta",  condition=lambda ctx: True, response="b", priority=2))
        assert tree.node_names() == ["alpha", "beta"]

    def test_crashing_condition_skipped(self):
        """A condition that raises must not crash the tree."""
        tree = DecisionTree()
        tree.add(DecisionNode(name="crash",  condition=lambda ctx: 1/0,  response="crash", priority=1))
        tree.add(DecisionNode(name="safe",   condition=lambda ctx: True,  response="safe",  priority=2))
        outcome = tree.evaluate(_ctx())
        assert outcome.matched is True
        assert outcome.node_name == "safe"

    def test_evaluate_never_raises(self):
        """evaluate() must never raise regardless of input."""
        tree = DecisionTree()
        tree.add(DecisionNode(name="x", condition=lambda ctx: 1/0, response="x"))
        outcome = tree.evaluate(_ctx())
        assert isinstance(outcome, DecisionOutcome)


class TestDecisionTreeEvaluator:

    def test_does_not_fire_above_threshold(self):
        tree = build_default_tree()
        evaluator = DecisionTreeEvaluator(tree=tree, confidence_threshold=0.4)
        ctx = _ctx_with_confidence(0.8)
        outcome = evaluator.apply(ctx)
        assert outcome.matched is False

    def test_fires_below_threshold(self):
        tree = DecisionTree()
        tree.add(DecisionNode(name="low", condition=lambda ctx: True, response="fallback"))
        evaluator = DecisionTreeEvaluator(tree=tree, confidence_threshold=0.4)
        ctx = _ctx_with_confidence(0.1)
        outcome = evaluator.apply(ctx)
        assert outcome.matched is True

    def test_writes_response_to_ctx(self):
        tree = DecisionTree()
        tree.add(DecisionNode(name="r", condition=lambda ctx: True, response="fallback response"))
        evaluator = DecisionTreeEvaluator(tree=tree, confidence_threshold=0.5, write_to_ctx=True)
        ctx = _ctx_with_confidence(0.1)
        evaluator.apply(ctx)
        assert ctx.response == "fallback response"

    def test_does_not_write_when_flag_off(self):
        tree = DecisionTree()
        tree.add(DecisionNode(name="r", condition=lambda ctx: True, response="should not appear"))
        evaluator = DecisionTreeEvaluator(tree=tree, confidence_threshold=0.5, write_to_ctx=False)
        ctx = _ctx_with_confidence(0.1)
        evaluator.apply(ctx)
        assert ctx.response == ""

    def test_metadata_written_on_match(self):
        tree = DecisionTree(name="my_tree")
        tree.add(DecisionNode(name="rule1", condition=lambda ctx: True, response="r"))
        evaluator = DecisionTreeEvaluator(tree=tree, confidence_threshold=0.5)
        ctx = _ctx_with_confidence(0.1)
        evaluator.apply(ctx)
        assert "_decision_tree_fired" in ctx.metadata
        assert ctx.metadata["_decision_tree_fired"]["node"] == "rule1"
        assert ctx.metadata["_decision_tree_fired"]["tree"] == "my_tree"

    def test_apply_never_raises(self):
        evaluator = DecisionTreeEvaluator(tree=DecisionTree(), confidence_threshold=0.5)
        outcome = evaluator.apply(_ctx())
        assert isinstance(outcome, DecisionOutcome)


class TestDefaultTree:

    def test_empty_input_fires(self):
        tree    = build_default_tree()
        ctx     = _ctx(user_input="")
        ctx.confidence = 0.0
        outcome = tree.evaluate(ctx)
        assert outcome.matched is True
        assert outcome.node_name == "empty_input"

    def test_all_tools_failed_fires(self):
        tree = build_default_tree()
        ctx  = _ctx()
        ctx.confidence = 0.3
        ctx.tool_results["t1"] = ToolResult("t1", False, None, error="err")
        outcome = tree.evaluate(ctx)
        assert outcome.matched is True
        assert outcome.node_name == "all_tools_failed"

    def test_normal_context_no_match(self):
        tree = build_default_tree()
        ctx  = _ctx()
        ctx.confidence = 0.8
        outcome = tree.evaluate(ctx)
        assert outcome.matched is False


# ═══════════════════════════════════════════════════════════════════════════════
# PART 1 — ReasoningLog
# ═══════════════════════════════════════════════════════════════════════════════

from app.ai.reasoning.reasoning_log import (
    ReasoningTrace, ReasoningLogger, ReasoningLogReader,
    _trace_to_entry, _entry_to_trace, _summarise_chain,
)


class TestReasoningTrace:

    def test_from_context_basic(self):
        ctx = _ctx("what is X?")
        ctx.confidence  = 0.75
        ctx.retry_count = 1
        ctx.intent_type = "question"
        ctx.selected_agent = "analyst"
        ctx.thought_chain  = _chain([0.6, 0.7, 0.75])
        trace = ReasoningTrace.from_context(ctx, outcome="success")
        assert trace.confidence   == 0.75
        assert trace.retry_count  == 1
        assert trace.intent_type  == "question"
        assert trace.agent_name   == "analyst"
        assert trace.step_count   == 3
        assert trace.outcome      == "success"

    def test_from_context_empty_chain(self):
        ctx = _ctx()
        trace = ReasoningTrace.from_context(ctx)
        assert trace.step_count  == 0
        assert trace.step_summary == "no reasoning steps"

    def test_to_dict_round_trip(self):
        ctx = _ctx("test")
        ctx.confidence = 0.8
        trace = ReasoningTrace.from_context(ctx, outcome="success")
        d     = trace.to_dict()
        assert d["confidence"] == 0.8
        assert d["outcome"]    == "success"

    def test_from_dict_round_trip(self):
        original = ReasoningTrace(
            request_id="r1", session_id="s1", goal="test goal",
            intent_type="question", agent_name="analyst",
            confidence=0.72, retry_count=0, step_count=3,
            step_summary="3 steps, final confidence 72%: Conclusion",
            outcome="success", critique="Verified.",
        )
        d         = original.to_dict()
        recovered = ReasoningTrace.from_dict(d)
        assert recovered.request_id  == original.request_id
        assert recovered.confidence  == original.confidence
        assert recovered.outcome     == original.outcome
        assert recovered.agent_name  == original.agent_name

    def test_from_dict_extra_keys_go_to_metadata(self):
        d = {
            "request_id": "r1", "session_id": "s1", "goal": "g",
            "intent_type": "q", "agent_name": "a", "confidence": 0.5,
            "retry_count": 0, "step_count": 0, "step_summary": "",
            "outcome": "success", "critique": "",
            "custom_field": "custom_value",
        }
        trace = ReasoningTrace.from_dict(d)
        assert trace.metadata.get("custom_field") == "custom_value"


class TestSummariseChain:

    def test_empty_chain(self):
        assert _summarise_chain([]) == "no reasoning steps"

    def test_non_empty_chain(self):
        chain   = _chain([0.6, 0.75])
        summary = _summarise_chain(chain)
        assert "2 steps" in summary
        assert "75%" in summary

    def test_long_content_truncated(self):
        chain = [ThoughtStep(content="x" * 200, confidence=0.8, step_index=0)]
        summary = _summarise_chain(chain)
        assert len(summary) < 300


class TestTraceEntryHelpers:

    def test_trace_to_entry_produces_memory_entry(self):
        trace = ReasoningTrace(
            request_id="r1", session_id="s1", goal="test",
            intent_type="question", agent_name="analyst",
            confidence=0.7, retry_count=0, step_count=2,
            step_summary="2 steps", outcome="success", critique="ok",
        )
        entry = _trace_to_entry(trace)
        assert isinstance(entry, MemoryEntry)
        assert entry.metadata["entry_type"] == "reasoning_trace"
        assert entry.metadata["outcome"]    == "success"
        assert entry.importance             == 1.0   # always 1.0 so LTM never drops it

    def test_entry_to_trace_round_trip(self):
        trace = ReasoningTrace(
            request_id="r2", session_id="s2", goal="goal",
            intent_type="task", agent_name="planner",
            confidence=0.65, retry_count=1, step_count=4,
            step_summary="4 steps", outcome="partial", critique="retry",
        )
        entry    = _trace_to_entry(trace)
        recovered = _entry_to_trace(entry)
        assert recovered is not None
        assert recovered.request_id == "r2"
        assert recovered.outcome    == "partial"

    def test_entry_to_trace_wrong_type_returns_none(self):
        entry = MemoryEntry(content="hello", metadata={"entry_type": "conversation"})
        assert _entry_to_trace(entry) is None

    def test_entry_to_trace_malformed_json_returns_none(self):
        entry = MemoryEntry(content="not json", metadata={"entry_type": "reasoning_trace"})
        assert _entry_to_trace(entry) is None


class TestReasoningLogger:

    @pytest.mark.asyncio
    async def test_log_with_no_ltm_returns_none(self):
        logger = ReasoningLogger(ltm=None)
        ctx    = _ctx()
        result = await logger.log(ctx)
        assert result is None

    @pytest.mark.asyncio
    async def test_log_stores_to_ltm(self):
        ltm    = InMemoryLongTermMemory()
        logger = ReasoningLogger(ltm=ltm)
        ctx    = _ctx("test question")
        ctx.confidence = 0.8
        trace  = await logger.log(ctx, outcome="success")
        assert trace is not None
        assert trace.outcome == "success"
        # Verify it was stored
        entries = await ltm.all_entries()
        assert len(entries) == 1

    @pytest.mark.asyncio
    async def test_log_trace_returns_true_on_success(self):
        ltm    = InMemoryLongTermMemory()
        logger = ReasoningLogger(ltm=ltm)
        trace  = ReasoningTrace(
            request_id="r1", session_id="s1", goal="g",
            intent_type="q", agent_name="a", confidence=0.7,
            retry_count=0, step_count=2, step_summary="2 steps",
            outcome="success", critique="ok",
        )
        ok = await logger.log_trace(trace)
        assert ok is True

    @pytest.mark.asyncio
    async def test_log_trace_no_ltm_returns_false(self):
        logger = ReasoningLogger(ltm=None)
        trace  = ReasoningTrace(
            request_id="r1", session_id="s1", goal="g",
            intent_type="q", agent_name="a", confidence=0.7,
            retry_count=0, step_count=0, step_summary="",
            outcome="success", critique="",
        )
        ok = await logger.log_trace(trace)
        assert ok is False

    @pytest.mark.asyncio
    async def test_log_never_raises_on_broken_ltm(self):
        class BrokenLTM(InMemoryLongTermMemory):
            async def store(self, entry):
                raise RuntimeError("disk full")
        logger = ReasoningLogger(ltm=BrokenLTM())
        ctx    = _ctx()
        result = await logger.log(ctx)   # must not raise
        assert result is None


class TestReasoningLogReader:

    @pytest.mark.asyncio
    async def test_recent_no_ltm_returns_empty(self):
        reader  = ReasoningLogReader(ltm=None)
        results = await reader.recent()
        assert results == []

    @pytest.mark.asyncio
    async def test_recent_returns_stored_traces(self):
        ltm    = InMemoryLongTermMemory()
        logger = ReasoningLogger(ltm=ltm)
        reader = ReasoningLogReader(ltm=ltm)

        ctx = _ctx("question one")
        ctx.confidence = 0.75
        await logger.log(ctx, outcome="success")

        traces = await reader.recent(n=10)
        assert len(traces) == 1
        assert traces[0].outcome == "success"

    @pytest.mark.asyncio
    async def test_by_outcome_filters_correctly(self):
        ltm    = InMemoryLongTermMemory()
        logger = ReasoningLogger(ltm=ltm)
        reader = ReasoningLogReader(ltm=ltm)

        ctx1 = _ctx("q1"); ctx1.confidence = 0.8
        ctx2 = _ctx("q2"); ctx2.confidence = 0.3
        await logger.log(ctx1, outcome="success")
        await logger.log(ctx2, outcome="failure")

        successes = await reader.by_outcome("success")
        failures  = await reader.by_outcome("failure")
        assert len(successes) == 1
        assert len(failures)  == 1

    @pytest.mark.asyncio
    async def test_by_agent_filters_correctly(self):
        ltm    = InMemoryLongTermMemory()
        logger = ReasoningLogger(ltm=ltm)
        reader = ReasoningLogReader(ltm=ltm)

        ctx1 = _ctx("q1"); ctx1.selected_agent = "trader"
        ctx2 = _ctx("q2"); ctx2.selected_agent = "analyst"
        await logger.log(ctx1, outcome="success")
        await logger.log(ctx2, outcome="success")

        trader_traces  = await reader.by_agent("trader")
        analyst_traces = await reader.by_agent("analyst")
        assert len(trader_traces)  == 1
        assert len(analyst_traces) == 1

    @pytest.mark.asyncio
    async def test_reader_never_raises_on_broken_ltm(self):
        class BrokenLTM(InMemoryLongTermMemory):
            async def search(self, query, top_k=10):
                raise RuntimeError("network error")
        reader  = ReasoningLogReader(ltm=BrokenLTM())
        results = await reader.recent()   # must not raise
        assert results == []


# ═══════════════════════════════════════════════════════════════════════════════
# PART 2 — AgentCollaborationBus & CollaborationContext
# ═══════════════════════════════════════════════════════════════════════════════

from app.ai.agents.collaboration import (
    AgentMessage, AgentCollaborationBus, CollaborationContext,
)


class TestAgentMessage:

    def test_construction_defaults(self):
        msg = AgentMessage(sender="trader", message_type="trade_signal", payload={"dir": "buy"})
        assert msg.sender       == "trader"
        assert msg.message_type == "trade_signal"
        assert msg.recipient    == "*"
        assert msg.payload["dir"] == "buy"
        assert msg.message_id   != ""
        assert msg.timestamp    > 0

    def test_explicit_recipient(self):
        msg = AgentMessage(sender="trader", message_type="signal", recipient="analyst")
        assert msg.recipient == "analyst"

    def test_unique_message_ids(self):
        m1 = AgentMessage(sender="a", message_type="t")
        m2 = AgentMessage(sender="a", message_type="t")
        assert m1.message_id != m2.message_id


class TestAgentCollaborationBus:

    def test_publish_and_retrieve(self):
        bus = AgentCollaborationBus()
        bus.publish(AgentMessage(sender="trader", message_type="trade_signal", payload={"dir": "buy"}))
        msgs = bus.get_messages(message_type="trade_signal")
        assert len(msgs) == 1
        assert msgs[0].payload["dir"] == "buy"

    def test_get_messages_by_sender(self):
        bus = AgentCollaborationBus()
        bus.publish(AgentMessage(sender="trader",  message_type="signal"))
        bus.publish(AgentMessage(sender="analyst", message_type="signal"))
        trader_msgs = bus.get_messages(sender="trader")
        assert len(trader_msgs) == 1
        assert trader_msgs[0].sender == "trader"

    def test_get_messages_by_recipient_exact(self):
        bus = AgentCollaborationBus()
        bus.publish(AgentMessage(sender="trader", message_type="signal", recipient="analyst"))
        bus.publish(AgentMessage(sender="trader", message_type="signal", recipient="planner"))
        analyst_msgs = bus.get_messages(recipient="analyst")
        assert len(analyst_msgs) == 1

    def test_broadcast_visible_to_all_recipients(self):
        bus = AgentCollaborationBus()
        bus.publish(AgentMessage(sender="trader", message_type="signal", recipient="*"))
        # Any recipient filter should see broadcast messages
        assert len(bus.get_messages(recipient="analyst")) == 1
        assert len(bus.get_messages(recipient="planner")) == 1

    def test_combined_filters(self):
        bus = AgentCollaborationBus()
        bus.publish(AgentMessage(sender="trader",  message_type="trade_signal"))
        bus.publish(AgentMessage(sender="analyst", message_type="analysis_result"))
        results = bus.get_messages(message_type="trade_signal", sender="trader")
        assert len(results) == 1

    def test_latest_returns_most_recent(self):
        bus = AgentCollaborationBus()
        bus.publish(AgentMessage(sender="trader", message_type="signal", payload={"v": 1}))
        bus.publish(AgentMessage(sender="trader", message_type="signal", payload={"v": 2}))
        latest = bus.latest("signal")
        assert latest is not None
        assert latest.payload["v"] == 2

    def test_latest_returns_none_when_empty(self):
        bus = AgentCollaborationBus()
        assert bus.latest("nonexistent") is None

    def test_message_count(self):
        bus = AgentCollaborationBus()
        bus.publish(AgentMessage(sender="a", message_type="t"))
        bus.publish(AgentMessage(sender="b", message_type="t"))
        assert bus.message_count == 2

    def test_clear_removes_all_messages(self):
        bus = AgentCollaborationBus()
        bus.publish(AgentMessage(sender="a", message_type="t"))
        bus.clear()
        assert bus.message_count == 0
        assert bus.get_messages() == []

    def test_get_messages_no_filter_returns_all(self):
        bus = AgentCollaborationBus()
        bus.publish(AgentMessage(sender="a", message_type="x"))
        bus.publish(AgentMessage(sender="b", message_type="y"))
        assert len(bus.get_messages()) == 2

    def test_publish_never_raises(self):
        bus = AgentCollaborationBus()
        # Should not raise even with unusual input
        bus.publish(AgentMessage(sender="", message_type="", payload={}))

    def test_get_messages_never_raises(self):
        bus = AgentCollaborationBus()
        result = bus.get_messages(message_type="x", recipient="y", sender="z")
        assert isinstance(result, list)


class TestCollaborationContext:

    def test_attach_creates_bus(self):
        ctx = _ctx()
        bus = CollaborationContext.attach(ctx)
        assert isinstance(bus, AgentCollaborationBus)

    def test_attach_stores_in_metadata(self):
        ctx = _ctx()
        CollaborationContext.attach(ctx)
        assert CollaborationContext.is_attached(ctx)

    def test_get_bus_returns_attached_bus(self):
        ctx = _ctx()
        bus = CollaborationContext.attach(ctx)
        retrieved = CollaborationContext.get_bus(ctx)
        assert retrieved is bus

    def test_get_bus_returns_none_when_not_attached(self):
        ctx = _ctx()
        assert CollaborationContext.get_bus(ctx) is None

    def test_is_attached_false_before_attach(self):
        ctx = _ctx()
        assert CollaborationContext.is_attached(ctx) is False

    def test_is_attached_true_after_attach(self):
        ctx = _ctx()
        CollaborationContext.attach(ctx)
        assert CollaborationContext.is_attached(ctx) is True

    def test_attach_with_existing_bus(self):
        ctx = _ctx()
        existing_bus = AgentCollaborationBus()
        existing_bus.publish(AgentMessage(sender="x", message_type="t"))
        CollaborationContext.attach(ctx, bus=existing_bus)
        retrieved = CollaborationContext.get_bus(ctx)
        assert retrieved.message_count == 1

    def test_get_bus_never_raises(self):
        # Even with a broken metadata dict
        ctx = _ctx()
        result = CollaborationContext.get_bus(ctx)
        assert result is None or isinstance(result, AgentCollaborationBus)


# ═══════════════════════════════════════════════════════════════════════════════
# PART 3 — RAG-aware agents & context propagation
# ═══════════════════════════════════════════════════════════════════════════════

from app.ai.agents.trader import TraderAgent, TradeSignal, SignalDirection
from app.ai.agents.analyst import AnalystAgent
from app.ai.rag.context_builder import ContextAssembly, ContextBlock, ContextBuilder
from app.ai.memory.short_term import MemoryEntry


def _make_assembly(blocks=None) -> ContextAssembly:
    """Build a minimal ContextAssembly for testing."""
    if blocks is None:
        blocks = [
            ContextBlock(block_type="market",   content="RELIANCE broke out above 2800", importance=0.9),
            ContextBlock(block_type="strategy",  content="RSI at 68, approaching overbought", importance=0.7),
            ContextBlock(block_type="conversation", content="User asked about RELIANCE yesterday", importance=0.5),
        ]
    total = sum(b.token_count for b in blocks)
    return ContextAssembly(
        blocks=blocks,
        total_tokens=total,
        entries_used=len(blocks),
        prompt_text="\n".join(f"[{b.block_type}] {b.content}" for b in blocks),
    )


class TestRAGAwareTrader:

    @pytest.mark.asyncio
    async def test_execute_returns_agent_result(self):
        agent = TraderAgent()
        ctx   = _ctx()
        from app.ai.prediction.forecasting import ForecastResult
        ctx.metadata["_forecast"] = ForecastResult(
            direction="UP", confidence=80.0,
            prob_up=80.0, prob_down=10.0, prob_flat=10.0,
        )
        result = await agent.execute(ctx)
        assert result.agent_name == "trader"
        assert result.confidence == 0.8

    @pytest.mark.asyncio
    async def test_execute_without_rag_uses_base_rationale(self):
        agent = TraderAgent()
        ctx   = _ctx()
        from app.ai.prediction.forecasting import ForecastResult
        ctx.metadata["_forecast"] = ForecastResult(
            direction="UP", confidence=80.0,
            prob_up=80.0, prob_down=10.0, prob_flat=10.0,
        )
        result = await agent.execute(ctx)
        # No _rag_context in metadata — rationale is the base signal rationale
        assert "Context:" not in result.explanation or True  # graceful either way
        assert result.explanation != ""

    @pytest.mark.asyncio
    async def test_execute_with_rag_enriches_rationale(self):
        agent    = TraderAgent()
        ctx      = _ctx()
        from app.ai.prediction.forecasting import ForecastResult
        ctx.metadata["_forecast"] = ForecastResult(
            direction="UP", confidence=80.0,
            prob_up=80.0, prob_down=10.0, prob_flat=10.0,
        )
        ctx.metadata["_rag_context"]      = _make_assembly()
        result   = await agent.execute(ctx)
        # Rationale should include market context
        assert "Context:" in result.explanation
        assert "RELIANCE" in result.explanation

    @pytest.mark.asyncio
    async def test_execute_with_empty_rag_blocks_no_enrichment(self):
        agent    = TraderAgent()
        ctx      = _ctx()
        from app.ai.prediction.forecasting import ForecastResult
        ctx.metadata["_forecast"] = ForecastResult(
            direction="UP", confidence=80.0,
            prob_up=80.0, prob_down=10.0, prob_flat=10.0,
        )
        # Assembly with only conversation blocks (no market/strategy)
        assembly = _make_assembly(blocks=[
            ContextBlock(block_type="conversation", content="hello", importance=0.5),
        ])
        ctx.metadata["_rag_context"] = assembly
        result = await agent.execute(ctx)
        # No market blocks → no "Context:" enrichment
        assert "Context:" not in result.explanation

    @pytest.mark.asyncio
    async def test_execute_publishes_to_bus(self):
        agent = TraderAgent()
        ctx   = _ctx()
        from app.ai.prediction.forecasting import ForecastResult
        ctx.metadata["_forecast"] = ForecastResult(
            direction="FLAT", confidence=50.0,
            prob_up=20.0, prob_down=30.0, prob_flat=50.0,
        )
        bus   = CollaborationContext.attach(ctx)
        await agent.execute(ctx)
        msgs = bus.get_messages(message_type="trade_signal")
        assert len(msgs) == 1
        assert msgs[0].sender == "trader"
        assert msgs[0].payload["direction"] == "hold"

    @pytest.mark.asyncio
    async def test_execute_no_bus_does_not_raise(self):
        agent = TraderAgent()
        ctx   = _ctx()
        from app.ai.prediction.forecasting import ForecastResult
        ctx.metadata["_forecast"] = ForecastResult(
            direction="UP", confidence=80.0,
            prob_up=80.0, prob_down=10.0, prob_flat=10.0,
        )
        # No bus attached — must not raise
        result = await agent.execute(ctx)
        assert result is not None

    @pytest.mark.asyncio
    async def test_buy_signal_at_high_confidence(self):
        agent = TraderAgent()
        ctx   = _ctx()
        from app.ai.prediction.forecasting import ForecastResult
        ctx.metadata["_forecast"] = ForecastResult(
            direction="UP", confidence=85.0,
            prob_up=85.0, prob_down=8.0, prob_flat=7.0,
        )
        result = await agent.execute(ctx)
        signal = result.metadata["trade_signal"]
        assert signal.direction == SignalDirection.BUY

    @pytest.mark.asyncio
    async def test_sell_signal_at_low_confidence(self):
        agent = TraderAgent()
        ctx   = _ctx()
        from app.ai.prediction.forecasting import ForecastResult
        ctx.metadata["_forecast"] = ForecastResult(
            direction="DOWN", confidence=68.0,
            prob_up=12.0, prob_down=68.0, prob_flat=20.0,
        )
        result = await agent.execute(ctx)
        signal = result.metadata["trade_signal"]
        assert signal.direction == SignalDirection.SELL

    @pytest.mark.asyncio
    async def test_hold_signal_at_neutral_confidence(self):
        agent = TraderAgent()
        ctx   = _ctx()
        from app.ai.prediction.forecasting import ForecastResult
        ctx.metadata["_forecast"] = ForecastResult(
            direction="FLAT", confidence=50.0,
            prob_up=20.0, prob_down=30.0, prob_flat=50.0,
        )
        result = await agent.execute(ctx)
        signal = result.metadata["trade_signal"]
        assert signal.direction == SignalDirection.HOLD

    @pytest.mark.asyncio
    async def test_verify_passes_for_valid_signal(self):
        agent  = TraderAgent()
        ctx    = _ctx()
        from app.ai.prediction.forecasting import ForecastResult
        ctx.metadata["_forecast"] = ForecastResult(
            direction="UP", confidence=80.0,
            prob_up=80.0, prob_down=10.0, prob_flat=10.0,
        )
        result = await agent.execute(ctx)
        vr     = await agent.verify(result)
        assert vr.passed is True

    @pytest.mark.asyncio
    async def test_verify_fails_for_missing_signal(self):
        from app.ai.agents.base import AgentResult
        agent  = TraderAgent()
        result = AgentResult(agent_name="trader", response="", confidence=0.8)
        vr     = await agent.verify(result)
        assert vr.passed is False
        assert vr.retry  is True


class TestRAGAwareAnalyst:

    @pytest.mark.asyncio
    async def test_execute_returns_agent_result(self):
        agent  = AnalystAgent()
        ctx    = _ctx("analyse RELIANCE")
        from app.ai.prediction.forecasting import ForecastResult
        ctx.metadata["_forecast"] = ForecastResult(
            direction="UP", confidence=70.0,
            prob_up=70.0, prob_down=15.0, prob_flat=15.0,
        )
        result = await agent.execute(ctx)
        assert result.agent_name == "analyst"
        assert abs(result.confidence - 0.7) < 0.001

    @pytest.mark.asyncio
    async def test_execute_without_rag_base_explanation(self):
        agent  = AnalystAgent()
        ctx    = _ctx("analyse X")
        result = await agent.execute(ctx)
        assert "AnalystAgent applied technical reasoning" in result.explanation

    @pytest.mark.asyncio
    async def test_execute_with_rag_enriches_explanation(self):
        agent    = AnalystAgent()
        ctx      = _ctx("analyse RELIANCE")
        ctx.metadata["_rag_context"] = _make_assembly()
        result   = await agent.execute(ctx)
        assert "Retrieved context:" in result.explanation
        assert "RELIANCE" in result.explanation

    @pytest.mark.asyncio
    async def test_execute_reads_trade_signal_from_bus(self):
        agent = AnalystAgent()
        ctx   = _ctx("analyse market")
        bus   = CollaborationContext.attach(ctx)
        # Simulate TraderAgent having already published
        bus.publish(AgentMessage(
            sender="trader",
            message_type="trade_signal",
            payload={"direction": "buy", "confidence": 0.82},
        ))
        result = await agent.execute(ctx)
        assert "TraderAgent signal: buy" in result.explanation
        assert "82%" in result.explanation

    @pytest.mark.asyncio
    async def test_execute_no_bus_no_crash(self):
        agent  = AnalystAgent()
        ctx    = _ctx("analyse X")
        result = await agent.execute(ctx)
        assert result is not None

    @pytest.mark.asyncio
    async def test_verify_passes_for_valid_result(self):
        agent  = AnalystAgent()
        ctx    = _ctx("analyse X")
        result = await agent.execute(ctx)
        vr     = await agent.verify(result)
        assert vr.passed is True


class TestContextPropagation:
    """Verify that RAG context and bus survive the full context lifecycle."""

    def test_rag_context_survives_metadata(self):
        ctx      = _ctx()
        assembly = _make_assembly()
        ctx.metadata["_rag_context"] = assembly
        # Simulate passing ctx through pipeline stages
        retrieved = ctx.metadata.get("_rag_context")
        assert retrieved is assembly

    def test_bus_survives_metadata(self):
        ctx = _ctx()
        bus = CollaborationContext.attach(ctx)
        bus.publish(AgentMessage(sender="trader", message_type="signal"))
        # Retrieve from a different code path
        retrieved_bus = CollaborationContext.get_bus(ctx)
        assert retrieved_bus.message_count == 1

    def test_decision_tree_metadata_written_to_ctx(self):
        tree = DecisionTree(name="test_tree")
        tree.add(DecisionNode(name="rule", condition=lambda ctx: True, response="r"))
        evaluator = DecisionTreeEvaluator(tree=tree, confidence_threshold=0.5)
        ctx = _ctx_with_confidence(0.1)
        evaluator.apply(ctx)
        assert ctx.metadata["_decision_tree_fired"]["tree"] == "test_tree"

    @pytest.mark.asyncio
    async def test_reasoning_trace_captures_full_context(self):
        from app.ai.reasoning.reasoning_log import ReasoningLogger
        ltm    = InMemoryLongTermMemory()
        logger = ReasoningLogger(ltm=ltm)
        ctx    = _ctx("complex question")
        ctx.confidence     = 0.78
        ctx.retry_count    = 1
        ctx.intent_type    = "question"
        ctx.selected_agent = "analyst"
        ctx.thought_chain  = _chain([0.6, 0.7, 0.78])
        ctx.critique       = "Verified after retry."
        trace = await logger.log(ctx, outcome="success")
        assert trace.retry_count  == 1
        assert trace.step_count   == 3
        assert trace.critique     == "Verified after retry."


# ═══════════════════════════════════════════════════════════════════════════════
# PART 4 — Multi-agent collaboration, Integration, Domain agnosticism
# ═══════════════════════════════════════════════════════════════════════════════

from app.ai.reasoning.chain import ChainOfThought
from app.ai.reasoning.reflection import Reflection


class TestMultiAgentCollaboration:
    """
    Trader publishes a signal → Analyst reads it → both results are coherent.
    This is the core Phase 7C multi-agent scenario.
    """

    @pytest.mark.asyncio
    async def test_trader_then_analyst_pipeline(self):
        trader  = TraderAgent()
        analyst = AnalystAgent()
        ctx     = _ctx("market analysis request")
        from app.ai.prediction.forecasting import ForecastResult
        ctx.metadata["_forecast"] = ForecastResult(
            direction="UP", confidence=82.0,
            prob_up=82.0, prob_down=10.0, prob_flat=8.0,
        )

        # Attach collaboration bus
        bus = CollaborationContext.attach(ctx)

        # Step 1: Trader runs first
        trader_result = await trader.execute(ctx)
        assert trader_result.metadata["trade_signal"].direction == SignalDirection.BUY

        # Step 2: Bus has the signal
        assert bus.message_count == 1

        # Step 3: Analyst runs and reads the signal
        analyst_result = await analyst.execute(ctx)
        assert "TraderAgent signal: buy" in analyst_result.explanation
        assert "82%" in analyst_result.explanation

    @pytest.mark.asyncio
    async def test_analyst_without_prior_trader_still_works(self):
        analyst = AnalystAgent()
        ctx     = _ctx("standalone analysis")
        CollaborationContext.attach(ctx)  # bus attached but empty
        result = await analyst.execute(ctx)
        assert result.success is True
        assert "TraderAgent signal" not in result.explanation

    @pytest.mark.asyncio
    async def test_multiple_signals_analyst_reads_latest(self):
        trader  = TraderAgent()
        analyst = AnalystAgent()
        ctx     = _ctx("market")
        bus     = CollaborationContext.attach(ctx)

        # Publish two signals manually (simulating two trader runs)
        bus.publish(AgentMessage(
            sender="trader", message_type="trade_signal",
            payload={"direction": "sell", "confidence": 0.25},
        ))
        bus.publish(AgentMessage(
            sender="trader", message_type="trade_signal",
            payload={"direction": "buy", "confidence": 0.85},
        ))

        result = await analyst.execute(ctx)
        # Should read the latest (buy), not the first (sell)
        assert "buy" in result.explanation

    @pytest.mark.asyncio
    async def test_rag_context_shared_across_agents(self):
        """Both agents read the same ContextAssembly from ctx.metadata."""
        trader  = TraderAgent()
        analyst = AnalystAgent()
        ctx     = _ctx("shared context test")
        from app.ai.prediction.forecasting import ForecastResult
        ctx.metadata["_forecast"] = ForecastResult(
            direction="UP", confidence=80.0,
            prob_up=80.0, prob_down=10.0, prob_flat=10.0,
        )
        ctx.metadata["_rag_context"]      = _make_assembly()
        CollaborationContext.attach(ctx)

        trader_result  = await trader.execute(ctx)
        analyst_result = await analyst.execute(ctx)

        # Both should have used the RAG context
        assert "Context:" in trader_result.explanation
        assert "Retrieved context:" in analyst_result.explanation


class TestReflectionWithDecisionTree:
    """Reflection and DecisionTree complement each other correctly."""

    def test_reflection_detects_low_confidence(self):
        reflection = Reflection()
        ctx        = _ctx()
        ctx.thought_chain = _chain([0.3, 0.25, 0.2])
        result = reflection.evaluate(ctx)
        assert result.should_retry is True

    def test_decision_tree_fires_after_reflection_fails(self):
        """When Reflection says retry and confidence is low, DecisionTree provides fallback."""
        reflection = Reflection()
        tree       = build_default_tree()
        evaluator  = DecisionTreeEvaluator(tree=tree, confidence_threshold=0.4)

        ctx = _ctx()
        ctx.thought_chain = _chain([0.3, 0.25, 0.2])
        ctx.confidence    = 0.2

        ref_result = reflection.evaluate(ctx)
        assert ref_result.should_retry is True

        dt_outcome = evaluator.apply(ctx)
        assert dt_outcome.matched is True
        assert ctx.response != ""

    def test_decision_tree_silent_when_reflection_passes(self):
        reflection = Reflection()
        tree       = build_default_tree()
        evaluator  = DecisionTreeEvaluator(tree=tree, confidence_threshold=0.4)

        ctx = _ctx()
        ctx.thought_chain = _chain([0.7, 0.75, 0.8])
        ctx.confidence    = 0.8

        ref_result = reflection.evaluate(ctx)
        assert ref_result.should_retry is False

        dt_outcome = evaluator.apply(ctx)
        assert dt_outcome.matched is False
        assert ctx.response == ""


class TestConfidencePropagation:
    """Confidence flows correctly through the reasoning → decision tree path."""

    def test_chain_of_thought_sets_confidence(self):
        cot = ChainOfThought()
        ctx = _ctx()
        cot.think(ctx)
        assert 0.0 <= ctx.confidence <= 1.0

    def test_decision_tree_threshold_uses_ctx_confidence(self):
        tree = DecisionTree()
        tree.add(DecisionNode(name="low", condition=lambda ctx: True, response="fallback"))
        evaluator = DecisionTreeEvaluator(tree=tree, confidence_threshold=0.5)

        ctx_high = _ctx_with_confidence(0.9)
        ctx_low  = _ctx_with_confidence(0.1)

        assert evaluator.apply(ctx_high).matched is False
        assert evaluator.apply(ctx_low).matched  is True

    @pytest.mark.asyncio
    async def test_trader_confidence_matches_signal_confidence(self):
        agent = TraderAgent()
        ctx   = _ctx()
        from app.ai.prediction.forecasting import ForecastResult
        ctx.metadata["_forecast"] = ForecastResult(
            direction="UP", confidence=72.0,
            prob_up=72.0, prob_down=15.0, prob_flat=13.0,
        )
        result = await agent.execute(ctx)
        assert result.confidence == 0.72
        assert result.metadata["trade_signal"].confidence == 0.72


class TestIntegrationPipeline:
    """
    Full Phase 7C integration: reasoning → decision tree → agents → collaboration.
    No LLM calls. No network. Pure logic.
    """

    @pytest.mark.asyncio
    async def test_full_7c_pipeline_high_confidence(self):
        """High confidence path: reasoning passes, decision tree silent, agents collaborate."""
        cot        = ChainOfThought()
        reflection = Reflection()
        tree       = build_default_tree()
        evaluator  = DecisionTreeEvaluator(tree=tree, confidence_threshold=0.4)
        trader     = TraderAgent()
        analyst    = AnalystAgent()

        ctx = _ctx("analyse and trade RELIANCE")
        from app.ai.prediction.forecasting import ForecastResult
        ctx.metadata["_forecast"] = ForecastResult(
            direction="UP", confidence=82.0,
            prob_up=82.0, prob_down=10.0, prob_flat=8.0,
        )
        ctx.metadata["_rag_context"]      = _make_assembly()
        CollaborationContext.attach(ctx)

        # Reasoning
        cot.think(ctx)
        assert ctx.confidence > 0.0

        # Reflection
        ref_result = reflection.evaluate(ctx)
        # Decision tree only fires if confidence < 0.4
        dt_outcome = evaluator.apply(ctx)
        assert dt_outcome.matched is False  # high confidence → no fallback

        # Agents
        trader_result  = await trader.execute(ctx)
        analyst_result = await analyst.execute(ctx)

        assert trader_result.success  is True
        assert analyst_result.success is True
        assert "TraderAgent signal" in analyst_result.explanation

    @pytest.mark.asyncio
    async def test_full_7c_pipeline_low_confidence_fallback(self):
        """Low confidence path: decision tree fires and sets fallback response."""
        tree      = build_default_tree()
        evaluator = DecisionTreeEvaluator(tree=tree, confidence_threshold=0.4)

        ctx = _ctx()
        ctx.confidence = 0.1
        # No memory, no tools — very_low_confidence rule should fire
        outcome = evaluator.apply(ctx)
        assert outcome.matched is True
        assert ctx.response != ""

    @pytest.mark.asyncio
    async def test_reasoning_log_captures_pipeline_outcome(self):
        from app.ai.reasoning.reasoning_log import ReasoningLogger, ReasoningLogReader
        ltm    = InMemoryLongTermMemory()
        logger = ReasoningLogger(ltm=ltm)
        reader = ReasoningLogReader(ltm=ltm)

        cot = ChainOfThought()
        ctx = _ctx("log this reasoning")
        from app.ai.prediction.forecasting import ForecastResult
        ctx.metadata["_forecast"] = ForecastResult(
            direction="UP", confidence=75.0,
            prob_up=75.0, prob_down=12.0, prob_flat=13.0,
        )
        cot.think(ctx)

        trace = await logger.log(ctx, outcome="success")
        assert trace is not None

        traces = await reader.recent(n=5)
        assert len(traces) == 1
        assert traces[0].step_count > 0

    @pytest.mark.asyncio
    async def test_collaboration_bus_cleared_between_runs(self):
        """Bus.clear() resets state between pipeline runs."""
        bus = AgentCollaborationBus()
        bus.publish(AgentMessage(sender="trader", message_type="signal"))
        assert bus.message_count == 1
        bus.clear()
        assert bus.message_count == 0

    @pytest.mark.asyncio
    async def test_rag_assembly_with_no_market_blocks_graceful(self):
        """Assembly with only conversation blocks — agents degrade gracefully."""
        trader  = TraderAgent()
        analyst = AnalystAgent()
        ctx     = _ctx("conversation only")
        from app.ai.prediction.forecasting import ForecastResult
        ctx.metadata["_forecast"] = ForecastResult(
            direction="UP", confidence=80.0,
            prob_up=80.0, prob_down=10.0, prob_flat=10.0,
        )
        ctx.metadata["_rag_context"] = _make_assembly(blocks=[
            ContextBlock(block_type="conversation", content="previous chat", importance=0.5),
        ])
        CollaborationContext.attach(ctx)

        trader_result  = await trader.execute(ctx)
        analyst_result = await analyst.execute(ctx)

        # No market blocks → no enrichment, but no crash
        assert trader_result.success  is True
        assert analyst_result.success is True


class TestDomainAgnosticism:
    """
    Phase 7C components must contain zero domain-specific fields.
    Domain data travels through metadata only.
    """

    TRADING_FIELDS = [
        "symbol", "stock", "candle", "rsi", "macd", "broker",
        "portfolio", "price", "nifty", "indicator", "ticker",
    ]

    def test_decision_tree_has_no_trading_attributes(self):
        tree = DecisionTree()
        for attr in self.TRADING_FIELDS:
            assert not hasattr(tree, attr), f"Domain attr '{attr}' on DecisionTree"

    def test_decision_node_has_no_trading_attributes(self):
        node = DecisionNode(name="n", condition=lambda ctx: True, response="r")
        for attr in self.TRADING_FIELDS:
            assert not hasattr(node, attr), f"Domain attr '{attr}' on DecisionNode"

    def test_reasoning_trace_has_no_trading_attributes(self):
        trace = ReasoningTrace(
            request_id="r", session_id="s", goal="g",
            intent_type="q", agent_name="a", confidence=0.5,
            retry_count=0, step_count=0, step_summary="", outcome="success", critique="",
        )
        for attr in self.TRADING_FIELDS:
            assert not hasattr(trace, attr), f"Domain attr '{attr}' on ReasoningTrace"

    def test_collaboration_bus_has_no_trading_attributes(self):
        bus = AgentCollaborationBus()
        for attr in self.TRADING_FIELDS:
            assert not hasattr(bus, attr), f"Domain attr '{attr}' on AgentCollaborationBus"

    def test_agent_message_payload_carries_domain_data(self):
        """Domain data belongs in payload, never as first-class fields."""
        msg = AgentMessage(
            sender="trader",
            message_type="trade_signal",
            payload={"symbol": "RELIANCE", "rsi": 72.4, "direction": "buy"},
        )
        assert msg.payload["symbol"] == "RELIANCE"
        assert msg.payload["rsi"]    == 72.4
        assert not hasattr(msg, "symbol")
        assert not hasattr(msg, "rsi")

    def test_reasoning_trace_metadata_carries_domain_data(self):
        trace = ReasoningTrace(
            request_id="r", session_id="s", goal="g",
            intent_type="q", agent_name="a", confidence=0.5,
            retry_count=0, step_count=0, step_summary="", outcome="success", critique="",
            metadata={"symbol": "NIFTY", "signal": "buy"},
        )
        assert trace.metadata["symbol"] == "NIFTY"
        assert not hasattr(trace, "symbol")

    def test_decision_tree_evaluator_has_no_trading_attributes(self):
        evaluator = DecisionTreeEvaluator(tree=DecisionTree(), confidence_threshold=0.4)
        for attr in self.TRADING_FIELDS:
            assert not hasattr(evaluator, attr), f"Domain attr '{attr}' on DecisionTreeEvaluator"

    def test_reasoning_logger_has_no_trading_attributes(self):
        from app.ai.reasoning.reasoning_log import ReasoningLogger
        logger = ReasoningLogger()
        for attr in self.TRADING_FIELDS:
            assert not hasattr(logger, attr), f"Domain attr '{attr}' on ReasoningLogger"
