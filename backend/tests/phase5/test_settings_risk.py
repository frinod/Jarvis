"""
test_settings_risk.py -- Task 8 validation
Tests for app/config/settings/risk.py
"""
from __future__ import annotations

import os
import pytest

from app.config.settings.risk import (
    PositionSizingMethod,
    HaltReason,
    PositionSizingConfig,
    DrawdownConfig,
    ExposureConfig,
    CircuitBreakerConfig,
    SlippageConfig,
    RiskSettings,
    build_risk_settings,
)


# ── PositionSizingConfig ──────────────────────────────────────

class TestPositionSizingConfig:

    def test_defaults(self):
        c = PositionSizingConfig()
        assert c.method             == PositionSizingMethod.FIXED_AMOUNT.value
        assert c.fixed_amount       == 10000.0
        assert c.fixed_percent      == 2.0
        assert c.max_position_value == 50000.0
        assert c.min_position_value == 500.0
        assert c.round_to_lot_size  is True

    def test_fixed_percent_must_be_positive(self):
        with pytest.raises(Exception):
            PositionSizingConfig(fixed_percent=0.0)

    def test_fixed_percent_upper_bound(self):
        c = PositionSizingConfig(fixed_percent=100.0)
        assert c.fixed_percent == 100.0

    def test_fixed_percent_over_100_rejected(self):
        with pytest.raises(Exception):
            PositionSizingConfig(fixed_percent=100.1)

    def test_fixed_amount_must_be_positive(self):
        with pytest.raises(Exception):
            PositionSizingConfig(fixed_amount=0.0)

    def test_max_position_value_must_be_positive(self):
        with pytest.raises(Exception):
            PositionSizingConfig(max_position_value=0.0)

    def test_min_less_than_max(self):
        with pytest.raises(Exception):
            PositionSizingConfig(min_position_value=60000.0, max_position_value=50000.0)

    def test_immutable(self):
        c = PositionSizingConfig()
        with pytest.raises(TypeError):
            c.fixed_amount = 20000.0

    def test_to_dict(self):
        c = PositionSizingConfig()
        d = c.to_dict()
        assert d["fixed_amount"] == 10000.0

    def test_all_sizing_methods_accepted(self):
        for method in PositionSizingMethod:
            c = PositionSizingConfig(method=method)
            assert c.method == method.value


# ── DrawdownConfig ────────────────────────────────────────────

class TestDrawdownConfig:

    def test_defaults(self):
        d = DrawdownConfig()
        assert d.max_daily_loss   == 5000.0
        assert d.max_weekly_loss  == 15000.0
        assert d.max_monthly_loss == 40000.0
        assert d.max_drawdown_pct == 10.0
        assert d.auto_reset_daily is True

    def test_loss_limits_must_be_positive(self):
        with pytest.raises(Exception):
            DrawdownConfig(max_daily_loss=0.0)

    def test_drawdown_pct_must_be_positive(self):
        with pytest.raises(Exception):
            DrawdownConfig(max_drawdown_pct=0.0)

    def test_drawdown_pct_upper_bound(self):
        d = DrawdownConfig(max_drawdown_pct=100.0)
        assert d.max_drawdown_pct == 100.0

    def test_trailing_stop_pct_must_be_positive(self):
        with pytest.raises(Exception):
            DrawdownConfig(trailing_stop_pct=0.0)

    def test_immutable(self):
        d = DrawdownConfig()
        with pytest.raises(TypeError):
            d.max_daily_loss = 1000.0

    def test_to_dict(self):
        d = DrawdownConfig()
        result = d.to_dict()
        assert result["max_daily_loss"] == 5000.0


# ── ExposureConfig ────────────────────────────────────────────

class TestExposureConfig:

    def test_defaults(self):
        e = ExposureConfig()
        assert e.max_open_positions   == 10
        assert e.max_sector_exposure  == 30.0
        assert e.max_symbol_exposure  == 15.0
        assert e.max_capital_deployed == 80.0
        assert e.allow_overnight      is False
        assert e.allow_derivatives    is False
        assert e.allow_short_selling  is False

    def test_max_open_positions_must_be_positive(self):
        with pytest.raises(Exception):
            ExposureConfig(max_open_positions=0)

    def test_sector_exposure_must_be_positive(self):
        with pytest.raises(Exception):
            ExposureConfig(max_sector_exposure=0.0)

    def test_capital_deployed_upper_bound(self):
        e = ExposureConfig(max_capital_deployed=100.0)
        assert e.max_capital_deployed == 100.0

    def test_capital_deployed_over_100_rejected(self):
        with pytest.raises(Exception):
            ExposureConfig(max_capital_deployed=100.1)

    def test_allow_overnight_configurable(self):
        e = ExposureConfig(allow_overnight=True)
        assert e.allow_overnight is True

    def test_immutable(self):
        e = ExposureConfig()
        with pytest.raises(TypeError):
            e.max_open_positions = 20

    def test_to_dict(self):
        e = ExposureConfig()
        d = e.to_dict()
        assert d["max_open_positions"] == 10


# ── CircuitBreakerConfig ──────────────────────────────────────

class TestCircuitBreakerConfig:

    def test_defaults(self):
        c = CircuitBreakerConfig()
        assert c.enabled             is True
        assert c.consecutive_losses  == 5
        assert c.loss_streak_reset   == 2
        assert c.rapid_loss_window_s == 300
        assert c.rapid_loss_amount   == 2000.0

    def test_consecutive_losses_must_be_positive(self):
        with pytest.raises(Exception):
            CircuitBreakerConfig(consecutive_losses=0)

    def test_loss_streak_reset_must_be_positive(self):
        with pytest.raises(Exception):
            CircuitBreakerConfig(loss_streak_reset=0)

    def test_rapid_loss_window_must_be_positive(self):
        with pytest.raises(Exception):
            CircuitBreakerConfig(rapid_loss_window_s=0)

    def test_rapid_loss_amount_must_be_positive(self):
        with pytest.raises(Exception):
            CircuitBreakerConfig(rapid_loss_amount=0.0)

    def test_market_halt_gap_in_range(self):
        with pytest.raises(Exception):
            CircuitBreakerConfig(market_halt_on_gap=0.0)

    def test_disabled_circuit_breaker(self):
        c = CircuitBreakerConfig(enabled=False)
        assert c.enabled is False

    def test_immutable(self):
        c = CircuitBreakerConfig()
        with pytest.raises(TypeError):
            c.enabled = False

    def test_to_dict(self):
        c = CircuitBreakerConfig()
        d = c.to_dict()
        assert d["enabled"] is True


# ── SlippageConfig ────────────────────────────────────────────

class TestSlippageConfig:

    def test_defaults(self):
        s = SlippageConfig()
        assert s.enabled              is True
        assert s.default_slippage_bps == 5.0
        assert s.market_order_bps     == 10.0
        assert s.limit_order_bps      == 2.0
        assert s.illiquid_multiplier  == 3.0

    def test_bps_can_be_zero(self):
        s = SlippageConfig(default_slippage_bps=0.0)
        assert s.default_slippage_bps == 0.0

    def test_bps_negative_rejected(self):
        with pytest.raises(Exception):
            SlippageConfig(default_slippage_bps=-1.0)

    def test_multiplier_must_be_at_least_one(self):
        with pytest.raises(Exception):
            SlippageConfig(illiquid_multiplier=0.5)

    def test_multiplier_exactly_one_accepted(self):
        s = SlippageConfig(illiquid_multiplier=1.0)
        assert s.illiquid_multiplier == 1.0

    def test_immutable(self):
        s = SlippageConfig()
        with pytest.raises(TypeError):
            s.enabled = False

    def test_to_dict(self):
        s = SlippageConfig()
        d = s.to_dict()
        assert d["default_slippage_bps"] == 5.0


# ── RiskSettings ──────────────────────────────────────────────

class TestRiskSettings:

    def test_defaults(self):
        r = RiskSettings()
        assert r.global_halt is False
        assert isinstance(r.sizing,          PositionSizingConfig)
        assert isinstance(r.drawdown,        DrawdownConfig)
        assert isinstance(r.exposure,        ExposureConfig)
        assert isinstance(r.circuit_breaker, CircuitBreakerConfig)
        assert isinstance(r.slippage,        SlippageConfig)

    def test_is_trading_halted_false_by_default(self):
        r = RiskSettings()
        assert r.is_trading_halted() is False

    def test_is_trading_halted_true_when_global_halt(self):
        r = RiskSettings(global_halt=True)
        assert r.is_trading_halted() is True

    def test_max_single_trade_value(self):
        r = RiskSettings()
        assert r.max_single_trade_value() == r.sizing.max_position_value

    def test_immutable(self):
        r = RiskSettings()
        with pytest.raises(TypeError):
            r.global_halt = True

    def test_to_dict_structure(self):
        r = RiskSettings()
        d = r.to_dict()
        for key in ("global_halt", "sizing", "drawdown",
                    "exposure", "circuit_breaker", "slippage"):
            assert key in d

    def test_to_dict_global_halt_false(self):
        r = RiskSettings()
        assert r.to_dict()["global_halt"] is False


# ── Factory ───────────────────────────────────────────────────

class TestBuildRiskSettings:

    def setup_method(self):
        for key in ("GLOBAL_HALT", "MAX_DAILY_LOSS", "MAX_POSITION_VALUE",
                    "MAX_OPEN_POSITIONS", "MAX_CAPITAL_DEPLOYED",
                    "ALLOW_OVERNIGHT", "ALLOW_DERIVATIVES",
                    "CIRCUIT_BREAKER_ENABLED", "SIZING_METHOD"):
            os.environ.pop(key, None)

    def test_factory_returns_risk_settings(self):
        r = build_risk_settings()
        assert isinstance(r, RiskSettings)

    def test_factory_global_halt_false_by_default(self):
        r = build_risk_settings()
        assert r.global_halt is False

    def test_factory_global_halt_from_env(self):
        os.environ["GLOBAL_HALT"] = "true"
        r = build_risk_settings()
        assert r.global_halt is True

    def test_factory_max_daily_loss_from_env(self):
        os.environ["MAX_DAILY_LOSS"] = "3000.0"
        r = build_risk_settings()
        assert r.drawdown.max_daily_loss == 3000.0

    def test_factory_max_position_value_from_env(self):
        os.environ["MAX_POSITION_VALUE"] = "25000.0"
        r = build_risk_settings()
        assert r.sizing.max_position_value == 25000.0

    def test_factory_max_open_positions_from_env(self):
        os.environ["MAX_OPEN_POSITIONS"] = "5"
        r = build_risk_settings()
        assert r.exposure.max_open_positions == 5

    def test_factory_max_capital_deployed_from_env(self):
        os.environ["MAX_CAPITAL_DEPLOYED"] = "60.0"
        r = build_risk_settings()
        assert r.exposure.max_capital_deployed == 60.0

    def test_factory_allow_overnight_from_env(self):
        os.environ["ALLOW_OVERNIGHT"] = "true"
        r = build_risk_settings()
        assert r.exposure.allow_overnight is True

    def test_factory_allow_derivatives_from_env(self):
        os.environ["ALLOW_DERIVATIVES"] = "true"
        r = build_risk_settings()
        assert r.exposure.allow_derivatives is True

    def test_factory_circuit_breaker_disabled_from_env(self):
        os.environ["CIRCUIT_BREAKER_ENABLED"] = "false"
        r = build_risk_settings()
        assert r.circuit_breaker.enabled is False

    def test_factory_sizing_method_from_env(self):
        os.environ["SIZING_METHOD"] = "fixed_percent"
        r = build_risk_settings()
        assert r.sizing.method == PositionSizingMethod.FIXED_PERCENT.value

    def test_factory_invalid_sizing_method_defaults_to_fixed_amount(self):
        os.environ["SIZING_METHOD"] = "banana"
        r = build_risk_settings()
        assert r.sizing.method == PositionSizingMethod.FIXED_AMOUNT.value

    def test_factory_overrides_take_precedence(self):
        r = build_risk_settings(overrides={"global_halt": True})
        assert r.global_halt is True

    def test_halt_reason_enum_values(self):
        for reason in HaltReason:
            assert reason.value  # all have non-empty string values
