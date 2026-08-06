"""
core/lifecycle/manager.py
==========================
Lifecycle Manager for the JARVIS Kernel.

Manages ordered startup and shutdown of all kernel services.
Every service that needs initialisation registers a startup hook.
Every service that needs cleanup registers a shutdown hook.

The lifecycle manager guarantees:
  - Startup hooks run in priority order (lower number = earlier)
  - Shutdown hooks run in reverse priority order
  - A failed startup hook stops the boot sequence
  - Shutdown always runs even if startup partially failed
  - Each hook has a timeout to prevent hangs

Design principles
-----------------
  Priority-ordered -- database before cache before broker before AI
  Fail-fast on startup -- one bad hook aborts the sequence
  Best-effort on shutdown -- all hooks run even if some fail
  Async-native -- all hooks are async callables
  Observable -- emits lifecycle events for monitoring

500-module test
---------------
  "Will this package still make sense when JARVIS has 500+ modules?"
  Yes. Every service in the kernel registers here. The lifecycle
  manager is the kernel's boot sequence. It never grows beyond
  this single responsibility.
"""
from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional


class LifecycleState(str, Enum):
    CREATED   = "created"
    STARTING  = "starting"
    RUNNING   = "running"
    STOPPING  = "stopping"
    STOPPED   = "stopped"
    FAILED    = "failed"


@dataclass
class HookResult:
    """Result of executing one lifecycle hook."""
    name:       str
    success:    bool
    duration_s: float
    error:      Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "name":       self.name,
            "success":    self.success,
            "duration_s": round(self.duration_s, 4),
            "error":      self.error,
        }


@dataclass
class LifecycleHook:
    """One registered startup or shutdown hook."""
    name:       str
    fn:         Callable[[], Any]
    priority:   int   = 50      # lower = runs earlier on startup
    timeout_s:  float = 30.0
    required:   bool  = True    # if True, failure aborts startup


class LifecycleManager:
    """
    Ordered startup and shutdown manager for the JARVIS Kernel.

    Usage
    -----
        lm = LifecycleManager()

        @lm.on_startup("init_db", priority=10)
        async def init_db():
            await db.connect()

        @lm.on_shutdown("close_db", priority=10)
        async def close_db():
            await db.disconnect()

        await lm.startup()
        # ... application runs ...
        await lm.shutdown()
    """

    def __init__(self) -> None:
        self._startup_hooks:  List[LifecycleHook] = []
        self._shutdown_hooks: List[LifecycleHook] = []
        self._state:          LifecycleState      = LifecycleState.CREATED
        self._startup_results:  List[HookResult]  = []
        self._shutdown_results: List[HookResult]  = []

    # ── Registration ──────────────────────────────────────────

    def on_startup(
        self,
        name:      str,
        priority:  int   = 50,
        timeout_s: float = 30.0,
        required:  bool  = True,
    ) -> Callable:
        """Decorator to register an async startup hook."""
        def decorator(fn: Callable) -> Callable:
            self.register_startup(name, fn, priority, timeout_s, required)
            return fn
        return decorator

    def on_shutdown(
        self,
        name:      str,
        priority:  int   = 50,
        timeout_s: float = 30.0,
    ) -> Callable:
        """Decorator to register an async shutdown hook."""
        def decorator(fn: Callable) -> Callable:
            self.register_shutdown(name, fn, priority, timeout_s)
            return fn
        return decorator

    def register_startup(
        self,
        name:      str,
        fn:        Callable,
        priority:  int   = 50,
        timeout_s: float = 30.0,
        required:  bool  = True,
    ) -> "LifecycleManager":
        """Register a startup hook directly."""
        self._startup_hooks.append(
            LifecycleHook(name=name, fn=fn, priority=priority,
                          timeout_s=timeout_s, required=required)
        )
        return self

    def register_shutdown(
        self,
        name:      str,
        fn:        Callable,
        priority:  int   = 50,
        timeout_s: float = 30.0,
    ) -> "LifecycleManager":
        """Register a shutdown hook directly."""
        self._shutdown_hooks.append(
            LifecycleHook(name=name, fn=fn, priority=priority,
                          timeout_s=timeout_s, required=False)
        )
        return self

    # ── Execution ─────────────────────────────────────────────

    async def startup(self) -> List[HookResult]:
        """
        Run all startup hooks in priority order.
        Raises RuntimeError if a required hook fails.
        Returns list of HookResult for all hooks that ran.
        """
        self._state = LifecycleState.STARTING
        self._startup_results = []

        ordered = sorted(self._startup_hooks, key=lambda h: h.priority)

        for hook in ordered:
            result = await self._run_hook(hook)
            self._startup_results.append(result)
            if not result.success and hook.required:
                self._state = LifecycleState.FAILED
                raise RuntimeError(
                    f"Required startup hook '{hook.name}' failed: {result.error}"
                )

        self._state = LifecycleState.RUNNING
        return self._startup_results

    async def shutdown(self) -> List[HookResult]:
        """
        Run all shutdown hooks in reverse priority order.
        Never raises -- all hooks run even if some fail.
        Returns list of HookResult for all hooks that ran.
        """
        self._state = LifecycleState.STOPPING
        self._shutdown_results = []

        ordered = sorted(self._shutdown_hooks, key=lambda h: h.priority, reverse=True)

        for hook in ordered:
            result = await self._run_hook(hook)
            self._shutdown_results.append(result)
            # shutdown never aborts -- continue even on failure

        self._state = LifecycleState.STOPPED
        return self._shutdown_results

    # ── Introspection ─────────────────────────────────────────

    @property
    def state(self) -> LifecycleState:
        return self._state

    @property
    def is_running(self) -> bool:
        return self._state == LifecycleState.RUNNING

    @property
    def startup_results(self) -> List[HookResult]:
        return list(self._startup_results)

    @property
    def shutdown_results(self) -> List[HookResult]:
        return list(self._shutdown_results)

    def startup_hook_names(self) -> List[str]:
        return [h.name for h in sorted(self._startup_hooks, key=lambda h: h.priority)]

    def shutdown_hook_names(self) -> List[str]:
        return [h.name for h in sorted(self._shutdown_hooks, key=lambda h: h.priority, reverse=True)]

    # ── Internal ──────────────────────────────────────────────

    async def _run_hook(self, hook: LifecycleHook) -> HookResult:
        start = time.monotonic()
        try:
            coro = hook.fn()
            if asyncio.iscoroutine(coro):
                await asyncio.wait_for(coro, timeout=hook.timeout_s)
            duration = time.monotonic() - start
            return HookResult(name=hook.name, success=True, duration_s=duration)
        except asyncio.TimeoutError:
            duration = time.monotonic() - start
            return HookResult(
                name=hook.name, success=False, duration_s=duration,
                error=f"Timed out after {hook.timeout_s}s"
            )
        except Exception as exc:
            duration = time.monotonic() - start
            return HookResult(
                name=hook.name, success=False, duration_s=duration,
                error=str(exc)
            )
