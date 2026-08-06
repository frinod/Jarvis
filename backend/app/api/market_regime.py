"""Market Regime Detector — classify market conditions before generating signals.

Regime is determined from NIFTY 50 daily candles + VIX proxy.
All signal generators should call get_regime() and adapt accordingly.
"""
from __future__ import annotations
import time
from typing import Dict, Any, Optional, List

# ── Regime definitions ────────────────────────────────────────
REGIMES = {
    "strong_bull":    "Strong Bull — trend up, low volatility, buy signals reliable",
    "weak_bull":      "Weak Bull — uptrend but losing momentum, be selective",
    "sideways":       "Sideways / Range — mean reversion works, breakouts fail often",
    "high_volatility":"High Volatility — widen stops, reduce position size",
    "weak_bear":      "Weak Bear — downtrend forming, avoid longs",
    "strong_bear":    "Strong Bear — strong downtrend, only shorts or cash",
    "panic":          "Panic / Capitulation — extreme fear, potential reversal zone",
    "distribution":   "Distribution — smart money selling into strength",
    "accumulation":   "Accumulation — smart money buying into weakness",
    "unknown":        "Unknown — insufficient data",
}

# ── In-memory cache ───────────────────────────────────────────
_regime_cache: Optional[Dict] = None
_regime_ts: float = 0
_REGIME_TTL = 300  # 5 minutes


async def get_market_regime(force_refresh: bool = False) -> Dict[str, Any]:
    """
    Detect current market regime from NIFTY 50 daily data.
    Cached for 5 minutes to avoid repeated fetches.
    """
    global _regime_cache, _regime_ts

    if not force_refresh and _regime_cache and (time.time() - _regime_ts) < _REGIME_TTL:
        return _regime_cache

    try:
        from app.market_data.service import fetch_candles
        from app.api.technical_analysis import (
            _ema, _atr, _rsi, _bollinger
        )

        # Fetch NIFTY 50 daily — 6 months for regime context
        chart = await fetch_candles("^NSEI", interval="1d", days=180)
        if chart.get("error") or len(chart.get("candles", [])) < 50:
            return _unknown_regime("Insufficient NIFTY data")

        candles = chart["candles"]
        closes  = [c["c"] for c in candles]
        highs   = [c["h"] for c in candles]
        lows    = [c["l"] for c in candles]
        volumes = [c["v"] for c in candles]

        regime = _classify_regime(closes, highs, lows, volumes)
        _regime_cache = regime
        _regime_ts    = time.time()
        return regime

    except Exception as e:
        return _unknown_regime(str(e))


def _classify_regime(
    closes: List[float],
    highs:  List[float],
    lows:   List[float],
    volumes: List[float],
) -> Dict[str, Any]:
    from app.api.technical_analysis import _ema, _atr, _rsi, _bollinger, _sma

    n = len(closes)
    price = closes[-1]

    # ── Trend indicators ──────────────────────────────────────
    ema20  = _ema(closes, 20)
    ema50  = _ema(closes, 50)
    ema200 = _ema(closes, 200)
    rsi14  = _rsi(closes, 14)
    atr14  = _atr(highs, lows, closes, 14)
    bb     = _bollinger(closes, 20, 2.0)

    def last(lst):
        return next((v for v in reversed(lst) if v is not None), None)

    e20  = last(ema20)
    e50  = last(ema50)
    e200 = last(ema200)
    rsi  = last(rsi14)
    atr  = last(atr14)
    bb_u = last(bb["upper"])
    bb_l = last(bb["lower"])
    bb_m = last(bb["mid"])

    # ── Volatility regime ─────────────────────────────────────
    # ATR% = ATR / price — compare current vs 20-period average
    atr_pct = (atr / price * 100) if atr and price else 1.0
    atr_vals = [v for v in atr14 if v is not None]
    avg_atr_pct = (sum(atr_vals[-20:]) / min(20, len(atr_vals)) / price * 100) if atr_vals and price else 1.0
    volatility_ratio = atr_pct / avg_atr_pct if avg_atr_pct else 1.0
    high_volatility  = volatility_ratio > 1.5

    # ── Trend strength ────────────────────────────────────────
    above_e200 = price > e200 if e200 else None
    above_e50  = price > e50  if e50  else None
    above_e20  = price > e20  if e20  else None
    e20_above_e50  = (e20 > e50)  if (e20 and e50)  else None
    e50_above_e200 = (e50 > e200) if (e50 and e200) else None

    # ── Recent performance (20-day return) ────────────────────
    ret_20 = (closes[-1] - closes[-21]) / closes[-21] if len(closes) > 21 and closes[-21] else 0
    ret_5  = (closes[-1] - closes[-6])  / closes[-6]  if len(closes) > 6  and closes[-6]  else 0

    # ── Volume trend ──────────────────────────────────────────
    avg_vol_20 = sum(volumes[-20:]) / min(20, len(volumes)) if volumes else 1
    avg_vol_5  = sum(volumes[-5:])  / min(5,  len(volumes)) if volumes else 1
    vol_expanding = avg_vol_5 > avg_vol_20 * 1.1

    # ── Breadth proxy: BB position ────────────────────────────
    bb_pos = (price - bb_l) / (bb_u - bb_l) if (bb_u and bb_l and bb_u != bb_l) else 0.5

    # ── Classify ──────────────────────────────────────────────
    regime_key = "unknown"
    confidence = 50

    if high_volatility and rsi and rsi < 30:
        regime_key = "panic"
        confidence = 80
    elif high_volatility:
        regime_key = "high_volatility"
        confidence = 75
    elif above_e200 and above_e50 and above_e20 and e20_above_e50 and e50_above_e200:
        if ret_20 > 0.04 and vol_expanding:
            regime_key = "strong_bull"
            confidence = 85
        else:
            regime_key = "weak_bull"
            confidence = 70
    elif not above_e200 and not above_e50 and not above_e20:
        if ret_20 < -0.06:
            regime_key = "strong_bear"
            confidence = 80
        else:
            regime_key = "weak_bear"
            confidence = 65
    elif above_e200 and not above_e50:
        # Price below 50 but above 200 — distribution or accumulation
        if vol_expanding and ret_5 < -0.02:
            regime_key = "distribution"
            confidence = 65
        elif vol_expanding and ret_5 > 0.01:
            regime_key = "accumulation"
            confidence = 65
        else:
            regime_key = "sideways"
            confidence = 60
    else:
        regime_key = "sideways"
        confidence = 55

    # ── Signal filter rules ───────────────────────────────────
    # What signal types are reliable in this regime
    allow_longs  = regime_key in ("strong_bull", "weak_bull", "accumulation", "panic")
    allow_shorts = regime_key in ("strong_bear", "weak_bear", "distribution")
    reduce_size  = regime_key in ("high_volatility", "panic", "sideways")
    avoid_breakouts = regime_key in ("sideways", "high_volatility")

    return {
        "regime":          regime_key,
        "label":           REGIMES.get(regime_key, "Unknown"),
        "confidence":      confidence,
        "allow_longs":     allow_longs,
        "allow_shorts":    allow_shorts,
        "reduce_size":     reduce_size,
        "avoid_breakouts": avoid_breakouts,
        "metrics": {
            "price":            round(price, 2),
            "ema20":            round(e20, 2)  if e20  else None,
            "ema50":            round(e50, 2)  if e50  else None,
            "ema200":           round(e200, 2) if e200 else None,
            "rsi":              round(rsi, 1)  if rsi  else None,
            "atr_pct":          round(atr_pct, 2),
            "volatility_ratio": round(volatility_ratio, 2),
            "ret_20d_pct":      round(ret_20 * 100, 2),
            "vol_expanding":    vol_expanding,
            "bb_position":      round(bb_pos, 2),
        },
        "recommendation": _regime_recommendation(regime_key),
    }


def _regime_recommendation(regime: str) -> str:
    recs = {
        "strong_bull":    "Full position size. Favour momentum and trend-following entries.",
        "weak_bull":      "Reduce position size 25%. Be selective — only A-grade setups.",
        "sideways":       "Reduce size 50%. Favour mean-reversion. Avoid breakout trades.",
        "high_volatility":"Reduce size 50-75%. Widen stops by 1.5×. Wait for clarity.",
        "weak_bear":      "Avoid new longs. Hold cash or hedge. Only short setups.",
        "strong_bear":    "Cash or short only. No long positions.",
        "panic":          "Potential reversal zone. Small contrarian longs with tight stops.",
        "distribution":   "Reduce longs. Watch for breakdown. Institutions selling.",
        "accumulation":   "Cautious longs near support. Institutions buying quietly.",
        "unknown":        "Insufficient data. Trade minimum size only.",
    }
    return recs.get(regime, "No recommendation available.")


def _unknown_regime(reason: str) -> Dict[str, Any]:
    return {
        "regime":          "unknown",
        "label":           REGIMES["unknown"],
        "confidence":      0,
        "allow_longs":     True,   # don't block trading on data failure
        "allow_shorts":    True,
        "reduce_size":     True,
        "avoid_breakouts": False,
        "metrics":         {},
        "recommendation":  "Regime detection failed. Trade minimum size.",
        "error":           reason,
    }


def apply_regime_filter(signal: str, regime: Dict[str, Any]) -> Dict[str, Any]:
    """
    Apply regime filter to a generated signal.
    Returns adjusted signal with regime context.
    """
    if regime.get("regime") == "unknown":
        return {"signal": signal, "regime_adjusted": False, "warning": None}

    warning = None
    adjusted = signal

    if signal == "BUY" and not regime.get("allow_longs"):
        adjusted = "HOLD"
        warning  = f"BUY suppressed — regime is {regime['regime']} (longs not recommended)"

    elif signal == "SELL" and not regime.get("allow_shorts"):
        adjusted = "HOLD"
        warning  = f"SELL suppressed — regime is {regime['regime']} (shorts not recommended)"

    size_multiplier = 0.5 if regime.get("reduce_size") else 1.0

    return {
        "signal":           adjusted,
        "original_signal":  signal,
        "regime_adjusted":  adjusted != signal,
        "size_multiplier":  size_multiplier,
        "warning":          warning,
        "regime":           regime["regime"],
        "regime_label":     regime["label"],
    }
