"""
test_settings_broker.py -- Task 5 validation
Tests for app/config/settings/broker.py
"""
from __future__ import annotations

import os
import pytest

from app.config.settings.broker import (
    ProviderSettings,
    BrokerCapabilities,
    BrokerRiskConfig,
    BrokerHealthSlot,
    BrokerProfile,
    BrokerSettings,
    BrokerMarket,
    TradingMode,
    build_broker_settings,
)


# ── ProviderSettings base ─────────────────────────────────────

class TestProviderSettings:

    def test_defaults(self):
        p = ProviderSettings()
        assert p.enabled           is True
        assert p.priority          == 50
        assert p.timeout_s         == 30.0
        assert p.retry_policy_name == "default"
        assert p.credentials_key   == ""

    def test_immutable(self):
        p = ProviderSettings()
        with pytest.raises(TypeError):
            p.enabled = False

    def test_custom_values(self):
        p = ProviderSettings(enabled=False, priority=10, timeout_s=5.0)
        assert p.enabled   is False
        assert p.priority  == 10
        assert p.timeout_s == 5.0


# ── BrokerCapabilities ────────────────────────────────────────

class TestBrokerCapabilities:

    def test_all_false_by_default(self):
        c = BrokerCapabilities()
        assert c.historical_data  is False
        assert c.live_quotes      is False
        assert c.order_placement  is False
        assert c.websocket_feed   is False

    def test_supports_by_name_true(self):
        c = BrokerCapabilities(historical_data=True, live_quotes=True)
        assert c.supports("historical_data") is True
        assert c.supports("live_quotes")     is True

    def test_supports_by_name_false(self):
        c = BrokerCapabilities(historical_data=True)
        assert c.supports("order_placement") is False

    def test_supports_unknown_name_returns_false(self):
        c = BrokerCapabilities()
        assert c.supports("nonexistent_capability") is False

    def test_supported_list_returns_true_only(self):
        c = BrokerCapabilities(historical_data=True, live_quotes=True)
        lst = c.supported_list()
        assert "historical_data" in lst
        assert "live_quotes"     in lst
        assert "order_placement" not in lst

    def test_supported_list_empty_when_all_false(self):
        c = BrokerCapabilities()
        assert c.supported_list() == []

    def test_immutable(self):
        c = BrokerCapabilities()
        with pytest.raises(TypeError):
            c.historical_data = True


# ── BrokerRiskConfig ──────────────────────────────────────────

class TestBrokerRiskConfig:

    def test_defaults(self):
        r = BrokerRiskConfig()
        assert r.max_order_value    == 50000.0
        assert r.max_daily_loss     == 5000.0
        assert r.emergency_stop     is False
        assert "INTRADAY" in r.allowed_products

    def test_emergency_stop_configurable(self):
        r = BrokerRiskConfig(emergency_stop=True)
        assert r.emergency_stop is True

    def test_immutable(self):
        r = BrokerRiskConfig()
        with pytest.raises(TypeError):
            r.emergency_stop = True


# ── BrokerHealthSlot ──────────────────────────────────────────

class TestBrokerHealthSlot:

    def test_all_none_by_default(self):
        h = BrokerHealthSlot()
        assert h.connected      is None
        assert h.authenticated  is None
        assert h.latency_ms     is None
        assert h.last_failure   is None

    def test_health_slot_is_mutable(self):
        """Health slots must be mutable -- runtime updates."""
        h = BrokerHealthSlot()
        h.connected    = True
        h.latency_ms   = 42.5
        assert h.connected  is True
        assert h.latency_ms == 42.5


# ── BrokerProfile ─────────────────────────────────────────────

class TestBrokerProfile:

    def _paper(self, **kwargs) -> BrokerProfile:
        return BrokerProfile(name="paper", trading_mode=TradingMode.PAPER, **kwargs)

    def _live(self, **kwargs) -> BrokerProfile:
        return BrokerProfile(name="angel", trading_mode=TradingMode.LIVE, **kwargs)

    def test_name_required(self):
        with pytest.raises(Exception):
            BrokerProfile(name="")

    def test_name_whitespace_stripped(self):
        p = BrokerProfile(name="  angel  ")
        assert p.name == "angel"

    def test_priority_must_be_positive(self):
        with pytest.raises(Exception):
            BrokerProfile(name="x", priority=0)

    def test_is_paper_true(self):
        p = self._paper()
        assert p.is_paper    is True
        assert p.is_live     is False
        assert p.is_read_only is False

    def test_is_live_true(self):
        p = self._live()
        assert p.is_live  is True
        assert p.is_paper is False

    def test_is_read_only(self):
        p = BrokerProfile(name="ro", trading_mode=TradingMode.READ_ONLY)
        assert p.is_read_only is True

    def test_disabled_profile_is_not_live(self):
        p = self._live(enabled=False)
        assert p.is_live is False

    def test_disabled_profile_is_not_paper(self):
        p = self._paper(enabled=False)
        assert p.is_paper is False

    def test_supports_capability(self):
        p = BrokerProfile(
            name="x",
            capabilities=BrokerCapabilities(historical_data=True)
        )
        assert p.supports("historical_data") is True
        assert p.supports("live_quotes")     is False

    def test_supports_market(self):
        p = BrokerProfile(
            name="x",
            markets=[BrokerMarket.NSE, BrokerMarket.BSE]
        )
        assert p.supports_market("NSE") is True
        assert p.supports_market("MCX") is False

    def test_to_safe_dict_redacts_credentials(self):
        p = BrokerProfile(name="x", credentials_key="ANGEL_SECRET")
        d = p.to_safe_dict()
        assert d["credentials_key"] == "[REDACTED]"
        assert "ANGEL_SECRET" not in str(d)

    def test_to_safe_dict_empty_credentials_not_redacted(self):
        p = BrokerProfile(name="x", credentials_key="")
        d = p.to_safe_dict()
        assert d["credentials_key"] == ""

    def test_immutable(self):
        p = self._paper()
        with pytest.raises(TypeError):
            p.trading_mode = TradingMode.LIVE


# ── BrokerSettings ────────────────────────────────────────────

class TestBrokerSettings:

    def _settings(self, **kwargs) -> BrokerSettings:
        paper = BrokerProfile(name="paper", trading_mode=TradingMode.PAPER)
        angel = BrokerProfile(name="angel", trading_mode=TradingMode.LIVE)
        return BrokerSettings(
            profiles={"paper": paper, "angel": angel},
            active_broker="paper",
            fallback_chain=["paper"],
            **kwargs,
        )

    def test_get_active_returns_correct_profile(self):
        s = self._settings()
        assert s.get_active().name == "paper"

    def test_get_active_returns_none_for_unknown(self):
        s = BrokerSettings(active_broker="nonexistent")
        assert s.get_active() is None

    def test_get_profile_by_name(self):
        s = self._settings()
        assert s.get_profile("angel").name == "angel"
        assert s.get_profile("missing")    is None

    def test_enabled_profiles_filters_disabled(self):
        disabled = BrokerProfile(name="off", enabled=False)
        enabled  = BrokerProfile(name="on",  enabled=True)
        s = BrokerSettings(profiles={"off": disabled, "on": enabled})
        names = [p.name for p in s.enabled_profiles()]
        assert "on"  in names
        assert "off" not in names

    def test_live_profiles_returns_live_only(self):
        s = self._settings()
        live = s.live_profiles()
        assert all(p.is_live for p in live)

    def test_fallback_sequence_ordered(self):
        paper = BrokerProfile(name="paper")
        angel = BrokerProfile(name="angel")
        s = BrokerSettings(
            profiles={"paper": paper, "angel": angel},
            fallback_chain=["angel", "paper"],
        )
        seq = s.fallback_sequence()
        assert seq[0].name == "angel"
        assert seq[1].name == "paper"

    def test_fallback_sequence_skips_missing(self):
        paper = BrokerProfile(name="paper")
        s = BrokerSettings(
            profiles={"paper": paper},
            fallback_chain=["missing", "paper"],
        )
        seq = s.fallback_sequence()
        assert len(seq) == 1
        assert seq[0].name == "paper"

    def test_has_live_broker_true(self):
        s = self._settings()
        assert s.has_live_broker() is True

    def test_has_live_broker_false(self):
        paper = BrokerProfile(name="paper", trading_mode=TradingMode.PAPER)
        s = BrokerSettings(profiles={"paper": paper})
        assert s.has_live_broker() is False

    def test_paper_capital_positive_required(self):
        with pytest.raises(Exception):
            BrokerSettings(paper_capital=0.0)

    def test_immutable(self):
        s = self._settings()
        with pytest.raises(TypeError):
            s.active_broker = "angel"


# ── Factory ───────────────────────────────────────────────────

class TestBuildBrokerSettings:

    def setup_method(self):
        for key in ("ACTIVE_BROKER", "BROKER_FALLBACK_CHAIN",
                    "PAPER_CAPITAL", "ANGEL_TRADING_MODE", "ANGEL_ENABLED"):
            os.environ.pop(key, None)

    def test_factory_returns_broker_settings(self):
        s = build_broker_settings()
        assert isinstance(s, BrokerSettings)

    def test_factory_default_active_broker(self):
        s = build_broker_settings()
        assert s.active_broker == "paper"

    def test_factory_active_broker_from_env(self):
        os.environ["ACTIVE_BROKER"] = "angel_one"
        s = build_broker_settings()
        assert s.active_broker == "angel_one"

    def test_factory_paper_capital_from_env(self):
        os.environ["PAPER_CAPITAL"] = "250000.0"
        s = build_broker_settings()
        assert s.paper_capital == 250000.0

    def test_factory_angel_mode_live(self):
        os.environ["ANGEL_TRADING_MODE"] = "live"
        s = build_broker_settings()
        assert s.profiles["angel_one"].trading_mode == TradingMode.LIVE

    def test_factory_angel_mode_invalid_defaults_to_paper(self):
        os.environ["ANGEL_TRADING_MODE"] = "banana"
        s = build_broker_settings()
        assert s.profiles["angel_one"].trading_mode == TradingMode.PAPER

    def test_factory_angel_disabled(self):
        os.environ["ANGEL_ENABLED"] = "false"
        s = build_broker_settings()
        assert s.profiles["angel_one"].enabled is False

    def test_factory_fallback_chain_from_env(self):
        os.environ["BROKER_FALLBACK_CHAIN"] = "angel_one,paper"
        s = build_broker_settings()
        assert s.fallback_chain == ["angel_one", "paper"]

    def test_factory_overrides_take_precedence(self):
        s = build_broker_settings(overrides={"active_broker": "angel_one"})
        assert s.active_broker == "angel_one"

    def test_factory_paper_profile_always_present(self):
        s = build_broker_settings()
        assert "paper" in s.profiles

    def test_factory_angel_profile_always_present(self):
        s = build_broker_settings()
        assert "angel_one" in s.profiles

    def test_angel_profile_capabilities(self):
        s = build_broker_settings()
        angel = s.profiles["angel_one"]
        assert angel.supports("historical_data")  is True
        assert angel.supports("websocket_feed")   is True
        assert angel.supports("order_placement")  is True

    def test_paper_profile_capabilities(self):
        s = build_broker_settings()
        paper = s.profiles["paper"]
        assert paper.supports("paper_trading")    is True
        assert paper.supports("websocket_feed")   is False
