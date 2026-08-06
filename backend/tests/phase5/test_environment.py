"""
test_environment.py -- Task 1 validation
Tests for app/config/environment.py
"""
from __future__ import annotations
import os
import pytest

# Each test sets JARVIS_ENV explicitly and reloads the module
# to avoid state leaking between tests.


def _reload_env():
    """Force re-import so get_env() re-reads os.environ."""
    import importlib
    import app.config.environment as m
    importlib.reload(m)
    return m


class TestEnvironmentDetection:

    def test_default_is_development(self):
        os.environ.pop("JARVIS_ENV", None)
        m = _reload_env()
        assert m.get_env() == m.Environment.DEVELOPMENT

    def test_development_explicit(self):
        os.environ["JARVIS_ENV"] = "development"
        m = _reload_env()
        assert m.get_env() == m.Environment.DEVELOPMENT

    def test_testing_profile(self):
        os.environ["JARVIS_ENV"] = "testing"
        m = _reload_env()
        assert m.get_env() == m.Environment.TESTING

    def test_staging_profile(self):
        os.environ["JARVIS_ENV"] = "staging"
        m = _reload_env()
        assert m.get_env() == m.Environment.STAGING

    def test_production_profile(self):
        os.environ["JARVIS_ENV"] = "production"
        m = _reload_env()
        assert m.get_env() == m.Environment.PRODUCTION

    def test_unknown_value_defaults_to_development(self):
        os.environ["JARVIS_ENV"] = "banana"
        m = _reload_env()
        assert m.get_env() == m.Environment.DEVELOPMENT

    def test_case_insensitive(self):
        os.environ["JARVIS_ENV"] = "PRODUCTION"
        m = _reload_env()
        assert m.get_env() == m.Environment.PRODUCTION

    def test_whitespace_stripped(self):
        os.environ["JARVIS_ENV"] = "  staging  "
        m = _reload_env()
        assert m.get_env() == m.Environment.STAGING


class TestBooleanHelpers:

    def test_is_production_true(self):
        os.environ["JARVIS_ENV"] = "production"
        m = _reload_env()
        assert m.is_production() is True
        assert m.is_testing() is False
        assert m.is_staging() is False
        assert m.is_development() is False

    def test_is_testing_true(self):
        os.environ["JARVIS_ENV"] = "testing"
        m = _reload_env()
        assert m.is_testing() is True
        assert m.is_production() is False

    def test_is_staging_true(self):
        os.environ["JARVIS_ENV"] = "staging"
        m = _reload_env()
        assert m.is_staging() is True

    def test_is_development_true(self):
        os.environ.pop("JARVIS_ENV", None)
        m = _reload_env()
        assert m.is_development() is True


class TestProfileOverrides:

    def test_development_overrides_empty(self):
        os.environ["JARVIS_ENV"] = "development"
        m = _reload_env()
        overrides = m.profile_overrides()
        assert overrides == {}

    def test_testing_overrides_broker(self):
        os.environ["JARVIS_ENV"] = "testing"
        m = _reload_env()
        overrides = m.profile_overrides()
        assert overrides["active_broker"] == "paper_only"
        assert overrides["active_data_provider"] == "yahoo"

    def test_testing_overrides_cache_ttls(self):
        os.environ["JARVIS_ENV"] = "testing"
        m = _reload_env()
        overrides = m.profile_overrides()
        assert overrides["ttl_candle_5m_s"] == 1
        assert overrides["ttl_fundamentals_s"] == 5

    def test_testing_disables_live_trading(self):
        os.environ["JARVIS_ENV"] = "testing"
        m = _reload_env()
        overrides = m.profile_overrides()
        assert overrides["live_trading_enabled"] is False
        assert overrides["angel_one_ws_enabled"] is False

    def test_staging_overrides_log_format(self):
        os.environ["JARVIS_ENV"] = "staging"
        m = _reload_env()
        overrides = m.profile_overrides()
        assert overrides["log_format"] == "json"

    def test_production_overrides_log_level(self):
        os.environ["JARVIS_ENV"] = "production"
        m = _reload_env()
        overrides = m.profile_overrides()
        assert overrides["log_level"] == "WARNING"
        assert overrides["log_format"] == "json"

    def test_overrides_returns_copy(self):
        """Mutating the returned dict must not affect the internal profile."""
        os.environ["JARVIS_ENV"] = "testing"
        m = _reload_env()
        overrides = m.profile_overrides()
        overrides["active_broker"] = "hacked"
        assert m.profile_overrides()["active_broker"] == "paper_only"


class TestSecurityGuard:

    def test_require_strict_security_production(self):
        os.environ["JARVIS_ENV"] = "production"
        m = _reload_env()
        assert m.require_strict_security() is True

    def test_require_strict_security_staging(self):
        os.environ["JARVIS_ENV"] = "staging"
        m = _reload_env()
        assert m.require_strict_security() is True

    def test_require_strict_security_development(self):
        os.environ.pop("JARVIS_ENV", None)
        m = _reload_env()
        assert m.require_strict_security() is False

    def test_require_strict_security_testing(self):
        os.environ["JARVIS_ENV"] = "testing"
        m = _reload_env()
        assert m.require_strict_security() is False
