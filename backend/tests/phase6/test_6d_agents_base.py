"""
tests/phase6/test_6d_agents_base.py
=====================================
Unit tests for BaseAgent ABC (Task 6D.1).

Covers: AgentStatus, AgentPlan, AgentResult, VerificationResult,
        BaseAgent contract enforcement, lifecycle, metrics.
"""
import pytest

from app.ai.agents.base import (
    AgentStatus, AgentPlan, AgentResult, VerificationResult, BaseAgent,
)
from app.ai.runtime.context import ExecutionContext


# ── Minimal concrete agent for testing ───────────────────────────────────────

class _MinimalAgent(BaseAgent):
    name         = "minimal"
    version      = "1.0.0"
    capabilities = ["general"]

    def can_handle(self, context):
        return True

    async def plan(self, context):
        return AgentPlan(steps=["step 1", "step 2"], estimated_confidence=0.7)

    async def execute(self, context):
        return AgentResult(agent_name=self.name, response="done", confidence=0.8)

    async def verify(self, result):
        return VerificationResult(passed=True, critique="ok")

    def confidence(self, result):
        return result.confidence

    def explain(self, result):
        return "minimal explanation"

    async def learn(self, result, outcome):
        pass


def _ctx(user_input="hello"):
    ctx = ExecutionContext(user_input=user_input)
    ctx.active_goal = user_input
    return ctx


# ── TestAgentDataclasses ──────────────────────────────────────────────────────

class TestAgentDataclasses:

    def test_agent_plan_construction(self):
        p = AgentPlan(steps=["a", "b"], estimated_confidence=0.7)
        assert p.steps == ["a", "b"]
        assert p.estimated_confidence == 0.7

    def test_agent_plan_metadata_default_empty(self):
        p = AgentPlan(steps=[])
        assert p.metadata == {}

    def test_agent_result_construction(self):
        r = AgentResult(agent_name="test", response="hello", confidence=0.8)
        assert r.agent_name  == "test"
        assert r.response    == "hello"
        assert r.confidence  == 0.8
        assert r.success     is True

    def test_agent_result_failure(self):
        r = AgentResult(agent_name="test", response="", confidence=0.0,
                        success=False, error="timeout")
        assert r.success is False
        assert r.error   == "timeout"

    def test_agent_result_metadata_default_empty(self):
        r = AgentResult(agent_name="t", response="", confidence=0.0)
        assert r.metadata == {}

    def test_verification_result_construction(self):
        v = VerificationResult(passed=True, critique="clean")
        assert v.passed  is True
        assert v.retry   is False

    def test_verification_result_retry_flag(self):
        v = VerificationResult(passed=False, critique="low conf", retry=True)
        assert v.retry is True

    def test_agent_status_values(self):
        assert AgentStatus.HEALTHY.value      == "healthy"
        assert AgentStatus.DEGRADED.value     == "degraded"
        assert AgentStatus.OFFLINE.value      == "offline"
        assert AgentStatus.INITIALISING.value == "initialising"


# ── TestBaseAgentContract ─────────────────────────────────────────────────────

class TestBaseAgentContract:

    def test_abstract_class_cannot_be_instantiated(self):
        with pytest.raises(TypeError):
            BaseAgent()

    def test_concrete_agent_instantiates(self):
        agent = _MinimalAgent()
        assert agent is not None

    def test_name_attribute(self):
        agent = _MinimalAgent()
        assert agent.name == "minimal"

    def test_version_attribute(self):
        agent = _MinimalAgent()
        assert agent.version == "1.0.0"

    def test_capabilities_attribute(self):
        agent = _MinimalAgent()
        assert "general" in agent.capabilities

    def test_can_handle_returns_bool(self):
        agent = _MinimalAgent()
        assert agent.can_handle(_ctx()) is True

    @pytest.mark.asyncio
    async def test_plan_returns_agent_plan(self):
        agent = _MinimalAgent()
        plan  = await agent.plan(_ctx())
        assert isinstance(plan, AgentPlan)
        assert len(plan.steps) >= 1

    @pytest.mark.asyncio
    async def test_execute_returns_agent_result(self):
        agent  = _MinimalAgent()
        result = await agent.execute(_ctx())
        assert isinstance(result, AgentResult)
        assert result.agent_name == "minimal"

    @pytest.mark.asyncio
    async def test_verify_returns_verification_result(self):
        agent  = _MinimalAgent()
        result = await agent.execute(_ctx())
        vr     = await agent.verify(result)
        assert isinstance(vr, VerificationResult)

    def test_confidence_returns_float(self):
        agent  = _MinimalAgent()
        result = AgentResult(agent_name="minimal", response="x", confidence=0.75)
        assert agent.confidence(result) == 0.75

    def test_explain_returns_string(self):
        agent  = _MinimalAgent()
        result = AgentResult(agent_name="minimal", response="x", confidence=0.75)
        assert isinstance(agent.explain(result), str)

    @pytest.mark.asyncio
    async def test_learn_does_not_raise(self):
        agent  = _MinimalAgent()
        result = AgentResult(agent_name="minimal", response="x", confidence=0.75)
        await agent.learn(result, {"outcome": "success"})   # must not raise


# ── TestBaseAgentLifecycle ────────────────────────────────────────────────────

class TestBaseAgentLifecycle:

    def test_initial_status_is_initialising(self):
        agent = _MinimalAgent()
        assert agent.health_check() == AgentStatus.INITIALISING

    def test_initialize_sets_healthy(self):
        agent = _MinimalAgent()
        agent.initialize()
        assert agent.health_check() == AgentStatus.HEALTHY

    def test_shutdown_sets_offline(self):
        agent = _MinimalAgent()
        agent.initialize()
        agent.shutdown()
        assert agent.health_check() == AgentStatus.OFFLINE

    def test_stats_structure(self):
        agent = _MinimalAgent()
        agent.initialize()
        s = agent.stats()
        assert s["name"]         == "minimal"
        assert s["version"]      == "1.0.0"
        assert s["status"]       == "healthy"
        assert "capabilities"    in s
        assert "requests"        in s
        assert "errors"          in s
        assert "error_rate"      in s

    def test_record_request_increments_count(self):
        agent = _MinimalAgent()
        agent.record_request(success=True)
        agent.record_request(success=True)
        assert agent.stats()["requests"] == 2

    def test_record_request_failure_increments_errors(self):
        agent = _MinimalAgent()
        agent.record_request(success=False)
        s = agent.stats()
        assert s["errors"]     == 1
        assert s["error_rate"] == 1.0

    def test_error_rate_zero_on_fresh_agent(self):
        agent = _MinimalAgent()
        assert agent.stats()["error_rate"] == 0.0

    def test_mixed_requests_error_rate(self):
        agent = _MinimalAgent()
        agent.record_request(success=True)
        agent.record_request(success=False)
        assert agent.stats()["error_rate"] == 0.5
