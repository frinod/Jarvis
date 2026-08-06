"""
test_config_init.py -- Task 12 validation
Tests for app/config/__init__.py (top-level public API)
"""
from __future__ import annotations

import pytest


class TestConfigPublicAPI:
    """All public symbols must be importable from app.config."""

    def test_environment_symbols(self):
        from app.config import (
            Environment, get_env, is_production, is_testing,
            is_staging, is_development, profile_overrides,
            require_strict_security,
        )
        assert all(x is not None for x in [
            Environment, get_env, is_production, is_testing,
            is_staging, is_development, profile_overrides,
            require_strict_security,
        ])

    def test_exception_symbols(self):
        from app.config import (
            JarvisError, ConfigurationError, MissingCredentialError,
            InvalidSettingError, StartupValidationError,
            MarketDataError, ProviderUnavailableError, InsufficientDataError,
            RateLimitError, InvalidSymbolError,
            BrokerError, AuthenticationError, OrderRejectedError,
            SessionExpiredError, InsufficientFundsError,
            AIError, LLMTimeoutError, InferenceError, ModelNotFoundError,
            TradingError, RiskLimitExceededError, FeatureDisabledError,
            PositionNotFoundError, DrawdownHaltError,
        )
        assert JarvisError is not None
        assert issubclass(ConfigurationError, JarvisError)
        assert issubclass(MarketDataError,    JarvisError)
        assert issubclass(BrokerError,        JarvisError)
        assert issubclass(AIError,            JarvisError)
        assert issubclass(TradingError,       JarvisError)

    def test_retry_symbols(self):
        from app.config import (
            RetryPolicy, RetryStrategy, RetryObserver,
            RetryExhaustedError, with_retry,
            PROVIDER_RETRY, LLM_RETRY, BROKER_RETRY, DEFAULT_RETRY,
        )
        assert RetryPolicy    is not None
        assert PROVIDER_RETRY is not None
        assert callable(with_retry)

    def test_settings_symbols(self):
        from app.config import (
            JarvisSettings, build_settings, get_settings, reset_settings,
            AppSettings, BrokerSettings, MarketSettings, AISettings,
            RiskSettings, CacheSettings, LoggingSettings, ProviderSettings,
        )
        assert JarvisSettings is not None
        assert callable(get_settings)
        assert callable(reset_settings)

    def test_get_settings_returns_jarvis_settings(self):
        from app.config import get_settings, reset_settings, JarvisSettings
        reset_settings()
        s = get_settings()
        assert isinstance(s, JarvisSettings)
        reset_settings()

    def test_single_import_path_works(self):
        """Consumers should only need to import from app.config."""
        import app.config as cfg
        assert hasattr(cfg, "get_settings")
        assert hasattr(cfg, "JarvisError")
        assert hasattr(cfg, "RetryPolicy")
        assert hasattr(cfg, "Environment")

    def test_retry_policy_shim_same_as_resilience(self):
        """config.RetryPolicy and resilience.RetryPolicy must be the same object."""
        from app.config import RetryPolicy as CRP
        from app.resilience import RetryPolicy as RRP
        assert CRP is RRP
