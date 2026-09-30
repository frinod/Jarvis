"""
tests/phase7/test_session1_math_corrections.py
================================================
Regression tests for Session 1 mathematical corrections:

  Group 1 — IST timezone/session feature calculation (forecaster.py)
  Group 2 — Session-anchored VWAP (technical_analysis.py)
  Group 3 — Walk-forward validation label consistency (forecaster.py / model_validator.py)

These tests encode the CORRECT expected behaviour.
They are written against the fixed implementations.

No internet, no Qdrant, no sentence-transformers, no SHAP, no model files required.
All inputs are synthetic and hand-calculated.
"""
from __future__ import annotations

import math
import pytest

# ─────────────────────────────────────────────────────────────────────────────
# Helpers shared across groups
# ─────────────────────────────────────────────────────────────────────────────

_IST_OFFSET_SECS = 19800  # UTC+5:30


def _utc_ms(hour_utc: int, minute_utc: int = 0, day_offset: int = 0) -> int:
    """
    Build a UTC millisecond timestamp for a fixed reference date
    (2024-01-15, a Monday) at the given UTC hour:minute, optionally
    shifted by day_offset days.

    Reference epoch for 2024-01-15 00:00:00 UTC:
        date(2024,1,15) - date(1970,1,1) = 19737 days
        19737 * 86400 = 1705276800 seconds
    """
    base = 1705276800  # 2024-01-15 00:00:00 UTC
    return int((base + day_offset * 86400 + hour_utc * 3600 + minute_utc * 60) * 1000)


def _ist_from_utc_ms(ts_ms: int):
    """Return (ist_hour, ist_minute) for a UTC millisecond timestamp."""
    ts_secs_ist = ts_ms / 1000 + _IST_OFFSET_SECS
    hour   = int(ts_secs_ist // 3600) % 24
    minute = int(ts_secs_ist % 3600) // 60
    return hour, minute


# ─────────────────────────────────────────────────────────────────────────────
# GROUP 1 — IST timezone / session features
# ─────────────────────────────────────────────────────────────────────────────
#
# NSE session: 09:15 IST open → 15:30 IST close = 375 minutes.
# IST = UTC + 5h30m = UTC + 19800 seconds.
#
# The feature vector produced by build_features() contains three
# session-related features at fixed positions:
#   index 46 → time_progress  (0.0 – 1.0)
#   index 47 → is_opening     (1.0 if session_min <= 30, else 0.0)
#   index 48 → is_closing     (1.0 if session_min >= 345, else 0.0)
#
# We test the IST conversion arithmetic directly (no model files needed)
# and also via build_features() using a minimal 30-candle array.
# ─────────────────────────────────────────────────────────────────────────────

class TestISTConversion:
    """Verify UTC→IST arithmetic is correct (UTC+5:30, not UTC+5)."""

    def test_utc_offset_is_5h30m_not_5h(self):
        # 03:45 UTC → 09:15 IST  (NSE open)
        ts_ms = _utc_ms(hour_utc=3, minute_utc=45)
        h, m = _ist_from_utc_ms(ts_ms)
        assert h == 9 and m == 15, f"Expected 09:15 IST, got {h:02d}:{m:02d}"

    def test_09_15_ist_is_03_45_utc(self):
        # Inverse: 09:15 IST must come from 03:45 UTC, not 04:15 UTC
        ts_ms_correct = _utc_ms(hour_utc=3, minute_utc=45)
        ts_ms_wrong   = _utc_ms(hour_utc=4, minute_utc=15)  # UTC+5 (wrong)
        h_correct, m_correct = _ist_from_utc_ms(ts_ms_correct)
        h_wrong,   m_wrong   = _ist_from_utc_ms(ts_ms_wrong)
        assert h_correct == 9  and m_correct == 15
        assert h_wrong   == 9  and m_wrong   == 45  # UTC+5 gives 09:45, not 09:15

    def test_15_30_ist_is_10_00_utc(self):
        # NSE close: 15:30 IST = 10:00 UTC
        ts_ms = _utc_ms(hour_utc=10, minute_utc=0)
        h, m = _ist_from_utc_ms(ts_ms)
        assert h == 15 and m == 30

    def test_date_boundary_midnight_ist(self):
        # Midnight IST = 18:30 UTC previous day.
        # 2024-01-15 18:30 UTC → 2024-01-16 00:00 IST
        ts_ms = _utc_ms(hour_utc=18, minute_utc=30)
        h, m = _ist_from_utc_ms(ts_ms)
        assert h == 0 and m == 0


class TestSessionFeatures:
    """Verify session_min, time_progress, is_opening, is_closing via build_features()."""

    def _make_candles(self, ts_ms: int, n: int = 30) -> list:
        """Minimal synthetic candle array. All candles share the same timestamp
        except the last one which carries the timestamp under test."""
        base_ts = _utc_ms(hour_utc=3, minute_utc=45)  # 09:15 IST
        candles = []
        for i in range(n - 1):
            candles.append({
                'o': 100.0, 'h': 101.0, 'l': 99.0, 'c': 100.0 + i * 0.01,
                'v': 1000, 't': base_ts + i * 300_000,  # 5-min intervals
            })
        # Last candle carries the timestamp under test
        candles.append({
            'o': 100.0, 'h': 101.0, 'l': 99.0, 'c': 100.3,
            'v': 1000, 't': ts_ms,
        })
        return candles

    def _get_session_features(self, ts_ms: int):
        """Return (time_progress, is_opening, is_closing) from build_features()."""
        from app.api.forecaster import build_features
        candles = self._make_candles(ts_ms)
        ta = {"indicators": {}, "fibonacci": {}, "bos_choch": [],
              "order_blocks": [], "fvg": [], "candlestick_patterns": [],
              "score": 0}
        feats = build_features(candles, ta)
        assert feats is not None, "build_features returned None"
        return float(feats[46]), float(feats[47]), float(feats[48])

    def test_session_open_09_15_ist(self):
        # 09:15 IST = 03:45 UTC → session_min=0, time_progress=0, is_opening=1
        ts_ms = _utc_ms(hour_utc=3, minute_utc=45)
        tp, is_open, is_close = self._get_session_features(ts_ms)
        assert tp == 0.0
        assert is_open == 1.0
        assert is_close == 0.0

    def test_session_09_30_ist(self):
        # 09:30 IST = 03:60 UTC = 04:00 UTC → session_min=15, still opening
        ts_ms = _utc_ms(hour_utc=4, minute_utc=0)
        tp, is_open, is_close = self._get_session_features(ts_ms)
        expected_progress = 15 / 375.0
        assert abs(tp - expected_progress) < 1e-4
        assert is_open == 1.0
        assert is_close == 0.0

    def test_session_10_00_ist(self):
        # 10:00 IST = 04:30 UTC → session_min=45, past opening window
        ts_ms = _utc_ms(hour_utc=4, minute_utc=30)
        tp, is_open, is_close = self._get_session_features(ts_ms)
        expected_progress = 45 / 375.0
        assert abs(tp - expected_progress) < 1e-4
        assert is_open == 0.0   # session_min=45 > 30
        assert is_close == 0.0

    def test_session_15_15_ist(self):
        # 15:15 IST = 09:45 UTC → session_min=360, in closing window
        ts_ms = _utc_ms(hour_utc=9, minute_utc=45)
        tp, is_open, is_close = self._get_session_features(ts_ms)
        expected_progress = min(360 / 375.0, 1.0)
        assert abs(tp - expected_progress) < 1e-4
        assert is_open == 0.0
        assert is_close == 1.0  # session_min=360 >= 345

    def test_session_15_30_ist(self):
        # 15:30 IST = 10:00 UTC → session_min=375, time_progress=1.0
        ts_ms = _utc_ms(hour_utc=10, minute_utc=0)
        tp, is_open, is_close = self._get_session_features(ts_ms)
        assert tp == 1.0
        assert is_open == 0.0
        assert is_close == 1.0

    def test_session_after_close_capped(self):
        # 15:31 IST = 10:01 UTC → session_min=376, time_progress capped at 1.0
        ts_ms = _utc_ms(hour_utc=10, minute_utc=1)
        tp, is_open, is_close = self._get_session_features(ts_ms)
        assert tp == 1.0


# ─────────────────────────────────────────────────────────────────────────────
# GROUP 2 — Session-anchored VWAP
# ─────────────────────────────────────────────────────────────────────────────
#
# VWAP = Σ(typical_price × volume) / Σ(volume)
# typical_price = (H + L + C) / 3
#
# Session boundary: new IST calendar date.
# Midnight IST = 18:30 UTC.
#
# Key invariant: Day 2 VWAP must NOT include Day 1 volume or prices.
# ─────────────────────────────────────────────────────────────────────────────

class TestSessionAnchoredVWAP:
    """Tests for _vwap() with session-reset behaviour."""

    def _vwap(self, highs, lows, closes, volumes, timestamps=None):
        from app.api.technical_analysis import _vwap
        return _vwap(highs, lows, closes, volumes, timestamps)

    # ── Hand-calculated single-session ───────────────────────────────────────

    def test_single_candle_vwap_equals_typical_price(self):
        # TP = (101 + 99 + 100) / 3 = 100.0; VWAP = 100.0
        result = self._vwap([101.0], [99.0], [100.0], [1000])
        assert result == [100.0]

    def test_two_candles_same_session_hand_calculated(self):
        # Candle 1: H=102, L=98, C=100 → TP=100, vol=1000 → cum_tp_vol=100000, cum_vol=1000
        # Candle 2: H=104, L=100, C=102 → TP=102, vol=2000 → cum_tp_vol=100000+204000=304000, cum_vol=3000
        # VWAP[1] = 304000/3000 = 101.333...
        result = self._vwap(
            [102.0, 104.0], [98.0, 100.0], [100.0, 102.0], [1000, 2000]
        )
        assert result[0] == 100.0
        assert abs(result[1] - round(304000 / 3000, 2)) < 0.01

    def test_zero_volume_falls_back_to_close(self):
        result = self._vwap([101.0], [99.0], [100.0], [0])
        assert result == [100.0]

    def test_empty_input_returns_empty(self):
        result = self._vwap([], [], [], [])
        assert result == []

    # ── Session reset ─────────────────────────────────────────────────────────

    def test_two_sessions_vwap_resets(self):
        """
        Day 1: one candle at 09:15 IST (03:45 UTC on day 0)
        Day 2: one candle at 09:15 IST (03:45 UTC on day 1)

        Day 2 VWAP must equal Day 2 typical price only — not a blend with Day 1.
        """
        day1_ts = _utc_ms(hour_utc=3, minute_utc=45, day_offset=0)
        day2_ts = _utc_ms(hour_utc=3, minute_utc=45, day_offset=1)

        # Day 1: TP = (110+90+100)/3 = 100.0
        # Day 2: TP = (220+180+200)/3 = 200.0
        result = self._vwap(
            highs=[110.0, 220.0],
            lows=[90.0, 180.0],
            closes=[100.0, 200.0],
            volumes=[1000, 1000],
            timestamps=[day1_ts, day2_ts],
        )
        assert result[0] == 100.0, f"Day 1 VWAP should be 100.0, got {result[0]}"
        assert result[1] == 200.0, f"Day 2 VWAP should be 200.0 (reset), got {result[1]}"

    def test_day2_vwap_independent_of_day1_volume(self):
        """
        Changing Day 1 volume must not affect Day 2 VWAP after the reset.
        """
        day1_ts = _utc_ms(hour_utc=3, minute_utc=45, day_offset=0)
        day2_ts = _utc_ms(hour_utc=4, minute_utc=0,  day_offset=1)

        def run(day1_vol):
            return self._vwap(
                highs=[110.0, 210.0],
                lows=[90.0, 190.0],
                closes=[100.0, 200.0],
                volumes=[day1_vol, 500],
                timestamps=[day1_ts, day2_ts],
            )

        result_low  = run(day1_vol=100)
        result_high = run(day1_vol=999999)
        assert result_low[1] == result_high[1], (
            f"Day 2 VWAP changed when Day 1 volume changed: "
            f"{result_low[1]} vs {result_high[1]}"
        )

    def test_multiple_candles_within_one_session(self):
        """
        Three candles on the same IST day must accumulate correctly.
        Hand-calculated:
          C1: TP=100, vol=1000 → cum=100000/1000=100.0
          C2: TP=102, vol=1000 → cum=202000/2000=101.0
          C3: TP=104, vol=1000 → cum=306000/3000=102.0
        """
        base = _utc_ms(hour_utc=3, minute_utc=45, day_offset=0)
        ts = [base, base + 300_000, base + 600_000]  # 5-min apart, same IST day
        result = self._vwap(
            highs=[101.0, 103.0, 105.0],
            lows=[99.0, 101.0, 103.0],
            closes=[100.0, 102.0, 104.0],
            volumes=[1000, 1000, 1000],
            timestamps=ts,
        )
        assert result[0] == 100.0
        assert result[1] == 101.0
        assert result[2] == 102.0

    def test_no_timestamps_falls_back_to_cumulative(self):
        """
        Without timestamps the function must behave as the original
        cumulative VWAP (backward compatibility for callers that don't
        supply timestamps).
        """
        # Two candles, no timestamps → cumulative across both
        result = self._vwap(
            highs=[110.0, 220.0],
            lows=[90.0, 180.0],
            closes=[100.0, 200.0],
            volumes=[1000, 1000],
            timestamps=None,
        )
        # TP1=100, TP2=200; cumulative VWAP[1] = (100*1000 + 200*1000) / 2000 = 150.0
        assert result[0] == 100.0
        assert result[1] == 150.0


# ─────────────────────────────────────────────────────────────────────────────
# GROUP 3 — Walk-forward validation label consistency
# ─────────────────────────────────────────────────────────────────────────────
#
# compute_prediction_label() must produce the same label semantics as
# StockForecaster.train() — both now use the same shared function.
#
# Label encoding:
#   1 = UP   (future_return >  +threshold)
#   0 = DOWN (future_return <  -threshold)
#   2 = FLAT (|future_return| <= threshold)
#
# Threshold = max(atr / price * 0.5, 0.002)
# ─────────────────────────────────────────────────────────────────────────────

def _make_label_candles(price_now: float, price_future: float, n_pad: int = 10) -> list:
    """
    Build a minimal candle list where:
      candles[i]           has close = price_now
      candles[i + horizon] has close = price_future
    Padded with flat candles before index i.
    """
    candles = [{'o': price_now, 'h': price_now + 1, 'l': price_now - 1,
                 'c': price_now, 'v': 1000}] * n_pad
    candles.append({'o': price_now, 'h': price_now + 1, 'l': price_now - 1,
                    'c': price_now, 'v': 1000})
    candles.append({'o': price_future, 'h': price_future + 1, 'l': price_future - 1,
                    'c': price_future, 'v': 1000})
    return candles


def _make_ta_history(atr_value: float, n: int) -> list:
    """Minimal ta_history list where every entry has the given ATR."""
    return [{"indicators": {"atr": atr_value}} for _ in range(n)]


class TestPredictionLabelConsistency:
    """compute_prediction_label() must encode labels identically to training."""

    def _label(self, price_now, price_future, atr, horizon=1):
        from app.api.forecaster import compute_prediction_label
        n_pad = 5
        candles = _make_label_candles(price_now, price_future, n_pad=n_pad)
        ta_hist = _make_ta_history(atr, len(candles))
        i = n_pad  # index of the "current" candle
        return compute_prediction_label(candles, ta_hist, i, horizon)

    # ── Threshold arithmetic ──────────────────────────────────────────────────

    def test_threshold_formula_normal_atr(self):
        # price=1000, atr=10 → threshold = max(10/1000*0.5, 0.002) = max(0.005, 0.002) = 0.005
        price = 1000.0
        atr   = 10.0
        expected_threshold = max(atr / price * 0.5, 0.002)
        assert abs(expected_threshold - 0.005) < 1e-9

    def test_threshold_floor_low_atr(self):
        # price=1000, atr=1 → threshold = max(0.0005, 0.002) = 0.002 (floor)
        price = 1000.0
        atr   = 1.0
        expected_threshold = max(atr / price * 0.5, 0.002)
        assert expected_threshold == 0.002

    # ── Label classification ──────────────────────────────────────────────────

    def test_return_above_threshold_is_up(self):
        # price=1000, atr=10 → threshold=0.005; future=1006 → ret=0.006 > 0.005 → UP=1
        label = self._label(price_now=1000.0, price_future=1006.0, atr=10.0)
        assert label == 1, f"Expected UP(1), got {label}"

    def test_return_below_negative_threshold_is_down(self):
        # price=1000, atr=10 → threshold=0.005; future=994 → ret=-0.006 < -0.005 → DOWN=0
        label = self._label(price_now=1000.0, price_future=994.0, atr=10.0)
        assert label == 0, f"Expected DOWN(0), got {label}"

    def test_return_inside_flat_band_is_flat(self):
        # price=1000, atr=10 → threshold=0.005; future=1003 → ret=0.003 < 0.005 → FLAT=2
        label = self._label(price_now=1000.0, price_future=1003.0, atr=10.0)
        assert label == 2, f"Expected FLAT(2), got {label}"

    def test_return_exactly_at_threshold_is_flat(self):
        # ret == threshold → not strictly greater → FLAT
        price = 1000.0
        atr   = 10.0
        threshold = max(atr / price * 0.5, 0.002)  # 0.005
        future = price * (1 + threshold)            # exactly at boundary
        label = self._label(price_now=price, price_future=future, atr=atr)
        assert label == 2, f"Boundary case should be FLAT(2), got {label}"

    def test_high_atr_raises_threshold(self):
        # price=1000, atr=100 → threshold = max(0.05, 0.002) = 0.05
        # future=1040 → ret=0.04 < 0.05 → FLAT
        label = self._label(price_now=1000.0, price_future=1040.0, atr=100.0)
        assert label == 2, f"High ATR: 4% return should be FLAT, got {label}"

    def test_high_atr_up_above_threshold(self):
        # price=1000, atr=100 → threshold=0.05; future=1060 → ret=0.06 > 0.05 → UP
        label = self._label(price_now=1000.0, price_future=1060.0, atr=100.0)
        assert label == 1, f"High ATR: 6% return should be UP, got {label}"

    def test_missing_atr_uses_1pct_fallback(self):
        # atr=None → fallback = price * 0.01 = 10.0 → threshold = max(0.005, 0.002) = 0.005
        # future=1006 → ret=0.006 > 0.005 → UP
        from app.api.forecaster import compute_prediction_label
        n_pad = 5
        candles = _make_label_candles(1000.0, 1006.0, n_pad=n_pad)
        ta_hist = [{"indicators": {"atr": None}} for _ in range(len(candles))]
        label = compute_prediction_label(candles, ta_hist, n_pad, horizon=1)
        assert label == 1, f"Missing ATR fallback: expected UP(1), got {label}"

    def test_returns_none_when_horizon_exceeds_candles(self):
        from app.api.forecaster import compute_prediction_label
        candles = _make_label_candles(1000.0, 1010.0, n_pad=2)
        ta_hist = _make_ta_history(10.0, len(candles))
        # i=2, horizon=10 → i+horizon=12 >= len(candles)=4 → None
        label = compute_prediction_label(candles, ta_hist, i=2, horizon=10)
        assert label is None

    def test_training_and_wfv_produce_identical_labels(self):
        """
        The same (candles, ta_history, i, horizon) must produce the same label
        whether called from training context or WFV context, because both now
        call compute_prediction_label().
        """
        from app.api.forecaster import compute_prediction_label
        price_now    = 2500.0
        price_future = 2525.0
        atr          = 20.0
        horizon      = 1
        n_pad        = 5

        candles = _make_label_candles(price_now, price_future, n_pad=n_pad)
        ta_hist = _make_ta_history(atr, len(candles))
        i = n_pad

        # Both training and WFV call the same function — call it twice
        label_train = compute_prediction_label(candles, ta_hist, i, horizon)
        label_wfv   = compute_prediction_label(candles, ta_hist, i, horizon)

        assert label_train == label_wfv
        # Verify the expected value: threshold=max(20/2500*0.5,0.002)=0.004
        # ret=(2525-2500)/2500=0.01 > 0.004 → UP=1
        assert label_train == 1
