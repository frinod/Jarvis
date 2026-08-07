"""
app/ai/memory/memory_health.py
===============================
MemoryHealthMonitor -- health state machine for the memory layer.

States and allowed transitions (ADR-002):

    Healthy ──► Degraded ──► Offline ──► Recovering ──► Healthy
                    │                         │
                    └──────────────────────► Offline

Forbidden transitions:
    Healthy    → Recovering  (must degrade first)
    Offline    → Healthy     (must recover first)

Brain reads .state to adjust retrieval strategy per ADR-002:
    Healthy    → full semantic search, top-k retrieval
    Degraded   → top-5 retrieval only, no reranking
    Offline    → skip retrieval, return fallback
    Recovering → use in-process cache only
"""
from __future__ import annotations

import logging
import time
from enum import Enum
from typing import Callable, List, Optional

logger = logging.getLogger(__name__)


# ── States ────────────────────────────────────────────────────────────────────

class MemoryHealthState(str, Enum):
    HEALTHY    = "healthy"
    DEGRADED   = "degraded"
    OFFLINE    = "offline"
    RECOVERING = "recovering"


# Allowed transitions: {from_state: {allowed_to_states}}
_ALLOWED: dict = {
    MemoryHealthState.HEALTHY:    {MemoryHealthState.DEGRADED},
    MemoryHealthState.DEGRADED:   {MemoryHealthState.HEALTHY, MemoryHealthState.OFFLINE},
    MemoryHealthState.OFFLINE:    {MemoryHealthState.RECOVERING},
    MemoryHealthState.RECOVERING: {MemoryHealthState.HEALTHY, MemoryHealthState.OFFLINE},
}


# ── Event ─────────────────────────────────────────────────────────────────────

class MemoryHealthEvent:
    """Emitted on every state transition."""
    __slots__ = ("from_state", "to_state", "reason", "timestamp")

    def __init__(
        self,
        from_state: MemoryHealthState,
        to_state:   MemoryHealthState,
        reason:     str = "",
    ) -> None:
        self.from_state = from_state
        self.to_state   = to_state
        self.reason     = reason
        self.timestamp  = time.time()


# ── Monitor ───────────────────────────────────────────────────────────────────

class MemoryHealthMonitor:
    """
    Deterministic state machine for memory layer health.

    Thread-safe for reads. Transitions are synchronous and logged.
    Observers are called synchronously after each transition.

    Usage
    -----
        monitor = MemoryHealthMonitor()
        monitor.record_failure("qdrant timeout")
        monitor.record_failure("qdrant timeout")
        assert monitor.state == MemoryHealthState.DEGRADED

        monitor.record_failure("qdrant unreachable")
        assert monitor.state == MemoryHealthState.OFFLINE

        monitor.begin_recovery()
        assert monitor.state == MemoryHealthState.RECOVERING

        monitor.record_success()
        assert monitor.state == MemoryHealthState.HEALTHY
    """

    # Consecutive failures before transitioning Healthy → Degraded
    FAILURES_TO_DEGRADE = 2
    # Consecutive failures before transitioning Degraded → Offline
    FAILURES_TO_OFFLINE = 3
    # Consecutive successes before transitioning Recovering → Healthy
    SUCCESSES_TO_RECOVER = 2

    def __init__(self) -> None:
        self._state:            MemoryHealthState = MemoryHealthState.HEALTHY
        self._consecutive_fail: int               = 0
        self._consecutive_ok:   int               = 0
        self._history:          List[MemoryHealthEvent] = []
        self._observers:        List[Callable[[MemoryHealthEvent], None]] = []

    # ── Public state ──────────────────────────────────────────────────

    @property
    def state(self) -> MemoryHealthState:
        return self._state

    @property
    def is_available(self) -> bool:
        """True when memory can be used (Healthy or Degraded)."""
        return self._state in (MemoryHealthState.HEALTHY, MemoryHealthState.DEGRADED)

    @property
    def use_cache_only(self) -> bool:
        """True when only in-process cache should be used (Recovering)."""
        return self._state == MemoryHealthState.RECOVERING

    # ── Signal methods ────────────────────────────────────────────────

    def record_success(self) -> None:
        """Call after a successful Qdrant operation."""
        self._consecutive_fail = 0
        self._consecutive_ok  += 1

        if self._state == MemoryHealthState.RECOVERING:
            if self._consecutive_ok >= self.SUCCESSES_TO_RECOVER:
                self._transition(MemoryHealthState.HEALTHY, "consecutive successes during recovery")
        elif self._state == MemoryHealthState.DEGRADED:
            if self._consecutive_ok >= self.SUCCESSES_TO_RECOVER:
                self._transition(MemoryHealthState.HEALTHY, "consecutive successes")

    def record_failure(self, reason: str = "") -> None:
        """Call after a failed or timed-out Qdrant operation."""
        self._consecutive_ok   = 0
        self._consecutive_fail += 1

        if self._state == MemoryHealthState.HEALTHY:
            if self._consecutive_fail >= self.FAILURES_TO_DEGRADE:
                self._transition(MemoryHealthState.DEGRADED, reason or "consecutive failures")

        elif self._state == MemoryHealthState.DEGRADED:
            if self._consecutive_fail >= self.FAILURES_TO_OFFLINE:
                self._transition(MemoryHealthState.OFFLINE, reason or "consecutive failures while degraded")

        elif self._state == MemoryHealthState.RECOVERING:
            self._transition(MemoryHealthState.OFFLINE, reason or "failure during recovery")

    def begin_recovery(self) -> None:
        """Call when Qdrant becomes reachable again after being Offline."""
        if self._state == MemoryHealthState.OFFLINE:
            self._consecutive_fail = 0
            self._consecutive_ok   = 0
            self._transition(MemoryHealthState.RECOVERING, "recovery probe succeeded")

    # ── Observer ──────────────────────────────────────────────────────

    def add_observer(self, fn: Callable[[MemoryHealthEvent], None]) -> None:
        """Register a callback invoked on every state transition."""
        self._observers.append(fn)

    # ── History ───────────────────────────────────────────────────────

    def history(self) -> List[MemoryHealthEvent]:
        return list(self._history)

    def last_event(self) -> Optional[MemoryHealthEvent]:
        return self._history[-1] if self._history else None

    # ── Internal ──────────────────────────────────────────────────────

    def _transition(self, to: MemoryHealthState, reason: str) -> None:
        allowed = _ALLOWED.get(self._state, set())
        if to not in allowed:
            logger.warning(
                "MemoryHealthMonitor: forbidden transition %s → %s ignored",
                self._state.value, to.value,
            )
            return

        event = MemoryHealthEvent(from_state=self._state, to_state=to, reason=reason)
        logger.info(
            "MemoryHealth: %s → %s (%s)",
            self._state.value, to.value, reason,
        )
        self._state = to
        self._history.append(event)
        for obs in self._observers:
            try:
                obs(event)
            except Exception:
                pass  # observers must never crash the state machine
