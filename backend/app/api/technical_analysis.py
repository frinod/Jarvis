"""Technical Analysis Engine — indicators, candlestick & chart patterns."""
from __future__ import annotations
from typing import Dict, List, Any
import numpy as np


def _ema(values: List[float], period: int) -> List[float]:
    result = [None] * len(values)
    if len(values) < period:
        return result
    k = 2 / (period + 1)
    # seed with SMA
    result[period - 1] = sum(values[:period]) / period
    for i in range(period, len(values)):
        result[i] = values[i] * k + result[i - 1] * (1 - k)
    return result


def _sma(values: List[float], period: int) -> List[float]:
    result = [None] * len(values)
    if len(values) < period:
        return result
    window_sum = sum(values[:period])
    result[period - 1] = window_sum / period
    for i in range(period, len(values)):
        window_sum += values[i] - values[i - period]
        result[i] = window_sum / period
    return result


def _rsi(closes: List[float], period: int = 14) -> List[float]:
    result = [None] * len(closes)
    if len(closes) < period + 1:
        return result
    gains, losses = [], []
    for i in range(1, len(closes)):
        diff = closes[i] - closes[i - 1]
        gains.append(max(diff, 0))
        losses.append(max(-diff, 0))
    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period
    for i in range(period, len(closes)):
        if i > period:
            avg_gain = (avg_gain * (period - 1) + gains[i - 1]) / period
            avg_loss = (avg_loss * (period - 1) + losses[i - 1]) / period
        rs = avg_gain / avg_loss if avg_loss != 0 else 100
        result[i] = round(100 - (100 / (1 + rs)), 2)
    return result


def _macd(closes: List[float]) -> Dict[str, List]:
    ema12 = _ema(closes, 12)
    ema26 = _ema(closes, 26)
    macd_line = [
        round(ema12[i] - ema26[i], 4) if ema12[i] is not None and ema26[i] is not None else None
        for i in range(len(closes))
    ]
    signal = _ema([v for v in macd_line if v is not None], 9)
    # pad signal back
    offset = next(i for i, v in enumerate(macd_line) if v is not None)
    padded_signal = [None] * offset + signal
    histogram = [
        round(macd_line[i] - padded_signal[i], 4)
        if macd_line[i] is not None and padded_signal[i] is not None else None
        for i in range(len(closes))
    ]
    return {"macd": macd_line, "signal": padded_signal, "histogram": histogram}


def _bollinger(closes: List[float], period: int = 20, std_dev: float = 2.0) -> Dict[str, List]:
    mid = _sma(closes, period)
    upper, lower = [None] * len(closes), [None] * len(closes)
    for i in range(period - 1, len(closes)):
        window = closes[i - period + 1:i + 1]
        std = (sum((x - mid[i]) ** 2 for x in window) / period) ** 0.5
        upper[i] = round(mid[i] + std_dev * std, 2)
        lower[i] = round(mid[i] - std_dev * std, 2)
    return {"upper": upper, "mid": mid, "lower": lower}


def _atr(highs: List[float], lows: List[float], closes: List[float], period: int = 14) -> List[float]:
    trs = [highs[0] - lows[0]]
    for i in range(1, len(closes)):
        tr = max(highs[i] - lows[i], abs(highs[i] - closes[i - 1]), abs(lows[i] - closes[i - 1]))
        trs.append(tr)
    result = [None] * len(closes)
    if len(trs) >= period:
        result[period - 1] = sum(trs[:period]) / period
        for i in range(period, len(closes)):
            result[i] = round((result[i - 1] * (period - 1) + trs[i]) / period, 2)
    return result


def _stochastic(highs: List[float], lows: List[float], closes: List[float], k_period: int = 14, d_period: int = 3) -> Dict[str, List]:
    k = [None] * len(closes)
    for i in range(k_period - 1, len(closes)):
        h = max(highs[i - k_period + 1:i + 1])
        l = min(lows[i - k_period + 1:i + 1])
        k[i] = round((closes[i] - l) / (h - l) * 100, 2) if h != l else 50.0
    k_vals = [v for v in k if v is not None]
    d_raw = _sma(k_vals, d_period)
    offset = next(i for i, v in enumerate(k) if v is not None)
    d = [None] * offset + d_raw
    return {"k": k, "d": d}


def _vwap(highs: List[float], lows: List[float], closes: List[float], volumes: List[float]) -> List[float]:
    result = []
    cum_tp_vol = cum_vol = 0
    for i in range(len(closes)):
        tp = (highs[i] + lows[i] + closes[i]) / 3
        cum_tp_vol += tp * volumes[i]
        cum_vol += volumes[i]
        result.append(round(cum_tp_vol / cum_vol, 2) if cum_vol else closes[i])
    return result


def _williams_r(highs: List[float], lows: List[float], closes: List[float], period: int = 14) -> List[float]:
    """Williams %R — momentum oscillator, -100 to 0. Below -80 = oversold, above -20 = overbought."""
    result = [None] * len(closes)
    for i in range(period - 1, len(closes)):
        hh = max(highs[i - period + 1:i + 1])
        ll = min(lows[i - period + 1:i + 1])
        result[i] = round(-100 * (hh - closes[i]) / (hh - ll), 2) if hh != ll else -50.0
    return result


def _cci(highs: List[float], lows: List[float], closes: List[float], period: int = 20) -> List[float]:
    """Commodity Channel Index — above +100 = overbought, below -100 = oversold."""
    result = [None] * len(closes)
    for i in range(period - 1, len(closes)):
        tp_window = [(highs[j] + lows[j] + closes[j]) / 3 for j in range(i - period + 1, i + 1)]
        mean_tp = sum(tp_window) / period
        mean_dev = sum(abs(tp - mean_tp) for tp in tp_window) / period
        result[i] = round((tp_window[-1] - mean_tp) / (0.015 * mean_dev), 2) if mean_dev else 0.0
    return result


def _mfi(highs: List[float], lows: List[float], closes: List[float], volumes: List[float], period: int = 14) -> List[float]:
    """Money Flow Index — volume-weighted RSI. Above 80 = overbought, below 20 = oversold."""
    result = [None] * len(closes)
    tp = [(highs[i] + lows[i] + closes[i]) / 3 for i in range(len(closes))]
    mf = [tp[i] * volumes[i] for i in range(len(closes))]
    for i in range(period, len(closes)):
        pos = sum(mf[j] for j in range(i - period + 1, i + 1) if tp[j] > tp[j - 1])
        neg = sum(mf[j] for j in range(i - period + 1, i + 1) if tp[j] < tp[j - 1])
        result[i] = round(100 - 100 / (1 + pos / neg), 2) if neg else 100.0
    return result


def _obv(closes: List[float], volumes: List[float]) -> List[float]:
    """On-Balance Volume — cumulative volume direction."""
    result = [0.0]
    for i in range(1, len(closes)):
        if closes[i] > closes[i - 1]:
            result.append(result[-1] + volumes[i])
        elif closes[i] < closes[i - 1]:
            result.append(result[-1] - volumes[i])
        else:
            result.append(result[-1])
    return result


# ── Candlestick Pattern Detection ────────────────────────────

def _body(o, c): return abs(c - o)
def _upper_wick(o, c, h): return h - max(o, c)
def _lower_wick(o, c, l): return min(o, c) - l
def _is_bullish(o, c): return c > o
def _is_bearish(o, c): return c < o


def detect_candlestick_patterns(candles: List[Dict]) -> List[Dict]:
    """Detect candlestick patterns from last 10 candles."""
    patterns = []
    n = len(candles)
    if n < 3:
        return patterns

    def c(i): return candles[i]

    # Check last 5 candles for patterns
    for i in range(max(2, n - 5), n):
        o, h, l, cl = c(i)['o'], c(i)['h'], c(i)['l'], c(i)['c']
        body = _body(o, cl)
        uw = _upper_wick(o, cl, h)
        lw = _lower_wick(o, cl, l)
        total_range = h - l or 0.001

        # Doji
        if body / total_range < 0.1:
            patterns.append({"pattern": "Doji", "type": "neutral", "index": i,
                              "desc": "Indecision — potential reversal signal"})

        # Hammer (bullish reversal at bottom)
        if lw > 2 * body and uw < body * 0.3 and _is_bullish(o, cl):
            patterns.append({"pattern": "Hammer", "type": "bullish", "index": i,
                              "desc": "Bullish reversal — buyers rejected lower prices"})

        # Shooting Star (bearish reversal at top)
        if uw > 2 * body and lw < body * 0.3 and _is_bearish(o, cl):
            patterns.append({"pattern": "Shooting Star", "type": "bearish", "index": i,
                              "desc": "Bearish reversal — sellers rejected higher prices"})

        # Marubozu bullish
        if _is_bullish(o, cl) and body / total_range > 0.9:
            patterns.append({"pattern": "Bullish Marubozu", "type": "bullish", "index": i,
                              "desc": "Strong bullish momentum — full body candle"})

        # Marubozu bearish
        if _is_bearish(o, cl) and body / total_range > 0.9:
            patterns.append({"pattern": "Bearish Marubozu", "type": "bearish", "index": i,
                              "desc": "Strong bearish momentum — full body candle"})

        # Engulfing patterns (need previous candle)
        if i > 0:
            po, pcl = c(i - 1)['o'], c(i - 1)['c']
            prev_body = _body(po, pcl)
            # Bullish engulfing
            if _is_bearish(po, pcl) and _is_bullish(o, cl) and body > prev_body and o < pcl and cl > po:
                patterns.append({"pattern": "Bullish Engulfing", "type": "bullish", "index": i,
                                  "desc": "Strong bullish reversal — current candle engulfs previous bearish candle"})
            # Bearish engulfing
            if _is_bullish(po, pcl) and _is_bearish(o, cl) and body > prev_body and o > pcl and cl < po:
                patterns.append({"pattern": "Bearish Engulfing", "type": "bearish", "index": i,
                                  "desc": "Strong bearish reversal — current candle engulfs previous bullish candle"})

        # Morning Star (3-candle bullish reversal)
        if i >= 2:
            o1, c1 = c(i - 2)['o'], c(i - 2)['c']
            o2, c2 = c(i - 1)['o'], c(i - 1)['c']
            if _is_bearish(o1, c1) and _body(o2, c2) < _body(o1, c1) * 0.3 and _is_bullish(o, cl) and cl > (o1 + c1) / 2:
                patterns.append({"pattern": "Morning Star", "type": "bullish", "index": i,
                                  "desc": "3-candle bullish reversal pattern — strong buy signal"})

        # Evening Star (3-candle bearish reversal)
        if i >= 2:
            o1, c1 = c(i - 2)['o'], c(i - 2)['c']
            o2, c2 = c(i - 1)['o'], c(i - 1)['c']
            if _is_bullish(o1, c1) and _body(o2, c2) < _body(o1, c1) * 0.3 and _is_bearish(o, cl) and cl < (o1 + c1) / 2:
                patterns.append({"pattern": "Evening Star", "type": "bearish", "index": i,
                                  "desc": "3-candle bearish reversal pattern — strong sell signal"})

        # Spinning Top
        if 0.1 <= body / total_range <= 0.3 and uw > body and lw > body:
            patterns.append({"pattern": "Spinning Top", "type": "neutral", "index": i,
                              "desc": "Small body, long wicks — indecision, neither bulls nor bears winning"})

        # Harami
        if i > 0:
            po, pcl = c(i - 1)['o'], c(i - 1)['c']
            prev_body = _body(po, pcl)
            if prev_body > 0 and body < prev_body * 0.5:
                if _is_bearish(po, pcl) and _is_bullish(o, cl) and o > pcl and cl < po:
                    patterns.append({"pattern": "Bullish Harami", "type": "bullish", "index": i,
                                      "desc": "Small bullish candle inside large bearish — potential reversal up"})
                if _is_bullish(po, pcl) and _is_bearish(o, cl) and o < pcl and cl > po:
                    patterns.append({"pattern": "Bearish Harami", "type": "bearish", "index": i,
                                      "desc": "Small bearish candle inside large bullish — potential reversal down"})

        # Tweezer Bottom
        if i > 0:
            prev_l = c(i - 1)['l']
            if abs(l - prev_l) / (l or 1) < 0.001 and _is_bullish(o, cl) and _is_bearish(c(i-1)['o'], c(i-1)['c']):
                patterns.append({"pattern": "Tweezer Bottom", "type": "bullish", "index": i,
                                  "desc": "Two candles with same low — bullish reversal signal"})

        # Tweezer Top
        if i > 0:
            prev_h = c(i - 1)['h']
            if abs(h - prev_h) / (h or 1) < 0.001 and _is_bearish(o, cl) and _is_bullish(c(i-1)['o'], c(i-1)['c']):
                patterns.append({"pattern": "Tweezer Top", "type": "bearish", "index": i,
                                  "desc": "Two candles with same high — bearish reversal signal"})

    # Three White Soldiers (last 3 candles)
    if n >= 3:
        c1, c2, c3 = candles[-3], candles[-2], candles[-1]
        if (_is_bullish(c1['o'], c1['c']) and _is_bullish(c2['o'], c2['c']) and _is_bullish(c3['o'], c3['c'])
                and c2['c'] > c1['c'] and c3['c'] > c2['c']
                and c2['o'] > c1['o'] and c3['o'] > c2['o']
                and _body(c1['o'], c1['c']) / (c1['h'] - c1['l'] or 0.001) > 0.6
                and _body(c2['o'], c2['c']) / (c2['h'] - c2['l'] or 0.001) > 0.6
                and _body(c3['o'], c3['c']) / (c3['h'] - c3['l'] or 0.001) > 0.6):
            patterns.append({"pattern": "Three White Soldiers", "type": "bullish", "index": n - 1,
                              "desc": "Three consecutive strong bullish candles — very strong buy signal"})

    # Three Black Crows (last 3 candles)
    if n >= 3:
        c1, c2, c3 = candles[-3], candles[-2], candles[-1]
        if (_is_bearish(c1['o'], c1['c']) and _is_bearish(c2['o'], c2['c']) and _is_bearish(c3['o'], c3['c'])
                and c2['c'] < c1['c'] and c3['c'] < c2['c']
                and c2['o'] < c1['o'] and c3['o'] < c2['o']
                and _body(c1['o'], c1['c']) / (c1['h'] - c1['l'] or 0.001) > 0.6
                and _body(c2['o'], c2['c']) / (c2['h'] - c2['l'] or 0.001) > 0.6
                and _body(c3['o'], c3['c']) / (c3['h'] - c3['l'] or 0.001) > 0.6):
            patterns.append({"pattern": "Three Black Crows", "type": "bearish", "index": n - 1,
                              "desc": "Three consecutive strong bearish candles — very strong sell signal"})

    return patterns


# ── Chart Pattern Detection ───────────────────────────────────

def detect_chart_patterns(closes: List[float]) -> List[Dict]:
    """Detect chart patterns from close prices."""
    patterns = []
    n = len(closes)
    if n < 20:
        return patterns

    recent = closes[-20:]
    highs_idx = [i for i in range(1, 19) if recent[i] > recent[i-1] and recent[i] > recent[i+1]]
    lows_idx  = [i for i in range(1, 19) if recent[i] < recent[i-1] and recent[i] < recent[i+1]]

    # Double Top
    if len(highs_idx) >= 2:
        h1, h2 = recent[highs_idx[-2]], recent[highs_idx[-1]]
        if abs(h1 - h2) / h1 < 0.02:
            patterns.append({"pattern": "Double Top", "type": "bearish",
                              "desc": "Bearish reversal — price failed to break resistance twice"})

    # Double Bottom
    if len(lows_idx) >= 2:
        l1, l2 = recent[lows_idx[-2]], recent[lows_idx[-1]]
        if abs(l1 - l2) / l1 < 0.02:
            patterns.append({"pattern": "Double Bottom", "type": "bullish",
                              "desc": "Bullish reversal — price found support twice"})

    # Higher Highs + Higher Lows = Uptrend
    if len(highs_idx) >= 2 and len(lows_idx) >= 2:
        if recent[highs_idx[-1]] > recent[highs_idx[-2]] and recent[lows_idx[-1]] > recent[lows_idx[-2]]:
            patterns.append({"pattern": "Uptrend (HH+HL)", "type": "bullish",
                              "desc": "Price making higher highs and higher lows — bullish structure"})
        elif recent[highs_idx[-1]] < recent[highs_idx[-2]] and recent[lows_idx[-1]] < recent[lows_idx[-2]]:
            patterns.append({"pattern": "Downtrend (LH+LL)", "type": "bearish",
                              "desc": "Price making lower highs and lower lows — bearish structure"})

    # Consolidation / Range
    price_range = (max(recent) - min(recent)) / min(recent)
    if price_range < 0.03:
        patterns.append({"pattern": "Consolidation / Range", "type": "neutral",
                          "desc": "Price consolidating in tight range — breakout expected"})

    # Head & Shoulders (bearish reversal)
    if len(highs_idx) >= 3:
        lsh = recent[highs_idx[-3]]
        head = recent[highs_idx[-2]]
        rsh = recent[highs_idx[-1]]
        if head > lsh and head > rsh and abs(lsh - rsh) / head < 0.03:
            patterns.append({"pattern": "Head & Shoulders", "type": "bearish",
                              "desc": "Classic bearish reversal — head higher than both shoulders, neckline break expected"})

    # Inverse Head & Shoulders (bullish reversal)
    if len(lows_idx) >= 3:
        lsh = recent[lows_idx[-3]]
        head = recent[lows_idx[-2]]
        rsh = recent[lows_idx[-1]]
        if head < lsh and head < rsh and abs(lsh - rsh) / (lsh or 1) < 0.03:
            patterns.append({"pattern": "Inverse Head & Shoulders", "type": "bullish",
                              "desc": "Classic bullish reversal — head lower than both shoulders, breakout expected"})

    # Ascending Triangle (flat top + rising bottom)
    if len(highs_idx) >= 2 and len(lows_idx) >= 2:
        top_flat = abs(recent[highs_idx[-1]] - recent[highs_idx[-2]]) / (recent[highs_idx[-1]] or 1) < 0.015
        bottom_rising = recent[lows_idx[-1]] > recent[lows_idx[-2]]
        if top_flat and bottom_rising:
            patterns.append({"pattern": "Ascending Triangle", "type": "bullish",
                              "desc": "Flat resistance + rising support — bullish breakout expected"})

    # Descending Triangle (flat bottom + falling top)
    if len(highs_idx) >= 2 and len(lows_idx) >= 2:
        bottom_flat = abs(recent[lows_idx[-1]] - recent[lows_idx[-2]]) / (recent[lows_idx[-1]] or 1) < 0.015
        top_falling = recent[highs_idx[-1]] < recent[highs_idx[-2]]
        if bottom_flat and top_falling:
            patterns.append({"pattern": "Descending Triangle", "type": "bearish",
                              "desc": "Flat support + falling resistance — bearish breakdown expected"})

    # Symmetrical Triangle (converging highs and lows)
    if len(highs_idx) >= 2 and len(lows_idx) >= 2:
        highs_falling = recent[highs_idx[-1]] < recent[highs_idx[-2]]
        lows_rising = recent[lows_idx[-1]] > recent[lows_idx[-2]]
        if highs_falling and lows_rising:
            patterns.append({"pattern": "Symmetrical Triangle", "type": "neutral",
                              "desc": "Converging highs and lows — explosive breakout coming, direction unclear"})

    # Bull Flag (strong up move + tight consolidation)
    if n >= 10:
        pole = closes[-10] - closes[-15] if n >= 15 else 0
        flag_range = max(closes[-5:]) - min(closes[-5:])
        if pole > 0 and flag_range < pole * 0.3:
            patterns.append({"pattern": "Bull Flag", "type": "bullish",
                              "desc": "Strong up move followed by tight consolidation — continuation breakout likely"})

    # Bear Flag (strong down move + tight consolidation)
    if n >= 10:
        pole = closes[-15] - closes[-10] if n >= 15 else 0
        flag_range = max(closes[-5:]) - min(closes[-5:])
        if pole > 0 and flag_range < pole * 0.3:
            patterns.append({"pattern": "Bear Flag", "type": "bearish",
                              "desc": "Strong down move followed by tight consolidation — continuation breakdown likely"})

    return patterns


# ── Support & Resistance ──────────────────────────────────────

def find_support_resistance(candles: List[Dict]) -> Dict[str, List[float]]:
    """Find key support and resistance levels."""
    if len(candles) < 10:
        return {"support": [], "resistance": []}

    highs = [c['h'] for c in candles]
    lows  = [c['l'] for c in candles]
    closes = [c['c'] for c in candles]

    # Pivot points use PREVIOUS candle's HLC — not current bar
    last = candles[-2] if len(candles) >= 2 else candles[-1]
    pivot = (last['h'] + last['l'] + last['c']) / 3
    r1 = round(2 * pivot - last['l'], 2)
    r2 = round(pivot + (last['h'] - last['l']), 2)
    s1 = round(2 * pivot - last['h'], 2)
    s2 = round(pivot - (last['h'] - last['l']), 2)

    # Recent swing highs/lows
    swing_highs = sorted(set([round(highs[i], 1) for i in range(1, len(highs)-1)
                               if highs[i] >= highs[i-1] and highs[i] >= highs[i+1]]), reverse=True)[:3]
    swing_lows  = sorted(set([round(lows[i], 1) for i in range(1, len(lows)-1)
                               if lows[i] <= lows[i-1] and lows[i] <= lows[i+1]]))[:3]

    return {
        "pivot": round(pivot, 2),
        "resistance": sorted(set([r1, r2] + swing_highs), reverse=True)[:4],
        "support": sorted(set([s1, s2] + swing_lows), reverse=True)[:4],
    }


# ── Main Analysis Function ────────────────────────────────────

def compute_technical_analysis(candles: List[Dict]) -> Dict[str, Any]:
    """Full technical analysis from OHLCV candles."""
    if len(candles) < 26:
        return {"error": "insufficient_data"}

    opens   = [c['o'] for c in candles]
    highs   = [c['h'] for c in candles]
    lows    = [c['l'] for c in candles]
    closes  = [c['c'] for c in candles]
    volumes = [c['v'] for c in candles]

    # ── Existing indicators
    rsi_vals  = _rsi(closes)
    macd_data = _macd(closes)
    bb_data   = _bollinger(closes)
    atr_vals  = _atr(highs, lows, closes)
    stoch     = _stochastic(highs, lows, closes)
    ema9      = _ema(closes, 9)
    ema21     = _ema(closes, 21)
    ema50     = _ema(closes, 50)
    ema200    = _ema(closes, 200)
    sma20     = _sma(closes, 20)
    vwap_vals = _vwap(highs, lows, closes, volumes)

    # ── New indicators (Section 3a)
    st_data   = _supertrend(highs, lows, closes)
    ichi_data = _ichimoku(highs, lows, closes)
    sar_vals  = _parabolic_sar(highs, lows)
    fib_data  = _fibonacci(highs, lows)
    dc_data   = _donchian(highs, lows)
    kc_data   = _keltner(highs, lows, closes)
    # Pivot points use PREVIOUS candle's HLC — not current bar
    pivot_data = _pivot_points(highs[-2], lows[-2], closes[-2]) if len(candles) >= 2 else {}

    # ── Accuracy indicators
    wr_vals   = _williams_r(highs, lows, closes)
    cci_vals  = _cci(highs, lows, closes)
    mfi_vals  = _mfi(highs, lows, closes, volumes)
    obv_vals  = _obv(closes, volumes)

    # Latest values (last non-None)
    def last(lst): return next((v for v in reversed(lst) if v is not None), None)

    current_price = closes[-1]

    # Existing latest values
    rsi   = last(rsi_vals)
    macd  = last(macd_data['macd'])
    sig   = last(macd_data['signal'])
    hist  = last(macd_data['histogram'])
    bb_u  = last(bb_data['upper'])
    bb_m  = last(bb_data['mid'])
    bb_l  = last(bb_data['lower'])
    atr   = last(atr_vals)
    stk   = last(stoch['k'])
    std   = last(stoch['d'])
    e9    = last(ema9)
    e21   = last(ema21)
    e50   = last(ema50)
    e200  = last(ema200)
    vwap  = vwap_vals[-1] if vwap_vals else None

    # New latest values
    st_val    = last(st_data['supertrend'])
    st_dir    = last(st_data['direction'])   # 1 = bullish, -1 = bearish
    sar_val   = last(sar_vals)
    ichi_tenkan = last(ichi_data['tenkan'])
    ichi_kijun  = last(ichi_data['kijun'])
    ichi_sa     = last(ichi_data['senkou_a'])
    ichi_sb     = last(ichi_data['senkou_b'])
    dc_upper  = last(dc_data['upper'])
    dc_lower  = last(dc_data['lower'])
    dc_mid    = last(dc_data['middle'])
    kc_upper  = last(kc_data['upper'])
    kc_lower  = last(kc_data['lower'])
    kc_mid    = last(kc_data['mid'])

    wr_val  = last(wr_vals)
    cci_val = last(cci_vals)
    mfi_val = last(mfi_vals)
    obv_now = obv_vals[-1] if obv_vals else 0
    obv_prev = obv_vals[-6] if len(obv_vals) >= 6 else obv_now
    obv_rising = obv_now > obv_prev

    # Volume analysis
    avg_vol = sum(volumes[-20:]) / min(20, len(volumes))
    vol_ratio = round(volumes[-1] / avg_vol, 2) if avg_vol else 1.0

    # Trend determination
    trend = "neutral"
    if e50 and e200:
        if current_price > e50 > e200:
            trend = "strong_uptrend"
        elif current_price > e50:
            trend = "uptrend"
        elif current_price < e50 < e200:
            trend = "strong_downtrend"
        elif current_price < e50:
            trend = "downtrend"
    elif e21:
        trend = "uptrend" if current_price > e21 else "downtrend"

    # ── Signal scoring — each indicator votes ────────────────
    signals = []

    # RSI — fixed thresholds: <35 oversold, >65 overbought (not 45/55 which is neutral)
    if rsi is not None:
        if rsi < 35:
            signals.append({"indicator": "RSI", "signal": "buy", "strength": "strong",
                             "value": rsi, "reason": f"RSI {rsi:.1f} — oversold territory"})
        elif rsi < 45:
            signals.append({"indicator": "RSI", "signal": "buy", "strength": "weak",
                             "value": rsi, "reason": f"RSI {rsi:.1f} — recovering from oversold"})
        elif rsi > 65:
            signals.append({"indicator": "RSI", "signal": "sell", "strength": "strong",
                             "value": rsi, "reason": f"RSI {rsi:.1f} — overbought territory"})
        elif rsi > 55:
            signals.append({"indicator": "RSI", "signal": "sell", "strength": "weak",
                             "value": rsi, "reason": f"RSI {rsi:.1f} — approaching overbought"})
        else:
            signals.append({"indicator": "RSI", "signal": "hold", "strength": "neutral",
                             "value": rsi, "reason": f"RSI {rsi:.1f} — neutral zone"})

    # MACD — use relative threshold (% of price) not absolute 0.5
    if macd is not None and sig is not None and hist is not None:
        macd_threshold = current_price * 0.0002  # 0.02% of price = relative
        if macd > sig and hist and hist > 0:
            signals.append({"indicator": "MACD", "signal": "buy",
                             "strength": "strong" if hist > macd_threshold else "weak",
                             "value": round(macd, 4), "reason": f"MACD bullish crossover, hist={round(hist,4)}"})
        elif macd < sig and hist and hist < 0:
            signals.append({"indicator": "MACD", "signal": "sell",
                             "strength": "strong" if abs(hist) > macd_threshold else "weak",
                             "value": round(macd, 4), "reason": f"MACD bearish crossover, hist={round(hist,4)}"})

    # Bollinger Bands
    if bb_u and bb_l and bb_m:
        if current_price <= bb_l:
            signals.append({"indicator": "Bollinger Bands", "signal": "buy", "strength": "strong",
                             "value": round(current_price, 2), "reason": "Price at lower BB — oversold bounce likely"})
        elif current_price >= bb_u:
            signals.append({"indicator": "Bollinger Bands", "signal": "sell", "strength": "strong",
                             "value": round(current_price, 2), "reason": "Price at upper BB — overbought pullback likely"})
        bb_width = round((bb_u - bb_l) / bb_m * 100, 2)
        if bb_width < 2:
            signals.append({"indicator": "Bollinger Bands", "signal": "hold", "strength": "neutral",
                             "value": bb_width, "reason": f"BB squeeze ({bb_width}%) — big move imminent"})

    # EMA 9/21
    if e9 is not None and e21 is not None:
        if e9 > e21 and current_price > e9:
            signals.append({"indicator": "EMA 9/21", "signal": "buy", "strength": "moderate",
                             "value": round(e9, 2), "reason": f"EMA9 {e9:.2f} > EMA21 {e21:.2f} — bullish alignment"})
        elif e9 < e21 and current_price < e9:
            signals.append({"indicator": "EMA 9/21", "signal": "sell", "strength": "moderate",
                             "value": round(e9, 2), "reason": f"EMA9 {e9:.2f} < EMA21 {e21:.2f} — bearish alignment"})

    # VWAP
    if vwap is not None:
        if current_price > vwap:
            signals.append({"indicator": "VWAP", "signal": "buy", "strength": "weak",
                             "value": round(vwap, 2), "reason": f"Price above VWAP {vwap:.2f} — bullish bias"})
        else:
            signals.append({"indicator": "VWAP", "signal": "sell", "strength": "weak",
                             "value": round(vwap, 2), "reason": f"Price below VWAP {vwap:.2f} — bearish bias"})

    # Stochastic
    if stk is not None:
        if stk < 20:
            signals.append({"indicator": "Stochastic", "signal": "buy", "strength": "moderate",
                             "value": round(stk, 1), "reason": f"Stochastic {stk:.1f} — oversold"})
        elif stk > 80:
            signals.append({"indicator": "Stochastic", "signal": "sell", "strength": "moderate",
                             "value": round(stk, 1), "reason": f"Stochastic {stk:.1f} — overbought"})

    # Supertrend
    if st_dir is not None:
        if st_dir == 1:
            signals.append({"indicator": "Supertrend", "signal": "buy", "strength": "strong",
                             "value": round(st_val, 2) if st_val else None,
                             "reason": f"Supertrend bullish — price above support {round(st_val,2) if st_val else ''}"})
        else:
            signals.append({"indicator": "Supertrend", "signal": "sell", "strength": "strong",
                             "value": round(st_val, 2) if st_val else None,
                             "reason": f"Supertrend bearish — price below resistance {round(st_val,2) if st_val else ''}"})

    # Parabolic SAR
    if sar_val is not None:
        if current_price > sar_val:
            signals.append({"indicator": "Parabolic SAR", "signal": "buy", "strength": "moderate",
                             "value": round(sar_val, 2),
                             "reason": f"Price above SAR {sar_val:.2f} — uptrend, trail stop below SAR"})
        else:
            signals.append({"indicator": "Parabolic SAR", "signal": "sell", "strength": "moderate",
                             "value": round(sar_val, 2),
                             "reason": f"Price below SAR {sar_val:.2f} — downtrend, trail stop above SAR"})

    # Ichimoku
    if ichi_tenkan and ichi_kijun:
        if current_price > ichi_tenkan > ichi_kijun:
            signals.append({"indicator": "Ichimoku", "signal": "buy", "strength": "strong",
                             "value": round(ichi_tenkan, 2),
                             "reason": f"Price above Tenkan {ichi_tenkan:.2f} > Kijun {ichi_kijun:.2f} — bullish cloud"})
        elif current_price < ichi_tenkan < ichi_kijun:
            signals.append({"indicator": "Ichimoku", "signal": "sell", "strength": "strong",
                             "value": round(ichi_tenkan, 2),
                             "reason": f"Price below Tenkan {ichi_tenkan:.2f} < Kijun {ichi_kijun:.2f} — bearish cloud"})
        elif ichi_tenkan > ichi_kijun:
            signals.append({"indicator": "Ichimoku", "signal": "buy", "strength": "weak",
                             "value": round(ichi_tenkan, 2),
                             "reason": f"Tenkan {ichi_tenkan:.2f} > Kijun {ichi_kijun:.2f} — mild bullish bias"})
        else:
            signals.append({"indicator": "Ichimoku", "signal": "sell", "strength": "weak",
                             "value": round(ichi_tenkan, 2),
                             "reason": f"Tenkan {ichi_tenkan:.2f} < Kijun {ichi_kijun:.2f} — mild bearish bias"})

    # Donchian Channel
    if dc_upper and dc_lower and dc_mid:
        if current_price >= dc_upper:
            signals.append({"indicator": "Donchian", "signal": "buy", "strength": "moderate",
                             "value": round(dc_upper, 2),
                             "reason": f"Price at Donchian upper {dc_upper:.2f} — breakout momentum"})
        elif current_price <= dc_lower:
            signals.append({"indicator": "Donchian", "signal": "sell", "strength": "moderate",
                             "value": round(dc_lower, 2),
                             "reason": f"Price at Donchian lower {dc_lower:.2f} — breakdown momentum"})

    # Keltner Channel
    if kc_upper and kc_lower and kc_mid:
        if current_price > kc_upper:
            signals.append({"indicator": "Keltner", "signal": "buy", "strength": "moderate",
                             "value": round(kc_upper, 2),
                             "reason": f"Price above Keltner upper {kc_upper:.2f} — strong bullish momentum"})
        elif current_price < kc_lower:
            signals.append({"indicator": "Keltner", "signal": "sell", "strength": "moderate",
                             "value": round(kc_lower, 2),
                             "reason": f"Price below Keltner lower {kc_lower:.2f} — strong bearish momentum"})
        # BB inside Keltner = squeeze setup
        if bb_u and bb_l and bb_u < kc_upper and bb_l > kc_lower:
            signals.append({"indicator": "Keltner Squeeze", "signal": "hold", "strength": "neutral",
                             "value": round(kc_mid, 2),
                             "reason": "BB inside Keltner — volatility squeeze, explosive move coming"})

    # BOS / CHoCH signals
    bos_choch = detect_bos_choch(candles)
    for event in bos_choch:
        if event["type"] == "CHoCH":
            sig_type = "buy" if event["direction"] == "bullish" else "sell"
            signals.append({"indicator": "CHoCH", "signal": sig_type, "strength": "strong",
                             "value": event["level"], "reason": event["desc"]})
        elif event["type"] == "BOS":
            sig_type = "buy" if event["direction"] == "bullish" else "sell"
            signals.append({"indicator": "BOS", "signal": sig_type, "strength": "moderate",
                             "value": event["level"], "reason": event["desc"]})

    # Volume confirmation
    if vol_ratio > 1.5:
        signals.append({"indicator": "Volume", "signal": "confirm", "strength": "strong",
                         "value": vol_ratio, "reason": f"Volume {vol_ratio}x above average — strong conviction move"})

    # Williams %R
    if wr_val is not None:
        if wr_val < -80:
            signals.append({"indicator": "Williams %R", "signal": "buy", "strength": "strong",
                             "value": round(wr_val, 1), "reason": f"Williams %R {wr_val:.1f} — oversold, reversal likely"})
        elif wr_val > -20:
            signals.append({"indicator": "Williams %R", "signal": "sell", "strength": "strong",
                             "value": round(wr_val, 1), "reason": f"Williams %R {wr_val:.1f} — overbought, pullback likely"})

    # CCI
    if cci_val is not None:
        if cci_val < -100:
            signals.append({"indicator": "CCI", "signal": "buy", "strength": "moderate",
                             "value": round(cci_val, 1), "reason": f"CCI {cci_val:.0f} — oversold, mean reversion expected"})
        elif cci_val > 100:
            signals.append({"indicator": "CCI", "signal": "sell", "strength": "moderate",
                             "value": round(cci_val, 1), "reason": f"CCI {cci_val:.0f} — overbought, mean reversion expected"})

    # MFI (volume-weighted RSI)
    if mfi_val is not None:
        if mfi_val < 20:
            signals.append({"indicator": "MFI", "signal": "buy", "strength": "strong",
                             "value": round(mfi_val, 1), "reason": f"MFI {mfi_val:.1f} — money flowing in, oversold"})
        elif mfi_val > 80:
            signals.append({"indicator": "MFI", "signal": "sell", "strength": "strong",
                             "value": round(mfi_val, 1), "reason": f"MFI {mfi_val:.1f} — money flowing out, overbought"})

    # OBV trend
    if obv_rising and vol_ratio > 1.0:
        signals.append({"indicator": "OBV", "signal": "buy", "strength": "weak",
                         "value": round(obv_now, 0), "reason": "OBV rising — accumulation, buyers in control"})
    elif not obv_rising and vol_ratio > 1.0:
        signals.append({"indicator": "OBV", "signal": "sell", "strength": "weak",
                         "value": round(obv_now, 0), "reason": "OBV falling — distribution, sellers in control"})

    # ── Overall score ─────────────────────────────────────────
    score_map = {"buy": {"strong": 2, "moderate": 1.5, "weak": 1},
                 "sell": {"strong": -2, "moderate": -1.5, "weak": -1},
                 "hold": {"neutral": 0}, "confirm": {"strong": 0.5}}
    total_score = sum(score_map.get(s["signal"], {}).get(s["strength"], 0) for s in signals)
    max_possible = sum(2 for s in signals if s["signal"] in ("buy", "sell"))
    confidence = round(min(abs(total_score) / max(max_possible, 1) * 100, 95), 1) if signals else 50.0

    if total_score >= 2:
        overall = "BUY"
    elif total_score <= -2:
        overall = "SELL"
    else:
        overall = "HOLD"

    # ATR-based stop loss and targets
    atr_val = atr or (current_price * 0.01)
    if overall == "BUY":
        stop_loss = round(current_price - 1.5 * atr_val, 2)
        target1   = round(current_price + 2 * atr_val, 2)
        target2   = round(current_price + 3.5 * atr_val, 2)
    elif overall == "SELL":
        stop_loss = round(current_price + 1.5 * atr_val, 2)
        target1   = round(current_price - 2 * atr_val, 2)
        target2   = round(current_price - 3.5 * atr_val, 2)
    else:
        stop_loss = round(current_price - atr_val, 2)
        target1   = round(current_price + atr_val, 2)
        target2   = round(current_price + 2 * atr_val, 2)

    return {
        "current_price": current_price,
        "trend": trend,
        "overall_signal": overall,
        "confidence": confidence,
        "score": round(total_score, 2),
        "stop_loss": stop_loss,
        "target1": target1,
        "target2": target2,
        "risk_reward": round(abs(target1 - current_price) / abs(current_price - stop_loss), 2) if stop_loss != current_price else 0,
        "indicators": {
            # Existing
            "rsi": round(rsi, 2) if rsi else None,
            "macd": round(macd, 4) if macd else None,
            "macd_signal": round(sig, 4) if sig else None,
            "macd_histogram": round(hist, 4) if hist else None,
            "bb_upper": bb_u, "bb_mid": bb_m, "bb_lower": bb_l,
            "ema9": round(e9, 2) if e9 else None,
            "ema21": round(e21, 2) if e21 else None,
            "ema50": round(e50, 2) if e50 else None,
            "ema200": round(e200, 2) if e200 else None,
            "atr": atr,
            "stochastic_k": round(stk, 2) if stk else None,
            "stochastic_d": round(std, 2) if std else None,
            "vwap": vwap,
            "volume_ratio": vol_ratio,
            # New
            "supertrend": round(st_val, 2) if st_val else None,
            "supertrend_direction": "bullish" if st_dir == 1 else "bearish" if st_dir == -1 else None,
            "parabolic_sar": round(sar_val, 2) if sar_val else None,
            "ichimoku_tenkan": round(ichi_tenkan, 2) if ichi_tenkan else None,
            "ichimoku_kijun": round(ichi_kijun, 2) if ichi_kijun else None,
            "ichimoku_senkou_a": round(ichi_sa, 2) if ichi_sa else None,
            "ichimoku_senkou_b": round(ichi_sb, 2) if ichi_sb else None,
            "donchian_upper": dc_upper, "donchian_mid": dc_mid, "donchian_lower": dc_lower,
            "keltner_upper": kc_upper, "keltner_mid": round(kc_mid, 2) if kc_mid else None, "keltner_lower": kc_lower,
            "williams_r":    round(wr_val, 2) if wr_val is not None else None,
            "cci":           round(cci_val, 2) if cci_val is not None else None,
            "mfi":           round(mfi_val, 2) if mfi_val is not None else None,
            "obv":           round(obv_now, 0),
            "obv_rising":    obv_rising,
        },
        "fibonacci": fib_data,
        "pivot_points": pivot_data,
        "signals": signals,
        "candlestick_patterns": detect_candlestick_patterns(candles),
        "chart_patterns": detect_chart_patterns(closes),
        "support_resistance": find_support_resistance(candles),
        "order_blocks": detect_order_blocks(candles),
        "fvg": detect_fvg(candles),
        "bos_choch": bos_choch,
    }


# ── Section 1: New Indicator Functions ───────────────────────


def _supertrend(highs: List[float], lows: List[float], closes: List[float], period: int = 10, multiplier: float = 3.0) -> Dict[str, List]:
    """Supertrend indicator — trend following with ATR bands."""
    atr = _atr(highs, lows, closes, period)
    upper_band = [None] * len(closes)
    lower_band = [None] * len(closes)
    supertrend = [None] * len(closes)
    direction  = [None] * len(closes)  # 1 = bullish, -1 = bearish

    for i in range(period, len(closes)):
        if atr[i] is None:
            continue
        mid = (highs[i] + lows[i]) / 2
        ub = round(mid + multiplier * atr[i], 2)
        lb = round(mid - multiplier * atr[i], 2)

        # Adjust bands based on previous values
        if upper_band[i - 1] is not None:
            ub = ub if ub < upper_band[i - 1] or closes[i - 1] > upper_band[i - 1] else upper_band[i - 1]
        if lower_band[i - 1] is not None:
            lb = lb if lb > lower_band[i - 1] or closes[i - 1] < lower_band[i - 1] else lower_band[i - 1]

        upper_band[i] = ub
        lower_band[i] = lb

        # Direction — compare against previous band values, not newly computed ones
        if supertrend[i - 1] is None:
            direction[i] = 1 if closes[i] > ub else -1
        elif supertrend[i - 1] == upper_band[i - 1]:  # was bearish
            direction[i] = 1 if closes[i] > upper_band[i - 1] else -1
        else:  # was bullish
            direction[i] = -1 if closes[i] < lower_band[i - 1] else 1

        supertrend[i] = lb if direction[i] == 1 else ub

    return {"supertrend": supertrend, "direction": direction, "upper": upper_band, "lower": lower_band}


def _ichimoku(highs: List[float], lows: List[float], closes: List[float]) -> Dict[str, List]:
    """Ichimoku Cloud — tenkan, kijun, senkou A/B, chikou."""
    n = len(closes)

    def mid_range(h, l, p, i):
        if i < p:
            return None
        return round((max(h[i-p+1:i+1]) + min(l[i-p+1:i+1])) / 2, 2)

    tenkan  = [mid_range(highs, lows, 9,  i) for i in range(n)]   # Conversion line
    kijun   = [mid_range(highs, lows, 26, i) for i in range(n)]   # Base line
    chikou  = [None] * 26 + closes[:-26] if n > 26 else [None] * n  # Lagging span

    # Senkou A = (tenkan + kijun) / 2, plotted 26 ahead
    senkou_a = [None] * n
    for i in range(n):
        if tenkan[i] is not None and kijun[i] is not None:
            val = round((tenkan[i] + kijun[i]) / 2, 2)
            if i + 26 < n:
                senkou_a[i + 26] = val

    # Senkou B = 52-period mid, plotted 26 ahead
    senkou_b = [None] * n
    for i in range(n):
        if i >= 52:
            val = round((max(highs[i-52+1:i+1]) + min(lows[i-52+1:i+1])) / 2, 2)
            if i + 26 < n:
                senkou_b[i + 26] = val

    return {
        "tenkan": tenkan,
        "kijun": kijun,
        "senkou_a": senkou_a,
        "senkou_b": senkou_b,
        "chikou": chikou,
    }


def _parabolic_sar(highs: List[float], lows: List[float], af_start: float = 0.02, af_max: float = 0.2) -> List[float]:
    """Parabolic SAR — stop and reverse trailing stop."""
    n = len(highs)
    sar = [None] * n
    if n < 2:
        return sar

    bull = True
    af   = af_start
    ep   = highs[0]   # extreme point
    sar[0] = lows[0]

    for i in range(1, n):
        prev_sar = sar[i - 1]

        if bull:
            sar[i] = round(prev_sar + af * (ep - prev_sar), 2)
            sar[i] = min(sar[i], lows[i - 1], lows[i - 2] if i >= 2 else lows[i - 1])
            if highs[i] > ep:
                ep = highs[i]
                af = min(af + af_start, af_max)
            if lows[i] < sar[i]:          # reversal to bearish
                bull = False
                sar[i] = ep
                ep = lows[i]
                af = af_start
        else:
            sar[i] = round(prev_sar - af * (prev_sar - ep), 2)
            sar[i] = max(sar[i], highs[i - 1], highs[i - 2] if i >= 2 else highs[i - 1])
            if lows[i] < ep:
                ep = lows[i]
                af = min(af + af_start, af_max)
            if highs[i] > sar[i]:         # reversal to bullish
                bull = True
                sar[i] = ep
                ep = highs[i]
                af = af_start

    return sar


def _fibonacci(highs: List[float], lows: List[float], lookback: int = 50) -> Dict[str, float]:
    """Fibonacci retracement levels from recent swing high/low."""
    h = highs[-lookback:] if len(highs) >= lookback else highs
    l = lows[-lookback:]  if len(lows)  >= lookback else lows
    swing_high = max(h)
    swing_low  = min(l)
    diff = swing_high - swing_low
    if diff == 0:
        return {}
    return {
        "swing_high": round(swing_high, 2),
        "swing_low":  round(swing_low, 2),
        "fib_0":      round(swing_high, 2),
        "fib_236":    round(swing_high - 0.236 * diff, 2),
        "fib_382":    round(swing_high - 0.382 * diff, 2),
        "fib_500":    round(swing_high - 0.500 * diff, 2),
        "fib_618":    round(swing_high - 0.618 * diff, 2),
        "fib_786":    round(swing_high - 0.786 * diff, 2),
        "fib_100":    round(swing_low, 2),
    }


def _pivot_points(high: float, low: float, close: float) -> Dict[str, Any]:
    """Standard, Camarilla, and Woodie pivot points from previous candle HLC."""
    pivot = (high + low + close) / 3

    standard = {
        "pivot": round(pivot, 2),
        "r1": round(2 * pivot - low, 2),
        "r2": round(pivot + (high - low), 2),
        "r3": round(high + 2 * (pivot - low), 2),
        "s1": round(2 * pivot - high, 2),
        "s2": round(pivot - (high - low), 2),
        "s3": round(low - 2 * (high - pivot), 2),
    }

    rng = high - low
    camarilla = {
        "r4": round(close + rng * 1.1 / 2, 2),
        "r3": round(close + rng * 1.1 / 4, 2),
        "r2": round(close + rng * 1.1 / 6, 2),
        "r1": round(close + rng * 1.1 / 12, 2),
        "s1": round(close - rng * 1.1 / 12, 2),
        "s2": round(close - rng * 1.1 / 6, 2),
        "s3": round(close - rng * 1.1 / 4, 2),
        "s4": round(close - rng * 1.1 / 2, 2),
    }

    woodie_pivot = (high + low + 2 * close) / 4
    woodie = {
        "pivot": round(woodie_pivot, 2),
        "r1": round(2 * woodie_pivot - low, 2),
        "r2": round(woodie_pivot + (high - low), 2),
        "s1": round(2 * woodie_pivot - high, 2),
        "s2": round(woodie_pivot - (high - low), 2),
    }

    return {"standard": standard, "camarilla": camarilla, "woodie": woodie}


def _donchian(highs: List[float], lows: List[float], period: int = 20) -> Dict[str, List]:
    """Donchian Channel — highest high / lowest low over period."""
    upper  = [None] * len(highs)
    lower  = [None] * len(lows)
    middle = [None] * len(highs)
    for i in range(period - 1, len(highs)):
        u = max(highs[i - period + 1:i + 1])
        l = min(lows[i  - period + 1:i + 1])
        upper[i]  = round(u, 2)
        lower[i]  = round(l, 2)
        middle[i] = round((u + l) / 2, 2)
    return {"upper": upper, "lower": lower, "middle": middle}


def _keltner(highs: List[float], lows: List[float], closes: List[float], period: int = 20, multiplier: float = 2.0) -> Dict[str, List]:
    """Keltner Channel — EMA ± ATR multiplier."""
    ema    = _ema(closes, period)
    atr    = _atr(highs, lows, closes, period)
    upper  = [None] * len(closes)
    lower  = [None] * len(closes)
    for i in range(len(closes)):
        if ema[i] is not None and atr[i] is not None:
            upper[i] = round(ema[i] + multiplier * atr[i], 2)
            lower[i] = round(ema[i] - multiplier * atr[i], 2)
    return {"upper": upper, "mid": ema, "lower": lower}


# ── Section 2: Smart Money Concepts ─────────────────────────


def detect_order_blocks(candles: List[Dict]) -> List[Dict]:
    """Detect bullish and bearish order blocks (last strong impulse candle before a move)."""
    blocks = []
    n = len(candles)
    if n < 5:
        return blocks

    for i in range(2, n - 2):
        o, h, l, c = candles[i]['o'], candles[i]['h'], candles[i]['l'], candles[i]['c']
        body = abs(c - o)
        total_range = h - l or 0.001

        # Must be a strong candle (body > 60% of range)
        if body / total_range < 0.6:
            continue

        # Bullish Order Block: bearish candle followed by strong bullish move up
        if c < o:  # bearish candle
            next_high = max(candles[j]['h'] for j in range(i + 1, min(i + 3, n)))
            if next_high > h * 1.003:  # price moved up strongly after
                blocks.append({
                    "type": "bullish",
                    "top": round(o, 2),
                    "bottom": round(c, 2),
                    "index": i,
                    "desc": f"Bullish OB zone ₹{round(c,2)}–₹{round(o,2)} — institutional buy zone",
                })

        # Bearish Order Block: bullish candle followed by strong bearish move down
        if c > o:  # bullish candle
            next_low = min(candles[j]['l'] for j in range(i + 1, min(i + 3, n)))
            if next_low < l * 0.997:  # price moved down strongly after
                blocks.append({
                    "type": "bearish",
                    "top": round(c, 2),
                    "bottom": round(o, 2),
                    "index": i,
                    "desc": f"Bearish OB zone ₹{round(o,2)}–₹{round(c,2)} — institutional sell zone",
                })

    return blocks[-6:]  # return last 6 most recent


def detect_fvg(candles: List[Dict]) -> List[Dict]:
    """Detect Fair Value Gaps (FVG) — 3-candle imbalance zones."""
    gaps = []
    n = len(candles)
    if n < 3:
        return gaps

    for i in range(1, n - 1):
        prev_h = candles[i - 1]['h']
        prev_l = candles[i - 1]['l']
        next_h = candles[i + 1]['h']
        next_l = candles[i + 1]['l']

        # Bullish FVG: gap between candle[i-1] high and candle[i+1] low
        if next_l > prev_h:
            gap_size = round(next_l - prev_h, 2)
            gaps.append({
                "type": "bullish",
                "top": round(next_l, 2),
                "bottom": round(prev_h, 2),
                "gap_size": gap_size,
                "index": i,
                "desc": f"Bullish FVG ₹{round(prev_h,2)}–₹{round(next_l,2)} — unfilled buy imbalance",
            })

        # Bearish FVG: gap between candle[i-1] low and candle[i+1] high
        if next_h < prev_l:
            gap_size = round(prev_l - next_h, 2)
            gaps.append({
                "type": "bearish",
                "top": round(prev_l, 2),
                "bottom": round(next_h, 2),
                "gap_size": gap_size,
                "index": i,
                "desc": f"Bearish FVG ₹{round(next_h,2)}–₹{round(prev_l,2)} — unfilled sell imbalance",
            })

    return gaps[-6:]  # return last 6 most recent


def detect_bos_choch(candles: List[Dict]) -> List[Dict]:
    """Detect Break of Structure (BOS) and Change of Character (CHoCH)."""
    events = []
    n = len(candles)
    if n < 10:
        return events

    closes = [c['c'] for c in candles]
    highs  = [c['h'] for c in candles]
    lows   = [c['l'] for c in candles]

    # Find swing highs and lows (simple: local max/min over 3 candles)
    swing_highs = [(i, highs[i]) for i in range(1, n - 1) if highs[i] > highs[i-1] and highs[i] > highs[i+1]]
    swing_lows  = [(i, lows[i])  for i in range(1, n - 1) if lows[i]  < lows[i-1]  and lows[i]  < lows[i+1]]

    if len(swing_highs) < 2 or len(swing_lows) < 2:
        return events

    last_sh_idx, last_sh_val = swing_highs[-1]
    prev_sh_idx, prev_sh_val = swing_highs[-2]
    last_sl_idx, last_sl_val = swing_lows[-1]
    prev_sl_idx, prev_sl_val = swing_lows[-2]

    current = closes[-1]

    # BOS Bullish: price breaks above last swing high (continuation of uptrend)
    if current > last_sh_val and last_sh_val > prev_sh_val:
        events.append({
            "type": "BOS",
            "direction": "bullish",
            "level": round(last_sh_val, 2),
            "desc": f"BOS Bullish — broke above swing high ₹{round(last_sh_val,2)}, uptrend continuation",
        })

    # BOS Bearish: price breaks below last swing low (continuation of downtrend)
    if current < last_sl_val and last_sl_val < prev_sl_val:
        events.append({
            "type": "BOS",
            "direction": "bearish",
            "level": round(last_sl_val, 2),
            "desc": f"BOS Bearish — broke below swing low ₹{round(last_sl_val,2)}, downtrend continuation",
        })

    # CHoCH Bullish: was making lower highs, now breaks above last swing high (trend flip)
    if current > last_sh_val and last_sh_val < prev_sh_val:
        events.append({
            "type": "CHoCH",
            "direction": "bullish",
            "level": round(last_sh_val, 2),
            "desc": f"CHoCH Bullish — broke above lower high ₹{round(last_sh_val,2)}, potential trend reversal to bullish",
        })

    # CHoCH Bearish: was making higher lows, now breaks below last swing low (trend flip)
    if current < last_sl_val and last_sl_val > prev_sl_val:
        events.append({
            "type": "CHoCH",
            "direction": "bearish",
            "level": round(last_sl_val, 2),
            "desc": f"CHoCH Bearish — broke below higher low ₹{round(last_sl_val,2)}, potential trend reversal to bearish",
        })

    return events
