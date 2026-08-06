"""Stock Price Forecaster — XGBoost-based price direction prediction."""
from __future__ import annotations
from typing import Dict, List, Any, Optional
import os, pickle, time
import numpy as np

MODEL_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "models")


def build_features(candles: List[Dict], ta: Dict[str, Any]) -> Optional[np.ndarray]:
    if len(candles) < 30:
        return None

    closes  = [c['c'] for c in candles]
    highs   = [c['h'] for c in candles]
    lows    = [c['l'] for c in candles]
    volumes = [c['v'] for c in candles]
    ind     = ta.get("indicators", {})

    def safe(val, default=0.0):
        try: return float(val) if val is not None else default
        except: return default

    price = closes[-1]

    returns_1  = (closes[-1] - closes[-2]) / closes[-2] if closes[-2] else 0
    returns_3  = (closes[-1] - closes[-4]) / closes[-4] if len(closes) >= 4 and closes[-4] else 0
    returns_5  = (closes[-1] - closes[-6]) / closes[-6] if len(closes) >= 6 and closes[-6] else 0
    returns_10 = (closes[-1] - closes[-11]) / closes[-11] if len(closes) >= 11 and closes[-11] else 0

    high_low_ratio = (highs[-1] - lows[-1]) / price if price else 0
    close_position = (closes[-1] - lows[-1]) / (highs[-1] - lows[-1]) if highs[-1] != lows[-1] else 0.5

    vol_ratio  = safe(ind.get("volume_ratio"), 1.0)
    vol_change = (volumes[-1] - volumes[-2]) / volumes[-2] if len(volumes) >= 2 and volumes[-2] else 0

    rsi        = safe(ind.get("rsi"), 50)
    rsi_norm   = (rsi - 50) / 50
    macd       = safe(ind.get("macd"))
    macd_hist  = safe(ind.get("macd_histogram"))
    stoch_k    = safe(ind.get("stochastic_k"), 50)
    stoch_norm = (stoch_k - 50) / 50

    e9   = safe(ind.get("ema9"),   price)
    e21  = safe(ind.get("ema21"),  price)
    e50  = safe(ind.get("ema50"),  price)
    e200 = safe(ind.get("ema200"), price)

    price_vs_e9   = (price - e9)   / e9   if e9   else 0
    price_vs_e21  = (price - e21)  / e21  if e21  else 0
    price_vs_e50  = (price - e50)  / e50  if e50  else 0
    price_vs_e200 = (price - e200) / e200 if e200 else 0
    e9_vs_e21     = (e9 - e21)     / e21  if e21  else 0
    e21_vs_e50    = (e21 - e50)    / e50  if e50  else 0

    vwap          = safe(ind.get("vwap"), price)
    price_vs_vwap = (price - vwap) / vwap if vwap else 0

    atr     = safe(ind.get("atr"), price * 0.01)
    atr_pct = atr / price if price else 0

    bb_u   = safe(ind.get("bb_upper"), price * 1.02)
    bb_l   = safe(ind.get("bb_lower"), price * 0.98)
    bb_m   = safe(ind.get("bb_mid"),   price)
    bb_pos = (price - bb_l) / (bb_u - bb_l) if bb_u != bb_l else 0.5
    bb_width = (bb_u - bb_l) / bb_m if bb_m else 0

    kc_u  = safe(ind.get("keltner_upper"), price * 1.02)
    kc_l  = safe(ind.get("keltner_lower"), price * 0.98)
    kc_pos = (price - kc_l) / (kc_u - kc_l) if kc_u != kc_l else 0.5

    dc_u  = safe(ind.get("donchian_upper"), price * 1.02)
    dc_l  = safe(ind.get("donchian_lower"), price * 0.98)
    dc_pos = (price - dc_l) / (dc_u - dc_l) if dc_u != dc_l else 0.5

    st_dir  = 1.0 if ind.get("supertrend_direction") == "bullish" else -1.0
    sar     = safe(ind.get("parabolic_sar"), price)
    sar_pos = (price - sar) / price if price else 0

    tenkan = safe(ind.get("ichimoku_tenkan"), price)
    kijun  = safe(ind.get("ichimoku_kijun"),  price)
    price_vs_tenkan = (price - tenkan) / tenkan if tenkan else 0
    tenkan_vs_kijun = (tenkan - kijun) / kijun  if kijun  else 0

    fib = ta.get("fibonacci", {})
    fib_levels = [safe(fib.get(k), price) for k in ("fib_236","fib_382","fib_500","fib_618")]
    nearest_fib_dist = min(abs(price - f) / price for f in fib_levels) if fib_levels else 0

    bos_choch = ta.get("bos_choch", [])
    has_bos_bull   = float(any(e["type"] == "BOS"   and e["direction"] == "bullish" for e in bos_choch))
    has_bos_bear   = float(any(e["type"] == "BOS"   and e["direction"] == "bearish" for e in bos_choch))
    has_choch_bull = float(any(e["type"] == "CHoCH" and e["direction"] == "bullish" for e in bos_choch))
    has_choch_bear = float(any(e["type"] == "CHoCH" and e["direction"] == "bearish" for e in bos_choch))

    obs = ta.get("order_blocks", [])
    near_bull_ob = float(any(o["bottom"] <= price <= o["top"] * 1.005 for o in obs if o["type"] == "bullish"))
    near_bear_ob = float(any(o["bottom"] * 0.995 <= price <= o["top"] for o in obs if o["type"] == "bearish"))

    fvgs = ta.get("fvg", [])
    in_bull_fvg = float(any(f["bottom"] <= price <= f["top"] for f in fvgs if f["type"] == "bullish"))
    in_bear_fvg = float(any(f["bottom"] <= price <= f["top"] for f in fvgs if f["type"] == "bearish"))

    cp = ta.get("candlestick_patterns", [])
    cp_bull  = float(any(p["type"] == "bullish" for p in cp))
    cp_bear  = float(any(p["type"] == "bearish" for p in cp))
    cp_neut  = float(any(p["type"] == "neutral" for p in cp))
    cp_count = float(len([p for p in cp if p["type"] == "bullish"]) - len([p for p in cp if p["type"] == "bearish"]))

    ta_score = safe(ta.get("score"), 0) / 10.0

    # Williams %R, CCI, MFI, OBV from indicators
    wr_norm  = safe(ind.get("williams_r"), -50) / 100.0   # normalise -1 to 0
    cci_norm = max(-1.0, min(1.0, safe(ind.get("cci"), 0) / 200.0))  # normalise
    mfi_norm = (safe(ind.get("mfi"), 50) - 50) / 50.0    # normalise -1 to 1
    obv_trend = 1.0 if ind.get("obv_rising") else -1.0

    last_ts = candles[-1].get('t', 0)
    if last_ts:
        ist_hour   = ((last_ts // 3600) + 5) % 24
        ist_minute = (last_ts % 3600) // 60
        session_min = max(0, (ist_hour - 9) * 60 + ist_minute - 15)
        time_progress = min(session_min / 375.0, 1.0)
        is_opening = float(session_min <= 30)
        is_closing = float(session_min >= 345)
    else:
        time_progress = 0.5
        is_opening    = 0.0
        is_closing    = 0.0

    return np.array([
        returns_1, returns_3, returns_5, returns_10,
        high_low_ratio, close_position,
        vol_ratio, vol_change,
        rsi_norm, macd, macd_hist, stoch_norm, ta_score,
        price_vs_e9, price_vs_e21, price_vs_e50, price_vs_e200,
        e9_vs_e21, e21_vs_e50, price_vs_vwap,
        atr_pct, bb_pos, bb_width, kc_pos, dc_pos, sar_pos, st_dir,
        price_vs_tenkan, tenkan_vs_kijun,
        nearest_fib_dist,
        has_bos_bull, has_bos_bear, has_choch_bull, has_choch_bear,
        near_bull_ob, near_bear_ob, in_bull_fvg, in_bear_fvg,
        cp_bull, cp_bear, cp_neut, cp_count,
        wr_norm, cci_norm, mfi_norm, obv_trend,
        time_progress, is_opening, is_closing,
    ], dtype=np.float32)


class StockForecaster:
    RETRAIN_INTERVAL = 4 * 3600

    def __init__(self, symbol: str):
        self.symbol    = symbol.replace(".NS", "").replace(".", "_")
        self.model     = None
        self.trained   = False
        self.trained_at: float = 0.0
        os.makedirs(MODEL_DIR, exist_ok=True)

    def _model_path(self): return os.path.join(MODEL_DIR, f"{self.symbol}_xgb.pkl")
    def _meta_path(self):  return os.path.join(MODEL_DIR, f"{self.symbol}_xgb.meta")

    def is_stale(self) -> bool:
        return (time.time() - self.trained_at) > self.RETRAIN_INTERVAL

    def load(self) -> bool:
        if os.path.exists(self._model_path()):
            try:
                with open(self._model_path(), "rb") as f:
                    self.model = pickle.load(f)
                self.trained = True
                if os.path.exists(self._meta_path()):
                    with open(self._meta_path()) as mf:
                        self.trained_at = float(mf.read().strip())
                return True
            except Exception:
                pass
        return False

    def save(self):
        if self.model:
            with open(self._model_path(), "wb") as f:
                pickle.dump(self.model, f)
            with open(self._meta_path(), "w") as mf:
                mf.write(str(self.trained_at))

    def train(self, candles: List[Dict], ta_history: List[Dict], horizon: int = 6) -> bool:
        try:
            from xgboost import XGBClassifier
        except ImportError:
            return False

        X, y = [], []
        for i in range(len(candles) - horizon):
            if i >= len(ta_history):
                break
            # FIX: skip samples where TA had insufficient data (bad features)
            if ta_history[i].get("error"):
                continue
            feats = build_features(candles[:i + 1], ta_history[i])
            if feats is None:
                continue
            # ATR-relative threshold — avoids 80% FLAT labels on low-volatility stocks
            price_i = candles[i]["c"]
            atr_i   = ta_history[i].get("indicators", {}).get("atr") or price_i * 0.01
            threshold = max(atr_i / price_i * 0.5, 0.002)  # at least 0.2%, at most 0.5 ATR
            future_ret = (candles[i + horizon]['c'] - candles[i]['c']) / candles[i]['c']
            label = 1 if future_ret > threshold else (0 if future_ret < -threshold else 2)
            X.append(feats)
            y.append(label)

        if len(X) < 30:
            return False

        X, y = np.array(X), np.array(y)

        # FIX: actually use sample_weight to counter FLAT class dominance
        n_flat = max((y == 2).sum(), 1)
        n_up   = max((y == 1).sum(), 1)
        n_down = max((y == 0).sum(), 1)
        w = np.ones(len(y))
        w[y == 1] = n_flat / n_up    # upweight UP class
        w[y == 0] = n_flat / n_down  # upweight DOWN class

        self.model = XGBClassifier(
            n_estimators=300,
            max_depth=5,
            learning_rate=0.04,
            subsample=0.8,
            colsample_bytree=0.8,
            min_child_weight=3,
            eval_metric="mlogloss",
            verbosity=0,
            num_class=3,
            objective="multi:softprob",
        )
        self.model.fit(X, y, sample_weight=w)
        self.trained    = True
        self.trained_at = time.time()
        self.save()
        return True

    def predict(self, candles: List[Dict], ta: Dict, horizon_minutes: int = 30) -> Optional[Dict]:
        if not self.trained or self.model is None:
            return None
        feats = build_features(candles, ta)
        if feats is None:
            return None
        try:
            proba = self.model.predict_proba(feats.reshape(1, -1))[0]
        except Exception:
            return None

        classes  = self.model.classes_
        prob_map = {int(c): float(p) for c, p in zip(classes, proba)}
        prob_up   = prob_map.get(1, 0.0)
        prob_down = prob_map.get(0, 0.0)
        prob_flat = prob_map.get(2, 0.0)

        # FIX 1: prob_up must exceed 45% AND beat prob_flat to call UP
        # FIX 2: margin of 0.05 over flat required — avoids borderline calls
        if prob_up >= 0.45 and prob_up > prob_flat + 0.05:
            direction  = "UP"
            confidence = round(prob_up * 100, 1)
        elif prob_down >= 0.45 and prob_down > prob_flat + 0.05:
            direction  = "DOWN"
            confidence = round(prob_down * 100, 1)
        else:
            direction  = "FLAT"
            confidence = round(prob_flat * 100, 1)

        price = candles[-1]['c']
        atr   = ta.get("indicators", {}).get("atr") or price * 0.01

        if direction == "UP":
            estimated_target = round(price + 2.0 * atr, 2)
            estimated_low    = round(price - 1.0 * atr, 2)
        elif direction == "DOWN":
            estimated_target = round(price - 2.0 * atr, 2)
            estimated_low    = round(price + 1.0 * atr, 2)
        else:
            estimated_target = round(price + 0.3 * atr, 2)
            estimated_low    = round(price - 0.3 * atr, 2)

        return {
            "direction":        direction,
            "confidence":       confidence,
            "prob_up":          round(prob_up * 100, 1),
            "prob_down":        round(prob_down * 100, 1),
            "prob_flat":        round(prob_flat * 100, 1),
            "current_price":    price,
            "estimated_target": estimated_target,
            "estimated_low":    estimated_low,
            "horizon":          f"{horizon_minutes} minutes",
            "model":            "XGBoost",
        }


_forecasters: Dict[str, StockForecaster] = {}


def get_forecaster(symbol: str) -> StockForecaster:
    key = symbol.replace(".NS", "")
    if key not in _forecasters:
        fc = StockForecaster(symbol)
        fc.load()
        _forecasters[key] = fc
    return _forecasters[key]


async def forecast(symbol: str, horizon: int = 30) -> Dict[str, Any]:
    from app.market_data.service import fetch_candles
    from app.api.technical_analysis import compute_technical_analysis
    from app.api.data_quality import clean_candles
    from app.api.market_regime import get_market_regime, apply_regime_filter
    from app.api.mtf_analysis import get_mtf_analysis
    from app.api.model_validator import walk_forward_test, get_calibrated_accuracy

    full_symbol   = symbol if "." in symbol else f"{symbol}.NS"
    candles_ahead = 3 if horizon == 15 else 6
    model_key     = f"{full_symbol}_h{candles_ahead}"

    chart = await fetch_candles(full_symbol, interval="5m", days=10)
    if chart.get("error") or len(chart.get("candles", [])) < 30:
        return {"error": "insufficient_data", "symbol": symbol}

    # ── Data quality gate ─────────────────────────────────────────
    candles, quality_report = clean_candles(chart["candles"])
    if len(candles) < 30:
        return {"error": "insufficient_clean_data", "symbol": symbol, "quality": quality_report}

    fc  = get_forecaster(model_key)
    ta  = compute_technical_analysis(candles)
    if ta.get("error"):
        return {"error": ta["error"], "symbol": symbol}

    if not fc.trained or fc.is_stale():
        ta_history = []
        for i in range(30, len(candles)):
            snap = compute_technical_analysis(candles[:i])
            ta_history.append(snap if not snap.get("error") else ta)

        if not fc.train(candles, ta_history, horizon=candles_ahead):
            return {"error": "model_training_failed", "symbol": symbol,
                    "reason": "pip install xgboost"}

        # ── Walk-forward validation ────────────────────────────────────
        wfv = walk_forward_test(candles, ta_history, fc.model, horizon=candles_ahead)
        fc.wfv_result = wfv  # store on forecaster instance
    else:
        wfv = getattr(fc, "wfv_result", {})

    prediction = fc.predict(candles, ta, horizon_minutes=horizon)
    if prediction is None:
        return {"error": "prediction_failed", "symbol": symbol}

    # ── Market regime filter ─────────────────────────────────────────
    regime = await get_market_regime()
    regime_result = apply_regime_filter(
        "BUY" if prediction["direction"] == "UP" else
        "SELL" if prediction["direction"] == "DOWN" else "HOLD",
        regime,
    )

    # ── Multi-timeframe confirmation ─────────────────────────────────
    mtf = await get_mtf_analysis(symbol)
    mtf_confluence = mtf.get("confluence", {})

    # ── Calibrated confidence ─────────────────────────────────────────
    # Replace raw model confidence with historically calibrated value
    signal_dir = "BUY" if prediction["direction"] == "UP" else "SELL"
    cal_acc = get_calibrated_accuracy(symbol, signal_dir)
    if cal_acc.get("calibrated"):
        # Blend model confidence with historical accuracy
        hist_acc = cal_acc["accuracy"]
        model_conf = prediction["confidence"]
        calibrated_conf = round(0.4 * model_conf + 0.6 * hist_acc, 1)
        prediction["confidence"]           = calibrated_conf
        prediction["historical_accuracy"]  = hist_acc
        prediction["calibration_samples"]  = cal_acc["sample_size"]
    else:
        # No history yet — cap raw model confidence at 65% to avoid overconfidence
        prediction["confidence"] = min(prediction["confidence"], 65.0)
        prediction["historical_accuracy"] = None
        prediction["calibration_samples"] = 0

    # ── ATR-adaptive stop loss ─────────────────────────────────────────
    price = candles[-1]["c"]
    atr   = ta.get("indicators", {}).get("atr") or price * 0.01
    # Widen stops during high volatility regime
    stop_multiplier = 2.0 if regime.get("reduce_size") else 1.5
    if prediction["direction"] == "UP":
        prediction["estimated_low"] = round(price - stop_multiplier * atr, 2)
    elif prediction["direction"] == "DOWN":
        prediction["estimated_target"] = round(price - stop_multiplier * atr, 2)

    ind = ta.get("indicators", {})
    sr  = ta.get("support_resistance", {})
    fib = ta.get("fibonacci", {})
    pp  = ta.get("pivot_points", {}).get("standard", {})

    resistances = sr.get("resistance", [])
    supports    = sr.get("support", [])
    nearest_res = min(resistances, key=lambda x: abs(x - price)) if resistances else None
    nearest_sup = min(supports,    key=lambda x: abs(x - price)) if supports    else None

    return {
        "symbol":   full_symbol,
        "forecast": prediction,
        "regime":   {
            "regime":      regime.get("regime"),
            "label":       regime.get("label"),
            "adjusted":    regime_result.get("regime_adjusted"),
            "warning":     regime_result.get("warning"),
            "size_mult":   regime_result.get("size_multiplier"),
        },
        "mtf": {
            "confluence":      mtf_confluence.get("level"),
            "score":           mtf_confluence.get("score"),
            "htf_signal":      mtf_confluence.get("htf_signal"),
            "recommendation":  mtf_confluence.get("recommendation"),
        },
        "validation": {
            "wfv_accuracy":    wfv.get("accuracy_pct"),
            "wfv_useful":      wfv.get("is_useful"),
            "test_samples":    wfv.get("test_samples"),
        },
        "data_quality": {
            "score":    quality_report.get("quality_score"),
            "warnings": quality_report.get("warnings", []),
        },
        "context": {
            "trend":              ta.get("trend"),
            "overall_signal":     ta.get("overall_signal"),
            "ta_confidence":      ta.get("confidence"),
            "ta_score":           ta.get("score"),
            "nearest_resistance": nearest_res,
            "nearest_support":    nearest_sup,
            "pivot":              pp.get("pivot"),
            "fib_618":            fib.get("fib_618"),
            "fib_382":            fib.get("fib_382"),
            "atr":                ind.get("atr"),
            "rsi":                ind.get("rsi"),
            "supertrend":         ind.get("supertrend_direction"),
            "ichimoku_bias": (
                "bullish" if (ind.get("ichimoku_tenkan") or 0) > (ind.get("ichimoku_kijun") or 0)
                else "bearish"
            ),
        },
        "signals_summary": [
            {"indicator": s["indicator"], "signal": s["signal"], "reason": s["reason"]}
            for s in ta.get("signals", [])[:8]
        ],
        "order_blocks":  ta.get("order_blocks", [])[-3:],
        "fvg":           ta.get("fvg", [])[-3:],
        "bos_choch":     ta.get("bos_choch", []),
        "candles_used":  len(candles),
        "model_trained": fc.trained,
    }
