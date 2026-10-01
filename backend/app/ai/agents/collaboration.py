"""
app/ai/agents/collaboration.py
================================
AgentCollaborationBus -- in-pipeline agent message passing.

Design
------
  - AgentMessage: typed message from one agent to another (or broadcast).
  - AgentCollaborationBus: in-memory message bus scoped to one pipeline run.
    Agents publish messages; other agents subscribe by message_type.
  - CollaborationContext: thin wrapper that attaches a bus to an
    ExecutionContext without modifying ExecutionContext itself.
  - Pure in-memory, synchronous -- no network, no persistence.
    Messages are discarded when the pipeline run ends.

Purpose
-------
  Enables multi-agent coordination within one request:
    - TraderAgent publishes a TradeSignal
    - AnalystAgent reads it and enriches its analysis
    - PlannerAgent reads both and produces a coordinated plan
  Without this, agents are isolated and cannot share intermediate results.

Resilience (Rule 11b):
  publish() and subscribe() never raise.
  get_messages() returns [] on any failure.

Domain agnosticism:
  AgentMessage.payload is Dict[str, Any] -- no domain fields.
  message_type is a plain string -- no enums.
"""
from __future__ import annotations

import logging
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from app.ai.runtime.context import ExecutionContext

logger = logging.getLogger(__name__)

_BUS_KEY = "_collaboration_bus"


# ── AgentMessage ──────────────────────────────────────────────────────────────

@dataclass
class AgentMessage:
    """
    One message from one agent to another (or broadcast).

    sender:       name of the publishing agent
    recipient:    name of the target agent, or "*" for broadcast
    message_type: semantic type, e.g. "trade_signal", "analysis_result"
    payload:      arbitrary data (domain data goes here, not as fields)
    timestamp:    epoch seconds at publish time
    message_id:   unique identifier for deduplication
    """
    sender:       str
    message_type: str
    payload:      Dict[str, Any]  = field(default_factory=dict)
    recipient:    str             = "*"
    timestamp:    float           = field(default_factory=time.time)
    message_id:   str             = field(default_factory=lambda: str(uuid.uuid4()))


# ── AgentCollaborationBus ─────────────────────────────────────────────────────

class AgentCollaborationBus:
    """
    In-memory message bus scoped to one pipeline run.

    Agents publish messages; other agents retrieve by message_type
    or by recipient. Messages are never persisted -- they exist only
    for the duration of one ExecutionEngine.run() call.

    Usage
    -----
        bus = AgentCollaborationBus()
        bus.publish(AgentMessage(sender="trader", message_type="trade_signal",
                                 payload={"direction": "buy", "confidence": 0.82}))
        signals = bus.get_messages(message_type="trade_signal")
    """

    def __init__(self) -> None:
        self._messages: List[AgentMessage] = []

    def publish(self, message: AgentMessage) -> None:
        """Publish a message to the bus. Never raises."""
        try:
            self._messages.append(message)
        except Exception as exc:
            logger.debug("AgentCollaborationBus.publish failed: %s", exc)

    def get_messages(
        self,
        message_type: Optional[str] = None,
        recipient:    Optional[str] = None,
        sender:       Optional[str] = None,
    ) -> List[AgentMessage]:
        """
        Retrieve messages matching the given filters.
        All filters are ANDed. Returns [] on any failure.
        recipient filter matches both exact name and broadcast ("*").
        """
        try:
            msgs = self._messages
            if message_type is not None:
                msgs = [m for m in msgs if m.message_type == message_type]
            if recipient is not None:
                msgs = [m for m in msgs if m.recipient in (recipient, "*")]
            if sender is not None:
                msgs = [m for m in msgs if m.sender == sender]
            return list(msgs)
        except Exception as exc:
            logger.debug("AgentCollaborationBus.get_messages failed: %s", exc)
            return []

    def latest(
        self,
        message_type: str,
        recipient:    Optional[str] = None,
    ) -> Optional[AgentMessage]:
        """Return the most recent message of the given type, or None."""
        msgs = self.get_messages(message_type=message_type, recipient=recipient)
        return msgs[-1] if msgs else None

    def clear(self) -> None:
        """Remove all messages. Called between pipeline runs."""
        self._messages.clear()

    @property
    def message_count(self) -> int:
        return len(self._messages)


# ── CollaborationContext ──────────────────────────────────────────────────────

class CollaborationContext:
    """
    Attaches an AgentCollaborationBus to an ExecutionContext without
    modifying ExecutionContext itself.

    The bus is stored in ctx.metadata[_BUS_KEY] so it travels through
    the pipeline automatically. Agents retrieve it via get_bus(ctx).

    Usage
    -----
        # At pipeline start (ExecutionEngine or Brain):
        CollaborationContext.attach(ctx)

        # In any agent:
        bus = CollaborationContext.get_bus(ctx)
        if bus:
            bus.publish(AgentMessage(...))
    """

    @staticmethod
    def attach(ctx: ExecutionContext, bus: Optional[AgentCollaborationBus] = None) -> AgentCollaborationBus:
        """
        Attach a bus to ctx. Creates a new bus if none provided.
        Returns the attached bus.
        """
        if bus is None:
            bus = AgentCollaborationBus()
        ctx.metadata[_BUS_KEY] = bus
        return bus

    @staticmethod
    def get_bus(ctx: ExecutionContext) -> Optional[AgentCollaborationBus]:
        """
        Retrieve the bus from ctx. Returns None if not attached.
        Never raises.
        """
        try:
            return ctx.metadata.get(_BUS_KEY)
        except Exception:
            return None

    @staticmethod
    def is_attached(ctx: ExecutionContext) -> bool:
        """Return True if a bus is attached to ctx."""
        return _BUS_KEY in ctx.metadata
