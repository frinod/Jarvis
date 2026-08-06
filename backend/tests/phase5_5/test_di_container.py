"""
test_di_container.py -- Task 5.5.1 validation
Tests for app/core/di/container.py
"""
from __future__ import annotations

import pytest
from app.core.di import DIContainer, Scope


# ── Test fixtures ─────────────────────────────────────────────

class IService:
    """Interface stub."""
    def name(self) -> str: ...


class ServiceA(IService):
    def name(self) -> str:
        return "A"


class ServiceB(IService):
    def name(self) -> str:
        return "B"


class Counter:
    _count = 0
    def __init__(self):
        Counter._count += 1
    @classmethod
    def reset(cls): cls._count = 0


# ── Singleton registration ────────────────────────────────────

class TestSingleton:

    def test_register_and_resolve_singleton(self):
        c = DIContainer()
        c.register_singleton(ServiceA)
        svc = c.resolve(ServiceA)
        assert isinstance(svc, ServiceA)

    def test_singleton_same_instance_on_repeated_resolve(self):
        c = DIContainer()
        c.register_singleton(ServiceA)
        s1 = c.resolve(ServiceA)
        s2 = c.resolve(ServiceA)
        assert s1 is s2

    def test_register_interface_with_implementation(self):
        c = DIContainer()
        c.register_singleton(IService, ServiceA)
        svc = c.resolve(IService)
        assert isinstance(svc, ServiceA)

    def test_register_instance_returns_same_object(self):
        c = DIContainer()
        instance = ServiceA()
        c.register_instance(IService, instance)
        resolved = c.resolve(IService)
        assert resolved is instance

    def test_singleton_instantiated_only_once(self):
        Counter.reset()
        c = DIContainer()
        c.register_singleton(Counter)
        c.resolve(Counter)
        c.resolve(Counter)
        c.resolve(Counter)
        assert Counter._count == 1


# ── Transient registration ────────────────────────────────────

class TestTransient:

    def test_transient_returns_new_instance_each_time(self):
        Counter.reset()
        c = DIContainer()
        c.register_transient(Counter)
        i1 = c.resolve(Counter)
        i2 = c.resolve(Counter)
        assert i1 is not i2
        assert Counter._count == 2

    def test_transient_with_interface(self):
        c = DIContainer()
        c.register_transient(IService, ServiceA)
        s1 = c.resolve(IService)
        s2 = c.resolve(IService)
        assert s1 is not s2
        assert isinstance(s1, ServiceA)


# ── Factory registration ──────────────────────────────────────

class TestFactory:

    def test_factory_called_on_resolve(self):
        c = DIContainer()
        calls = []
        def make_service():
            calls.append(1)
            return ServiceA()
        c.register_factory(IService, make_service)
        c.resolve(IService)
        c.resolve(IService)
        assert len(calls) == 2

    def test_factory_returns_correct_type(self):
        c = DIContainer()
        c.register_factory(ServiceA, lambda: ServiceA())
        svc = c.resolve(ServiceA)
        assert isinstance(svc, ServiceA)

    def test_async_factory_raises_on_sync_resolve(self):
        c = DIContainer()
        async def async_factory():
            return ServiceA()
        c.register_factory(IService, async_factory)
        with pytest.raises(RuntimeError, match="resolve_async"):
            c.resolve(IService)


# ── Alias registration ────────────────────────────────────────

class TestAlias:

    def test_alias_resolves_to_target(self):
        c = DIContainer()
        c.register_singleton(ServiceA)
        c.register_alias(IService, ServiceA)
        svc = c.resolve(IService)
        assert isinstance(svc, ServiceA)

    def test_alias_shares_singleton_instance(self):
        c = DIContainer()
        c.register_singleton(ServiceA)
        c.register_alias(IService, ServiceA)
        s1 = c.resolve(ServiceA)
        s2 = c.resolve(IService)
        assert s1 is s2


# ── Resolution errors ─────────────────────────────────────────

class TestResolutionErrors:

    def test_unregistered_type_raises_key_error(self):
        c = DIContainer()
        with pytest.raises(KeyError):
            c.resolve(ServiceA)

    def test_resolve_optional_returns_none_for_unregistered(self):
        c = DIContainer()
        result = c.resolve_optional(ServiceA)
        assert result is None

    def test_resolve_optional_returns_instance_when_registered(self):
        c = DIContainer()
        c.register_singleton(ServiceA)
        result = c.resolve_optional(ServiceA)
        assert isinstance(result, ServiceA)


# ── Introspection ─────────────────────────────────────────────

class TestIntrospection:

    def test_is_registered_true(self):
        c = DIContainer()
        c.register_singleton(ServiceA)
        assert c.is_registered(ServiceA) is True

    def test_is_registered_false(self):
        c = DIContainer()
        assert c.is_registered(ServiceA) is False

    def test_registered_types_lists_all(self):
        c = DIContainer()
        c.register_singleton(ServiceA)
        c.register_singleton(ServiceB)
        types = c.registered_types()
        assert ServiceA in types
        assert ServiceB in types

    def test_registered_types_empty_initially(self):
        c = DIContainer()
        assert c.registered_types() == []


# ── Child containers ──────────────────────────────────────────

class TestChildContainers:

    def test_child_inherits_parent_registrations(self):
        parent = DIContainer()
        parent.register_singleton(ServiceA)
        child = parent.child()
        svc = child.resolve(ServiceA)
        assert isinstance(svc, ServiceA)

    def test_child_can_override_parent_registration(self):
        parent = DIContainer()
        parent.register_singleton(IService, ServiceA)
        child = parent.child()
        child.register_singleton(IService, ServiceB)
        svc = child.resolve(IService)
        assert isinstance(svc, ServiceB)

    def test_parent_not_affected_by_child_override(self):
        parent = DIContainer()
        parent.register_singleton(IService, ServiceA)
        child = parent.child()
        child.register_singleton(IService, ServiceB)
        svc = parent.resolve(IService)
        assert isinstance(svc, ServiceA)

    def test_child_is_registered_checks_parent(self):
        parent = DIContainer()
        parent.register_singleton(ServiceA)
        child = parent.child()
        assert child.is_registered(ServiceA) is True

    def test_child_registered_types_excludes_parent(self):
        parent = DIContainer()
        parent.register_singleton(ServiceA)
        child = parent.child()
        child.register_singleton(ServiceB)
        # registered_types() only returns directly registered types
        assert ServiceB in child.registered_types()
        assert ServiceA not in child.registered_types()


# ── Async resolution ──────────────────────────────────────────

class TestAsyncResolution:

    @pytest.mark.asyncio
    async def test_async_resolve_sync_singleton(self):
        c = DIContainer()
        c.register_singleton(ServiceA)
        svc = await c.resolve_async(ServiceA)
        assert isinstance(svc, ServiceA)

    @pytest.mark.asyncio
    async def test_async_resolve_async_factory(self):
        c = DIContainer()
        async def make():
            return ServiceA()
        c.register_factory(IService, make)
        svc = await c.resolve_async(IService)
        assert isinstance(svc, ServiceA)

    @pytest.mark.asyncio
    async def test_async_resolve_sync_factory(self):
        c = DIContainer()
        c.register_factory(ServiceA, lambda: ServiceA())
        svc = await c.resolve_async(ServiceA)
        assert isinstance(svc, ServiceA)

    @pytest.mark.asyncio
    async def test_async_singleton_same_instance(self):
        c = DIContainer()
        c.register_singleton(ServiceA)
        s1 = await c.resolve_async(ServiceA)
        s2 = await c.resolve_async(ServiceA)
        assert s1 is s2
