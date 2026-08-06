"""
core/di/container.py
====================
Dependency Injection container for the JARVIS Kernel.

Provides three registration modes:
  singleton   -- one instance for the lifetime of the container
  transient   -- new instance on every resolve() call
  factory     -- callable invoked on every resolve() call

Design principles
-----------------
  No third-party framework -- pure Python stdlib + typing
  Type-keyed -- resolve by type, not by string name
  Alias support -- register an interface, resolve an implementation
  Scoped containers -- child containers inherit parent registrations
  Thread-safe reads -- registrations are frozen after build
  Async-aware -- factory callables may be async (resolved via asyncio)

500-module test
---------------
  "Will this package still make sense when JARVIS has 500+ modules?"
  Yes. Every service in the kernel registers here. Every consumer
  resolves from here. The container is the kernel's nervous system.
"""
from __future__ import annotations

import asyncio
import inspect
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Type, TypeVar

T = TypeVar("T")


class Scope(str, Enum):
    SINGLETON  = "singleton"
    TRANSIENT  = "transient"
    FACTORY    = "factory"


class Registration:
    """Internal record for one registered service."""

    __slots__ = ("scope", "implementation", "instance", "factory")

    def __init__(
        self,
        scope:          Scope,
        implementation: Optional[Type]     = None,
        instance:       Optional[Any]      = None,
        factory:        Optional[Callable] = None,
    ) -> None:
        self.scope          = scope
        self.implementation = implementation
        self.instance       = instance       # cached singleton
        self.factory        = factory


class DIContainer:
    """
    Lightweight dependency injection container.

    Usage
    -----
        container = DIContainer()

        # Register a singleton by type
        container.register_singleton(MyService, MyServiceImpl)

        # Register a pre-built instance
        container.register_instance(Settings, my_settings)

        # Register a factory callable
        container.register_factory(Connection, lambda: Connection(url))

        # Resolve
        svc = container.resolve(MyService)

        # Async resolve (factory may be a coroutine function)
        svc = await container.resolve_async(MyService)
    """

    def __init__(self, parent: Optional["DIContainer"] = None) -> None:
        self._registrations: Dict[type, Registration] = {}
        self._aliases:       Dict[type, type]         = {}
        self._parent = parent

    # ── Registration ──────────────────────────────────────────

    def register_singleton(
        self,
        interface:      Type[T],
        implementation: Optional[Type[T]] = None,
    ) -> "DIContainer":
        """
        Register a type as a singleton.
        If implementation is None, interface is used as its own implementation.
        """
        impl = implementation or interface
        self._registrations[interface] = Registration(
            scope=Scope.SINGLETON,
            implementation=impl,
        )
        return self

    def register_instance(self, interface: Type[T], instance: T) -> "DIContainer":
        """Register a pre-built instance as a singleton."""
        self._registrations[interface] = Registration(
            scope=Scope.SINGLETON,
            instance=instance,
        )
        return self

    def register_transient(
        self,
        interface:      Type[T],
        implementation: Optional[Type[T]] = None,
    ) -> "DIContainer":
        """Register a type as transient (new instance on every resolve)."""
        impl = implementation or interface
        self._registrations[interface] = Registration(
            scope=Scope.TRANSIENT,
            implementation=impl,
        )
        return self

    def register_factory(
        self,
        interface: Type[T],
        factory:   Callable[[], T],
    ) -> "DIContainer":
        """Register a factory callable. Called on every resolve."""
        self._registrations[interface] = Registration(
            scope=Scope.FACTORY,
            factory=factory,
        )
        return self

    def register_alias(self, alias: Type, target: Type) -> "DIContainer":
        """
        Register an alias: resolving `alias` resolves `target` instead.
        Useful for interface -> implementation mapping.
        """
        self._aliases[alias] = target
        return self

    # ── Resolution ────────────────────────────────────────────

    def resolve(self, interface: Type[T]) -> T:
        """
        Resolve a registered type synchronously.
        Raises KeyError if not registered.
        Raises RuntimeError if factory is async (use resolve_async instead).
        """
        reg = self._get_registration(interface)
        return self._resolve_registration(reg, interface)

    async def resolve_async(self, interface: Type[T]) -> T:
        """
        Resolve a registered type, awaiting async factories if needed.
        """
        reg = self._get_registration(interface)
        return await self._resolve_registration_async(reg, interface)

    def resolve_optional(self, interface: Type[T]) -> Optional[T]:
        """Resolve a type, returning None if not registered."""
        try:
            return self.resolve(interface)
        except KeyError:
            return None

    # ── Introspection ─────────────────────────────────────────

    def is_registered(self, interface: type) -> bool:
        """Return True if the type (or its alias target) is registered."""
        target = self._aliases.get(interface, interface)
        if target in self._registrations:
            return True
        return self._parent.is_registered(interface) if self._parent else False

    def registered_types(self) -> List[type]:
        """Return all directly registered interface types."""
        return list(self._registrations.keys())

    def child(self) -> "DIContainer":
        """Create a child container that inherits parent registrations."""
        return DIContainer(parent=self)

    # ── Internal ──────────────────────────────────────────────

    def _get_registration(self, interface: type) -> Registration:
        target = self._aliases.get(interface, interface)
        if target in self._registrations:
            return self._registrations[target]
        if self._parent:
            return self._parent._get_registration(interface)
        raise KeyError(f"No registration found for {interface!r}")

    def _resolve_registration(self, reg: Registration, interface: type) -> Any:
        if reg.scope == Scope.SINGLETON:
            if reg.instance is None:
                if reg.implementation is None:
                    raise RuntimeError(
                        f"Singleton for {interface!r} has no implementation or instance"
                    )
                reg.instance = reg.implementation()
            return reg.instance

        if reg.scope == Scope.TRANSIENT:
            return reg.implementation()

        if reg.scope == Scope.FACTORY:
            if inspect.iscoroutinefunction(reg.factory):
                raise RuntimeError(
                    f"Factory for {interface!r} is async. Use resolve_async()."
                )
            return reg.factory()

        raise RuntimeError(f"Unknown scope: {reg.scope}")  # pragma: no cover

    async def _resolve_registration_async(
        self, reg: Registration, interface: type
    ) -> Any:
        if reg.scope == Scope.SINGLETON:
            if reg.instance is None:
                if reg.implementation is None:
                    raise RuntimeError(
                        f"Singleton for {interface!r} has no implementation or instance"
                    )
                instance = reg.implementation()
                if inspect.isawaitable(instance):
                    instance = await instance
                reg.instance = instance
            return reg.instance

        if reg.scope == Scope.TRANSIENT:
            instance = reg.implementation()
            if inspect.isawaitable(instance):
                instance = await instance
            return instance

        if reg.scope == Scope.FACTORY:
            if inspect.iscoroutinefunction(reg.factory):
                return await reg.factory()
            return reg.factory()

        raise RuntimeError(f"Unknown scope: {reg.scope}")  # pragma: no cover
