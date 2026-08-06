"""
config/exceptions.py
====================
JARVIS OS typed exception hierarchy.

Every module raises from this tree instead of returning error dicts
or bare Exception instances. Callers catch specific types to make
precise retry, degradation, and recovery decisions.

All exceptions carry:
  message   -- human-readable description
  code      -- machine-readable string (for API responses, logs, metrics)
  context   -- dict of extra diagnostic info (symbol, provider, etc.)
  retryable -- True if the caller should retry the operation
"""
from __future__ import annotations

from typing import Dict, Any, Optional


# ── Base ──────────────────────────────────────────────────────

class JarvisError(Exception):
    """Base class for all JARVIS exceptions."""

    code:      str  = "jarvis_error"
    retryable: bool = False

    def __init__(
        self,
        message:  str,
        code:     Optional[str]         = None,
        context:  Optional[Dict[str, Any]] = None,
        retryable: Optional[bool]       = None,
    ):
        super().__init__(message)
        self.message  = message
        self.code     = code      if code      is not None else self.__class__.code
        self.context  = context   if context   is not None else {}
        self.retryable = retryable if retryable is not None else self.__class__.retryable

    def to_dict(self) -> Dict[str, Any]:
        """Serialise to a dict suitable for API error responses."""
        return {
            "error":     self.code,
            "message":   self.message,
            "retryable": self.retryable,
            "context":   self.context,
        }

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(code={self.code!r}, message={self.message!r})"


# ── Configuration errors ──────────────────────────────────────

class ConfigurationError(JarvisError):
    """Raised when the application is misconfigured."""
    code      = "configuration_error"
    retryable = False


class MissingCredentialError(ConfigurationError):
    """A required credential (API key, secret, token) is absent."""
    code = "missing_credential"


class InvalidSettingError(ConfigurationError):
    """A settings value is present but invalid (wrong type, out of range)."""
    code = "invalid_setting"


class StartupValidationError(ConfigurationError):
    """
    Raised during the startup validation chain when a critical
    requirement is not met. Server must not start.
    """
    code = "startup_validation_failed"


# ── Market data errors ────────────────────────────────────────

class MarketDataError(JarvisError):
    """Base for all market data fetch failures."""
    code      = "market_data_error"
    retryable = True


class ProviderUnavailableError(MarketDataError):
    """No market data provider is currently available."""
    code      = "provider_unavailable"
    retryable = True


class InsufficientDataError(MarketDataError):
    """Provider returned data but not enough for the requested operation."""
    code      = "insufficient_data"
    retryable = False


class RateLimitError(MarketDataError):
    """Provider rate limit hit -- back off before retrying."""
    code      = "rate_limit"
    retryable = True


class InvalidSymbolError(MarketDataError):
    """Symbol is not recognised by the provider."""
    code      = "invalid_symbol"
    retryable = False


# ── Broker errors ─────────────────────────────────────────────

class BrokerError(JarvisError):
    """Base for all broker/order management failures."""
    code      = "broker_error"
    retryable = False


class AuthenticationError(BrokerError):
    """Broker login or token validation failed."""
    code      = "authentication_failed"
    retryable = True   # re-login may succeed


class OrderRejectedError(BrokerError):
    """Broker rejected the order (invalid params, market closed, etc.)."""
    code      = "order_rejected"
    retryable = False


class SessionExpiredError(BrokerError):
    """Broker session has expired -- re-login required."""
    code      = "session_expired"
    retryable = True


class InsufficientFundsError(BrokerError):
    """Not enough funds/margin to place the order."""
    code      = "insufficient_funds"
    retryable = False


# ── AI errors ─────────────────────────────────────────────────

class AIError(JarvisError):
    """Base for all AI/LLM/model failures."""
    code      = "ai_error"
    retryable = True


class LLMTimeoutError(AIError):
    """LLM API call exceeded the configured timeout."""
    code      = "llm_timeout"
    retryable = True


class InferenceError(AIError):
    """Model inference failed (bad input, internal model error)."""
    code      = "inference_error"
    retryable = False


class ModelNotFoundError(AIError):
    """Requested model is not registered or available."""
    code      = "model_not_found"
    retryable = False


# ── Trading errors ────────────────────────────────────────────

class TradingError(JarvisError):
    """Base for all trading logic failures."""
    code      = "trading_error"
    retryable = False


class RiskLimitExceededError(TradingError):
    """Trade would breach a configured risk limit."""
    code = "risk_limit_exceeded"


class FeatureDisabledError(TradingError):
    """Operation attempted on a disabled feature flag."""
    code = "feature_disabled"


class PositionNotFoundError(TradingError):
    """Referenced position does not exist in the portfolio."""
    code = "position_not_found"


class DrawdownHaltError(TradingError):
    """
    Trading halted because daily drawdown limit was breached.
    All new orders must be blocked until the next session.
    """
    code = "drawdown_halt"
