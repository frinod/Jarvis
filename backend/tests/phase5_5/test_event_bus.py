"""
test_event_bus.py -- Task 5.5.5 validation
Tests for app/core/events/bus.py
"""
from __future__ import annotations

from dataclasses import dataclass
import pytest
from app.core.events import EventBus, Event, EventRecord


# ── Test event types ──────────────────────────────────────────

@dataclass
class PriceUpdated(Event):
    symbol: str = ""
    price:  float = 0.0

@dataclass
class OrderFilled(Event):
    order_id: str = ""

@dataclass
class SpecialPriceUpdated(PriceUpdated):
    """Subclass of PriceUpdated for inheritance tests."""
    pass


# ── Subscription ──────────────────────────────────────────────

class TestSubscription:

    def test_subscribe_decorator(self):
        bus = EventBus()
        @bus.subscribe(PriceUpdated)
        async def handler(e): pass
        assert bus.subscriber_count(PriceUpdated) == 1

    def test_add_subscriber_directly(self):
        bus = EventBus()
        async def handler(e): pass
        bus.add_subscriber(PriceUpdated, handler)
        assert bus.subscriber_count(PriceUpdated) == 1

    def test_duplicate_subscriber_not_added_twice(self):
        bus = EventBus()
        async def handler(e): pass
        bus.add_subscriber(PriceUpdated, handler)
        bus.add_subscriber(PriceUpdated, handler)
        assert bus.subscriber_count(PriceUpdated) == 1

    def test_multiple_subscribers_for_same_type(self):
        bus = EventBus()
        async def h1(e): pass
        async def h2(e): pass
        bus.add_subscriber(PriceUpdated, h1)
        bus.add_subscriber(PriceUpdated, h2)
        assert bus.subscriber_count(PriceUpdated) == 2

    def test_remove_subscriber(self):
        bus = EventBus()
        async def handler(e): pass
        bus.add_subscriber(PriceUpdated, handler)
        result = bus.remove_subscriber(PriceUpdated, handler)
        assert result is True
        assert bus.subscriber_count(PriceUpdated) == 0

    def test_remove_nonexistent_subscriber_returns_false(self):
        bus = EventBus()
        async def handler(e): pass
        result = bus.remove_subscriber(PriceUpdated, handler)
        assert result is False

    def test_clear_subscribers_for_type(self):
        bus = EventBus()
        async def h1(e): pass
        async def h2(e): pass
        bus.add_subscriber(PriceUpdated, h1)
        bus.add_subscriber(OrderFilled, h2)
        bus.clear_subscribers(PriceUpdated)
        assert bus.subscriber_count(PriceUpdated) == 0
        assert bus.subscriber_count(OrderFilled) == 1

    def test_clear_all_subscribers(self):
        bus = EventBus()
        async def h(e): pass
        bus.add_subscriber(PriceUpdated, h)
        bus.add_subscriber(OrderFilled, h)
        bus.clear_subscribers()
        assert bus.subscriber_count() == 0

    def test_subscribed_types_lists_active(self):
        bus = EventBus()
        async def h(e): pass
        bus.add_subscriber(PriceUpdated, h)
        bus.add_subscriber(OrderFilled, h)
        types = bus.subscribed_types()
        assert PriceUpdated in types
        assert OrderFilled  in types

    def test_decorator_returns_original_function(self):
        bus = EventBus()
        @bus.subscribe(PriceUpdated)
        async def my_handler(e): pass
        assert my_handler.__name__ == "my_handler"


# ── Publishing ────────────────────────────────────────────────

class TestPublishing:

    @pytest.mark.asyncio
    async def test_publish_calls_subscriber(self):
        bus = EventBus()
        received = []
        @bus.subscribe(PriceUpdated)
        async def handler(e: PriceUpdated):
            received.append(e.symbol)
        await bus.publish(PriceUpdated(source="test", symbol="RELIANCE", price=2500.0))
        assert received == ["RELIANCE"]

    @pytest.mark.asyncio
    async def test_publish_returns_subscriber_count(self):
        bus = EventBus()
        async def h1(e): pass
        async def h2(e): pass
        bus.add_subscriber(PriceUpdated, h1)
        bus.add_subscriber(PriceUpdated, h2)
        count = await bus.publish(PriceUpdated())
        assert count == 2

    @pytest.mark.asyncio
    async def test_publish_no_subscribers_returns_zero(self):
        bus = EventBus()
        count = await bus.publish(PriceUpdated())
        assert count == 0

    @pytest.mark.asyncio
    async def test_publish_calls_all_subscribers(self):
        bus = EventBus()
        calls = []
        async def h1(e): calls.append("h1")
        async def h2(e): calls.append("h2")
        bus.add_subscriber(PriceUpdated, h1)
        bus.add_subscriber(PriceUpdated, h2)
        await bus.publish(PriceUpdated())
        assert "h1" in calls
        assert "h2" in calls

    @pytest.mark.asyncio
    async def test_subscriber_error_does_not_propagate(self):
        bus = EventBus()
        @bus.subscribe(PriceUpdated)
        async def bad_handler(e):
            raise RuntimeError("subscriber crashed")
        # Must not raise
        count = await bus.publish(PriceUpdated())
        assert count == 1

    @pytest.mark.asyncio
    async def test_other_subscribers_run_after_one_fails(self):
        bus = EventBus()
        calls = []
        @bus.subscribe(PriceUpdated)
        async def bad(e): raise RuntimeError("crash")
        @bus.subscribe(PriceUpdated)
        async def good(e): calls.append("good")
        await bus.publish(PriceUpdated())
        assert "good" in calls

    @pytest.mark.asyncio
    async def test_wrong_event_type_not_delivered(self):
        bus = EventBus()
        received = []
        @bus.subscribe(OrderFilled)
        async def handler(e): received.append(e)
        await bus.publish(PriceUpdated())
        assert received == []


# ── Inheritance / MRO matching ────────────────────────────────

class TestInheritanceMatching:

    @pytest.mark.asyncio
    async def test_base_subscriber_receives_subclass_event(self):
        bus = EventBus()
        received = []
        @bus.subscribe(PriceUpdated)
        async def handler(e): received.append(type(e).__name__)
        await bus.publish(SpecialPriceUpdated(source="test"))
        assert "SpecialPriceUpdated" in received

    @pytest.mark.asyncio
    async def test_event_base_subscriber_receives_all(self):
        bus = EventBus()
        received = []
        @bus.subscribe(Event)
        async def catch_all(e): received.append(type(e).__name__)
        await bus.publish(PriceUpdated())
        await bus.publish(OrderFilled())
        assert "PriceUpdated" in received
        assert "OrderFilled"  in received

    @pytest.mark.asyncio
    async def test_subclass_subscriber_does_not_receive_parent_event(self):
        bus = EventBus()
        received = []
        @bus.subscribe(SpecialPriceUpdated)
        async def handler(e): received.append(e)
        await bus.publish(PriceUpdated())
        assert received == []


# ── History ───────────────────────────────────────────────────

class TestHistory:

    @pytest.mark.asyncio
    async def test_history_records_successful_dispatch(self):
        bus = EventBus()
        @bus.subscribe(PriceUpdated)
        async def handler(e): pass
        await bus.publish(PriceUpdated(source="test"))
        history = bus.history()
        assert len(history) == 1
        assert history[0].success is True

    @pytest.mark.asyncio
    async def test_history_records_failed_dispatch(self):
        bus = EventBus()
        @bus.subscribe(PriceUpdated)
        async def bad(e): raise RuntimeError("oops")
        await bus.publish(PriceUpdated())
        history = bus.history()
        assert history[0].success is False
        assert "oops" in history[0].error

    @pytest.mark.asyncio
    async def test_history_respects_max_size(self):
        bus = EventBus(history_size=3)
        @bus.subscribe(PriceUpdated)
        async def handler(e): pass
        for _ in range(5):
            await bus.publish(PriceUpdated())
        assert len(bus.history()) == 3

    def test_clear_history(self):
        bus = EventBus()
        bus.clear_history()
        assert bus.history() == []
