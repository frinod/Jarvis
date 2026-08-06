"""
test_lifecycle.py -- Task 5.5.3 validation
Tests for app/core/lifecycle/manager.py
"""
from __future__ import annotations

import pytest
from app.core.lifecycle import LifecycleManager, LifecycleState, HookResult


# ── Initial state ─────────────────────────────────────────────

class TestInitialState:

    def test_initial_state_is_created(self):
        lm = LifecycleManager()
        assert lm.state == LifecycleState.CREATED

    def test_is_running_false_initially(self):
        lm = LifecycleManager()
        assert lm.is_running is False

    def test_no_hooks_initially(self):
        lm = LifecycleManager()
        assert lm.startup_hook_names() == []
        assert lm.shutdown_hook_names() == []


# ── Hook registration ─────────────────────────────────────────

class TestHookRegistration:

    def test_register_startup_hook(self):
        lm = LifecycleManager()
        async def noop(): pass
        lm.register_startup("init", noop)
        assert "init" in lm.startup_hook_names()

    def test_register_shutdown_hook(self):
        lm = LifecycleManager()
        async def noop(): pass
        lm.register_shutdown("cleanup", noop)
        assert "cleanup" in lm.shutdown_hook_names()

    def test_decorator_registers_startup(self):
        lm = LifecycleManager()
        @lm.on_startup("init_db", priority=10)
        async def init_db(): pass
        assert "init_db" in lm.startup_hook_names()

    def test_decorator_registers_shutdown(self):
        lm = LifecycleManager()
        @lm.on_shutdown("close_db", priority=10)
        async def close_db(): pass
        assert "close_db" in lm.shutdown_hook_names()

    def test_decorator_returns_original_function(self):
        lm = LifecycleManager()
        @lm.on_startup("init")
        async def my_fn(): return 42
        assert my_fn.__name__ == "my_fn"

    def test_startup_hooks_ordered_by_priority(self):
        lm = LifecycleManager()
        async def noop(): pass
        lm.register_startup("c", noop, priority=30)
        lm.register_startup("a", noop, priority=10)
        lm.register_startup("b", noop, priority=20)
        assert lm.startup_hook_names() == ["a", "b", "c"]

    def test_shutdown_hooks_ordered_reverse_priority(self):
        lm = LifecycleManager()
        async def noop(): pass
        lm.register_shutdown("a", noop, priority=10)
        lm.register_shutdown("b", noop, priority=20)
        lm.register_shutdown("c", noop, priority=30)
        # shutdown runs highest priority first (reverse)
        assert lm.shutdown_hook_names() == ["c", "b", "a"]


# ── Startup execution ─────────────────────────────────────────

class TestStartup:

    @pytest.mark.asyncio
    async def test_startup_sets_state_to_running(self):
        lm = LifecycleManager()
        await lm.startup()
        assert lm.state == LifecycleState.RUNNING

    @pytest.mark.asyncio
    async def test_startup_runs_hooks_in_order(self):
        lm = LifecycleManager()
        order = []
        async def first():  order.append("first")
        async def second(): order.append("second")
        lm.register_startup("second", second, priority=20)
        lm.register_startup("first",  first,  priority=10)
        await lm.startup()
        assert order == ["first", "second"]

    @pytest.mark.asyncio
    async def test_startup_returns_hook_results(self):
        lm = LifecycleManager()
        async def noop(): pass
        lm.register_startup("init", noop)
        results = await lm.startup()
        assert len(results) == 1
        assert results[0].name == "init"
        assert results[0].success is True

    @pytest.mark.asyncio
    async def test_startup_result_has_duration(self):
        lm = LifecycleManager()
        async def noop(): pass
        lm.register_startup("init", noop)
        results = await lm.startup()
        assert results[0].duration_s >= 0.0

    @pytest.mark.asyncio
    async def test_startup_is_running_after_success(self):
        lm = LifecycleManager()
        await lm.startup()
        assert lm.is_running is True

    @pytest.mark.asyncio
    async def test_required_hook_failure_raises(self):
        lm = LifecycleManager()
        async def bad_hook():
            raise RuntimeError("DB connection failed")
        lm.register_startup("init_db", bad_hook, required=True)
        with pytest.raises(RuntimeError, match="init_db"):
            await lm.startup()

    @pytest.mark.asyncio
    async def test_required_hook_failure_sets_failed_state(self):
        lm = LifecycleManager()
        async def bad_hook():
            raise ValueError("oops")
        lm.register_startup("bad", bad_hook, required=True)
        try:
            await lm.startup()
        except RuntimeError:
            pass
        assert lm.state == LifecycleState.FAILED

    @pytest.mark.asyncio
    async def test_optional_hook_failure_does_not_abort(self):
        lm = LifecycleManager()
        async def bad_hook():
            raise RuntimeError("optional failure")
        async def good_hook(): pass
        lm.register_startup("optional", bad_hook, required=False, priority=10)
        lm.register_startup("required", good_hook, required=True, priority=20)
        results = await lm.startup()
        assert lm.state == LifecycleState.RUNNING
        assert any(r.name == "optional" and not r.success for r in results)

    @pytest.mark.asyncio
    async def test_hook_timeout_recorded_as_failure(self):
        lm = LifecycleManager()
        async def slow_hook():
            import asyncio
            await asyncio.sleep(10)
        lm.register_startup("slow", slow_hook, timeout_s=0.05, required=False)
        results = await lm.startup()
        slow = next(r for r in results if r.name == "slow")
        assert slow.success is False
        assert "Timed out" in slow.error

    @pytest.mark.asyncio
    async def test_no_hooks_startup_succeeds(self):
        lm = LifecycleManager()
        results = await lm.startup()
        assert results == []
        assert lm.state == LifecycleState.RUNNING


# ── Shutdown execution ────────────────────────────────────────

class TestShutdown:

    @pytest.mark.asyncio
    async def test_shutdown_sets_state_to_stopped(self):
        lm = LifecycleManager()
        await lm.startup()
        await lm.shutdown()
        assert lm.state == LifecycleState.STOPPED

    @pytest.mark.asyncio
    async def test_shutdown_runs_hooks_in_reverse_order(self):
        lm = LifecycleManager()
        order = []
        async def first():  order.append("first")
        async def second(): order.append("second")
        lm.register_shutdown("first",  first,  priority=10)
        lm.register_shutdown("second", second, priority=20)
        await lm.startup()
        await lm.shutdown()
        assert order == ["second", "first"]

    @pytest.mark.asyncio
    async def test_shutdown_continues_after_hook_failure(self):
        lm = LifecycleManager()
        order = []
        async def bad():  raise RuntimeError("cleanup failed")
        async def good(): order.append("good")
        lm.register_shutdown("bad",  bad,  priority=20)
        lm.register_shutdown("good", good, priority=10)
        await lm.startup()
        results = await lm.shutdown()
        assert order == ["good"]
        assert any(r.name == "bad" and not r.success for r in results)

    @pytest.mark.asyncio
    async def test_shutdown_never_raises(self):
        lm = LifecycleManager()
        async def always_fails(): raise RuntimeError("always")
        lm.register_shutdown("fail", always_fails)
        await lm.startup()
        # Must not raise
        await lm.shutdown()
        assert lm.state == LifecycleState.STOPPED

    @pytest.mark.asyncio
    async def test_shutdown_results_accessible(self):
        lm = LifecycleManager()
        async def noop(): pass
        lm.register_shutdown("cleanup", noop)
        await lm.startup()
        await lm.shutdown()
        assert len(lm.shutdown_results) == 1
        assert lm.shutdown_results[0].name == "cleanup"


# ── HookResult ────────────────────────────────────────────────

class TestHookResult:

    def test_to_dict_structure(self):
        r = HookResult(name="init", success=True, duration_s=0.123)
        d = r.to_dict()
        assert d["name"]       == "init"
        assert d["success"]    is True
        assert d["duration_s"] == 0.123
        assert d["error"]      is None

    def test_to_dict_with_error(self):
        r = HookResult(name="bad", success=False, duration_s=0.5, error="oops")
        d = r.to_dict()
        assert d["error"] == "oops"
