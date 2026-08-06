"""
tests/phase6/test_6d_tools.py
================================
Unit tests for AIToolRegistry (Task 6D.7).

Covers: BaseTool contract, ToolResult, AIToolRegistry registration,
        security check, timeout, error isolation, metrics.
"""
import asyncio
import pytest

from app.ai.tools.registry import AIToolRegistry, BaseTool, ToolResult, ToolMetrics


# ── Concrete tools for testing ────────────────────────────────────────────────

class _EchoTool(BaseTool):
    name        = "echo"
    description = "Returns input as output"

    async def call(self, params: dict) -> dict:
        return {"echo": params.get("message", "")}


class _FailingTool(BaseTool):
    name = "failing"

    async def call(self, params: dict) -> dict:
        raise RuntimeError("tool exploded")


class _SlowTool(BaseTool):
    name = "slow"

    async def call(self, params: dict) -> dict:
        await asyncio.sleep(10)   # will always timeout in tests
        return {}


# ── TestToolResult ────────────────────────────────────────────────────────────

class TestToolResult:

    def test_construction(self):
        r = ToolResult(tool_name="echo", success=True, output={"result": "x"})
        assert r.tool_name == "echo"
        assert r.success   is True

    def test_error_field(self):
        r = ToolResult(tool_name="t", success=False, output=None, error="timeout")
        assert r.error == "timeout"

    def test_elapsed_ms_default(self):
        r = ToolResult(tool_name="t", success=True, output=None)
        assert r.elapsed_ms == 0.0

    def test_metadata_default_empty(self):
        r = ToolResult(tool_name="t", success=True, output=None)
        assert r.metadata == {}


# ── TestToolMetrics ───────────────────────────────────────────────────────────

class TestToolMetrics:

    def test_error_rate_zero_on_fresh(self):
        m = ToolMetrics()
        assert m.error_rate == 0.0

    def test_avg_latency_zero_on_fresh(self):
        m = ToolMetrics()
        assert m.avg_latency_ms == 0.0

    def test_error_rate_computed(self):
        m = ToolMetrics(call_count=4, error_count=1)
        assert m.error_rate == 0.25

    def test_avg_latency_computed(self):
        m = ToolMetrics(call_count=2, total_ms=100.0)
        assert m.avg_latency_ms == 50.0


# ── TestAIToolRegistry ────────────────────────────────────────────────────────

class TestAIToolRegistry:

    def test_register_and_has(self):
        registry = AIToolRegistry()
        registry.register(_EchoTool())
        assert registry.has("echo") is True

    def test_names_returns_list(self):
        registry = AIToolRegistry()
        registry.register(_EchoTool())
        assert "echo" in registry.names()

    @pytest.mark.asyncio
    async def test_call_success(self):
        registry = AIToolRegistry()
        registry.register(_EchoTool())
        result = await registry.call("echo", {"message": "hello"})
        assert result.success is True
        assert result.output  == {"echo": "hello"}

    @pytest.mark.asyncio
    async def test_call_missing_tool_returns_failed_result(self):
        registry = AIToolRegistry()
        result   = await registry.call("nonexistent", {})
        assert result.success is False
        assert "not registered" in result.error

    @pytest.mark.asyncio
    async def test_call_exception_is_isolated(self):
        registry = AIToolRegistry()
        registry.register(_FailingTool())
        result = await registry.call("failing", {})
        assert result.success is False
        assert "tool exploded" in result.error

    @pytest.mark.asyncio
    async def test_call_timeout_returns_failed_result(self):
        registry = AIToolRegistry(default_timeout_s=0.01)
        registry.register(_SlowTool())
        result = await registry.call("slow", {})
        assert result.success is False
        assert result.error   == "timeout"

    @pytest.mark.asyncio
    async def test_security_check_allowed_role(self):
        registry = AIToolRegistry()
        registry.register(_EchoTool(), allowed_roles={"analyst"})
        result = await registry.call("echo", {}, agent_role="analyst")
        assert result.success is True

    @pytest.mark.asyncio
    async def test_security_check_denied_role(self):
        registry = AIToolRegistry()
        registry.register(_EchoTool(), allowed_roles={"analyst"})
        result = await registry.call("echo", {}, agent_role="trader")
        assert result.success is False
        assert "not permitted" in result.error

    @pytest.mark.asyncio
    async def test_empty_allowed_roles_permits_all(self):
        registry = AIToolRegistry()
        registry.register(_EchoTool(), allowed_roles=set())
        result = await registry.call("echo", {}, agent_role="any_role")
        assert result.success is True

    @pytest.mark.asyncio
    async def test_no_role_check_when_agent_role_empty(self):
        registry = AIToolRegistry()
        registry.register(_EchoTool(), allowed_roles={"analyst"})
        result = await registry.call("echo", {}, agent_role="")
        assert result.success is True

    def test_is_allowed_returns_bool(self):
        registry = AIToolRegistry()
        registry.register(_EchoTool(), allowed_roles={"analyst"})
        assert registry.is_allowed("echo", "analyst") is True
        assert registry.is_allowed("echo", "trader")  is False

    @pytest.mark.asyncio
    async def test_metrics_recorded_on_success(self):
        registry = AIToolRegistry()
        registry.register(_EchoTool())
        await registry.call("echo", {})
        m = registry.metrics("echo")
        assert m.call_count == 1
        assert m.error_count == 0

    @pytest.mark.asyncio
    async def test_metrics_recorded_on_failure(self):
        registry = AIToolRegistry()
        registry.register(_FailingTool())
        await registry.call("failing", {})
        m = registry.metrics("failing")
        assert m.call_count  == 1
        assert m.error_count == 1

    def test_metrics_returns_none_for_unknown_tool(self):
        registry = AIToolRegistry()
        assert registry.metrics("unknown") is None

    def test_all_metrics_returns_dict(self):
        registry = AIToolRegistry()
        registry.register(_EchoTool())
        all_m = registry.all_metrics()
        assert "echo" in all_m
        assert isinstance(all_m["echo"], ToolMetrics)
