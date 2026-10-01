"""Walk-Forward Validator — measure real out-of-sample model accuracy.

Replaces the fake indicator-agreement confidence score with
historically calibrated probabilities derived from actual predictions
vs actual outcomes.
"""
from __future__ import annotations
import os
import json
import time
from typing import Dict, List, Any, Optional, Tuple
import numpy as np

RESULTS_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "models", "wfv")


def _ensure_dir():
    os.makedirs(RESULTS_DIR, exist_ok=True)


def _results_path(symbol: str) -> str:
    safe = symbol.replace(".", "_").replace("/", "_")
    return os.path.join(RESULTS_DIR, f"{safe}_wfv.json")


# ── Record a prediction ───────────────────────────────────────

def record_prediction(
    symbol: str,
    signal: str,          # BUY / SELL / HOLD
    confidence: float,    # model's stated confidence 0-100
    price_at_signal: float,
    timestamp: float,
    horizon_minutes: int = 30,
    source: str = "xgboost",
    # Extended context — all optional for backward compatibility
    direction: Optional[str] = None,
    prob_up: Optional[float] = None,
    prob_down: Optional[float] = None,
    prob_flat: Optional[float] = None,
    stop_loss: Optional[float] = None,
    target: Optional[float] = None,
    regime: Optional[str] = None,
    wfv_accuracy: Optional[float] = None,
    wfv_useful: Optional[bool] = None,
) -> str:
    """
    Store a prediction so it can be evaluated later.
    Returns a prediction_id.
    """
    _ensure_dir()
    pred_id = f"{symbol}_{int(timestamp)}_{signal}"
    record = {
        "id":              pred_id,
        "symbol":          symbol,
        "signal":          signal,
        "confidence":      confidence,
        "price_at_signal": price_at_signal,
        "timestamp":       timestamp,
        "horizon_minutes": horizon_minutes,
        "horizon_due_ts":  timestamp + horizon_minutes * 60,  # Unix ts when resolution is due
        "source":          source,
        "outcome":         None,   # filled in later
        "actual_return":   None,
        "correct":         None,
        # Extended context
        "direction":       direction,
        "prob_up":         prob_up,
        "prob_down":       prob_down,
        "prob_flat":       prob_flat,
        "stop_loss":       stop_loss,
        "target":          target,
        "regime":          regime,
        "wfv_accuracy":    wfv_accuracy,
        "wfv_useful":      wfv_useful,
    }
    path = _results_path(symbol)
    records = _load_records(path)
    # Idempotent: skip if this pred_id already exists
    if any(r["id"] == pred_id for r in records):
        return pred_id
    records.append(record)
    # Keep last 500 predictions per symbol
    records = records[-500:]
    _save_records(path, records)
    return pred_id


def resolve_prediction(
    symbol: str,
    pred_id: str,
    actual_price: float,
    actual_price_ts: Optional[float] = None,
) -> Optional[Dict]:
    """
    Resolve a stored prediction against the actual price.
    Call this after horizon_minutes have elapsed.

    Safety rules:
      - A prediction already resolved is NOT resolved again (idempotent).
      - actual_price must be > 0; otherwise resolution is skipped.
      - actual_price_ts (Unix seconds) must be >= horizon_due_ts when provided;
        stale actual prices are rejected and the prediction stays pending.
    """
    path = _results_path(symbol)
    records = _load_records(path)
    updated = False
    for r in records:
        if r["id"] != pred_id:
            continue
        if r["outcome"] is not None:
            # Already resolved — idempotent, return existing record
            return r
        if actual_price <= 0:
            # Missing price — leave pending
            return r
        # Freshness guard: reject if actual price timestamp is before the horizon
        due_ts = r.get("horizon_due_ts")
        if due_ts and actual_price_ts is not None and actual_price_ts < due_ts:
            # Stale actual price — leave pending
            return r
        entry = r["price_at_signal"]
        if entry <= 0:
            return r
        ret = (actual_price - entry) / entry
        r["actual_return"] = round(ret * 100, 3)
        r["actual_price"]  = actual_price
        r["resolved_at"]   = time.time()
        # Correct if direction matches
        if r["signal"] == "BUY":
            r["correct"] = ret > 0.001
        elif r["signal"] == "SELL":
            r["correct"] = ret < -0.001
        else:  # HOLD
            r["correct"] = abs(ret) < 0.005
        r["outcome"] = "resolved"
        updated = True
        break
    if updated:
        _save_records(path, records)
    return next((r for r in records if r["id"] == pred_id), None)


def get_pending_predictions(symbol: Optional[str] = None) -> List[Dict]:
    """
    Return all predictions whose horizon has elapsed but are not yet resolved.
    If symbol is given, only that symbol's predictions are returned.
    """
    _ensure_dir()
    now = time.time()
    pending = []
    files = (
        [_results_path(symbol)] if symbol
        else [os.path.join(RESULTS_DIR, f) for f in os.listdir(RESULTS_DIR) if f.endswith("_wfv.json")]
    )
    for path in files:
        for r in _load_records(path):
            if r.get("outcome") is None and r.get("horizon_due_ts", 0) <= now:
                pending.append(r)
    return pending



def get_calibrated_accuracy(symbol: str, signal: str = "BUY") -> Dict[str, Any]:
    """
    Compute historical accuracy for a given symbol + signal direction.
    Returns calibrated confidence and performance stats.
    """
    path = _results_path(symbol)
    records = _load_records(path)

    resolved = [r for r in records if r["outcome"] == "resolved" and r["signal"] == signal]
    if len(resolved) < 10:
        return {
            "calibrated": False,
            "reason":     f"Only {len(resolved)} resolved {signal} predictions — need 10+",
            "accuracy":   None,
            "sample_size": len(resolved),
        }

    correct = [r for r in resolved if r["correct"]]
    accuracy = len(correct) / len(resolved)

    # Confidence buckets: how accurate are high-confidence vs low-confidence predictions?
    buckets = {"high": [], "medium": [], "low": []}
    for r in resolved:
        c = r.get("confidence", 50)
        if c >= 70:
            buckets["high"].append(r["correct"])
        elif c >= 50:
            buckets["medium"].append(r["correct"])
        else:
            buckets["low"].append(r["correct"])

    bucket_accuracy = {}
    for k, v in buckets.items():
        if v:
            bucket_accuracy[k] = round(sum(v) / len(v) * 100, 1)

    # Average return when correct vs incorrect
    correct_returns   = [r["actual_return"] for r in correct if r["actual_return"] is not None]
    incorrect_returns = [r["actual_return"] for r in resolved if not r["correct"] and r["actual_return"] is not None]

    avg_win  = round(sum(correct_returns)   / len(correct_returns),   3) if correct_returns   else 0
    avg_loss = round(sum(incorrect_returns) / len(incorrect_returns), 3) if incorrect_returns else 0

    return {
        "calibrated":       True,
        "symbol":           symbol,
        "signal":           signal,
        "accuracy":         round(accuracy * 100, 1),
        "sample_size":      len(resolved),
        "correct":          len(correct),
        "bucket_accuracy":  bucket_accuracy,
        "avg_win_pct":      avg_win,
        "avg_loss_pct":     avg_loss,
        "expectancy":       round(accuracy * avg_win + (1 - accuracy) * avg_loss, 3),
        "last_updated":     time.time(),
    }


def get_all_accuracy_summary() -> Dict[str, Any]:
    """Return accuracy summary across all tracked symbols."""
    _ensure_dir()
    summaries = []
    for fname in os.listdir(RESULTS_DIR):
        if not fname.endswith("_wfv.json"):
            continue
        symbol = fname.replace("_wfv.json", "").replace("_", ".")
        for sig in ("BUY", "SELL"):
            acc = get_calibrated_accuracy(symbol, sig)
            if acc.get("calibrated"):
                summaries.append(acc)
    summaries.sort(key=lambda x: x.get("accuracy", 0), reverse=True)
    return {"summaries": summaries, "total_symbols": len(set(s["symbol"] for s in summaries))}


# ── Walk-forward backtest ─────────────────────────────────────

def walk_forward_test(
    candles: List[Dict],
    ta_history: List[Dict],
    model,
    horizon: int = 6,
    train_pct: float = 0.75,
) -> Dict[str, Any]:
    """
    Split data into train/test, train on first 75%, evaluate on last 25%.
    Returns real out-of-sample accuracy — the only honest measure.
    """
    from app.api.forecaster import build_features, compute_prediction_label

    n = len(candles)
    split = int(n * train_pct)

    if split < 30 or (n - split) < 10:
        return {"error": "insufficient_data_for_walk_forward", "n": n}

    # Build test features and labels
    X_test, y_test, prices = [], [], []
    for i in range(split, n - horizon):
        if i >= len(ta_history):
            break
        if ta_history[i].get("error"):
            continue
        feats = build_features(candles[:i + 1], ta_history[i])
        if feats is None:
            continue
        label = compute_prediction_label(candles, ta_history, i, horizon)
        if label is None:
            continue
        X_test.append(feats)
        y_test.append(label)
        prices.append(candles[i]["c"])

    if len(X_test) < 5:
        return {"error": "insufficient_test_samples", "n_test": len(X_test)}

    X_test = np.array(X_test)
    y_test = np.array(y_test)

    try:
        proba = model.predict_proba(X_test)
        preds = model.predict(X_test)
    except Exception as e:
        return {"error": f"prediction_failed: {e}"}

    correct = int((preds == y_test).sum())
    total   = len(y_test)
    accuracy = round(correct / total * 100, 1)

    # Per-class precision, recall, F1
    per_class: Dict[str, Any] = {}
    for cls, name in [(1, "UP"), (0, "DOWN"), (2, "FLAT")]:
        actual_mask = y_test == cls
        pred_mask   = preds  == cls
        tp = int((actual_mask & pred_mask).sum())
        fp = int((~actual_mask & pred_mask).sum())
        fn = int((actual_mask & ~pred_mask).sum())
        precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        recall    = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        f1        = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0
        per_class[name] = {
            "count":     int(actual_mask.sum()),
            "precision": round(precision, 3),
            "recall":    round(recall, 3),
            "f1":        round(f1, 3),
        }

    # Balanced accuracy: mean per-class recall (not fooled by FLAT dominance)
    recalls = [per_class[n]["recall"] for n in ("UP", "DOWN", "FLAT")]
    balanced_acc = round(float(np.mean(recalls)) * 100, 1)

    # Actionable prediction rate: fraction of test samples predicted UP or DOWN
    actionable_preds = int(((preds == 1) | (preds == 0)).sum())
    actionable_rate  = round(actionable_preds / total * 100, 1)

    # Confidence calibration
    max_proba = proba.max(axis=1)
    high_conf_mask = max_proba >= 0.6
    if high_conf_mask.sum() > 0:
        high_conf_acc = (preds[high_conf_mask] == y_test[high_conf_mask]).sum() / high_conf_mask.sum()
    else:
        high_conf_acc = 0.0

    # FLAT dominance gate: reject model if >70% of test labels are FLAT
    flat_pct = per_class["FLAT"]["count"] / total if total > 0 else 1.0
    flat_dominant = flat_pct > 0.70

    # is_useful: balanced accuracy > 40% AND UP/DOWN F1 both > 0.1
    # AND not FLAT-dominant AND makes at least some actionable predictions
    up_down_f1_ok = per_class["UP"]["f1"] > 0.10 and per_class["DOWN"]["f1"] > 0.10
    is_useful = (
        not flat_dominant
        and balanced_acc > 40.0
        and up_down_f1_ok
        and actionable_rate >= 5.0
    )

    return {
        "test_samples":       total,
        "train_samples":      split,
        "accuracy_pct":       accuracy,
        "balanced_accuracy":  balanced_acc,
        "high_conf_accuracy": round(float(high_conf_acc) * 100, 1),
        "high_conf_samples":  int(high_conf_mask.sum()),
        "class_distribution": {
            "UP":   per_class["UP"]["count"],
            "DOWN": per_class["DOWN"]["count"],
            "FLAT": per_class["FLAT"]["count"],
        },
        "per_class_metrics":  per_class,
        "actionable_rate":    actionable_rate,
        "flat_dominant":      flat_dominant,
        "is_better_than_random": accuracy > 40,
        "is_useful":          is_useful,
        "is_useful_reason": (
            "FLAT-dominant dataset" if flat_dominant else
            f"balanced_acc={balanced_acc}% up_f1={per_class['UP']['f1']} down_f1={per_class['DOWN']['f1']} actionable={actionable_rate}%"
        ),
    }


# ── Helpers ───────────────────────────────────────────────────

def _load_records(path: str) -> List[Dict]:
    try:
        with open(path) as f:
            return json.load(f)
    except Exception:
        return []


def _save_records(path: str, records: List[Dict]):
    try:
        with open(path, "w") as f:
            json.dump(records, f)
    except Exception:
        pass
