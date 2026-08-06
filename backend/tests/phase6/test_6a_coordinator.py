"""
tests/phase6/test_6a_coordinator.py
=====================================
Unit tests for AgentCoordinator (Task 6A.5).

All tests are pure -- no network, no I/O, no LLM calls, no async.
Selection is synchronous by design.
"""
import pytest

from app.ai.brain.brain import Goal
from app.ai.orchestration.coordinator import (
    AgentHealth,
    AgentDescriptor,
    AgentMetrics,
    AgentScore,
    SelectionWeights,
    SelectionResult,
    CoordinatorResult,
    NoAgentAvailableError,
    SelectionPolicy,
    CapabilityMatchPolicy,
    AgentRegistry,
    Coordinator,
    CoordinatorAgentSelector,
)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _desc(
    name:       str,
    priority:   int            = 3,
    caps:       list           = None,
    intents:    list           = None,
    latency_ms: int            = 500,
    version:    str            = "1.0",
) -> AgentDescriptor:
    return AgentDescriptor(
        name=name,
        version=version,
        priority=priority,
        capabilities=caps or [],
        supported_intents=intents or [],
        estimated_latency_ms=latency_ms,
    )


def _goal(intent: str = "", caps: list = None) -> Goal:
    g = Goal(objective="test goal")
    if intent:
        g.metadata["intent_type"] = intent
    if caps:
        g.metadata["required_capabilities"] = caps
    return g


def _registry(*descriptors: AgentDescriptor) -> AgentRegistry:
    r = AgentRegistry()
    for d in descriptors:
        r.register(d)
    return r


def _coordinator(*descriptors: AgentDescriptor, policy=None) -> Coordinator:
    return Coordinator(registry=_registry(*descriptors), policy=policy)


# ── TestAgentHealth ───────────────────────────────────────────────────────────

class TestAgentHealth:

    def test_healthy_is_available(self):
        assert AgentHealth.HEALTHY.is_available() is True

    def test_degraded_is_available(self):
        assert AgentHealth.DEGRADED.is_available() is True

    def test_offline_is_not_available(self):
        assert AgentHealth.OFFLINE.is_available() is False

    def test_starting_is_not_available(self):
        assert AgentHealth.STARTING.is_available() is False

    def test_stopping_is_not_available(self):
        assert AgentHealth.STOPPING.is_available() is False

    def test_enum_values_are_strings(self):
        assert AgentHealth.HEALTHY == "healthy"
        assert AgentHealth.OFFLINE == "offline"


# ── TestAgentDescriptor ───────────────────────────────────────────────────────

class TestAgentDescriptor:

    def test_required_fields(self):
        d = AgentDescriptor(name="analyst")
        assert d.name == "analyst"

    def test_version_field_exists(self):
        d = AgentDescriptor(name="analyst", version="2.1")
        assert d.version == "2.1"

    def test_version_defaults_to_1_0(self):
        d = AgentDescriptor(name="analyst")
        assert d.version == "1.0"

    def test_priority_defaults_to_3(self):
        d = AgentDescriptor(name="analyst")
        assert d.priority == 3

    def test_capabilities_default_empty(self):
        d = AgentDescriptor(name="analyst")
        assert d.capabilities == []

    def test_supported_intents_default_empty(self):
        d = AgentDescriptor(name="analyst")
        assert d.supported_intents == []

    def test_metadata_is_domain_escape_hatch(self):
        d = AgentDescriptor(name="analyst")
        d.metadata["domain"] = "finance"
        assert d.metadata["domain"] == "finance"

    def test_full_construction(self):
        d = _desc("trader", priority=1, caps=["ta", "signals"],
                  intents=["analyze"], latency_ms=120, version="3.0")
        assert d.name                 == "trader"
        assert d.version              == "3.0"
        assert d.priority             == 1
        assert "ta"                   in d.capabilities
        assert "analyze"              in d.supported_intents
        assert d.estimated_latency_ms == 120


# ── TestAgentMetrics ──────────────────────────────────────────────────────────

class TestAgentMetrics:

    def test_initial_state(self):
        m = AgentMetrics(agent_name="analyst")
        assert m.requests    == 0
        assert m.success_rate == 0.0
        assert m.avg_latency_ms == 0.0

    def test_record_success(self):
        m = AgentMetrics(agent_name="analyst")
        m.record(success=True, latency_ms=100.0, confidence=0.9)
        assert m.requests  == 1
        assert m.successes == 1
        assert m.failures  == 0

    def test_record_failure(self):
        m = AgentMetrics(agent_name="analyst")
        m.record(success=False, latency_ms=200.0)
        assert m.failures == 1
        assert m.last_failure > 0

    def test_success_rate_calculation(self):
        m = AgentMetrics(agent_name="analyst")
        m.record(True, 100.0)
        m.record(True, 100.0)
        m.record(False, 100.0)
        assert round(m.success_rate, 3) == round(2 / 3, 3)

    def test_avg_latency_calculation(self):
        m = AgentMetrics(agent_name="analyst")
        m.record(True, 100.0)
        m.record(True, 300.0)
        assert m.avg_latency_ms == 200.0

    def test_avg_confidence_calculation(self):
        m = AgentMetrics(agent_name="analyst")
        m.record(True, 100.0, confidence=0.8)
        m.record(True, 100.0, confidence=0.6)
        assert m.avg_confidence == pytest.approx(0.7)


# ── TestAgentRegistry ─────────────────────────────────────────────────────────

class TestAgentRegistry:

    def test_register_and_retrieve(self):
        r = AgentRegistry()
        d = _desc("analyst")
        r.register(d)
        assert r.get("analyst") is d

    def test_deregister_removes_agent(self):
        r = AgentRegistry()
        r.register(_desc("analyst"))
        r.deregister("analyst")
        assert r.get("analyst") is None

    def test_default_health_is_healthy(self):
        r = AgentRegistry()
        r.register(_desc("analyst"))
        assert r.get_health("analyst") == AgentHealth.HEALTHY

    def test_set_health_changes_status(self):
        r = AgentRegistry()
        r.register(_desc("analyst"))
        r.set_health("analyst", AgentHealth.DEGRADED)
        assert r.get_health("analyst") == AgentHealth.DEGRADED

    def test_available_excludes_offline(self):
        r = AgentRegistry()
        r.register(_desc("analyst"))
        r.register(_desc("trader"))
        r.set_health("trader", AgentHealth.OFFLINE)
        names = [d.name for d in r.available()]
        assert "analyst" in names
        assert "trader"  not in names

    def test_available_includes_degraded(self):
        r = AgentRegistry()
        r.register(_desc("analyst"))
        r.set_health("analyst", AgentHealth.DEGRADED)
        assert len(r.available()) == 1

    def test_find_by_capability(self):
        r = AgentRegistry()
        r.register(_desc("analyst", caps=["technical_analysis", "charting"]))
        r.register(_desc("researcher", caps=["news", "sentiment"]))
        result = r.find("technical_analysis")
        assert len(result) == 1
        assert result[0].name == "analyst"

    def test_find_excludes_offline(self):
        r = AgentRegistry()
        r.register(_desc("analyst", caps=["ta"]))
        r.set_health("analyst", AgentHealth.OFFLINE)
        assert r.find("ta") == []

    def test_find_returns_empty_when_no_match(self):
        r = AgentRegistry()
        r.register(_desc("analyst", caps=["ta"]))
        assert r.find("nonexistent_capability") == []

    def test_all_names(self):
        r = AgentRegistry()
        r.register(_desc("analyst"))
        r.register(_desc("trader"))
        assert set(r.all_names()) == {"analyst", "trader"}

    def test_metrics_initialised_on_register(self):
        r = AgentRegistry()
        r.register(_desc("analyst"))
        assert r.metrics("analyst") is not None
        assert r.metrics("analyst").requests == 0

    def test_record_updates_metrics(self):
        r = AgentRegistry()
        r.register(_desc("analyst"))
        r.record("analyst", success=True, latency_ms=150.0, confidence=0.85)
        assert r.metrics("analyst").requests == 1


# ── TestCapabilityMatchPolicy ─────────────────────────────────────────────────

class TestCapabilityMatchPolicy:

    def test_intent_match_contributes_score(self):
        policy = CapabilityMatchPolicy()
        d      = _desc("analyst", intents=["analyze"])
        g      = _goal(intent="analyze")
        s      = policy.score(g, d)
        assert s.score > 0.0
        assert "analyze" in s.matched_intents

    def test_no_intent_match_zero_intent_score(self):
        policy = CapabilityMatchPolicy()
        d      = _desc("analyst", intents=["plan"])
        g      = _goal(intent="analyze")
        s      = policy.score(g, d)
        assert s.matched_intents == []

    def test_capability_overlap_contributes_score(self):
        policy = CapabilityMatchPolicy()
        d      = _desc("analyst", caps=["ta", "charting"])
        g      = _goal(caps=["ta", "charting"])
        s      = policy.score(g, d)
        assert s.score > 0.0
        assert set(s.matched_capabilities) == {"ta", "charting"}

    def test_partial_capability_overlap(self):
        policy = CapabilityMatchPolicy()
        d      = _desc("analyst", caps=["ta"])
        g      = _goal(caps=["ta", "news"])
        s      = policy.score(g, d)
        assert 0.0 < s.score < 1.0

    def test_priority_1_higher_than_priority_5(self):
        policy = CapabilityMatchPolicy()
        d1     = _desc("fast", priority=1)
        d5     = _desc("slow", priority=5)
        g      = _goal()
        s1     = policy.score(g, d1)
        s5     = policy.score(g, d5)
        assert s1.score > s5.score

    def test_custom_weights_respected(self):
        weights = SelectionWeights(intent=0.9, capability=0.05, priority=0.05)
        policy  = CapabilityMatchPolicy(weights=weights)
        d       = _desc("analyst", intents=["analyze"])
        g       = _goal(intent="analyze")
        s       = policy.score(g, d)
        assert s.score >= 0.9 * 0.9   # at least intent contribution

    def test_score_capped_at_1(self):
        policy = CapabilityMatchPolicy()
        d      = _desc("analyst", priority=1, caps=["ta"], intents=["analyze"])
        g      = _goal(intent="analyze", caps=["ta"])
        s      = policy.score(g, d)
        assert s.score <= 1.0

    def test_score_non_negative(self):
        policy = CapabilityMatchPolicy()
        d      = _desc("analyst")
        g      = _goal(intent="unknown", caps=["unknown_cap"])
        s      = policy.score(g, d)
        assert s.score >= 0.0

    def test_rationale_is_non_empty(self):
        policy = CapabilityMatchPolicy()
        s      = policy.score(_goal(), _desc("analyst"))
        assert len(s.rationale) > 0


# ── TestCoordinatorSelection ──────────────────────────────────────────────────

class TestCoordinatorSelection:

    def test_selects_highest_score(self):
        # analyst matches intent; trader does not
        c = _coordinator(
            _desc("analyst", intents=["analyze"]),
            _desc("trader",  intents=["execute"]),
        )
        g      = _goal(intent="analyze")
        result = c.select(g)
        assert result.agent_name == "analyst"

    def test_returns_coordinator_result(self):
        c      = _coordinator(_desc("analyst"))
        result = c.select(_goal())
        assert isinstance(result, CoordinatorResult)

    def test_result_contains_selection_result(self):
        c      = _coordinator(_desc("analyst"))
        result = c.select(_goal())
        assert isinstance(result.selection, SelectionResult)

    def test_selection_result_has_candidate_scores(self):
        c      = _coordinator(_desc("analyst"), _desc("trader"))
        result = c.select(_goal())
        assert len(result.selection.candidate_scores) == 2

    def test_selection_result_has_rejected_agents(self):
        c      = _coordinator(_desc("analyst", intents=["analyze"]), _desc("trader"))
        result = c.select(_goal(intent="analyze"))
        assert "trader" in result.selection.rejected_agents

    def test_tie_broken_by_lower_latency(self):
        # Both have same capabilities and intents -- latency decides
        fast = _desc("fast_agent", priority=3, latency_ms=100)
        slow = _desc("slow_agent", priority=3, latency_ms=900)
        c    = _coordinator(fast, slow)
        result = c.select(_goal())
        assert result.agent_name == "fast_agent"

    def test_raises_when_registry_empty(self):
        c = Coordinator(registry=AgentRegistry())
        with pytest.raises(NoAgentAvailableError):
            c.select(_goal())

    def test_raises_when_all_agents_offline(self):
        r = AgentRegistry()
        r.register(_desc("analyst"))
        r.set_health("analyst", AgentHealth.OFFLINE)
        c = Coordinator(registry=r)
        with pytest.raises(NoAgentAvailableError):
            c.select(_goal())

    def test_degraded_agent_still_selected(self):
        r = AgentRegistry()
        r.register(_desc("analyst"))
        r.set_health("analyst", AgentHealth.DEGRADED)
        c      = Coordinator(registry=r)
        result = c.select(_goal())
        assert result.agent_name == "analyst"

    def test_goal_id_in_result(self):
        c      = _coordinator(_desc("analyst"))
        g      = _goal()
        result = c.select(g)
        assert result.goal_id == g.id

    def test_selected_agents_placeholder_empty(self):
        c      = _coordinator(_desc("analyst"))
        result = c.select(_goal())
        assert result.selected_agents == []

    def test_selection_time_ms_recorded(self):
        c      = _coordinator(_desc("analyst"))
        result = c.select(_goal())
        assert result.selection.selection_time_ms >= 0.0


# ── TestNoAgentAvailableError ─────────────────────────────────────────────────

class TestNoAgentAvailableError:

    def test_carries_goal_id(self):
        err = NoAgentAvailableError(goal_id="g-123", reason="all offline")
        assert err.goal_id == "g-123"

    def test_carries_reason(self):
        err = NoAgentAvailableError(goal_id="g-1", reason="empty registry")
        assert err.reason == "empty registry"

    def test_is_exception(self):
        assert issubclass(NoAgentAvailableError, Exception)

    def test_str_representation(self):
        err = NoAgentAvailableError(goal_id="g-1", reason="offline")
        assert "g-1" in str(err)


# ── TestCoordinatorAgentSelector ──────────────────────────────────────────────

class TestCoordinatorAgentSelector:

    def test_returns_agent_name_string(self):
        c        = _coordinator(_desc("analyst"))
        selector = CoordinatorAgentSelector(c)
        name     = selector.select(_goal(), available_agents=[])
        assert isinstance(name, str)
        assert name == "analyst"

    def test_ignores_available_agents_argument(self):
        # Registry is authoritative; available_agents list is ignored
        c        = _coordinator(_desc("trader"))
        selector = CoordinatorAgentSelector(c)
        name     = selector.select(_goal(), available_agents=["analyst", "researcher"])
        assert name == "trader"

    def test_implements_brain_agent_selector(self):
        from app.ai.brain.brain import BrainAgentSelector
        c        = _coordinator(_desc("analyst"))
        selector = CoordinatorAgentSelector(c)
        assert isinstance(selector, BrainAgentSelector)

    def test_raises_when_no_agents(self):
        c        = Coordinator(registry=AgentRegistry())
        selector = CoordinatorAgentSelector(c)
        with pytest.raises(NoAgentAvailableError):
            selector.select(_goal(), available_agents=[])


# ── TestDomainAgnosticism ─────────────────────────────────────────────────────

class TestDomainAgnosticism:
    """Coordinator layer must contain zero domain-specific first-class fields."""

    TRADING_FIELDS = [
        "symbol", "stock", "candle", "rsi", "macd", "broker",
        "portfolio", "trade", "price", "market", "nifty",
        "signal", "indicator", "ticker",
    ]

    def test_coordinator_has_no_trading_attributes(self):
        c = _coordinator(_desc("analyst"))
        for attr in self.TRADING_FIELDS:
            assert not hasattr(c, attr), f"Domain attribute '{attr}' on Coordinator"

    def test_descriptor_has_no_trading_attributes(self):
        d = AgentDescriptor(name="analyst")
        for attr in self.TRADING_FIELDS:
            assert attr not in vars(d), f"Domain attribute '{attr}' on AgentDescriptor"

    def test_registry_has_no_trading_attributes(self):
        r = AgentRegistry()
        for attr in self.TRADING_FIELDS:
            assert not hasattr(r, attr), f"Domain attribute '{attr}' on AgentRegistry"

    def test_metadata_carries_domain_data(self):
        d = AgentDescriptor(name="analyst")
        d.metadata["domain"]   = "trading"
        d.metadata["exchange"] = "NSE"
        assert d.metadata["domain"]   == "trading"
        assert d.metadata["exchange"] == "NSE"
