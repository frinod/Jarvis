"""
Phase 7 — Prediction Resolution Tests
=======================================
Verifies the full prediction → resolution pipeline:
  record_prediction() → resolve_prediction() → get_ai_self_evaluation()
  resolve_pending_predictions()

All tests use a temporary directory so they never touch real WFV data.
Python 3.7 compatible (no AsyncMock — uses a coroutine factory instead).
"""
from __future__ import annotations

import asyncio
import time
import pytest
from unittest.mock import patch


# ── 3.7-compatible async mock helper ─────────────────────────

def _async_return(value):
    """Return a coroutine that yields value — works on Python 3.7."""
    async def _coro(*args, **kwargs):
        return value
    return _coro


# ── Shared helpers ────────────────────────────────────────────

def _record(tmp_dir, symbol, signal, price, confidence=70.0,
            horizon=30, ts=None):
    import app.api.model_validator as mv
    orig, mv.RESULTS_DIR = mv.RESULTS_DIR, tmp_dir
    try:
        return mv.record_prediction(
            symbol=symbol, signal=signal, confidence=confidence,
            price_at_signal=price, timestamp=ts or time.time(),
            horizon_minutes=horizon, source="xgboost",
            direction="UP" if signal == "BUY" else "DOWN" if signal == "SELL" else "FLAT",
            prob_up=0.6 if signal == "BUY" else 0.1,
            prob_down=0.1 if signal == "BUY" else 0.6,
            prob_flat=0.3,
            stop_loss=round(price * 0.98, 2),
            target=round(price * 1.02, 2),
            regime="trending",
            wfv_accuracy=65.0,
            wfv_useful=True,
        )
    finally:
        mv.RESULTS_DIR = orig


def _resolve(tmp_dir, symbol, pred_id, actual_price, actual_ts=None):
    import app.api.model_validator as mv
    orig, mv.RESULTS_DIR = mv.RESULTS_DIR, tmp_dir
    try:
        return mv.resolve_prediction(symbol, pred_id, actual_price, actual_ts)
    finally:
        mv.RESULTS_DIR = orig


def _load(tmp_dir, symbol):
    import app.api.model_validator as mv
    orig, mv.RESULTS_DIR = mv.RESULTS_DIR, tmp_dir
    try:
        return mv._load_records(mv._results_path(symbol))
    finally:
        mv.RESULTS_DIR = orig


def _pending(tmp_dir):
    import app.api.model_validator as mv
    orig, mv.RESULTS_DIR = mv.RESULTS_DIR, tmp_dir
    try:
        return mv.get_pending_predictions()
    finally:
        mv.RESULTS_DIR = orig


def _eval(tmp_dir):
    import app.api.model_validator as mv
    import app.api.paper_trading as pt
    orig, mv.RESULTS_DIR = mv.RESULTS_DIR, tmp_dir
    try:
        return pt.get_ai_self_evaluation()
    finally:
        mv.RESULTS_DIR = orig


# ── 1. record_prediction ──────────────────────────────────────

class TestRecordPrediction:

    def test_creates_file_with_record(self, tmp_path):
        pred_id = _record(str(tmp_path), "RELIANCE", "BUY", 2500.0)
        records = _load(str(tmp_path), "RELIANCE")
        assert len(records) == 1
        assert records[0]["id"] == pred_id

    def test_stores_all_context_fields(self, tmp_path):
        _record(str(tmp_path), "TCS", "BUY", 3500.0, confidence=72.5)
        r = _load(str(tmp_path), "TCS")[0]
        assert r["signal"] == "BUY"
        assert r["confidence"] == 72.5
        assert r["direction"] == "UP"
        assert r["prob_up"] == pytest.approx(0.6)
        assert r["prob_flat"] == pytest.approx(0.3)
        assert r["stop_loss"] == pytest.approx(3500.0 * 0.98, rel=1e-4)
        assert r["target"] == pytest.approx(3500.0 * 1.02, rel=1e-4)
        assert r["regime"] == "trending"
        assert r["wfv_accuracy"] == 65.0
        assert r["wfv_useful"] is True

    def test_sets_horizon_due_ts(self, tmp_path):
        ts = time.time()
        _record(str(tmp_path), "INFY", "SELL", 1800.0, horizon=30, ts=ts)
        r = _load(str(tmp_path), "INFY")[0]
        assert r["horizon_due_ts"] == pytest.approx(ts + 30 * 60, abs=1)

    def test_outcome_is_none_on_creation(self, tmp_path):
        _record(str(tmp_path), "HCLTECH", "BUY", 1200.0)
        r = _load(str(tmp_path), "HCLTECH")[0]
        assert r["outcome"] is None
        assert r["correct"] is None
        assert r["actual_return"] is None

    def test_idempotent_same_id(self, tmp_path):
        ts = 1700000000.0
        _record(str(tmp_path), "WIPRO", "BUY", 400.0, ts=ts)
        _record(str(tmp_path), "WIPRO", "BUY", 400.0, ts=ts)  # duplicate
        assert len(_load(str(tmp_path), "WIPRO")) == 1

    def test_multiple_different_symbols(self, tmp_path):
        _record(str(tmp_path), "RELIANCE", "BUY", 2500.0)
        _record(str(tmp_path), "TCS", "SELL", 3500.0)
        assert len(_load(str(tmp_path), "RELIANCE")) == 1
        assert len(_load(str(tmp_path), "TCS")) == 1

    def test_multiple_same_symbol_different_ts(self, tmp_path):
        _record(str(tmp_path), "RELIANCE", "BUY", 2500.0, ts=1700000001.0)
        _record(str(tmp_path), "RELIANCE", "SELL", 2510.0, ts=1700000002.0)
        assert len(_load(str(tmp_path), "RELIANCE")) == 2


# ── 2. resolve_prediction ─────────────────────────────────────

class TestResolvePrediction:

    def test_correct_buy(self, tmp_path):
        ts = time.time() - 3600
        pid = _record(str(tmp_path), "RELIANCE", "BUY", 2500.0, ts=ts)
        r = _resolve(str(tmp_path), "RELIANCE", pid, 2530.0, time.time())
        assert r["outcome"] == "resolved"
        assert r["correct"] is True
        assert r["actual_return"] == pytest.approx(1.2, abs=0.1)

    def test_incorrect_buy(self, tmp_path):
        ts = time.time() - 3600
        pid = _record(str(tmp_path), "RELIANCE", "BUY", 2500.0, ts=ts)
        r = _resolve(str(tmp_path), "RELIANCE", pid, 2480.0, time.time())
        assert r["outcome"] == "resolved"
        assert r["correct"] is False

    def test_correct_sell(self, tmp_path):
        ts = time.time() - 3600
        pid = _record(str(tmp_path), "TCS", "SELL", 3500.0, ts=ts)
        r = _resolve(str(tmp_path), "TCS", pid, 3460.0, time.time())
        assert r["outcome"] == "resolved"
        assert r["correct"] is True

    def test_incorrect_sell(self, tmp_path):
        ts = time.time() - 3600
        pid = _record(str(tmp_path), "TCS", "SELL", 3500.0, ts=ts)
        r = _resolve(str(tmp_path), "TCS", pid, 3540.0, time.time())
        assert r["outcome"] == "resolved"
        assert r["correct"] is False

    def test_hold_correct_when_flat(self, tmp_path):
        ts = time.time() - 3600
        pid = _record(str(tmp_path), "INFY", "HOLD", 1800.0, ts=ts)
        r = _resolve(str(tmp_path), "INFY", pid, 1801.0, time.time())
        assert r["outcome"] == "resolved"
        assert r["correct"] is True

    def test_hold_incorrect_when_large_move(self, tmp_path):
        ts = time.time() - 3600
        pid = _record(str(tmp_path), "INFY", "HOLD", 1800.0, ts=ts)
        r = _resolve(str(tmp_path), "INFY", pid, 1830.0, time.time())
        assert r["outcome"] == "resolved"
        assert r["correct"] is False

    def test_idempotent_double_resolution(self, tmp_path):
        ts = time.time() - 3600
        pid = _record(str(tmp_path), "RELIANCE", "BUY", 2500.0, ts=ts)
        r1 = _resolve(str(tmp_path), "RELIANCE", pid, 2530.0, time.time())
        r2 = _resolve(str(tmp_path), "RELIANCE", pid, 2400.0, time.time())
        assert r2["actual_price"] == r1["actual_price"]
        assert r2["correct"] == r1["correct"]

    def test_missing_price_leaves_pending(self, tmp_path):
        ts = time.time() - 3600
        pid = _record(str(tmp_path), "RELIANCE", "BUY", 2500.0, ts=ts)
        r = _resolve(str(tmp_path), "RELIANCE", pid, 0.0, time.time())
        assert r["outcome"] is None

    def test_stale_actual_price_leaves_pending(self, tmp_path):
        ts = time.time() - 3600
        pid = _record(str(tmp_path), "RELIANCE", "BUY", 2500.0,
                      horizon=30, ts=ts)
        # actual_price_ts is only 10 min after signal — horizon is 30 min
        stale_ts = ts + 10 * 60
        r = _resolve(str(tmp_path), "RELIANCE", pid, 2530.0, stale_ts)
        assert r["outcome"] is None

    def test_unknown_pred_id_returns_none(self, tmp_path):
        import app.api.model_validator as mv
        orig, mv.RESULTS_DIR = mv.RESULTS_DIR, str(tmp_path)
        try:
            result = mv.resolve_prediction("RELIANCE", "nonexistent_id", 2500.0)
        finally:
            mv.RESULTS_DIR = orig
        assert result is None

    def test_stores_resolved_at_timestamp(self, tmp_path):
        ts = time.time() - 3600
        pid = _record(str(tmp_path), "RELIANCE", "BUY", 2500.0, ts=ts)
        before = time.time()
        _resolve(str(tmp_path), "RELIANCE", pid, 2530.0, time.time())
        after = time.time()
        r = _load(str(tmp_path), "RELIANCE")[0]
        assert before <= r["resolved_at"] <= after


# ── 3. get_pending_predictions ────────────────────────────────

class TestGetPendingPredictions:

    def test_returns_due_unresolved(self, tmp_path):
        ts = time.time() - 3600
        _record(str(tmp_path), "RELIANCE", "BUY", 2500.0, ts=ts, horizon=30)
        assert len(_pending(str(tmp_path))) == 1

    def test_does_not_return_future_horizon(self, tmp_path):
        _record(str(tmp_path), "TCS", "BUY", 3500.0, ts=time.time(), horizon=30)
        assert len(_pending(str(tmp_path))) == 0

    def test_does_not_return_already_resolved(self, tmp_path):
        ts = time.time() - 3600
        pid = _record(str(tmp_path), "INFY", "BUY", 1800.0, ts=ts)
        _resolve(str(tmp_path), "INFY", pid, 1820.0, time.time())
        assert len(_pending(str(tmp_path))) == 0

    def test_multiple_symbols_multiple_pending(self, tmp_path):
        ts = time.time() - 3600
        _record(str(tmp_path), "RELIANCE", "BUY", 2500.0, ts=ts)
        _record(str(tmp_path), "TCS", "SELL", 3500.0, ts=ts)
        assert len(_pending(str(tmp_path))) == 2


# ── 4. get_ai_self_evaluation ─────────────────────────────────

class TestGetAiSelfEvaluation:

    def test_empty_returns_zero_total(self, tmp_path):
        result = _eval(str(tmp_path))
        assert result["total_predictions"] == 0

    def test_counts_pending_and_resolved(self, tmp_path):
        ts_past = time.time() - 3600
        pid1 = _record(str(tmp_path), "RELIANCE", "BUY", 2500.0, ts=ts_past)
        _resolve(str(tmp_path), "RELIANCE", pid1, 2530.0, time.time())
        _record(str(tmp_path), "TCS", "BUY", 3500.0, ts=time.time())  # pending

        result = _eval(str(tmp_path))
        assert result["total_predictions"] == 2
        assert result["evaluated"] == 1
        assert result["correct"] == 1
        assert result["incorrect"] == 0
        assert result["accuracy"] == 100.0

    def test_accuracy_with_mixed_results(self, tmp_path):
        ts = time.time() - 3600
        p1 = _record(str(tmp_path), "RELIANCE", "BUY", 2500.0, ts=ts - 10)
        p2 = _record(str(tmp_path), "TCS", "BUY", 3500.0, ts=ts - 20)
        p3 = _record(str(tmp_path), "INFY", "BUY", 1800.0, ts=ts - 30)
        _resolve(str(tmp_path), "RELIANCE", p1, 2530.0, time.time())  # correct
        _resolve(str(tmp_path), "TCS", p2, 3460.0, time.time())       # incorrect
        _resolve(str(tmp_path), "INFY", p3, 1820.0, time.time())      # correct

        result = _eval(str(tmp_path))
        assert result["evaluated"] == 3
        assert result["correct"] == 2
        assert result["incorrect"] == 1
        assert result["accuracy"] == pytest.approx(66.7, abs=0.1)

    def test_due_for_resolution_count(self, tmp_path):
        ts = time.time() - 3600
        _record(str(tmp_path), "RELIANCE", "BUY", 2500.0, ts=ts)  # due
        _record(str(tmp_path), "TCS", "BUY", 3500.0, ts=time.time())  # not due

        result = _eval(str(tmp_path))
        assert result["due_for_resolution"] == 1
        assert result["pending"] == 1


# ── 5. resolve_pending_predictions ───────────────────────────

def _run(coro):
    """Run a coroutine in a new event loop (Python 3.7 compatible)."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


class TestResolvePendingPredictions:

    def test_resolves_due_predictions(self, tmp_path):
        import app.api.model_validator as mv
        import app.api.paper_trading as pt

        ts = time.time() - 3600
        _record(str(tmp_path), "RELIANCE", "BUY", 2500.0, ts=ts)

        orig, mv.RESULTS_DIR = mv.RESULTS_DIR, str(tmp_path)
        try:
            with patch.object(pt, "_get_live_price", side_effect=_async_return(2530.0)):
                summary = _run(pt.resolve_pending_predictions())
        finally:
            mv.RESULTS_DIR = orig

        assert summary["resolved"] == 1
        assert summary["failed"] == 0

    def test_failed_when_price_unavailable(self, tmp_path):
        import app.api.model_validator as mv
        import app.api.paper_trading as pt

        ts = time.time() - 3600
        _record(str(tmp_path), "RELIANCE", "BUY", 2500.0, ts=ts)

        orig, mv.RESULTS_DIR = mv.RESULTS_DIR, str(tmp_path)
        try:
            with patch.object(pt, "_get_live_price", side_effect=_async_return(None)):
                summary = _run(pt.resolve_pending_predictions())
        finally:
            mv.RESULTS_DIR = orig

        assert summary["resolved"] == 0
        assert summary["failed"] == 1

    def test_no_pending_returns_zero(self, tmp_path):
        import app.api.model_validator as mv
        import app.api.paper_trading as pt

        orig, mv.RESULTS_DIR = mv.RESULTS_DIR, str(tmp_path)
        try:
            summary = _run(pt.resolve_pending_predictions())
        finally:
            mv.RESULTS_DIR = orig

        assert summary["resolved"] == 0

    def test_multiple_simultaneous_predictions(self, tmp_path):
        import app.api.model_validator as mv
        import app.api.paper_trading as pt

        ts = time.time() - 3600
        _record(str(tmp_path), "RELIANCE", "BUY", 2500.0, ts=ts - 10)
        _record(str(tmp_path), "TCS", "SELL", 3500.0, ts=ts - 20)
        _record(str(tmp_path), "INFY", "BUY", 1800.0, ts=ts - 30)

        orig, mv.RESULTS_DIR = mv.RESULTS_DIR, str(tmp_path)
        try:
            with patch.object(pt, "_get_live_price", side_effect=_async_return(2000.0)):
                summary = _run(pt.resolve_pending_predictions())
        finally:
            mv.RESULTS_DIR = orig

        assert summary["resolved"] == 3
        assert summary["checked"] == 3

    def test_different_horizons_only_due_resolved(self, tmp_path):
        import app.api.model_validator as mv
        import app.api.paper_trading as pt

        now = time.time()
        # 15-min horizon, 20 min ago → due
        _record(str(tmp_path), "RELIANCE", "BUY", 2500.0,
                ts=now - 20 * 60, horizon=15)
        # 60-min horizon, 30 min ago → NOT due yet
        _record(str(tmp_path), "TCS", "BUY", 3500.0,
                ts=now - 30 * 60, horizon=60)

        orig, mv.RESULTS_DIR = mv.RESULTS_DIR, str(tmp_path)
        try:
            with patch.object(pt, "_get_live_price", side_effect=_async_return(2530.0)):
                summary = _run(pt.resolve_pending_predictions())
        finally:
            mv.RESULTS_DIR = orig

        assert summary["resolved"] == 1
        assert summary["checked"] == 1
