"""
core/service_registry/registry.py
==================================
Service Registry for the JARVIS Kernel.

The registry is the kernel's service directory. Every named service
(broker provider, LLM provider, market data provider, etc.) registers
here. Consumers look up services by name or type without knowing
implementation details.

Relationship to DI container
-----------------------------
  DIContainer  -- resolves by type, manages lifecycle
  ServiceRegistry -- resolves by name, manages discovery

They are complementary. The DI container wires dependencies.
The service registry answers "which broker is active right now?"

Design principles
-----------------
  Name + type indexed -- look up by either
  Metadata-rich -- each entry carries tags, version, health status
  Plugin-ready -- entries can be registered at runtime by plugin loader
  Immutable entries -- once registered, metadata doesn't change
  Health slot -- mutable health status updated by health monitor

500-module test
---------------
  "Will this package still make sense when JARVIS has 500+ modules?"
  Yes. Every provider in the system registers here. The health monitor
  queries here. The plugin manager writes here. The DI container reads here.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Type


class ServiceStatus(str, Enum):
    UNKNOWN    = "unknown"
    STARTING   = "starting"
    HEALTHY    = "healthy"
    DEGRADED   = "degraded"
    UNHEALTHY  = "unhealthy"
    STOPPED    = "stopped"


@dataclass
class ServiceEntry:
    """
    One registered service entry.
    name:        unique string identifier (e.g. "angel_one", "gemini")
    service_type: the interface/base type this service implements
    instance:    the actual service object (may be None until started)
    tags:        arbitrary labels for filtering (e.g. {"broker", "live"})
    version:     semantic version string
    plugin_class: dotted import path (for plugin-loaded services)
    status:      mutable health status (updated by health monitor)
    metadata:    arbitrary key-value pairs for service-specific info
    """
    name:         str
    service_type: type
    instance:     Optional[Any]       = None
    tags:         Set[str]            = field(default_factory=set)
    version:      str                 = "0.0.0"
    plugin_class: str                 = ""
    status:       ServiceStatus       = ServiceStatus.UNKNOWN
    metadata:     Dict[str, Any]      = field(default_factory=dict)

    def is_healthy(self) -> bool:
        return self.status == ServiceStatus.HEALTHY

    def is_available(self) -> bool:
        return self.status in (ServiceStatus.HEALTHY, ServiceStatus.DEGRADED)

    def has_tag(self, tag: str) -> bool:
        return tag in self.tags

    def to_dict(self) -> dict:
        return {
            "name":         self.name,
            "service_type": self.service_type.__name__,
            "tags":         sorted(self.tags),
            "version":      self.version,
            "plugin_class": self.plugin_class,
            "status":       self.status,
            "has_instance": self.instance is not None,
            "metadata":     self.metadata,
        }


class ServiceRegistry:
    """
    Named service registry for the JARVIS Kernel.

    Usage
    -----
        registry = ServiceRegistry()

        # Register a service
        registry.register("gemini", LLMProvider, instance=gemini_provider,
                          tags={"llm", "cloud"}, version="2.0")

        # Look up by name
        entry = registry.get("gemini")

        # Look up by type
        providers = registry.get_by_type(LLMProvider)

        # Filter by tag
        cloud_llms = registry.get_by_tag("llm")

        # Update health status (called by health monitor)
        registry.set_status("gemini", ServiceStatus.HEALTHY)
    """

    def __init__(self) -> None:
        self._entries: Dict[str, ServiceEntry] = {}

    # ── Registration ──────────────────────────────────────────

    def register(
        self,
        name:         str,
        service_type: type,
        instance:     Optional[Any]  = None,
        tags:         Optional[Set[str]] = None,
        version:      str            = "0.0.0",
        plugin_class: str            = "",
        metadata:     Optional[Dict[str, Any]] = None,
    ) -> "ServiceRegistry":
        """
        Register a service. Overwrites any existing entry with the same name.
        """
        if not name.strip():
            raise ValueError("Service name must not be empty")
        self._entries[name] = ServiceEntry(
            name         = name,
            service_type = service_type,
            instance     = instance,
            tags         = tags or set(),
            version      = version,
            plugin_class = plugin_class,
            metadata     = metadata or {},
        )
        return self

    def unregister(self, name: str) -> bool:
        """Remove a service by name. Returns True if it existed."""
        return self._entries.pop(name, None) is not None

    # ── Lookup ────────────────────────────────────────────────

    def get(self, name: str) -> Optional[ServiceEntry]:
        """Look up a service entry by name."""
        return self._entries.get(name)

    def get_instance(self, name: str) -> Optional[Any]:
        """Return the service instance directly, or None."""
        entry = self._entries.get(name)
        return entry.instance if entry else None

    def get_by_type(self, service_type: type) -> List[ServiceEntry]:
        """Return all entries whose service_type is or inherits from service_type."""
        return [
            e for e in self._entries.values()
            if issubclass(e.service_type, service_type)
        ]

    def get_by_tag(self, tag: str) -> List[ServiceEntry]:
        """Return all entries that have the given tag."""
        return [e for e in self._entries.values() if e.has_tag(tag)]

    def get_healthy(self) -> List[ServiceEntry]:
        """Return all entries with HEALTHY status."""
        return [e for e in self._entries.values() if e.is_healthy()]

    def get_available(self) -> List[ServiceEntry]:
        """Return all entries that are HEALTHY or DEGRADED."""
        return [e for e in self._entries.values() if e.is_available()]

    # ── Health updates ────────────────────────────────────────

    def set_status(self, name: str, status: ServiceStatus) -> bool:
        """
        Update the health status of a registered service.
        Returns True if the service was found and updated.
        Called by the health monitor at runtime.
        """
        entry = self._entries.get(name)
        if entry is None:
            return False
        entry.status = status
        return True

    def set_instance(self, name: str, instance: Any) -> bool:
        """
        Attach a live instance to a registered entry.
        Called by the plugin loader after instantiation.
        Returns True if the service was found.
        """
        entry = self._entries.get(name)
        if entry is None:
            return False
        entry.instance = instance
        return True

    # ── Introspection ─────────────────────────────────────────

    def is_registered(self, name: str) -> bool:
        return name in self._entries

    def names(self) -> List[str]:
        return list(self._entries.keys())

    def count(self) -> int:
        return len(self._entries)

    def to_dict(self) -> dict:
        return {name: entry.to_dict() for name, entry in self._entries.items()}
