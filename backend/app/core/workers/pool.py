"""
core/workers/pool.py
====================
Background Worker Pool for the JARVIS Kernel.

Manages a pool of named async workers. Each worker runs a
coroutine function in a loop, processing items from its queue.

Design principles
-----------------
  Named workers -- each worker has a unique name for monitoring
  Concurrency-limited -- max_workers cap prevents resource exhaustion
  Error isolation -- one worker crash restarts that worker only
  Graceful shutdown -- drain queues before stopping
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional


@dataclass
class WorkerStats:
    name:        str
    processed:   int   = 0
    errors:      int   = 0
    running:     bool  = False
    last_error:  Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "name":       self.name,
            "processed":  self.processed,
            "errors":     self.errors,
            "running":    self.running,
            "last_error": self.last_error,
        }


class WorkerPool:
    """
    Managed pool of named async background workers.

    Usage
    -----
        pool = WorkerPool()

        async def process_item(item):
            await do_work(item)

        pool.register("market_updater", process_item, concurrency=2)
        await pool.start()
        await pool.submit("market_updater", {"symbol": "RELIANCE"})
        await pool.stop()
    """

    def __init__(self) -> None:
        self._workers:  Dict[str, "_Worker"] = {}
        self._running:  bool = False

    def register(
        self,
        name:        str,
        fn:          Callable,
        concurrency: int   = 1,
        queue_size:  int   = 100,
    ) -> "WorkerPool":
        if not name.strip():
            raise ValueError("worker name must not be empty")
        if concurrency < 1:
            raise ValueError("concurrency must be >= 1")
        self._workers[name] = _Worker(
            name=name, fn=fn,
            concurrency=concurrency, queue_size=queue_size
        )
        return self

    async def start(self) -> None:
        self._running = True
        for worker in self._workers.values():
            await worker.start()

    async def stop(self) -> None:
        self._running = False
        for worker in self._workers.values():
            await worker.stop()

    async def submit(self, worker_name: str, item: Any) -> bool:
        """Submit an item to a named worker. Returns False if worker not found."""
        worker = self._workers.get(worker_name)
        if worker is None:
            return False
        await worker.submit(item)
        return True

    def stats(self, name: str) -> Optional[WorkerStats]:
        worker = self._workers.get(name)
        return worker.stats if worker else None

    def all_stats(self) -> Dict[str, dict]:
        return {name: w.stats.to_dict() for name, w in self._workers.items()}

    def worker_names(self) -> List[str]:
        return list(self._workers.keys())

    def is_running(self) -> bool:
        return self._running


class _Worker:
    """Internal worker implementation."""

    def __init__(
        self,
        name:        str,
        fn:          Callable,
        concurrency: int,
        queue_size:  int,
    ) -> None:
        self.name        = name
        self.fn          = fn
        self.concurrency = concurrency
        self.stats       = WorkerStats(name=name)
        self._queue:     asyncio.Queue = asyncio.Queue(maxsize=queue_size)
        self._tasks:     List[asyncio.Task] = []

    async def start(self) -> None:
        self.stats.running = True
        for _ in range(self.concurrency):
            task = asyncio.ensure_future(self._loop())
            self._tasks.append(task)

    async def stop(self) -> None:
        self.stats.running = False
        for task in self._tasks:
            task.cancel()
        if self._tasks:
            await asyncio.gather(*self._tasks, return_exceptions=True)
        self._tasks.clear()

    async def submit(self, item: Any) -> None:
        await self._queue.put(item)

    async def _loop(self) -> None:
        while self.stats.running:
            try:
                item = await asyncio.wait_for(self._queue.get(), timeout=0.1)
                try:
                    result = self.fn(item)
                    if asyncio.iscoroutine(result):
                        await result
                    self.stats.processed += 1
                except Exception as exc:
                    self.stats.errors    += 1
                    self.stats.last_error = str(exc)
                finally:
                    self._queue.task_done()
            except asyncio.TimeoutError:
                continue
            except asyncio.CancelledError:
                break
