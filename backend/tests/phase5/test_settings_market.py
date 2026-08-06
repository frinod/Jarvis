"""
test_settings_market.py -- Task 6 validation
Tests for app/config/settings/market.py
"""
from __future__ import annotations

import os
import pytest

from app.config.settings.market import (
    MarketInterval, MarketType,
    TradingSession, MarketMetadata, AIMarketDefaults,
    RegimeThresholds, MarketProfile, MarketSettings,
    build_market_settings,
)


# ── MarketInterval helpers ────────────────────────────────────

class TestMarketInterval:

    def test_intraday_excludes_daily_and_above(self):
        intraday = MarketInterval.intraday()
        assert MarketInterval.DAY_1   not in intraday
        assert MarketInterval.WEEK_1  not in intraday
        assert MarketInterval.MONTH_1 not in intraday

    def test_intraday_includes_sub_hour(self):
        intraday = MarketInterval.intraday()
        assert MarketInterval.MIN_5  in intraday
        assert MarketInterval.MIN_15 in intraday
        assert MarketInterval.HOUR_1 in intraday

    def test_swing_excludes_intraday(self):
        swing = MarketInterval.swing()
        assert MarketInterval.MIN_5  not in swing
        assert MarketInterval.HOUR_1 not in swing

    def test_swing_includes_daily_and_above(self):
        swing = MarketInterval.swing()
        assert MarketInterval.DAY_1  in swing
        assert MarketInterval.WEEK_1 in swing


# ── TradingSession ────────────────────────────────────────────

class TestTradingSession:

    def test_defaults(self):
        s = TradingSession()
        assert s.open_time  == "09:15"
        assert s.close_time == "15:30"
        assert s.timezone   == "Asia/Kolkata"

    def test_invalid_time_format_raises(self):
        with pytest.raises(Exception):
            TradingSession(open_time="25:00")    # hour out of range
        with pytest.raises(Exception):
            TradingSession(open_time="09:60")    # minute out of range
        with pytest.raises(Exception):
            TradingSession(open_time="0915")     # no colon
        with pytest.raises(Exception):
            TradingSession(open_time="ab:cd")    # non-digit

    def test_single_digit_hour_accepted(self):
        """9:15 is valid -- validator checks range, not zero-padding."""
        s = TradingSession(open_time="9:15", close_time="15:30")
        assert s.open_time == "9:15"

    def test_close_must_be_after_open(self):
        with pytest.raises(Exception):
            TradingSession(open_time="15:30", close_time="09:15")

    def test_close_equal_to_open_raises(self):
        with pytest.raises(Exception):
            TradingSession(open_time="09:15", close_time="09:15")

    def test_valid_session(self):
        s = TradingSession(open_time="09:15", close_time="15:30")
        assert s.open_time  == "09:15"
        assert s.close_time == "15:30"

    def test_calendar_provider_empty_by_default(self):
        s = TradingSession()
        assert s.calendar_provider == ""

    def test_immutable(self):
        s = TradingSession()
        with pytest.raises(TypeError):
            s.open_time = "10:00"

    def test_to_dict_contains_all_fields(self):
        s = TradingSession()
        d = s.to_dict()
        assert "open_time"  in d
        assert "close_time" in d
        assert "timezone"   in d


# ── MarketMetadata ────────────────────────────────────────────

class TestMarketMetadata:

    def test_defaults(self):
        m = MarketMetadata()
        assert m.currency          == "INR"
        assert m.tick_size         == 0.05
        assert m.lot_size          == 1
        assert m.decimal_precision == 2

    def test_currency_uppercased(self):
        m = MarketMetadata(currency="usd")
        assert m.currency == "USD"

    def test_tick_size_must_be_positive(self):
        with pytest.raises(Exception):
            MarketMetadata(tick_size=0.0)
        with pytest.raises(Exception):
            MarketMetadata(tick_size=-0.05)

    def test_decimal_precision_non_negative(self):
        with pytest.raises(Exception):
            MarketMetadata(decimal_precision=-1)
        assert MarketMetadata(decimal_precision=0).decimal_precision == 0

    def test_immutable(self):
        m = MarketMetadata()
        with pytest.raises(TypeError):
            m.currency = "USD"


# ── AIMarketDefaults ──────────────────────────────────────────

class TestAIMarketDefaults:

    def test_defaults(self):
        a = AIMarketDefaults()
        assert a.confidence_threshold    == 0.65
        assert a.prediction_horizon_bars == 6
        assert a.forecast_refresh_s      == 300
        assert len(a.preferred_intervals) > 0
        assert len(a.mtf_combinations)   > 0

    def test_confidence_threshold_bounds(self):
        with pytest.raises(Exception):
            AIMarketDefaults(confidence_threshold=1.1)
        with pytest.raises(Exception):
            AIMarketDefaults(confidence_threshold=-0.1)
        assert AIMarketDefaults(confidence_threshold=0.0).confidence_threshold == 0.0
        assert AIMarketDefaults(confidence_threshold=1.0).confidence_threshold == 1.0

    def test_horizon_must_be_positive(self):
        with pytest.raises(Exception):
            AIMarketDefaults(prediction_horizon_bars=0)

    def test_immutable(self):
        a = AIMarketDefaults()
        with pytest.raises(TypeError):
            a.confidence_threshold = 0.9


# ── RegimeThresholds ──────────────────────────────────────────

class TestRegimeThresholds:

    def test_defaults(self):
        r = RegimeThresholds()
        assert r.trending_adx_min    == 25.0
        assert r.ranging_adx_max     == 20.0
        assert r.high_vol_percentile == 75.0
        assert r.low_vol_percentile  == 25.0

    def test_percentile_bounds(self):
        with pytest.raises(Exception):
            RegimeThresholds(high_vol_percentile=0.0)
        with pytest.raises(Exception):
            RegimeThresholds(high_vol_percentile=100.0)
        with pytest.raises(Exception):
            RegimeThresholds(low_vol_percentile=-1.0)

    def test_immutable(self):
        r = RegimeThresholds()
        with pytest.raises(TypeError):
            r.trending_adx_min = 30.0


# ── MarketProfile ─────────────────────────────────────────────

class TestMarketProfile:

    def _nse(self, **kwargs) -> MarketProfile:
        return MarketProfile(name="NSE", **kwargs)

    def test_name_required(self):
        with pytest.raises(Exception):
            MarketProfile(name="")

    def test_name_uppercased(self):
        p = MarketProfile(name="nse")
        assert p.name == "NSE"

    def test_name_whitespace_stripped(self):
        p = MarketProfile(name="  BSE  ")
        assert p.name == "BSE"

    def test_supports_interval_true(self):
        p = self._nse(supported_intervals=["5m", "15m", "1d"])
        assert p.supports_interval("5m")  is True
        assert p.supports_interval("15m") is True

    def test_supports_interval_false(self):
        p = self._nse(supported_intervals=["5m"])
        assert p.supports_interval("1w") is False

    def test_derivatives_flag(self):
        p = self._nse(supports_derivatives=True, supports_options=True)
        assert p.supports_derivatives is True
        assert p.supports_options     is True

    def test_disabled_profile(self):
        p = self._nse(enabled=False)
        assert p.enabled is False

    def test_to_dict_structure(self):
        p = self._nse()
        d = p.to_dict()
        for key in ("name", "market_type", "enabled", "session",
                    "metadata", "ai_defaults", "regime"):
            assert key in d, f"Missing key: {key}"

    def test_immutable(self):
        p = self._nse()
        with pytest.raises(TypeError):
            p.enabled = False


# ── MarketSettings ────────────────────────────────────────────

class TestMarketSettings:

    def _settings(self) -> MarketSettings:
        nse   = MarketProfile(name="NSE",   supports_derivatives=True)
        nfo   = MarketProfile(name="NFO",   supports_options=True, supports_futures=True,
                              market_type=MarketType.DERIVATIVE)
        off   = MarketProfile(name="OFF",   enabled=False)
        return MarketSettings(
            markets={"NSE": nse, "NFO": nfo, "OFF": off},
            default_market="NSE",
        )

    def test_get_market_by_name(self):
        s = self._settings()
        assert s.get_market("NSE").name == "NSE"

    def test_get_market_case_insensitive(self):
        s = self._settings()
        assert s.get_market("nse").name == "NSE"

    def test_get_market_missing_returns_none(self):
        s = self._settings()
        assert s.get_market("FAKE") is None

    def test_get_default(self):
        s = self._settings()
        assert s.get_default().name == "NSE"

    def test_enabled_markets_excludes_disabled(self):
        s = self._settings()
        names = [m.name for m in s.enabled_markets()]
        assert "NSE" in names
        assert "OFF" not in names

    def test_markets_by_type(self):
        s = self._settings()
        derivs = s.markets_by_type("derivative")
        assert all(m.market_type == "derivative" for m in derivs)

    def test_supports_derivatives(self):
        s = self._settings()
        assert s.supports_derivatives("NSE") is True
        assert s.supports_derivatives("OFF") is False
        assert s.supports_derivatives("FAKE") is False

    def test_supports_options(self):
        s = self._settings()
        assert s.supports_options("NFO") is True
        assert s.supports_options("NSE") is False

    def test_supports_futures(self):
        s = self._settings()
        assert s.supports_futures("NFO") is True
        assert s.supports_futures("NSE") is False

    def test_available_intervals_all(self):
        s = self._settings()
        intervals = s.available_intervals()
        assert "5m" in intervals
        assert "1d" in intervals

    def test_available_intervals_for_market(self):
        nse = MarketProfile(name="NSE", supported_intervals=["5m", "1d"])
        s   = MarketSettings(markets={"NSE": nse})
        assert s.available_intervals("NSE") == ["5m", "1d"]

    def test_available_intervals_unknown_market(self):
        s = self._settings()
        assert s.available_intervals("FAKE") == []

    def test_candle_days_must_be_positive(self):
        with pytest.raises(Exception):
            MarketSettings(default_candle_days=0)
        with pytest.raises(Exception):
            MarketSettings(max_candle_days=0)

    def test_to_dict_structure(self):
        s = self._settings()
        d = s.to_dict()
        assert "default_market"   in d
        assert "markets"          in d
        assert "NSE"              in d["markets"]

    def test_immutable(self):
        s = self._settings()
        with pytest.raises(TypeError):
            s.default_market = "NFO"


# ── Factory ───────────────────────────────────────────────────

class TestBuildMarketSettings:

    def setup_method(self):
        for key in ("DEFAULT_MARKET", "DEFAULT_INTERVAL", "DEFAULT_CANDLE_DAYS",
                    "MAX_CANDLE_DAYS", "DEFAULT_UNIVERSE", "CRYPTO_ENABLED"):
            os.environ.pop(key, None)

    def test_factory_returns_market_settings(self):
        s = build_market_settings()
        assert isinstance(s, MarketSettings)

    def test_factory_default_market(self):
        s = build_market_settings()
        assert s.default_market == "NSE"

    def test_factory_default_interval(self):
        s = build_market_settings()
        assert s.default_interval == "5m"

    def test_factory_default_candle_days(self):
        s = build_market_settings()
        assert s.default_candle_days == 10

    def test_factory_nse_always_present(self):
        s = build_market_settings()
        assert "NSE" in s.markets

    def test_factory_nfo_always_present(self):
        s = build_market_settings()
        assert "NFO" in s.markets

    def test_factory_crypto_disabled_by_default(self):
        s = build_market_settings()
        assert s.markets["CRYPTO"].enabled is False

    def test_factory_crypto_enabled_via_env(self):
        os.environ["CRYPTO_ENABLED"] = "true"
        s = build_market_settings()
        assert s.markets["CRYPTO"].enabled is True

    def test_factory_default_market_from_env(self):
        os.environ["DEFAULT_MARKET"] = "NFO"
        s = build_market_settings()
        assert s.default_market == "NFO"

    def test_factory_candle_days_from_env(self):
        os.environ["DEFAULT_CANDLE_DAYS"] = "30"
        s = build_market_settings()
        assert s.default_candle_days == 30

    def test_factory_overrides_take_precedence(self):
        s = build_market_settings(overrides={"default_interval": "1h"})
        assert s.default_interval == "1h"

    def test_nse_supports_derivatives(self):
        s = build_market_settings()
        assert s.supports_derivatives("NSE") is True

    def test_nfo_supports_options_and_futures(self):
        s = build_market_settings()
        assert s.supports_options("NFO")  is True
        assert s.supports_futures("NFO")  is True
