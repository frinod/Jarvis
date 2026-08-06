"""Data Quality Pipeline — validate, clean, and normalize OHLCV candles.

Every candle array must pass through clean_candles() before being used
by technical analysis, forecasting, or backtesting.
"""
from __future__ import annotations
from typing import List, Dict, Tuple, Optional
import math


# ── Validation thresholds ─────────────────────────────────────
_MAX_GAP_RATIO   = 0.15   # flag gap if price jumps > 15% in one candle
_MIN_CANDLES     = 30     # minimum usable candles after cleaning
_MAX_ZERO_BODY   = 0.80   # reject candle if body/range < this AND range is tiny


def clean_candles(candles: List[Dict]) -> Tuple[List[Dict], Dict]:
    """
    Clean and validate a list of OHLCV candles.

    Returns:
        (cleaned_candles, report)
        report keys: removed, gaps_found, duplicates_removed, quality_score (0-100)
    """
    if not candles:
        return [], {"error": "empty", "quality_score": 0}

    report = {
        "original_count":    len(candles),
        "removed":           0,
        "duplicates_removed": 0,
        "gaps_found":        0,
        "zero_volume":       0,
        "quality_score":     100,
        "warnings":          [],
    }

    # 1. Remove duplicates by timestamp
    seen_ts: set = set()
    deduped = []
    for c in candles:
        t = c.get("t", 0)
        if t in seen_ts:
            report["duplicates_removed"] += 1
            continue
        seen_ts.add(t)
        deduped.append(c)
    candles = sorted(deduped, key=lambda x: x.get("t", 0))

    # 2. Remove structurally invalid candles
    cleaned = []
    for c in candles:
        o, h, l, cl, v = (
            c.get("o", 0), c.get("h", 0), c.get("l", 0),
            c.get("c", 0), c.get("v", 0),
        )
        # Must have positive close
        if not cl or cl <= 0:
            report["removed"] += 1
            continue
        # High must be >= low
        if h < l:
            report["removed"] += 1
            continue
        # High must be >= close and open
        if h < cl or h < o:
            # Fix: set high to max of all
            c = {**c, "h": max(o, h, l, cl)}
        # Low must be <= close and open
        if l > cl or l > o:
            c = {**c, "l": min(o, l, h, cl)}
        # Zero volume is suspicious but not invalid for daily data
        if v == 0:
            report["zero_volume"] += 1
        cleaned.append(c)

    # 3. Detect price gaps (possible splits / bad data)
    for i in range(1, len(cleaned)):
        prev_c = cleaned[i - 1]["c"]
        curr_o = cleaned[i]["o"]
        if prev_c > 0:
            gap = abs(curr_o - prev_c) / prev_c
            if gap > _MAX_GAP_RATIO:
                report["gaps_found"] += 1

    # 4. Remove extreme outlier candles (price > 3× median or < 1/3 median)
    closes = [c["c"] for c in cleaned]
    if closes:
        sorted_c = sorted(closes)
        median   = sorted_c[len(sorted_c) // 2]
        filtered = []
        for c in cleaned:
            ratio = c["c"] / median if median else 1
            if 0.1 < ratio < 10:
                filtered.append(c)
            else:
                report["removed"] += 1
                report["warnings"].append(f"Outlier removed at t={c.get('t')}: close={c['c']}")
        cleaned = filtered

    # 5. Quality score
    total_issues = (
        report["removed"] +
        report["duplicates_removed"] +
        report["gaps_found"] * 2 +
        report["zero_volume"]
    )
    quality = max(0, 100 - int(total_issues / max(len(candles), 1) * 100))
    report["quality_score"]  = quality
    report["cleaned_count"]  = len(cleaned)
    report["usable"]         = len(cleaned) >= _MIN_CANDLES

    if quality < 60:
        report["warnings"].append(f"Low data quality ({quality}%) — predictions may be unreliable")

    return cleaned, report


def detect_corporate_actions(candles: List[Dict]) -> List[Dict]:
    """
    Detect likely stock splits or bonus issues from sudden price gaps.
    Returns list of suspected events with approximate date and ratio.
    """
    events = []
    for i in range(1, len(candles)):
        prev = candles[i - 1]["c"]
        curr = candles[i]["o"]
        if prev <= 0:
            continue
        ratio = curr / prev
        # Split: price drops to ~1/2, 1/5, 1/10
        for split in [0.5, 0.2, 0.1, 0.25]:
            if abs(ratio - split) < 0.05:
                events.append({
                    "type":  "split",
                    "ratio": f"1:{round(1/split)}",
                    "index": i,
                    "t":     candles[i].get("t"),
                })
        # Bonus: price drops to ~2/3, 1/2
        for bonus in [0.667, 0.5]:
            if abs(ratio - bonus) < 0.04:
                events.append({
                    "type":  "bonus",
                    "ratio": f"1:{round(1/bonus - 1)}",
                    "index": i,
                    "t":     candles[i].get("t"),
                })
    return events


def normalize_features(X: list) -> list:
    """
    Z-score normalize a flat feature vector in-place.
    Clips to [-5, 5] to prevent extreme outliers from dominating.
    """
    import math
    if not X:
        return X
    mean = sum(X) / len(X)
    std  = math.sqrt(sum((x - mean) ** 2 for x in X) / len(X)) or 1.0
    return [max(-5.0, min(5.0, (x - mean) / std)) for x in X]
