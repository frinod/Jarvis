"""
test_exceptions.py -- Task 2 validation
Tests for app/config/exceptions.py
"""
from __future__ import annotations
import pytest
from app.config.exceptions import (
    JarvisError,
    ConfigurationError, MissingCredentialError, InvalidSettingError,
    StartupValidationError,
    MarketDataError, ProviderUnavailableError, InsufficientDataError,
    RateLimitError, InvalidSymbolError,
    BrokerError, AuthenticationError, OrderRejectedError,
    SessionExpiredError, InsufficientFundsError,
    AIError, LLMTimeoutError, InferenceError, ModelNotFoundError,
    TradingError, RiskLimitExceededError, FeatureDisabledError,
    PositionNotFoundError, DrawdownHaltError,
)


class TestBaseException:

    def test_instantiates_with_message(self):
        e = JarvisError("something went wrong")
        assert e.message == "something went wrong"
        assert str(e) == "something went wrong"

    def test_default_code(self):
        e = JarvisError("msg")
        assert e.code == "jarvis_error"

    def test_default_retryable_false(self):
        e = JarvisError("msg")
        assert e.retryable is False

    def test_default_context_empty_dict(self):
        e = JarvisError("msg")
        assert e.context == {}

    def test_custom_code(self):
        e = JarvisError("msg", code="custom_code")
        assert e.code == "custom_code"

    def test_custom_context(self):
        e = JarvisError("msg", context={"symbol": "RELIANCE"})
        assert e.context["symbol"] == "RELIANCE"

    def test_custom_retryable(self):
        e = JarvisError("msg", retryable=True)
        assert e.retryable is True

    def test_to_dict_structure(self):
        e = JarvisError("msg", code="test_code", context={"k": "v"}, retryable=True)
        d = e.to_dict()
        assert d["error"]     == "test_code"
        assert d["message"]   == "msg"
        assert d["retryable"] is True
        assert d["context"]   == {"k": "v"}

    def test_repr_contains_code_and_message(self):
        e = JarvisError("bad thing", code="bad_code")
        r = repr(e)
        assert "bad_code" in r
        assert "bad thing" in r

    def test_is_exception_subclass(self):
        e = JarvisError("msg")
        assert isinstance(e, Exception)


class TestInheritanceTree:
    """Every exception must be an instance of its parent chain."""

    def test_configuration_error_chain(self):
        e = ConfigurationError("cfg")
        assert isinstance(e, JarvisError)

    def test_missing_credential_chain(self):
        e = MissingCredentialError("cred")
        assert isinstance(e, ConfigurationError)
        assert isinstance(e, JarvisError)

    def test_invalid_setting_chain(self):
        e = InvalidSettingError("setting")
        assert isinstance(e, ConfigurationError)

    def test_startup_validation_chain(self):
        e = StartupValidationError("startup")
        assert isinstance(e, ConfigurationError)

    def test_market_data_error_chain(self):
        e = MarketDataError("md")
        assert isinstance(e, JarvisError)

    def test_provider_unavailable_chain(self):
        e = ProviderUnavailableError("prov")
        assert isinstance(e, MarketDataError)
        assert isinstance(e, JarvisError)

    def test_insufficient_data_chain(self):
        e = InsufficientDataError("data")
        assert isinstance(e, MarketDataError)

    def test_rate_limit_chain(self):
        e = RateLimitError("rate")
        assert isinstance(e, MarketDataError)

    def test_invalid_symbol_chain(self):
        e = InvalidSymbolError("sym")
        assert isinstance(e, MarketDataError)

    def test_broker_error_chain(self):
        e = BrokerError("broker")
        assert isinstance(e, JarvisError)

    def test_authentication_error_chain(self):
        e = AuthenticationError("auth")
        assert isinstance(e, BrokerError)

    def test_order_rejected_chain(self):
        e = OrderRejectedError("order")
        assert isinstance(e, BrokerError)

    def test_session_expired_chain(self):
        e = SessionExpiredError("session")
        assert isinstance(e, BrokerError)

    def test_insufficient_funds_chain(self):
        e = InsufficientFundsError("funds")
        assert isinstance(e, BrokerError)

    def test_ai_error_chain(self):
        e = AIError("ai")
        assert isinstance(e, JarvisError)

    def test_llm_timeout_chain(self):
        e = LLMTimeoutError("timeout")
        assert isinstance(e, AIError)

    def test_inference_error_chain(self):
        e = InferenceError("infer")
        assert isinstance(e, AIError)

    def test_model_not_found_chain(self):
        e = ModelNotFoundError("model")
        assert isinstance(e, AIError)

    def test_trading_error_chain(self):
        e = TradingError("trade")
        assert isinstance(e, JarvisError)

    def test_risk_limit_chain(self):
        e = RiskLimitExceededError("risk")
        assert isinstance(e, TradingError)

    def test_feature_disabled_chain(self):
        e = FeatureDisabledError("flag")
        assert isinstance(e, TradingError)

    def test_position_not_found_chain(self):
        e = PositionNotFoundError("pos")
        assert isinstance(e, TradingError)

    def test_drawdown_halt_chain(self):
        e = DrawdownHaltError("dd")
        assert isinstance(e, TradingError)


class TestRetryableFlags:
    """Verify retryable is set correctly per exception type."""

    def test_configuration_errors_not_retryable(self):
        for cls in (ConfigurationError, MissingCredentialError,
                    InvalidSettingError, StartupValidationError):
            assert cls("x").retryable is False, f"{cls.__name__} should not be retryable"

    def test_market_data_base_retryable(self):
        assert MarketDataError("x").retryable is True

    def test_provider_unavailable_retryable(self):
        assert ProviderUnavailableError("x").retryable is True

    def test_rate_limit_retryable(self):
        assert RateLimitError("x").retryable is True

    def test_insufficient_data_not_retryable(self):
        assert InsufficientDataError("x").retryable is False

    def test_invalid_symbol_not_retryable(self):
        assert InvalidSymbolError("x").retryable is False

    def test_authentication_retryable(self):
        assert AuthenticationError("x").retryable is True

    def test_session_expired_retryable(self):
        assert SessionExpiredError("x").retryable is True

    def test_order_rejected_not_retryable(self):
        assert OrderRejectedError("x").retryable is False

    def test_insufficient_funds_not_retryable(self):
        assert InsufficientFundsError("x").retryable is False

    def test_ai_base_retryable(self):
        assert AIError("x").retryable is True

    def test_llm_timeout_retryable(self):
        assert LLMTimeoutError("x").retryable is True

    def test_inference_error_not_retryable(self):
        assert InferenceError("x").retryable is False

    def test_model_not_found_not_retryable(self):
        assert ModelNotFoundError("x").retryable is False

    def test_trading_errors_not_retryable(self):
        for cls in (TradingError, RiskLimitExceededError, FeatureDisabledError,
                    PositionNotFoundError, DrawdownHaltError):
            assert cls("x").retryable is False, f"{cls.__name__} should not be retryable"


class TestMachineCodes:
    """Every exception must have a unique, non-empty machine-readable code."""

    def _all_classes(self):
        return [
            JarvisError, ConfigurationError, MissingCredentialError,
            InvalidSettingError, StartupValidationError,
            MarketDataError, ProviderUnavailableError, InsufficientDataError,
            RateLimitError, InvalidSymbolError,
            BrokerError, AuthenticationError, OrderRejectedError,
            SessionExpiredError, InsufficientFundsError,
            AIError, LLMTimeoutError, InferenceError, ModelNotFoundError,
            TradingError, RiskLimitExceededError, FeatureDisabledError,
            PositionNotFoundError, DrawdownHaltError,
        ]

    def test_all_codes_non_empty(self):
        for cls in self._all_classes():
            assert cls.code, f"{cls.__name__} has empty code"

    def test_all_codes_unique(self):
        codes = [cls.code for cls in self._all_classes()]
        assert len(codes) == len(set(codes)), "Duplicate exception codes found"

    def test_codes_are_snake_case(self):
        import re
        for cls in self._all_classes():
            assert re.match(r'^[a-z][a-z0-9_]*$', cls.code), (
                f"{cls.__name__}.code={cls.code!r} is not snake_case"
            )


class TestContextAndCatchability:

    def test_catchable_as_jarvis_error(self):
        with pytest.raises(JarvisError):
            raise RateLimitError("too fast", context={"provider": "angel_one"})

    def test_catchable_as_market_data_error(self):
        with pytest.raises(MarketDataError):
            raise InsufficientDataError("not enough candles")

    def test_context_preserved_through_raise(self):
        try:
            raise InvalidSymbolError("bad sym", context={"symbol": "FAKE999"})
        except InvalidSymbolError as e:
            assert e.context["symbol"] == "FAKE999"

    def test_retryable_override_at_instantiation(self):
        e = ProviderUnavailableError("down", retryable=False)
        assert e.retryable is False

    def test_to_dict_used_in_api_response_pattern(self):
        e = OrderRejectedError("price out of range", context={"price": 9999})
        d = e.to_dict()
        assert d["error"] == "order_rejected"
        assert d["context"]["price"] == 9999
        assert d["retryable"] is False
