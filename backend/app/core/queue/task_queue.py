"""
core/queue/task_queue.py
========================
Priority Task Queue for the JARVIS Kernel.

In-process async task queue with priority ordering and retry.
Used for deferred work that needs ordering guarantees.

Design principles
-----------------
  Priority-ordered -- lower number = processed first
  Retry-capable -- failed tasks re-queued up to max_retries
  Named tasks -- each task has a unique ID for tracking
  Bounded -- max_size prevents unbounded memory growth
"""
from __future__ import annotations

import asyncio
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional


class TaskStatus(str, Enum):
    PENDING    = "pending"
    RUNNING    = "running"
    DONE       = "done"
    FAILED     = "failed"
    RETRYING   = "retrying"


@dataclass(order=True)
class QueuedTask:
    """One task in the priority queue."""
    priority:    int
    task_id:     str          = field(compare=False)
    fn:          Callable     = field(compare=False)
    args:        tuple        = field(default_factory=tuple, compare=False)
    kwargs:      dict         = field(default_factory=dict, compare=False)
    max_retries: int          = field(default=0, compare=False)
    attempt:     int          = field(default=0, compare=False)
    status:      TaskStatus   = field(default=TaskStatus.PENDING, compare=False)
    error:       Optional[str] = field(default=None, compare=False)

    def to_dict(self) -> dict:
        return {
            "task_id":    self.task_id,
            "priority":   self.priority,
            "status":     self.status,
            "attempt":    self.attempt,
            "max_retries": self.max_retries,
            "error":      self.error,
        }


class TaskQueue:
    """
    Priority async task queue with retry support.

    Usage
    -----
        queue = TaskQueue(max_size=500)

        async def send_alert(symbol, message):
            await notifier.send(symbol, message)

        task_id = await queue.enqueue(
            send_alert, priority=1,
            args=("RELIANCE", "Price alert"),
            max_retries=3
        )

        await queue.start()
        await queue.stop()
    """

    def __init__(self, max_size: int = 1000) -> None:
        self._queue:   asyncio.PriorityQueue = asyncio.PriorityQueue(maxsize=max_size)
        self._tasks:   Dict[str, QueuedTask] = {}
        self._running: bool = False
        self._worker:  Optional[asyncio.Task] = None

    async def enqueue(
        self,
        fn:          Callable,
        priority:    int   = 50,
        args:        tuple = (),
        kwargs:      Optional[dict] = None,
        max_retries: int   = 0,
        task_id:     Optional[str] = None,
    ) -> str:
        """Enqueue a task. Returns the task_id."""
        tid = task_id or str(uuid.uuid4())[:8]
        task = QueuedTask(
            priority=priority, task_id=tid, fn=fn,
            args=args, kwargs=kwargs or {},
            max_retries=max_retries,
        )
        self._tasks[tid] = task
        await self._queue.put(task)
        return tid

    async def start(self) -> None:
        self._running = True
        self._worker  = asyncio.ensure_future(self._process_loop())

    async def stop(self) -> None:
        self._running = False
        if self._worker:
            self._worker.cancel()
            await asyncio.gather(self._worker, return_exceptions=True)
            self._worker = None

    def get_task(self, task_id: str) -> Optional[QueuedTask]:
        return self._tasks.get(task_id)

    def pending_count(self) -> int:
        return self._queue.qsize()

    def total_count(self) -> int:
        return len(self._tasks)

    def is_running(self) -> bool:
        return self._running

    def to_dict(self) -> dict:
        return {tid: t.to_dict() for tid, t in self._tasks.items()}

    async def _process_loop(self) -> None:
        while self._running:
            try:
                task = await asyncio.wait_for(self._queue.get(), timeout=0.1)
                task.status  = TaskStatus.RUNNING
                task.attempt += 1
                try:
                    result = task.fn(*task.args, **task.kwargs)
                    if asyncio.iscoroutine(result):
                        await result
                    task.status = TaskStatus.DONE
                except Exception as exc:
                    task.error = str(exc)
                    if task.attempt <= task.max_retries:
                        task.status = TaskStatus.RETRYING
                        await self._queue.put(task)
                    else:
                        task.status = TaskStatus.FAILED
                finally:
                    self._queue.task_done()
            except asyncio.TimeoutError:
                continue
            except asyncio.CancelledError:
                break
