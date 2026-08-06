"""
test_settings_logging.py -- Task 10 validation
Tests for app/config/settings/logging.py
"""
from __future__ import annotations

import os
import pytest

from app.config.settings.logging import (
    LogLevel,
    LogFormat,
    LogHandler,
    FileHandlerConfig,
    ModuleLogConfig,
    LoggingSettings,
    build_logging_settings,
)


# ── FileHandlerConfig ─────────────────────────────────────────

class TestFileHandlerConfig:

    def test_defaults(self):
        f = FileHandlerConfig()
        assert f.log_dir          == "logs"
        assert f.max_bytes        == 10_485_760
        assert f.backup_count     == 7
        assert f.filename_pattern == "%Y-%m-%d"
        assert f.encoding         == "utf-8"

    def test_max_bytes_must_be_positive(self):
        with pytest.raises(Exception):
            FileHandlerConfig(max_bytes=0)

    def test_backup_count_zero_allowed(self):
        f = FileHandlerConfig(backup_count=0)
        assert f.backup_count == 0

    def test_backup_count_negative_rejected(self):
        with pytest.raises(Exception):
            FileHandlerConfig(backup_count=-1)

    def test_immutable(self):
        f = FileHandlerConfig()
        with pytest.raises(TypeError):
            f.log_dir = "/tmp/logs"

    def test_to_dict(self):
        f = FileHandlerConfig()
        d = f.to_dict()
        assert d["log_dir"] == "logs"


# ── ModuleLogConfig ───────────────────────────────────────────

class TestModuleLogConfig:

    def test_defaults(self):
        m = ModuleLogConfig()
        assert m.level       == LogLevel.INFO.value
        assert m.sample_rate == 1.0

    def test_sample_rate_lower_bound(self):
        m = ModuleLogConfig(sample_rate=0.0)
        assert m.sample_rate == 0.0

    def test_sample_rate_upper_bound(self):
        m = ModuleLogConfig(sample_rate=1.0)
        assert m.sample_rate == 1.0

    def test_sample_rate_out_of_range(self):
        with pytest.raises(Exception):
            ModuleLogConfig(sample_rate=1.1)

    def test_sample_rate_negative_rejected(self):
        with pytest.raises(Exception):
            ModuleLogConfig(sample_rate=-0.1)

    def test_all_log_levels_accepted(self):
        for level in LogLevel:
            m = ModuleLogConfig(level=level)
            assert m.level == level.value

    def test_immutable(self):
        m = ModuleLogConfig()
        with pytest.raises(TypeError):
            m.level = "DEBUG"

    def test_to_dict(self):
        m = ModuleLogConfig(level=LogLevel.DEBUG, sample_rate=0.5)
        d = m.to_dict()
        assert d["level"]       == LogLevel.DEBUG.value
        assert d["sample_rate"] == 0.5


# ── LoggingSettings ───────────────────────────────────────────

class TestLoggingSettings:

    def test_defaults(self):
        s = LoggingSettings()
        assert s.level             == LogLevel.INFO.value
        assert s.format            == LogFormat.HUMAN.value
        assert s.handler           == LogHandler.BOTH.value
        assert s.include_timestamp is True
        assert s.include_caller    is False

    def test_sensitive_fields_defaults(self):
        s = LoggingSettings()
        assert "password"     in s.sensitive_fields
        assert "api_key"      in s.sensitive_fields
        assert "secret_key"   in s.sensitive_fields
        assert "access_token" in s.sensitive_fields

    def test_is_sensitive_true(self):
        s = LoggingSettings()
        assert s.is_sensitive("password")     is True
        assert s.is_sensitive("api_key")      is True
        assert s.is_sensitive("ACCESS_TOKEN") is True   # case-insensitive

    def test_is_sensitive_false(self):
        s = LoggingSettings()
        assert s.is_sensitive("username") is False
        assert s.is_sensitive("symbol")   is False

    def test_level_for_no_override_returns_global(self):
        s = LoggingSettings(level=LogLevel.DEBUG)
        assert s.level_for("app.some.module") == LogLevel.DEBUG.value

    def test_level_for_with_override(self):
        override = ModuleLogConfig(level=LogLevel.WARNING)
        s = LoggingSettings(module_overrides={"httpx": override})
        assert s.level_for("httpx") == LogLevel.WARNING.value

    def test_sample_rate_for_no_override_returns_one(self):
        s = LoggingSettings()
        assert s.sample_rate_for("app.some.module") == 1.0

    def test_sample_rate_for_with_override(self):
        override = ModuleLogConfig(sample_rate=0.1)
        s = LoggingSettings(module_overrides={"app.market_data": override})
        assert s.sample_rate_for("app.market_data") == 0.1

    def test_immutable(self):
        s = LoggingSettings()
        with pytest.raises(TypeError):
            s.level = "DEBUG"

    def test_to_dict_structure(self):
        s = LoggingSettings()
        d = s.to_dict()
        for key in ("level", "format", "handler", "include_timestamp",
                    "include_caller", "sensitive_fields",
                    "file_handler", "module_overrides"):
            assert key in d

    def test_all_log_levels_accepted(self):
        for level in LogLevel:
            s = LoggingSettings(level=level)
            assert s.level == level.value

    def test_all_formats_accepted(self):
        for fmt in LogFormat:
            s = LoggingSettings(format=fmt)
            assert s.format == fmt.value

    def test_all_handlers_accepted(self):
        for handler in LogHandler:
            s = LoggingSettings(handler=handler)
            assert s.handler == handler.value


# ── Factory ───────────────────────────────────────────────────

class TestBuildLoggingSettings:

    def setup_method(self):
        for key in ("LOG_LEVEL", "LOG_FORMAT", "LOG_HANDLER",
                    "LOG_DIR", "LOG_MAX_BYTES", "LOG_BACKUP_COUNT",
                    "LOG_INCLUDE_CALLER"):
            os.environ.pop(key, None)

    def test_factory_returns_logging_settings(self):
        s = build_logging_settings()
        assert isinstance(s, LoggingSettings)

    def test_factory_default_level(self):
        s = build_logging_settings()
        assert s.level == LogLevel.INFO.value

    def test_factory_level_from_env(self):
        os.environ["LOG_LEVEL"] = "DEBUG"
        s = build_logging_settings()
        assert s.level == LogLevel.DEBUG.value

    def test_factory_invalid_level_defaults_to_info(self):
        os.environ["LOG_LEVEL"] = "BANANA"
        s = build_logging_settings()
        assert s.level == LogLevel.INFO.value

    def test_factory_format_from_env(self):
        os.environ["LOG_FORMAT"] = "json"
        s = build_logging_settings()
        assert s.format == LogFormat.JSON.value

    def test_factory_invalid_format_defaults_to_human(self):
        os.environ["LOG_FORMAT"] = "banana"
        s = build_logging_settings()
        assert s.format == LogFormat.HUMAN.value

    def test_factory_handler_from_env(self):
        os.environ["LOG_HANDLER"] = "console"
        s = build_logging_settings()
        assert s.handler == LogHandler.CONSOLE.value

    def test_factory_invalid_handler_defaults_to_both(self):
        os.environ["LOG_HANDLER"] = "banana"
        s = build_logging_settings()
        assert s.handler == LogHandler.BOTH.value

    def test_factory_log_dir_from_env(self):
        os.environ["LOG_DIR"] = "/var/log/jarvis"
        s = build_logging_settings()
        assert s.file_handler.log_dir == "/var/log/jarvis"

    def test_factory_max_bytes_from_env(self):
        os.environ["LOG_MAX_BYTES"] = "5242880"
        s = build_logging_settings()
        assert s.file_handler.max_bytes == 5242880

    def test_factory_backup_count_from_env(self):
        os.environ["LOG_BACKUP_COUNT"] = "14"
        s = build_logging_settings()
        assert s.file_handler.backup_count == 14

    def test_factory_include_caller_from_env(self):
        os.environ["LOG_INCLUDE_CALLER"] = "true"
        s = build_logging_settings()
        assert s.include_caller is True

    def test_factory_default_module_overrides_present(self):
        s = build_logging_settings()
        assert "httpx"           in s.module_overrides
        assert "uvicorn.access"  in s.module_overrides
        assert "app.market_data" in s.module_overrides

    def test_factory_httpx_silenced_by_default(self):
        s = build_logging_settings()
        assert s.level_for("httpx") == LogLevel.WARNING.value

    def test_factory_overrides_take_precedence(self):
        s = build_logging_settings(overrides={"include_caller": True})
        assert s.include_caller is True
