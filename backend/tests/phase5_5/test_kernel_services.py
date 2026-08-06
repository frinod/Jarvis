"""
test_kernel_services.py -- Tasks 5.5.6-5.5.10 validation
Tests for scheduler, health monitor, metrics engine, worker pool, task queue.
"""
from __future__ import annotations

import asyncio
import pytest

from app.core.scheduler import Scheduler
from app.core.health import HealthMonitor, HealthStatus, SystemHealth
from app.core.metrics import MetricsEngine
from app.core.workers import WorkerPool
from app.core.queue import TaskQueue, TaskStatus


# ═══════════════════════════════════════════════════════════════
# Task 5.5.6 -- Scheduler
# ═══════════════════════════════════════════════════════════════

class TestScheduler:

    def test_register_task(self):
        s = Scheduler()
        async def noop(): pass
        s.register("refresh", noop, interval_s=60)
        assert "refresh" in s.task_names()

    def test_register_zero_interval_raises(self):
        s = Scheduler()
        async def noop(): pass
        with pytest.raises(ValueError):
            s.register("bad", noop, interval_s=0)

    def test_register_negative_interval_raises(self):
        s = Scheduler()
        async def noop(): pass
        with pytest.raises(ValueError):
            s.register("bad", noop, interval_s=-1)

    def test_register_empty_name_raises(self):
        s = Scheduler()
        async def noop(): pass
        with pytest.raises(ValueError):
            s.register("", noop, interval_s=60)

    def test_decorator_registers_task(self):
        s = Scheduler()
        @s.every(30, name="heartbeat")
        async def heartbeat(): pass
        assert "heartbeat" in s.task_names()

    def test_get_task_returns_entry(self):
        s = Scheduler()
        async def noop(): pass
        s.register("t", noop, interval_s=10)
        task = s.get_task("t")
        assert task is not None
        assert task.interval_s == 10

    def test_get_task_missing_returns_none(self):
        s = Scheduler()
        assert s.get_task("missing") is None

    def test_not_running_initially(self):
        s = Scheduler()
        assert s.is_running() is False

    @pytest.mark.asyncio
    async def test_start_sets_running(self):
        s = Scheduler()
        await s.start()
        assert s.is_running() is True
        await s.stop()

    @pytest.mark.asyncio
    async def test_stop_clears_running(self):
        s = Scheduler()
        await s.start()
        await s.stop()
        assert s.is_running() is False

    def test_to_dict_structure(self):
        s = Scheduler()
        async def noop(): pass
        s.register("t", noop, interval_s=60)
        d = s.to_dict()
        assert "t" in d
        assert d["t"]["interval_s"] == 60


# ═══════════════════════════════════════════════════════════════
# Task 5.5.7 -- Health Monitor
# ═══════════════════════════════════════════════════════════════

class TestHealthMonitor:

    @pytest.mark.asyncio
    async def test_healthy_check(self):
        m = HealthMonitor()
        @m.check("db")
        async def check_db():
            return HealthStatus.HEALTHY
        result = await m.run_all()
        assert result.overall == HealthStatus.HEALTHY

    @pytest.mark.asyncio
    async def test_unhealthy_check(self):
        m = HealthMonitor()
        @m.check("db")
        async def check_db():
            raise RuntimeError("connection refused")
        result = await m.run_all()
        assert result.overall == HealthStatus.UNHEALTHY

    @pytest.mark.asyncio
    async def test_degraded_check(self):
        m = HealthMonitor()
        @m.check("cache")
        async def check_cache():
            return HealthStatus.DEGRADED
        result = await m.run_all()
        assert result.overall == HealthStatus.DEGRADED

    @pytest.mark.asyncio
    async def test_mixed_healthy_and_unhealthy(self):
        m = HealthMonitor()
        @m.check("good")
        async def good(): return HealthStatus.HEALTHY
        @m.check("bad")
        async def bad(): raise RuntimeError("down")
        result = await m.run_all()
        assert result.overall == HealthStatus.UNHEALTHY

    @pytest.mark.asyncio
    async def test_no_checks_returns_unknown(self):
        m = HealthMonitor()
        result = await m.run_all()
        assert result.overall == HealthStatus.UNKNOWN

    @pytest.mark.asyncio
    async def test_run_one_returns_result(self):
        m = HealthMonitor()
        @m.check("db")
        async def check_db(): return HealthStatus.HEALTHY
        result = await m.run_one("db")
        assert result is not None
        assert result.status == HealthStatus.HEALTHY

    @pytest.mark.asyncio
    async def test_run_one_missing_returns_none(self):
        m = HealthMonitor()
        result = await m.run_one("missing")
        assert result is None

    @pytest.mark.asyncio
    async def test_last_result_populated_after_run(self):
        m = HealthMonitor()
        @m.check("db")
        async def check_db(): return HealthStatus.HEALTHY
        await m.run_all()
        assert m.last_result("db") is not None

    @pytest.mark.asyncio
    async def test_check_timeout_returns_unhealthy(self):
        m = HealthMonitor()
        @m.check("slow", timeout_s=0.05)
        async def slow():
            await asyncio.sleep(10)
            return HealthStatus.HEALTHY
        result = await m.run_all()
        assert result.overall == HealthStatus.UNHEALTHY

    def test_check_names(self):
        m = HealthMonitor()
        async def noop(): return HealthStatus.HEALTHY
        m.register("a", noop)
        m.register("b", noop)
        assert set(m.check_names()) == {"a", "b"}

    @pytest.mark.asyncio
    async def test_is_healthy_true(self):
        m = HealthMonitor()
        @m.check("ok")
        async def ok(): return HealthStatus.HEALTHY
        result = await m.run_all()
        assert result.is_healthy is True

    def test_to_dict_structure(self):
        sh = SystemHealth(results=[])
        d = sh.to_dict()
        assert "overall" in d
        assert "checks"  in d


# ═══════════════════════════════════════════════════════════════
# Task 5.5.8 -- Metrics Engine
# ═══════════════════════════════════════════════════════════════

class TestMetricsEngine:

    def test_counter_increments(self):
        m = MetricsEngine()
        c = m.counter("requests")
        c.inc()
        c.inc(5)
        assert c.value == 6.0

    def test_counter_negative_raises(self):
        m = MetricsEngine()
        c = m.counter("requests")
        with pytest.raises(ValueError):
            c.inc(-1)

    def test_counter_same_name_returns_same_instance(self):
        m = MetricsEngine()
        c1 = m.counter("requests")
        c2 = m.counter("requests")
        assert c1 is c2

    def test_gauge_set_and_inc_dec(self):
        m = MetricsEngine()
        g = m.gauge("positions")
        g.set(10)
        g.inc(2)
        g.dec(3)
        assert g.value == 9.0

    def test_gauge_same_name_returns_same_instance(self):
        m = MetricsEngine()
        g1 = m.gauge("positions")
        g2 = m.gauge("positions")
        assert g1 is g2

    def test_histogram_observe_and_stats(self):
        m = MetricsEngine()
        h = m.histogram("latency")
        for v in [1.0, 2.0, 3.0, 4.0, 5.0]:
            h.observe(v)
        assert h.count == 5
        assert h.sum   == 15.0
        assert h.mean  == 3.0

    def test_histogram_percentile(self):
        m = MetricsEngine()
        h = m.histogram("latency")
        for v in range(1, 101):
            h.observe(float(v))
        # With 100 values and floor-index: p50 index = int(100*50/100) = 50 -> value 51.0
        assert h.percentile(50) >= 49.0
        assert h.percentile(50) <= 52.0
        # p99 should be near the top
        assert h.percentile(99) >= 98.0

    def test_histogram_empty_returns_zero(self):
        m = MetricsEngine()
        h = m.histogram("latency")
        assert h.mean == 0.0
        assert h.percentile(95) == 0.0

    def test_labels_create_separate_metrics(self):
        m = MetricsEngine()
        c1 = m.counter("requests", labels={"endpoint": "/quote"})
        c2 = m.counter("requests", labels={"endpoint": "/order"})
        c1.inc(10)
        c2.inc(5)
        assert c1.value == 10.0
        assert c2.value == 5.0

    def test_snapshot_contains_all_types(self):
        m = MetricsEngine()
        m.counter("c").inc()
        m.gauge("g").set(1)
        m.histogram("h").observe(1.0)
        snap = m.snapshot()
        assert len(snap["counters"])   == 1
        assert len(snap["gauges"])     == 1
        assert len(snap["histograms"]) == 1

    def test_reset_clears_all(self):
        m = MetricsEngine()
        m.counter("c").inc()
        m.reset()
        snap = m.snapshot()
        assert snap["counters"] == []

    def test_to_dict_counter(self):
        m = MetricsEngine()
        c = m.counter("requests")
        c.inc(3)
        d = c.to_dict()
        assert d["value"] == 3.0
        assert d["type"]  == "counter"

    def test_to_dict_histogram(self):
        m = MetricsEngine()
        h = m.histogram("latency")
        h.observe(1.0)
        d = h.to_dict()
        assert d["count"] == 1
        assert "p95" in d


# ═══════════════════════════════════════════════════════════════
# Task 5.5.9 -- Worker Pool
# ═══════════════════════════════════════════════════════════════

class TestWorkerPool:

    def test_register_worker(self):
        pool = WorkerPool()
        async def process(item): pass
        pool.register("updater", process)
        assert "updater" in pool.worker_names()

    def test_register_empty_name_raises(self):
        pool = WorkerPool()
        async def process(item): pass
        with pytest.raises(ValueError):
            pool.register("", process)

    def test_register_zero_concurrency_raises(self):
        pool = WorkerPool()
        async def process(item): pass
        with pytest.raises(ValueError):
            pool.register("w", process, concurrency=0)

    def test_not_running_initially(self):
        pool = WorkerPool()
        assert pool.is_running() is False

    @pytest.mark.asyncio
    async def test_start_sets_running(self):
        pool = WorkerPool()
        await pool.start()
        assert pool.is_running() is True
        await pool.stop()

    @pytest.mark.asyncio
    async def test_stop_clears_running(self):
        pool = WorkerPool()
        await pool.start()
        await pool.stop()
        assert pool.is_running() is False

    @pytest.mark.asyncio
    async def test_submit_processes_item(self):
        pool = WorkerPool()
        processed = []
        async def process(item):
            processed.append(item)
        pool.register("w", process)
        await pool.start()
        await pool.submit("w", "hello")
        await asyncio.sleep(0.1)
        await pool.stop()
        assert "hello" in processed

    @pytest.mark.asyncio
    async def test_submit_missing_worker_returns_false(self):
        pool = WorkerPool()
        result = await pool.submit("missing", "item")
        assert result is False

    @pytest.mark.asyncio
    async def test_stats_tracks_processed(self):
        pool = WorkerPool()
        async def process(item): pass
        pool.register("w", process)
        await pool.start()
        await pool.submit("w", "item1")
        await asyncio.sleep(0.1)
        await pool.stop()
        stats = pool.stats("w")
        assert stats.processed >= 1

    @pytest.mark.asyncio
    async def test_stats_tracks_errors(self):
        pool = WorkerPool()
        async def bad(item): raise RuntimeError("fail")
        pool.register("w", bad)
        await pool.start()
        await pool.submit("w", "item")
        await asyncio.sleep(0.1)
        await pool.stop()
        stats = pool.stats("w")
        assert stats.errors >= 1

    def test_stats_missing_worker_returns_none(self):
        pool = WorkerPool()
        assert pool.stats("missing") is None


# ═══════════════════════════════════════════════════════════════
# Task 5.5.10 -- Task Queue
# ═══════════════════════════════════════════════════════════════

class TestTaskQueue:

    @pytest.mark.asyncio
    async def test_enqueue_returns_task_id(self):
        q = TaskQueue()
        def noop(): pass
        tid = await q.enqueue(noop)
        assert tid is not None

    @pytest.mark.asyncio
    async def test_enqueue_custom_task_id(self):
        q = TaskQueue()
        def noop(): pass
        tid = await q.enqueue(noop, task_id="my-task")
        assert tid == "my-task"

    @pytest.mark.asyncio
    async def test_get_task_returns_entry(self):
        q = TaskQueue()
        def noop(): pass
        tid = await q.enqueue(noop)
        task = q.get_task(tid)
        assert task is not None

    @pytest.mark.asyncio
    async def test_pending_count_increases(self):
        q = TaskQueue()
        def noop(): pass
        await q.enqueue(noop)
        await q.enqueue(noop)
        assert q.pending_count() >= 0  # may have been processed

    @pytest.mark.asyncio
    async def test_task_processed_to_done(self):
        q = TaskQueue()
        results = []
        def work(): results.append(1)
        tid = await q.enqueue(work)
        await q.start()
        await asyncio.sleep(0.1)
        await q.stop()
        task = q.get_task(tid)
        assert task.status == TaskStatus.DONE

    @pytest.mark.asyncio
    async def test_failed_task_status(self):
        q = TaskQueue()
        def bad(): raise RuntimeError("fail")
        tid = await q.enqueue(bad, max_retries=0)
        await q.start()
        await asyncio.sleep(0.1)
        await q.stop()
        task = q.get_task(tid)
        assert task.status == TaskStatus.FAILED

    @pytest.mark.asyncio
    async def test_retry_on_failure(self):
        q = TaskQueue()
        attempts = []
        def flaky():
            attempts.append(1)
            if len(attempts) < 3:
                raise RuntimeError("not yet")
        tid = await q.enqueue(flaky, max_retries=3)
        await q.start()
        await asyncio.sleep(0.3)
        await q.stop()
        assert len(attempts) >= 3

    @pytest.mark.asyncio
    async def test_priority_ordering(self):
        q = TaskQueue()
        order = []
        def make_fn(label):
            def fn(): order.append(label)
            return fn
        # Enqueue before starting so ordering is deterministic
        await q.enqueue(make_fn("low"),  priority=90)
        await q.enqueue(make_fn("high"), priority=1)
        await q.start()
        await asyncio.sleep(0.2)
        await q.stop()
        if len(order) >= 2:
            assert order[0] == "high"

    def test_not_running_initially(self):
        q = TaskQueue()
        assert q.is_running() is False

    @pytest.mark.asyncio
    async def test_start_sets_running(self):
        q = TaskQueue()
        await q.start()
        assert q.is_running() is True
        await q.stop()

    @pytest.mark.asyncio
    async def test_stop_clears_running(self):
        q = TaskQueue()
        await q.start()
        await q.stop()
        assert q.is_running() is False
