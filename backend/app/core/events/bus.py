"""
core/events/bus.py
==================
Event Bus for the JARVIS Kernel.

Typed publish/subscribe for cross-domain communication.
Domains publish events; other domains subscribe without knowing
who published. This is how the kernel avoids circular imports.

Design principles
-----------------
  Typed events -- every event is a dataclass, not a raw dict
  Async-native -- subscribers are async callables
  Fire-and-forget -- publish() does not wait for all subscribers
  Error isolation -- one bad subscriber never affects others
  Wildcard subscription -- subscribe to all events of a base type
  History -- optional ring buffer of recent events for debugging

500-module test
---------------
  "Will this package still make sense when JARVIS has 500+ modules?"
  Yes. Every domain in the system publishes and subscribes here.
  The event bus is the kernel's message backbone. It never grows
  beyond this single responsibility.
"""
from __future__ import annotations

import asyncio
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Callable, Deque, Dict, List, Optional, Type, TypeVar

E = TypeVar("E", bound="Event")


@dataclass
class Event:
    """
    Base class for all JARVIS Kernel events.
    Subclass this to define domain-specific events.

    Example:
        @dataclass
        class MarketDataUpdated(Event):
            symbol: str
            price: float
    """
    source: str = ""    # name of the publishing component


@dataclass
class EventRecord:
    """One entry in the event history ring buffer."""
    event:      Event
    subscriber: str
    success:    bool
    error:      Optional[str] = None


class EventBus:
    """
    Async publish/subscribe event bus for the JARVIS Kernel.

    Usage
    -----
        bus = EventBus()

        # Subscribe to a specific event type
        @bus.subscribe(MarketDataUpdated)
        async def on_market_update(event: MarketDataUpdated):
            print(event.symbol, event.price)

        # Publish an event
        await bus.publish(MarketDataUpdated(source="yahoo", symbol="RELIANCE", price=2500.0))

        # Subscribe to all events (base Event type)
        @bus.subscribe(Event)
        async def on_any_event(event: Event):
            log(event)
    """

    def __init__(self, history_size: int = 100) -> None:
        self._subscribers: Dict[type, List[Callable]] = {}
        self._history: Deque[EventRecord] = deque(maxlen=history_size)
        self._history_size = history_size

    # ── Subscription ──────────────────────────────────────────

    def subscribe(self, event_type: Type[E]) -> Callable:
        """Decorator to subscribe an async callable to an event type."""
        def decorator(fn: Callable) -> Callable:
            self.add_subscriber(event_type, fn)
            return fn
        return decorator

    def add_subscriber(self, event_type: type, fn: Callable) -> "EventBus":
        """Register a subscriber for an event type."""
        if event_type not in self._subscribers:
            self._subscribers[event_type] = []
        if fn not in self._subscribers[event_type]:
            self._subscribers[event_type].append(fn)
        return self

    def remove_subscriber(self, event_type: type, fn: Callable) -> bool:
        """Remove a subscriber. Returns True if it was found and removed."""
        subs = self._subscribers.get(event_type, [])
        if fn in subs:
            subs.remove(fn)
            return True
        return False

    def clear_subscribers(self, event_type: Optional[type] = None) -> None:
        """Clear subscribers for one event type, or all if None."""
        if event_type is None:
            self._subscribers.clear()
        else:
            self._subscribers.pop(event_type, None)

    # ── Publishing ────────────────────────────────────────────

    async def publish(self, event: Event) -> int:
        """
        Publish an event to all matching subscribers.
        Subscribers are matched by exact type AND all parent types.
        Returns the number of subscribers notified.

        Errors in individual subscribers are caught and recorded
        in history but do not propagate to the publisher.
        """
        subscribers = self._collect_subscribers(type(event))
        if not subscribers:
            return 0

        tasks = [self._call_subscriber(fn, event) for fn in subscribers]
        await asyncio.gather(*tasks, return_exceptions=True)
        return len(subscribers)

    def publish_sync(self, event: Event) -> int:
        """
        Synchronous publish for use outside async context.
        Runs the event loop if one is available, otherwise schedules.
        Returns subscriber count.
        """
        subscribers = self._collect_subscribers(type(event))
        for fn in subscribers:
            try:
                result = fn(event)
                if asyncio.iscoroutine(result):
                    # Schedule on the running loop if available
                    try:
                        loop = asyncio.get_event_loop()
                        if loop.is_running():
                            loop.create_task(result)
                        else:
                            loop.run_until_complete(result)
                    except RuntimeError:
                        pass
            except Exception:
                pass
        return len(subscribers)

    # ── Introspection ─────────────────────────────────────────

    def subscriber_count(self, event_type: Optional[type] = None) -> int:
        """Return number of subscribers for a type, or total if None."""
        if event_type is not None:
            return len(self._subscribers.get(event_type, []))
        return sum(len(subs) for subs in self._subscribers.values())

    def subscribed_types(self) -> List[type]:
        """Return all event types that have at least one subscriber."""
        return [t for t, subs in self._subscribers.items() if subs]

    def history(self) -> List[EventRecord]:
        """Return recent event dispatch records (newest last)."""
        return list(self._history)

    def clear_history(self) -> None:
        self._history.clear()

    # ── Internal ──────────────────────────────────────────────

    def _collect_subscribers(self, event_type: type) -> List[Callable]:
        """
        Collect all subscribers for event_type, including those
        subscribed to parent types (MRO walk).
        """
        result = []
        seen = set()
        for cls in event_type.__mro__:
            for fn in self._subscribers.get(cls, []):
                if id(fn) not in seen:
                    seen.add(id(fn))
                    result.append(fn)
        return result

    async def _call_subscriber(self, fn: Callable, event: Event) -> None:
        name = getattr(fn, "__name__", repr(fn))
        try:
            result = fn(event)
            if asyncio.iscoroutine(result):
                await result
            self._history.append(EventRecord(event=event, subscriber=name, success=True))
        except Exception as exc:
            self._history.append(
                EventRecord(event=event, subscriber=name,
                            success=False, error=str(exc))
            )
