"""
test_service_registry.py -- Task 5.5.2 validation
Tests for app/core/service_registry/registry.py
"""
from __future__ import annotations

import pytest
from app.core.service_registry import ServiceRegistry, ServiceEntry, ServiceStatus


# ── Fixtures ──────────────────────────────────────────────────

class IProvider:
    pass

class BrokerProvider(IProvider):
    pass

class LLMProvider(IProvider):
    pass

class ConcreteA(BrokerProvider):
    pass

class ConcreteB(LLMProvider):
    pass


# ── Registration ──────────────────────────────────────────────

class TestRegistration:

    def test_register_and_get(self):
        r = ServiceRegistry()
        r.register("svc_a", IProvider)
        entry = r.get("svc_a")
        assert entry is not None
        assert entry.name == "svc_a"

    def test_register_with_instance(self):
        r = ServiceRegistry()
        instance = ConcreteA()
        r.register("broker", BrokerProvider, instance=instance)
        assert r.get_instance("broker") is instance

    def test_register_with_tags(self):
        r = ServiceRegistry()
        r.register("gemini", LLMProvider, tags={"llm", "cloud"})
        entry = r.get("gemini")
        assert entry.has_tag("llm")
        assert entry.has_tag("cloud")
        assert not entry.has_tag("local")

    def test_register_with_version(self):
        r = ServiceRegistry()
        r.register("svc", IProvider, version="1.2.3")
        assert r.get("svc").version == "1.2.3"

    def test_register_with_plugin_class(self):
        r = ServiceRegistry()
        r.register("svc", IProvider, plugin_class="app.brokers.angel.AngelProvider")
        assert r.get("svc").plugin_class == "app.brokers.angel.AngelProvider"

    def test_register_with_metadata(self):
        r = ServiceRegistry()
        r.register("svc", IProvider, metadata={"region": "IN"})
        assert r.get("svc").metadata["region"] == "IN"

    def test_register_overwrites_existing(self):
        r = ServiceRegistry()
        r.register("svc", IProvider, version="1.0")
        r.register("svc", IProvider, version="2.0")
        assert r.get("svc").version == "2.0"

    def test_empty_name_raises(self):
        r = ServiceRegistry()
        with pytest.raises(ValueError):
            r.register("", IProvider)

    def test_whitespace_name_raises(self):
        r = ServiceRegistry()
        with pytest.raises(ValueError):
            r.register("   ", IProvider)

    def test_unregister_existing(self):
        r = ServiceRegistry()
        r.register("svc", IProvider)
        result = r.unregister("svc")
        assert result is True
        assert r.get("svc") is None

    def test_unregister_nonexistent_returns_false(self):
        r = ServiceRegistry()
        assert r.unregister("missing") is False


# ── Lookup ────────────────────────────────────────────────────

class TestLookup:

    def test_get_missing_returns_none(self):
        r = ServiceRegistry()
        assert r.get("missing") is None

    def test_get_instance_missing_returns_none(self):
        r = ServiceRegistry()
        assert r.get_instance("missing") is None

    def test_get_instance_no_instance_returns_none(self):
        r = ServiceRegistry()
        r.register("svc", IProvider)
        assert r.get_instance("svc") is None

    def test_get_by_type_exact_match(self):
        r = ServiceRegistry()
        r.register("a", BrokerProvider)
        r.register("b", LLMProvider)
        results = r.get_by_type(BrokerProvider)
        names = [e.name for e in results]
        assert "a" in names
        assert "b" not in names

    def test_get_by_type_includes_subclasses(self):
        r = ServiceRegistry()
        r.register("concrete", ConcreteA)
        results = r.get_by_type(IProvider)
        assert any(e.name == "concrete" for e in results)

    def test_get_by_type_empty_when_none_match(self):
        r = ServiceRegistry()
        r.register("svc", LLMProvider)
        results = r.get_by_type(BrokerProvider)
        assert results == []

    def test_get_by_tag_returns_matching(self):
        r = ServiceRegistry()
        r.register("a", IProvider, tags={"llm"})
        r.register("b", IProvider, tags={"broker"})
        r.register("c", IProvider, tags={"llm", "cloud"})
        results = r.get_by_tag("llm")
        names = [e.name for e in results]
        assert "a" in names
        assert "c" in names
        assert "b" not in names

    def test_get_by_tag_empty_when_none_match(self):
        r = ServiceRegistry()
        r.register("svc", IProvider, tags={"broker"})
        assert r.get_by_tag("llm") == []


# ── Health status ─────────────────────────────────────────────

class TestHealthStatus:

    def test_default_status_is_unknown(self):
        r = ServiceRegistry()
        r.register("svc", IProvider)
        assert r.get("svc").status == ServiceStatus.UNKNOWN

    def test_set_status_updates_entry(self):
        r = ServiceRegistry()
        r.register("svc", IProvider)
        r.set_status("svc", ServiceStatus.HEALTHY)
        assert r.get("svc").status == ServiceStatus.HEALTHY

    def test_set_status_missing_returns_false(self):
        r = ServiceRegistry()
        result = r.set_status("missing", ServiceStatus.HEALTHY)
        assert result is False

    def test_set_status_existing_returns_true(self):
        r = ServiceRegistry()
        r.register("svc", IProvider)
        result = r.set_status("svc", ServiceStatus.HEALTHY)
        assert result is True

    def test_get_healthy_returns_only_healthy(self):
        r = ServiceRegistry()
        r.register("a", IProvider)
        r.register("b", IProvider)
        r.set_status("a", ServiceStatus.HEALTHY)
        r.set_status("b", ServiceStatus.UNHEALTHY)
        healthy = r.get_healthy()
        assert len(healthy) == 1
        assert healthy[0].name == "a"

    def test_get_available_includes_degraded(self):
        r = ServiceRegistry()
        r.register("a", IProvider)
        r.register("b", IProvider)
        r.register("c", IProvider)
        r.set_status("a", ServiceStatus.HEALTHY)
        r.set_status("b", ServiceStatus.DEGRADED)
        r.set_status("c", ServiceStatus.UNHEALTHY)
        available = r.get_available()
        names = [e.name for e in available]
        assert "a" in names
        assert "b" in names
        assert "c" not in names

    def test_is_healthy_true(self):
        entry = ServiceEntry(name="x", service_type=IProvider,
                             status=ServiceStatus.HEALTHY)
        assert entry.is_healthy() is True

    def test_is_healthy_false(self):
        entry = ServiceEntry(name="x", service_type=IProvider,
                             status=ServiceStatus.UNHEALTHY)
        assert entry.is_healthy() is False

    def test_is_available_healthy(self):
        entry = ServiceEntry(name="x", service_type=IProvider,
                             status=ServiceStatus.HEALTHY)
        assert entry.is_available() is True

    def test_is_available_degraded(self):
        entry = ServiceEntry(name="x", service_type=IProvider,
                             status=ServiceStatus.DEGRADED)
        assert entry.is_available() is True

    def test_is_available_unhealthy(self):
        entry = ServiceEntry(name="x", service_type=IProvider,
                             status=ServiceStatus.UNHEALTHY)
        assert entry.is_available() is False


# ── Instance management ───────────────────────────────────────

class TestInstanceManagement:

    def test_set_instance_attaches_to_entry(self):
        r = ServiceRegistry()
        r.register("svc", IProvider)
        instance = ConcreteA()
        r.set_instance("svc", instance)
        assert r.get_instance("svc") is instance

    def test_set_instance_missing_returns_false(self):
        r = ServiceRegistry()
        assert r.set_instance("missing", ConcreteA()) is False

    def test_set_instance_existing_returns_true(self):
        r = ServiceRegistry()
        r.register("svc", IProvider)
        assert r.set_instance("svc", ConcreteA()) is True


# ── Introspection ─────────────────────────────────────────────

class TestIntrospection:

    def test_is_registered_true(self):
        r = ServiceRegistry()
        r.register("svc", IProvider)
        assert r.is_registered("svc") is True

    def test_is_registered_false(self):
        r = ServiceRegistry()
        assert r.is_registered("missing") is False

    def test_names_returns_all(self):
        r = ServiceRegistry()
        r.register("a", IProvider)
        r.register("b", IProvider)
        assert set(r.names()) == {"a", "b"}

    def test_count(self):
        r = ServiceRegistry()
        assert r.count() == 0
        r.register("a", IProvider)
        assert r.count() == 1
        r.register("b", IProvider)
        assert r.count() == 2

    def test_to_dict_structure(self):
        r = ServiceRegistry()
        r.register("svc", IProvider, tags={"test"}, version="1.0")
        d = r.to_dict()
        assert "svc" in d
        assert d["svc"]["name"] == "svc"
        assert d["svc"]["version"] == "1.0"
        assert "test" in d["svc"]["tags"]
        assert d["svc"]["has_instance"] is False

    def test_to_dict_has_instance_true(self):
        r = ServiceRegistry()
        r.register("svc", IProvider, instance=ConcreteA())
        d = r.to_dict()
        assert d["svc"]["has_instance"] is True
