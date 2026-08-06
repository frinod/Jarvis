"""
app/ai/tools/registry.py
=========================
AIToolRegistry -- tool registration, security, timeout, and error isolation.

Architecture §13 defines the tool calling contract:
  - Timeout enforcement
  - Error isolation (tool failure does not crash agent)
  - Metrics recording (call count, latency, error rate)
  - Security check (tool allowed for this agent role?)

Domain agnosticism
-------------------
  Tools are registered by name. No domain-specific tool types.
  Tool output is always a plain dict -- domain data lives there.
"""
from __future__ import annotations

import asyncio
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Set


# ── ToolResult ────────────────────────────────────────────────────────────────

@dataclass
class ToolResult:
    """Output of one tool call."""
    tool_name:  str
    success:    bool
    output:     Any
    error:      Optional[str] = None
    elapsed_ms: float         = 0.0
    metadata:   Dict[str, Any] = field(default_factory=dict)


# ── Tool ABC ──────────────────────────────────────────────────────────────────

class BaseTool(ABC):
    """
    Base contract for all JARVIS tools.
    Tools own external I/O (APIs, databases, file system).
    """
    name:        str       = "base_tool"
    description: str       = ""
    allowed_roles: Set[str] = field(default_factory=set)

    @abstractmethod
    async def call(self, params: dict) -> dict:
        """Execute the tool. Returns a plain dict result."""


# ── ToolMetrics ───────────────────────────────────────────────────────────────

@dataclass
class ToolMetrics:
    """Per-tool call statistics."""
    call_count:   int   = 0
    error_count:  int   = 0
    total_ms:     float = 0.0

    @property
    def error_rate(self) -> float:
        return round(self.error_count / self.call_count, 3) if self.call_count > 0 else 0.0

    @property
    def avg_latency_ms(self) -> float:
        return round(self.total_ms / self.call_count, 2) if self.call_count > 0 else 0.0


# ── AIToolRegistry ────────────────────────────────────────────────────────────

class AIToolRegistry:
    """
    Registers tools and enforces security, timeout, and error isolation.

    Usage
    -----
        registry = AIToolRegistry(default_timeout_s=5.0)
        registry.register(my_tool, allowed_roles={"analyst", "researcher"})
        result = await registry.call("my_tool", params={}, agent_role="analyst")
    """

    def __init__(self, default_timeout_s: float = 10.0):
        self._tools:   Dict[str, BaseTool]    = {}
        self._roles:   Dict[str, Set[str]]    = {}   # tool_name -> allowed roles
        self._metrics: Dict[str, ToolMetrics] = {}
        self._timeout  = default_timeout_s

    # ── Registration ──────────────────────────────────────────────────

    def register(
        self,
        tool:          BaseTool,
        allowed_roles: Optional[Set[str]] = None,
    ) -> None:
        """Register a tool. allowed_roles=None means all roles are permitted."""
        self._tools[tool.name]   = tool
        self._roles[tool.name]   = allowed_roles or set()
        self._metrics[tool.name] = ToolMetrics()

    def has(self, name: str) -> bool:
        return name in self._tools

    def names(self) -> List[str]:
        return list(self._tools.keys())

    # ── Security check ────────────────────────────────────────────────

    def is_allowed(self, tool_name: str, agent_role: str) -> bool:
        """Return True if agent_role is permitted to call tool_name."""
        if tool_name not in self._roles:
            return False
        allowed = self._roles[tool_name]
        return len(allowed) == 0 or agent_role in allowed   # empty set = all roles

    # ── Call ──────────────────────────────────────────────────────────

    async def call(
        self,
        tool_name:  str,
        params:     dict,
        agent_role: str = "",
        timeout_s:  Optional[float] = None,
    ) -> ToolResult:
        """
        Call a tool with security check, timeout, and error isolation.
        Never raises -- failures are captured in ToolResult.
        """
        start = time.monotonic()

        # Tool not found
        if tool_name not in self._tools:
            return ToolResult(
                tool_name=tool_name, success=False, output=None,
                error=f"Tool '{tool_name}' not registered",
            )

        # Security check
        if agent_role and not self.is_allowed(tool_name, agent_role):
            return ToolResult(
                tool_name=tool_name, success=False, output=None,
                error=f"Role '{agent_role}' not permitted to call '{tool_name}'",
            )

        tool    = self._tools[tool_name]
        metrics = self._metrics[tool_name]
        timeout = timeout_s or self._timeout

        try:
            output = await asyncio.wait_for(tool.call(params), timeout=timeout)
            elapsed = (time.monotonic() - start) * 1000
            metrics.call_count += 1
            metrics.total_ms   += elapsed
            return ToolResult(
                tool_name=tool_name, success=True, output=output,
                elapsed_ms=round(elapsed, 2),
            )
        except asyncio.TimeoutError:
            elapsed = (time.monotonic() - start) * 1000
            metrics.call_count  += 1
            metrics.error_count += 1
            metrics.total_ms    += elapsed
            return ToolResult(
                tool_name=tool_name, success=False, output=None,
                error="timeout", elapsed_ms=round(elapsed, 2),
            )
        except Exception as exc:
            elapsed = (time.monotonic() - start) * 1000
            metrics.call_count  += 1
            metrics.error_count += 1
            metrics.total_ms    += elapsed
            return ToolResult(
                tool_name=tool_name, success=False, output=None,
                error=str(exc), elapsed_ms=round(elapsed, 2),
            )

    # ── Metrics ───────────────────────────────────────────────────────

    def metrics(self, tool_name: str) -> Optional[ToolMetrics]:
        return self._metrics.get(tool_name)

    def all_metrics(self) -> Dict[str, ToolMetrics]:
        return dict(self._metrics)
