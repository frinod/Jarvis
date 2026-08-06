"""
core/scheduler/scheduler.py
============================
Task Scheduler for the JARVIS Kernel.

Runs recurring async tasks on fixed intervals.
No external dependency -- pure asyncio.

Design principles
-----------------
  Interval-based -- run every N seconds
  Named tasks -- each task has a unique name for monitoring
  Error isolation -- one failing task never stops others
  Graceful shutdown -- all tasks cancelled cleanly on stop()
  Observable -- last_run, last_error, run_count per task
"""
from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional


@dataclass
class ScheduledTask:
    """One registered scheduled task."""
    name:        str
    fn:          Callable
    interval_s:  float
    enabled:     bool       = True
    run_count:   int        = 0
    last_run:    float      = 0.0    # monotonic timestamp
    last_error:  Optional[str] = None
    _handle:     Any        = field(default=None, repr=False)

    def to_dict(self) -> dict:
        return {
            "name":       self.name,
            "interval_s": self.interval_s,
            "enabled":    self.enabled,
            "run_count":  self.run_count,
            "last_error": self.last_error,
        }


class Scheduler:
    """
    Interval-based async task scheduler.

    Usage
    -----
        scheduler = Scheduler()

        @scheduler.every(60, name="refresh_quotes")
        async def refresh_quotes():
            await market_data.refresh()

        await scheduler.start()
        # ... runs in background ...
        await scheduler.stop()
    """

    def __init__(self) -> None:
        self._tasks:   Dict[str, ScheduledTask] = {}
        self._running: bool = False
        self._loop_tasks: List[asyncio.Task] = []

    def every(self, interval_s: float, name: str) -> Callable:
        """Decorator to register a recurring task."""
        def decorator(fn: Callable) -> Callable:
            self.register(name, fn, interval_s)
            return fn
        return decorator

    def register(
        self,
        name:       str,
        fn:         Callable,
        interval_s: float,
        enabled:    bool = True,
    ) -> "Scheduler":
        if interval_s <= 0:
            raise ValueError("interval_s must be positive")
        if not name.strip():
            raise ValueError("task name must not be empty")
        self._tasks[name] = ScheduledTask(
            name=name, fn=fn, interval_s=interval_s, enabled=enabled
        )
        return self

    async def start(self) -> None:
        """Start all enabled tasks as background asyncio tasks."""
        self._running = True
        for task in self._tasks.values():
            if task.enabled:
                loop_task = asyncio.ensure_future(self._run_loop(task))
                self._loop_tasks.append(loop_task)

    async def stop(self) -> None:
        """Cancel all running tasks and wait for them to finish."""
        self._running = False
        for t in self._loop_tasks:
            t.cancel()
        if self._loop_tasks:
            await asyncio.gather(*self._loop_tasks, return_exceptions=True)
        self._loop_tasks.clear()

    def get_task(self, name: str) -> Optional[ScheduledTask]:
        return self._tasks.get(name)

    def task_names(self) -> List[str]:
        return list(self._tasks.keys())

    def is_running(self) -> bool:
        return self._running

    def to_dict(self) -> dict:
        return {name: t.to_dict() for name, t in self._tasks.items()}

    async def _run_loop(self, task: ScheduledTask) -> None:
        while self._running:
            await asyncio.sleep(task.interval_s)
            if not self._running:
                break
            try:
                result = task.fn()
                if asyncio.iscoroutine(result):
                    await result
                task.run_count += 1
                task.last_run   = time.monotonic()
                task.last_error = None
            except Exception as exc:
                task.last_error = str(exc)
