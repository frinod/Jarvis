"""
test_settings_assembler.py -- Task 11 validation
Tests for app/config/settings/__init__.py (JarvisSettings assembler)
"""
from __future__ import annotations

import pytest

from app.config.settings import (
    JarvisSettings,
    build_settings,
    get_settings,
    reset_settings,
    AppSettings,
    BrokerSettings,
    MarketSettings,
    AISettings,
    RiskSettings,
    CacheSettings,
    LoggingSettings,
    ProviderSettings,
)


# ── Import surface ────────────────────────────────────────────

class TestPublicAPI:

    def test_jarvis_settings_importable(self):
        assert JarvisSettings is not None

    def test_build_settings_importable(self):
        assert callable(build_settings)

    def test_get_settings_importable(self):
        assert callable(get_settings)

    def test_reset_settings_importable(self):
        assert callable(reset_settings)

    def test_all_domain_types_re_exported(self):
        for cls in (AppSettings, BrokerSettings, MarketSettings,
                    AISettings, RiskSettings, CacheSettings,
                    LoggingSettings, ProviderSettings):
            assert cls is not None

    def test_provider_settings_same_object_as_broker_export(self):
        from app.config.settings.broker import ProviderSettings as BPS
        assert ProviderSettings is BPS


# ── JarvisSettings structure ──────────────────────────────────

class TestJarvisSettings:

    def setup_method(self):
        reset_settings()

    def teardown_method(self):
        reset_settings()

    def test_build_settings_returns_jarvis_settings(self):
        s = build_settings()
        assert isinstance(s, JarvisSettings)

    def test_all_domains_present(self):
        s = build_settings()
        assert isinstance(s.app,     AppSettings)
        assert isinstance(s.broker,  BrokerSettings)
        assert isinstance(s.market,  MarketSettings)
        assert isinstance(s.ai,      AISettings)
        assert isinstance(s.risk,    RiskSettings)
        assert isinstance(s.cache,   CacheSettings)
        assert isinstance(s.logging, LoggingSettings)

    def test_immutable(self):
        s = build_settings()
        with pytest.raises(TypeError):
            s.app = AppSettings()

    def test_to_dict_contains_all_domains(self):
        s = build_settings()
        d = s.to_dict()
        for key in ("app", "broker", "market", "ai", "risk", "cache", "logging"):
            assert key in d

    def test_to_dict_app_redacts_secret(self):
        s = build_settings()
        d = s.to_dict()
        assert d["app"].get("secret_key") == "[REDACTED]"

    def test_to_dict_ai_redacts_credentials(self):
        s = build_settings()
        d = s.to_dict()
        for profile in d["ai"].get("profiles", {}).values():
            assert profile.get("credentials_key") in ("", "[REDACTED]")


# ── Singleton behaviour ───────────────────────────────────────

class TestSingleton:

    def setup_method(self):
        reset_settings()

    def teardown_method(self):
        reset_settings()

    def test_get_settings_returns_same_instance(self):
        s1 = get_settings()
        s2 = get_settings()
        assert s1 is s2

    def test_reset_clears_singleton(self):
        s1 = get_settings()
        reset_settings()
        s2 = get_settings()
        assert s1 is not s2

    def test_get_settings_returns_jarvis_settings(self):
        s = get_settings()
        assert isinstance(s, JarvisSettings)

    def test_build_settings_always_fresh(self):
        s1 = build_settings()
        s2 = build_settings()
        # build_settings() always creates a new instance
        assert s1 is not s2


# ── Domain overrides ──────────────────────────────────────────

class TestBuildSettingsOverrides:

    def setup_method(self):
        reset_settings()

    def teardown_method(self):
        reset_settings()

    def test_override_risk_domain(self):
        from app.config.settings.risk import RiskSettings
        custom_risk = RiskSettings(global_halt=True)
        s = build_settings(overrides={"risk": custom_risk})
        assert s.risk.global_halt is True

    def test_override_cache_domain(self):
        from app.config.settings.cache import CacheSettings, CacheBackend
        custom_cache = CacheSettings(backend=CacheBackend.NONE)
        s = build_settings(overrides={"cache": custom_cache})
        assert s.cache.backend == CacheBackend.NONE.value

    def test_override_does_not_affect_other_domains(self):
        from app.config.settings.risk import RiskSettings
        custom_risk = RiskSettings(global_halt=True)
        s = build_settings(overrides={"risk": custom_risk})
        # Other domains should still be built normally
        assert isinstance(s.app,    AppSettings)
        assert isinstance(s.broker, BrokerSettings)
        assert isinstance(s.ai,     AISettings)


# ── Cross-domain consistency ──────────────────────────────────

class TestCrossDomainConsistency:

    def setup_method(self):
        reset_settings()

    def teardown_method(self):
        reset_settings()

    def test_app_and_broker_both_present(self):
        s = build_settings()
        assert s.app.app_name is not None
        assert s.broker.active_broker is not None

    def test_market_has_nse_profile(self):
        s = build_settings()
        assert s.market.get_market("NSE") is not None

    def test_ai_has_gemini_profile(self):
        s = build_settings()
        assert s.ai.has_profile("gemini") is True

    def test_risk_not_halted_by_default(self):
        s = build_settings()
        assert s.risk.is_trading_halted() is False

    def test_cache_has_market_quotes_domain(self):
        s = build_settings()
        assert s.cache.get_domain("market_quotes") is not None

    def test_logging_has_httpx_override(self):
        s = build_settings()
        assert "httpx" in s.logging.module_overrides
