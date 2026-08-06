"""Multi-Timeframe Analysis — confirm signals across timeframes.

A signal is only HIGH confidence when 2+ timeframes agree.
Prevents acting on noise from a single low timeframe.
"""
from __future__ import annotations
from typing import Dict, Any, List, Optional


# ── Timeframe ladder ──────────────────────────────────────────
# (label, interval, days)
TIMEFRAME_LADDER = [
    ("1h",  "60m",  5),
    ("4h",  "60m",  30),   # 4h approximated from 1h data
    ("1d",  "1d",   180),
]


async def get_mtf_analysis(symbol: str) -> Dict[str, Any]:
    """
    Run technical analysis on 1h, 4h, and 1d timeframes.
    Returns per-timeframe signals and an overall MTF confluence score.
    """
    from app.market_data.service import fetch_candles
    from app.api.technical_analysis import compute_technical_analysis
    from app.api.data_quality import clean_candles

    full_sym = symbol if "." in symbol else f"{symbol}.NS"
    results  = {}

    for label, interval, days in TIMEFRAME_LADDER:
        try:
            chart = await fetch_candles(full_sym, interval=interval, days=days)
            if chart.get("error") or len(chart.get("candles", [])) < 26:
                results[label] = {"error": "insufficient_data"}
                continue

            candles, qr = clean_candles(chart["candles"])
            if len(candles) < 26:
                results[label] = {"error": "insufficient_clean_data", "quality": qr}
                continue

            # For 4h: resample 1h candles into 4-candle groups
            if label == "4h":
                candles = _resample(candles, 4)
                if len(candles) < 26:
                    results[label] = {"error": "insufficient_after_resample"}
                    continue

            ta = compute_technical_analysis(candles)
            if ta.get("error"):
                results[label] = {"error": ta["error"]}
                continue

            results[label] = {
                "signal":     ta["overall_signal"],
                "trend":      ta["trend"],
                "rsi":        ta["indicators"].get("rsi"),
                "supertrend": ta["indicators"].get("supertrend_direction"),
                "ema_bias":   _ema_bias(ta),
                "score":      ta["score"],
                "confidence": ta["confidence"],
            }
        except Exception as e:
            results[label] = {"error": str(e)}

    confluence = _compute_confluence(results)
    return {
        "symbol":      symbol,
        "timeframes":  results,
        "confluence":  confluence,
    }


def _resample(candles: List[Dict], n: int) -> List[Dict]:
    """Resample candles into n-bar aggregates (e.g. 1h → 4h)."""
    resampled = []
    for i in range(0, len(candles) - n + 1, n):
        group = candles[i:i + n]
        resampled.append({
            "t": group[-1]["t"],
            "o": group[0]["o"],
            "h": max(c["h"] for c in group),
            "l": min(c["l"] for c in group),
            "c": group[-1]["c"],
            "v": sum(c["v"] for c in group),
        })
    return resampled


def _ema_bias(ta: Dict) -> str:
    ind   = ta.get("indicators", {})
    price = ta.get("current_price", 0)
    e50   = ind.get("ema50")
    e200  = ind.get("ema200")
    if e50 and e200:
        if price > e50 > e200:
            return "bullish"
        if price < e50 < e200:
            return "bearish"
    return "neutral"


def _compute_confluence(results: Dict[str, Any]) -> Dict[str, Any]:
    """
    Score how many timeframes agree on direction.
    Returns confluence level: strong / moderate / weak / conflicted
    """
    valid = {k: v for k, v in results.items() if "error" not in v}
    if not valid:
        return {"level": "unknown", "score": 0, "aligned": [], "conflicting": []}

    signals = {k: v["signal"] for k, v in valid.items()}
    buy_tfs  = [k for k, s in signals.items() if s == "BUY"]
    sell_tfs = [k for k, s in signals.items() if s == "SELL"]
    hold_tfs = [k for k, s in signals.items() if s == "HOLD"]

    n = len(valid)
    if len(buy_tfs) == n:
        level = "strong_bull"
        score = 100
    elif len(sell_tfs) == n:
        level = "strong_bear"
        score = 100
    elif len(buy_tfs) >= 2:
        level = "moderate_bull"
        score = 70
    elif len(sell_tfs) >= 2:
        level = "moderate_bear"
        score = 70
    elif len(buy_tfs) == 1 and len(sell_tfs) == 0:
        level = "weak_bull"
        score = 40
    elif len(sell_tfs) == 1 and len(buy_tfs) == 0:
        level = "weak_bear"
        score = 40
    elif buy_tfs and sell_tfs:
        level = "conflicted"
        score = 20
    else:
        level = "neutral"
        score = 30

    # Higher timeframe bias (1d) gets extra weight
    htf = valid.get("1d", {})
    htf_signal = htf.get("signal", "HOLD")

    return {
        "level":       level,
        "score":       score,
        "htf_signal":  htf_signal,
        "buy_tfs":     buy_tfs,
        "sell_tfs":    sell_tfs,
        "hold_tfs":    hold_tfs,
        "recommendation": _mtf_recommendation(level, htf_signal),
    }


def _mtf_recommendation(level: str, htf: str) -> str:
    recs = {
        "strong_bull":   "All timeframes bullish. High-confidence long entry.",
        "strong_bear":   "All timeframes bearish. High-confidence short/exit.",
        "moderate_bull": "2+ timeframes bullish. Good long setup with confirmation.",
        "moderate_bear": "2+ timeframes bearish. Good short/exit setup.",
        "weak_bull":     "Only 1 timeframe bullish. Wait for higher TF confirmation.",
        "weak_bear":     "Only 1 timeframe bearish. Wait for higher TF confirmation.",
        "conflicted":    "Timeframes disagree. Do not trade — wait for alignment.",
        "neutral":       "No clear direction. Stay in cash.",
        "unknown":       "Insufficient data for MTF analysis.",
    }
    base = recs.get(level, "No recommendation.")
    if htf == "BUY" and "bear" in level:
        base += " Note: Daily trend is bullish — short-term weakness may be a dip."
    elif htf == "SELL" and "bull" in level:
        base += " Note: Daily trend is bearish — short-term strength may be a bounce."
    return base
