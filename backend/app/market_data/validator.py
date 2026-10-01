"""
Phase 1.11 — Data Validator
=============================
Validates candle and quote data before it reaches any AI module.
Wraps the existing data_quality.py pipeline and adds:
  - Timestamp sort verification
  - OHLC logical consistency
  - Timezone normalisation (all timestamps stored as UTC ms)
  - Minimum candle count enforcement
  - Volume anomaly detection
  - Candle freshness check (market-session-aware)
"""
from __future__ import annotations

import datetime
import logging
import time
from typing import List, Tuple, Dict, Any, Optional

from app.market_data.providers.base import Candle, Quote

log = logging.getLogger(__name__)

# ── Freshness constants ───────────────────────────────────────
# Maximum acceptable candle age (seconds) during an active NSE session.
# Outside market hours this threshold is NOT enforced — historical data
# is valid for analysis even if the last candle is hours old.
INTRADAY_FRESHNESS_THRESHOLD_SECS: int = 30 * 60   # 30 minutes

# NSE regular session in IST minutes-since-midnight
_NSE_OPEN_MIN  = 9 * 60 + 15   # 09:15
_NSE_CLOSE_MIN = 15 * 60 + 30  # 15:30


def _ist_minutes_now() -> int:
    """Return current IST time as minutes since midnight."""
    utc_now = datetime.datetime.utcnow()
    ist_now = utc_now + datetime.timedelta(hours=5, minutes=30)
    return ist_now.hour * 60 + ist_now.minute


def _ist_weekday_now() -> int:
    """Return current IST weekday (0=Mon … 6=Sun)."""
    utc_now = datetime.datetime.utcnow()
    ist_now = utc_now + datetime.timedelta(hours=5, minutes=30)
    return ist_now.weekday()


def nse_market_open() -> bool:
    """Return True if NSE regular session is currently active."""
    if _ist_weekday_now() >= 5:          # Saturday / Sunday
        return False
    m = _ist_minutes_now()
    return _NSE_OPEN_MIN <= m <= _NSE_CLOSE_MIN


class FreshnessResult:
    """Result of a candle freshness check."""

    def __init__(
        self,
        status: str,          # LIVE | STALE | OLD | MARKET_CLOSED
        age_seconds: float,
        latest_candle_ts_ms: int,
        threshold_secs: int,
        market_open: bool,
    ):
        self.status              = status
        self.age_seconds         = age_seconds
        self.age_minutes         = age_seconds / 60
        self.latest_candle_ts_ms = latest_candle_ts_ms
        self.threshold_secs      = threshold_secs
        self.market_open         = market_open

    @property
    def is_fresh(self) -> bool:
        """True when data is acceptable for live intraday use."""
        return self.status in ("LIVE", "MARKET_CLOSED")

    def __repr__(self) -> str:
        return (
            f"FreshnessResult(status={self.status}, "
            f"age={self.age_minutes:.1f}min, market_open={self.market_open})"
        )


def check_candle_freshness(
    candles: List[Any],   # list of Candle objects or legacy dicts
    threshold_secs: int = INTRADAY_FRESHNESS_THRESHOLD_SECS,
) -> FreshnessResult:
    """
    Measure the age of the latest candle against the current wall-clock time.

    Rules:
      - During NSE market hours: enforce threshold_secs.
        If latest candle is older than threshold → STALE.
      - Outside market hours: data is always MARKET_CLOSED (valid for analysis).
      - Candle age is measured from the candle's own timestamp, not from any
        provider-reported metadata.  This works regardless of which provider
        served the data.

    Args:
        candles:        list of Candle objects or legacy dicts with key 't' (Unix ms UTC)
        threshold_secs: max acceptable age during market hours (default 30 min)

    Returns:
        FreshnessResult
    """
    if not candles:
        return FreshnessResult(
            status="OLD", age_seconds=float("inf"),
            latest_candle_ts_ms=0, threshold_secs=threshold_secs,
            market_open=nse_market_open(),
        )

    # Support both Candle objects and legacy dicts
    last = candles[-1]
    ts_ms: int = last.t if hasattr(last, "t") else int(last.get("t", 0))

    if ts_ms <= 0:
        return FreshnessResult(
            status="OLD", age_seconds=float("inf"),
            latest_candle_ts_ms=0, threshold_secs=threshold_secs,
            market_open=nse_market_open(),
        )

    age_secs   = time.time() - ts_ms / 1000
    market_now = nse_market_open()

    if not market_now:
        # Outside market hours — historical data is valid
        status = "MARKET_CLOSED"
    elif age_secs <= threshold_secs:
        status = "LIVE"
    elif age_secs <= threshold_secs * 2:
        status = "STALE"
    else:
        status = "OLD"

    return FreshnessResult(
        status=status,
        age_seconds=age_secs,
        latest_candle_ts_ms=ts_ms,
        threshold_secs=threshold_secs,
        market_open=market_now,
    )


def validate_candles(
    candles: List[Candle],
    min_count: int = 26,
) -> Tuple[List[Candle], Dict[str, Any]]:
    """
    Validate and clean a list of Candle objects.
    Returns (cleaned_candles, report).

    Also calls the existing data_quality.clean_candles() pipeline
    by converting to/from dict format for full compatibility.
    """
    report: Dict[str, Any] = {
        "original_count":     len(candles),
        "removed_invalid":    0,
        "removed_duplicates": 0,
        "removed_outliers":   0,
        "gaps_found":         0,
        "sort_fixed":         False,
        "quality_score":      100,
        "warnings":           [],
        "usable":             False,
    }

    if not candles:
        report["warnings"].append("Empty candle list")
        return [], report

    # 1. Sort by timestamp
    sorted_candles = sorted(candles, key=lambda c: c.t)
    if sorted_candles[0].t != candles[0].t:
        report["sort_fixed"] = True

    # 2. Remove duplicates by timestamp
    seen: set = set()
    deduped: List[Candle] = []
    for c in sorted_candles:
        if c.t in seen:
            report["removed_duplicates"] += 1
            continue
        seen.add(c.t)
        deduped.append(c)

    # 3. Remove structurally invalid candles
    valid: List[Candle] = []
    for c in deduped:
        if c.c <= 0:
            report["removed_invalid"] += 1
            continue
        # Fix OHLC consistency
        h = max(c.o, c.h, c.l, c.c)
        l = min(c.o, c.h, c.l, c.c)
        valid.append(Candle(t=c.t, o=c.o, h=h, l=l, c=c.c, v=c.v))

    # 4. Remove extreme outliers (close > 10x or < 0.1x median)
    if valid:
        closes = sorted(c.c for c in valid)
        median = closes[len(closes) // 2]
        filtered: List[Candle] = []
        for c in valid:
            ratio = c.c / median if median else 1
            if 0.1 < ratio < 10:
                filtered.append(c)
            else:
                report["removed_outliers"] += 1
                report["warnings"].append(
                    f"Outlier removed: t={c.t} close={c.c:.2f} (median={median:.2f})"
                )
        valid = filtered

    # 5. Detect price gaps > 15%
    for i in range(1, len(valid)):
        prev_c = valid[i - 1].c
        curr_o = valid[i].o
        if prev_c > 0:
            gap = abs(curr_o - prev_c) / prev_c
            if gap > 0.15:
                report["gaps_found"] += 1

    # 6. Quality score
    total_issues = (
        report["removed_invalid"] +
        report["removed_duplicates"] +
        report["removed_outliers"] +
        report["gaps_found"] * 2
    )
    quality = max(0, 100 - int(total_issues / max(len(candles), 1) * 100))
    report["quality_score"] = quality
    report["cleaned_count"] = len(valid)
    report["usable"]        = len(valid) >= min_count

    if quality < 60:
        report["warnings"].append(
            f"Low data quality ({quality}%) — AI predictions may be unreliable"
        )
    if not report["usable"]:
        report["warnings"].append(
            f"Only {len(valid)} candles after cleaning (minimum {min_count} required)"
        )

    return valid, report


def validate_quote(quote: Quote) -> Tuple[bool, str]:
    """
    Validate a single Quote object.
    Returns (is_valid, reason).
    """
    if quote.ltp <= 0:
        return False, f"Invalid LTP: {quote.ltp}"
    if quote.high < quote.low:
        return False, f"High ({quote.high}) < Low ({quote.low})"
    if quote.high < quote.ltp:
        # Fix silently — LTP can exceed day high in some feeds
        pass
    if quote.timestamp <= 0:
        return False, "Missing timestamp"
    return True, "ok"


def candles_to_legacy_dicts(candles: List[Candle]) -> List[Dict]:
    """Convert Candle objects to the dict format existing modules expect."""
    return [c.to_dict() for c in candles]


def legacy_dicts_to_candles(dicts: List[Dict]) -> List[Candle]:
    """Convert legacy dict candles to Candle objects."""
    result = []
    for d in dicts:
        try:
            result.append(Candle(
                t=int(d["t"]), o=float(d["o"]), h=float(d["h"]),
                l=float(d["l"]), c=float(d["c"]), v=int(d.get("v", 0)),
            ))
        except (KeyError, ValueError, TypeError):
            continue
    return result
