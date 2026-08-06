"""Unit tests for JARVIS OS core modules."""
import pytest
from datetime import datetime

from app.core.identity import JarvisCore, FocusState
from app.core.personality import PersonalityEngine, Emotion
from app.reasoning.engine import ReasoningEngine
from app.memory.manager import MemoryManager, MemoryType
from app.tools.registry import ToolRegistry
from app.agents.coordinator import AgentCoordinator, AgentTask, AgentRole
from app.security.manager import SecurityManager


class TestJarvisCore:
    def test_identity(self):
        core = JarvisCore()
        assert core.identity.name == "JARVIS"
        assert core.state.focus == FocusState.IDLE

    def test_focus_update(self):
        core = JarvisCore()
        core.update_focus(FocusState.THINKING, "test goal")
        assert core.state.focus == FocusState.THINKING
        assert core.state.current_goal == "test goal"

    def test_interaction_counter(self):
        core = JarvisCore()
        core.increment_interaction()
        core.increment_interaction()
        assert core.state.interaction_count == 2

    def test_reasoning_trace(self):
        core = JarvisCore()
        core.record_reasoning("step 1")
        assert len(core.state.reasoning_trace) == 1


class TestPersonality:
    def test_emotion_detection(self):
        engine = PersonalityEngine()
        state = engine.detect_emotion("I'm so frustrated with this!")
        assert state.detected_emotion == Emotion.FRUSTRATED

    def test_neutral_default(self):
        engine = PersonalityEngine()
        state = engine.detect_emotion("Tell me the time")
        assert state.detected_emotion == Emotion.NEUTRAL

    def test_response_modifiers(self):
        engine = PersonalityEngine()
        engine.detect_emotion("This is urgent and I'm stressed!")
        mods = engine.get_response_modifiers()
        assert mods["tone"] == "calm"


class TestReasoning:
    def test_think(self):
        engine = ReasoningEngine()
        step = engine.think("analyzing input", 0.9)
        assert step.confidence == 0.9

    def test_plan(self):
        engine = ReasoningEngine()
        plan = engine.create_plan("deploy app", ["build", "test", "deploy"])
        assert len(plan.steps) == 3

    def test_advance_plan(self):
        engine = ReasoningEngine()
        engine.create_plan("goal", ["a", "b"])
        step = engine.advance_plan()
        assert step == "a"
        step = engine.advance_plan()
        assert step == "b"
        step = engine.advance_plan()
        assert step is None

    def test_reflect(self):
        engine = ReasoningEngine()
        engine.think("test", 0.8)
        r = engine.reflect()
        assert r["total_thoughts"] == 1


@pytest.mark.asyncio
class TestMemory:
    async def test_remember_and_recall(self):
        manager = MemoryManager()
        await manager.remember("test fact", MemoryType.SEMANTIC, 0.8)
        results = await manager.recall("test")
        assert len(results) == 1

    async def test_short_term_summary(self):
        manager = MemoryManager()
        await manager.remember("episode 1", MemoryType.EPISODIC)
        summary = manager.get_short_term_summary()
        assert summary["total"] == 1


class TestTools:
    def test_registry(self):
        registry = ToolRegistry()
        tools = registry.list_tools()
        assert len(tools) >= 3

    @pytest.mark.asyncio
    async def test_read_file(self):
        registry = ToolRegistry()
        result = await registry.execute("read_file", confirmed=True, path=__file__)
        assert result.success

    @pytest.mark.asyncio
    async def test_requires_confirmation(self):
        registry = ToolRegistry()
        result = await registry.execute("write_file", confirmed=False, path="x", content="y")
        assert result.requires_confirmation


@pytest.mark.asyncio
class TestAgents:
    async def test_delegate(self):
        coord = AgentCoordinator()
        task = AgentTask(description="research AI", role=AgentRole.RESEARCH, context={})
        result = await coord.delegate(task)
        assert result["agent"] == "research"

    async def test_no_agent(self):
        coord = AgentCoordinator()
        task = AgentTask(description="x", role=AgentRole.CREATIVE, context={})
        result = await coord.delegate(task)
        assert "error" in result


class TestSecurity:
    def test_token_cycle(self):
        sm = SecurityManager()
        token = sm.create_token("user1")
        user = sm.verify_token(token)
        assert user == "user1"

    def test_approval_flow(self):
        sm = SecurityManager()
        aid = sm.request_approval("delete_file", {"path": "/tmp/x"})
        assert len(sm.get_pending_approvals()) == 1
        sm.approve(aid)
        assert len(sm.get_pending_approvals()) == 0
