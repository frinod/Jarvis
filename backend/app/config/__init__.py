"""
config/__init__.py
==================
Public API for the JARVIS OS configuration package.

Consumers import from here. Internal module structure is an
implementation detail -- only this surface is stable.

Usage
-----
    from app.config import get_settings, JarvisSettings
    from app.config import Environment, get_env, is_production
    from app.config import JarvisError, MarketDataError, BrokerError
    from app.config import RetryPolicy, with_retry, PROVIDER_RETRY

    settings = get_settings()
    settings.app.port
    settings.broker.get_active()
    settings.risk.is_trading_halted()
"""
from app.config.environment import (
    Environment,
    get_env,
    is_production,
    is_testing,
    is_staging,
    is_development,
    profile_overrides,
    require_strict_security,
)

from app.config.exceptions import (
    JarvisError,
    ConfigurationError,
    MissingCredentialError,
    InvalidSettingError,
    StartupValidationError,
    MarketDataError,
    ProviderUnavailableError,
    InsufficientDataError,
    RateLimitError,
    InvalidSymbolError,
    BrokerError,
    AuthenticationError,
    OrderRejectedError,
    SessionExpiredError,
    InsufficientFundsError,
    AIError,
    LLMTimeoutError,
    InferenceError,
    ModelNotFoundError,
    TradingError,
    RiskLimitExceededError,
    FeatureDisabledError,
    PositionNotFoundError,
    DrawdownHaltError,
)

from app.config.retry_policy import (
    RetryPolicy,
    RetryStrategy,
    RetryObserver,
    RetryExhaustedError,
    with_retry,
    PROVIDER_RETRY,
    LLM_RETRY,
    BROKER_RETRY,
    DEFAULT_RETRY,
)

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

__all__ = [
    # Environment
    "Environment",
    "get_env",
    "is_production",
    "is_testing",
    "is_staging",
    "is_development",
    "profile_overrides",
    "require_strict_security",
    # Exceptions
    "JarvisError",
    "ConfigurationError",
    "MissingCredentialError",
    "InvalidSettingError",
    "StartupValidationError",
    "MarketDataError",
    "ProviderUnavailableError",
    "InsufficientDataError",
    "RateLimitError",
    "InvalidSymbolError",
    "BrokerError",
    "AuthenticationError",
    "OrderRejectedError",
    "SessionExpiredError",
    "InsufficientFundsError",
    "AIError",
    "LLMTimeoutError",
    "InferenceError",
    "ModelNotFoundError",
    "TradingError",
    "RiskLimitExceededError",
    "FeatureDisabledError",
    "PositionNotFoundError",
    "DrawdownHaltError",
    # Retry
    "RetryPolicy",
    "RetryStrategy",
    "RetryObserver",
    "RetryExhaustedError",
    "with_retry",
    "PROVIDER_RETRY",
    "LLM_RETRY",
    "BROKER_RETRY",
    "DEFAULT_RETRY",
    # Settings
    "JarvisSettings",
    "build_settings",
    "get_settings",
    "reset_settings",
    "AppSettings",
    "BrokerSettings",
    "MarketSettings",
    "AISettings",
    "RiskSettings",
    "CacheSettings",
    "LoggingSettings",
    "ProviderSettings",
]
