"""
test_settings_app.py -- Task 4 validation
Tests for app/config/settings/app.py
"""
from __future__ import annotations

import os
import pytest
from datetime import datetime, timezone

from app.config.settings.app import AppSettings, ConfigMetadata, build_app_settings


# ── ConfigMetadata ────────────────────────────────────────────

class TestConfigMetadata:

    def test_defaults(self):
        m = ConfigMetadata()
        assert m.source         == "default"
        assert m.config_version == 1
        assert m.validated      is False
        assert m.environment    == "development"

    def test_loaded_at_is_utc_datetime(self):
        m = ConfigMetadata()
        assert isinstance(m.loaded_at, datetime)
        assert m.loaded_at.tzinfo is not None

    def test_mark_validated_returns_new_instance(self):
        m = ConfigMetadata(source="env", environment="production")
        m2 = m.mark_validated()
        assert m2.validated      is True
        assert m2.source         == "env"
        assert m2.environment    == "production"
        # Original unchanged
        assert m.validated is False

    def test_to_dict_structure(self):
        m = ConfigMetadata(source="env", config_version=2, environment="staging")
        d = m.to_dict()
        assert d["source"]         == "env"
        assert d["config_version"] == 2
        assert d["environment"]    == "staging"
        assert d["validated"]      is False
        assert "loaded_at" in d

    def test_to_dict_loaded_at_is_iso_string(self):
        m = ConfigMetadata()
        d = m.to_dict()
        # Should parse back to datetime without error
        datetime.fromisoformat(d["loaded_at"].replace("Z", "+00:00"))


# ── AppSettings defaults ──────────────────────────────────────

class TestAppSettingsDefaults:

    def test_default_app_name(self):
        s = AppSettings()
        assert s.app_name == "JARVIS OS"

    def test_default_version(self):
        s = AppSettings()
        assert s.version == "1.0.0"

    def test_default_environment(self):
        s = AppSettings()
        assert s.environment == "development"

    def test_default_port(self):
        s = AppSettings()
        assert s.port == 8000

    def test_default_debug_false(self):
        s = AppSettings()
        assert s.debug is False

    def test_default_secret_key_is_insecure(self):
        s = AppSettings()
        assert s.has_default_secret is True

    def test_default_config_version(self):
        s = AppSettings()
        assert s.config_version == 1

    def test_default_build_id(self):
        s = AppSettings()
        assert s.build_id == "local"


# ── AppSettings validators ────────────────────────────────────

class TestAppSettingsValidators:

    def test_unknown_environment_defaults_to_development(self):
        s = AppSettings(environment="banana")
        assert s.environment == "development"

    def test_known_environments_accepted(self):
        for env in ("development", "testing", "staging", "production"):
            s = AppSettings(environment=env)
            assert s.environment == env

    def test_port_out_of_range_raises(self):
        with pytest.raises(Exception):
            AppSettings(port=0)
        with pytest.raises(Exception):
            AppSettings(port=99999)

    def test_port_valid_boundary(self):
        assert AppSettings(port=1).port    == 1
        assert AppSettings(port=65535).port == 65535

    def test_token_expiry_zero_raises(self):
        with pytest.raises(Exception):
            AppSettings(access_token_expire_minutes=0)

    def test_token_expiry_negative_raises(self):
        with pytest.raises(Exception):
            AppSettings(access_token_expire_minutes=-1)

    def test_config_version_zero_raises(self):
        with pytest.raises(Exception):
            AppSettings(config_version=0)

    def test_config_version_positive_accepted(self):
        s = AppSettings(config_version=5)
        assert s.config_version == 5


# ── Immutability ──────────────────────────────────────────────

class TestImmutability:

    def test_mutation_raises(self):
        s = AppSettings()
        with pytest.raises(TypeError):
            s.app_name = "hacked"

    def test_port_mutation_raises(self):
        s = AppSettings()
        with pytest.raises(TypeError):
            s.port = 9999


# ── Security properties ───────────────────────────────────────

class TestSecurityProperties:

    def test_has_default_secret_true_for_default(self):
        s = AppSettings(secret_key="change-me-in-production")
        assert s.has_default_secret is True

    def test_has_default_secret_false_for_custom(self):
        s = AppSettings(secret_key="my-real-secret-key-abc123")
        assert s.has_default_secret is False

    def test_to_dict_redacts_secret_key(self):
        s = AppSettings(secret_key="super-secret")
        d = s.to_dict()
        assert d["secret_key"] == "[REDACTED]"
        assert "super-secret" not in str(d)

    def test_is_debug_property(self):
        assert AppSettings(debug=True).is_debug  is True
        assert AppSettings(debug=False).is_debug is False


# ── to_dict ───────────────────────────────────────────────────

class TestToDict:

    def test_to_dict_contains_expected_keys(self):
        s = AppSettings()
        d = s.to_dict()
        for key in ("app_name", "version", "config_version",
                    "environment", "build_id", "host", "port", "debug"):
            assert key in d, f"Missing key: {key}"

    def test_to_dict_values_match_fields(self):
        s = AppSettings(app_name="TestApp", port=9000, debug=True)
        d = s.to_dict()
        assert d["app_name"] == "TestApp"
        assert d["port"]     == 9000
        assert d["debug"]    is True


# ── Factory function ──────────────────────────────────────────

class TestBuildAppSettings:

    def setup_method(self):
        """Clean env vars before each test."""
        for key in ("JARVIS_APP_NAME", "JARVIS_PORT", "JARVIS_DEBUG",
                    "SECRET_KEY", "JARVIS_CONFIG_VERSION", "JARVIS_ENV"):
            os.environ.pop(key, None)

    def test_factory_returns_app_settings(self):
        s = build_app_settings()
        assert isinstance(s, AppSettings)

    def test_factory_reads_env_var(self):
        os.environ["JARVIS_APP_NAME"] = "MyJarvis"
        s = build_app_settings()
        assert s.app_name == "MyJarvis"
        os.environ.pop("JARVIS_APP_NAME")

    def test_factory_reads_port_env_var(self):
        os.environ["JARVIS_PORT"] = "9090"
        s = build_app_settings()
        assert s.port == 9090
        os.environ.pop("JARVIS_PORT")

    def test_factory_reads_debug_env_var(self):
        os.environ["JARVIS_DEBUG"] = "true"
        s = build_app_settings()
        assert s.debug is True
        os.environ.pop("JARVIS_DEBUG")

    def test_factory_overrides_take_precedence(self):
        os.environ["JARVIS_APP_NAME"] = "FromEnv"
        s = build_app_settings(overrides={"app_name": "FromOverride"})
        assert s.app_name == "FromOverride"
        os.environ.pop("JARVIS_APP_NAME")

    def test_factory_secret_key_from_env(self):
        os.environ["SECRET_KEY"] = "env-secret-xyz"
        s = build_app_settings()
        assert s.has_default_secret is False
        os.environ.pop("SECRET_KEY")

    def test_factory_environment_from_jarvis_env(self):
        os.environ["JARVIS_ENV"] = "staging"
        s = build_app_settings()
        assert s.environment == "staging"
        os.environ.pop("JARVIS_ENV")

    def test_factory_config_version_from_env(self):
        os.environ["JARVIS_CONFIG_VERSION"] = "3"
        s = build_app_settings()
        assert s.config_version == 3
        os.environ.pop("JARVIS_CONFIG_VERSION")
