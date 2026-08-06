"""Budget Advisor — recommends best Nifty 50 stocks to buy based on budget + TA scoring."""
from __future__ import annotations
from typing import Dict, List, Any, Optional


# ── Task 3a: Stock Scoring ────────────────────────────────────

def score_stock(ta: Dict[str, Any], price: float) -> Dict[str, Any]:
    """
    Score a stock 0–100 for buy worthiness based on full TA.
    Higher = stronger buy setup right now.
    """
    score = 0.0
    reasons = []
    ind = ta.get("indicators", {})

    def safe(val, default=0.0):
        try:
            return float(val) if val is not None else default
        except Exception:
            return default

    # ── Trend alignment (max 20 pts) ──────────────────────────
    trend = ta.get("trend", "neutral")
    if trend == "strong_uptrend":
        score += 20
        reasons.append("Strong uptrend (price > EMA50 > EMA200)")
    elif trend == "uptrend":
        score += 12
        reasons.append("Uptrend (price > EMA50)")
    elif trend == "neutral":
        score += 5
    elif trend == "downtrend":
        score -= 5
        reasons.append("Downtrend — caution")
    elif trend == "strong_downtrend":
        score -= 15
        reasons.append("Strong downtrend — avoid")

    # ── Supertrend (max 10 pts) ───────────────────────────────
    st_dir = ind.get("supertrend_direction")
    if st_dir == "bullish":
        score += 10
        reasons.append("Supertrend bullish")
    elif st_dir == "bearish":
        score -= 8

    # ── RSI (max 10 pts) ──────────────────────────────────────
    rsi = safe(ind.get("rsi"), 50)
    if 40 <= rsi <= 60:
        score += 10
        reasons.append(f"RSI {rsi:.0f} — healthy neutral zone")
    elif 30 <= rsi < 40:
        score += 8
        reasons.append(f"RSI {rsi:.0f} — approaching oversold, good entry")
    elif rsi < 30:
        score += 6
        reasons.append(f"RSI {rsi:.0f} — oversold, bounce potential")
    elif 60 < rsi <= 70:
        score += 4
    elif rsi > 70:
        score -= 5
        reasons.append(f"RSI {rsi:.0f} — overbought, risky entry")

    # ── MACD (max 10 pts) ─────────────────────────────────────
    macd = safe(ind.get("macd"))
    macd_hist = safe(ind.get("macd_histogram"))
    if macd > 0 and macd_hist > 0:
        score += 10
        reasons.append("MACD bullish crossover with positive histogram")
    elif macd > 0:
        score += 5
    elif macd < 0 and macd_hist < 0:
        score -= 8

    # ── EMA alignment (max 10 pts) ────────────────────────────
    e9  = safe(ind.get("ema9"),  price)
    e21 = safe(ind.get("ema21"), price)
    e50 = safe(ind.get("ema50"), price)
    if price > e9 > e21 > e50:
        score += 10
        reasons.append("Price > EMA9 > EMA21 > EMA50 — perfect bull stack")
    elif price > e9 > e21:
        score += 6
        reasons.append("Price > EMA9 > EMA21 — bullish EMA stack")
    elif price < e9 < e21:
        score -= 6

    # ── Ichimoku (max 8 pts) ──────────────────────────────────
    tenkan = safe(ind.get("ichimoku_tenkan"), price)
    kijun  = safe(ind.get("ichimoku_kijun"),  price)
    if price > tenkan > kijun:
        score += 8
        reasons.append("Price above Ichimoku cloud — bullish")
    elif tenkan > kijun:
        score += 4
    elif price < tenkan < kijun:
        score -= 6

    # ── Parabolic SAR (max 6 pts) ─────────────────────────────
    sar = safe(ind.get("parabolic_sar"), price)
    if price > sar:
        score += 6
        reasons.append(f"Price above SAR {sar:.2f} — uptrend confirmed")
    else:
        score -= 4

    # ── Bollinger Band position (max 6 pts) ───────────────────
    bb_u = safe(ind.get("bb_upper"), price * 1.02)
    bb_l = safe(ind.get("bb_lower"), price * 0.98)
    bb_m = safe(ind.get("bb_mid"),   price)
    if bb_u != bb_l:
        bb_pos = (price - bb_l) / (bb_u - bb_l)
        if 0.4 <= bb_pos <= 0.7:
            score += 6
            reasons.append("Price in healthy BB mid zone")
        elif bb_pos < 0.2:
            score += 4
            reasons.append("Price near lower BB — bounce zone")
        elif bb_pos > 0.9:
            score -= 4

    # ── Volume (max 6 pts) ────────────────────────────────────
    vol_ratio = safe(ind.get("volume_ratio"), 1.0)
    if vol_ratio >= 1.5:
        score += 6
        reasons.append(f"Volume {vol_ratio:.1f}x avg — strong conviction")
    elif vol_ratio >= 1.2:
        score += 3

    # ── Smart money: BOS/CHoCH (max 8 pts) ───────────────────
    bos_choch = ta.get("bos_choch", [])
    for event in bos_choch:
        if event["type"] == "CHoCH" and event["direction"] == "bullish":
            score += 8
            reasons.append("CHoCH bullish — trend reversal signal")
            break
        elif event["type"] == "BOS" and event["direction"] == "bullish":
            score += 5
            reasons.append("BOS bullish — trend continuation")
            break
        elif event["direction"] == "bearish":
            score -= 5

    # ── Order block proximity (max 6 pts) ─────────────────────
    obs = ta.get("order_blocks", [])
    for ob in obs:
        if ob["type"] == "bullish" and ob["bottom"] <= price <= ob["top"] * 1.01:
            score += 6
            reasons.append(f"Price in bullish OB zone ₹{ob['bottom']}–₹{ob['top']}")
            break

    # ── Candlestick patterns (max 6 pts) ──────────────────────
    cp = ta.get("candlestick_patterns", [])
    bull_patterns = [p for p in cp if p["type"] == "bullish"]
    bear_patterns = [p for p in cp if p["type"] == "bearish"]
    if bull_patterns:
        score += min(len(bull_patterns) * 3, 6)
        reasons.append(f"Bullish candle: {bull_patterns[-1]['pattern']}")
    if bear_patterns:
        score -= min(len(bear_patterns) * 3, 6)

    # ── Clamp to 0–100 ────────────────────────────────────────
    score = round(max(0.0, min(100.0, score)), 1)

    # ── Grade ─────────────────────────────────────────────────
    if score >= 75:
        grade = "A+"
    elif score >= 60:
        grade = "A"
    elif score >= 45:
        grade = "B"
    elif score >= 30:
        grade = "C"
    else:
        grade = "D"

    return {
        "score": score,
        "grade": grade,
        "top_reasons": reasons[:4],   # top 4 reasons
    }


# ── Task 3b: Main Recommendation Entry Point ─────────────────

async def recommend(budget: float, top_n: int = 5) -> Dict[str, Any]:
    """
    Recommend best Nifty 50 stocks to buy today based on budget + TA score.
    Returns top_n picks with quantity, cost, reasoning.
    """
    from app.market_data.service import fetch_candles
    from app.api.stock_universe import NAME_MAP, SECTOR_MAP, NIFTY50_SYMBOLS
    from app.api.technical_analysis import compute_technical_analysis
    import asyncio

    if budget <= 0:
        return {"error": "Budget must be greater than 0"}

    scored = []

    async def _analyze_one(full_sym: str):
        try:
            chart = await fetch_candles(full_sym, interval="5m", days=1)
            if chart.get("error") or len(chart.get("candles", [])) < 10:
                return
            candles = chart["candles"]
            price   = candles[-1]["c"]

            # Skip if price exceeds budget (can't buy even 1 share)
            if price > budget:
                return

            ta = compute_technical_analysis(candles)
            if ta.get("error"):
                return

            result = score_stock(ta, price)

            # Skip D-grade stocks
            if result["grade"] == "D":
                return

            sym_clean = full_sym.replace(".NS", "")
            qty       = int(budget // price)
            cost      = round(qty * price, 2)
            leftover  = round(budget - cost, 2)

            scored.append({
                "symbol":   sym_clean,
                "name":     NAME_MAP.get(full_sym, sym_clean),
                "sector":   SECTOR_MAP.get(full_sym, "Other"),
                "price":    round(price, 2),
                "score":    result["score"],
                "grade":    result["grade"],
                "qty":      qty,
                "cost":     cost,
                "leftover": leftover,
                "reasons":  result["top_reasons"],
                "signal":   ta.get("overall_signal"),
                "trend":    ta.get("trend"),
                "confidence": ta.get("confidence"),
                "stop_loss":  ta.get("stop_loss"),
                "target1":    ta.get("target1"),
                "target2":    ta.get("target2"),
                "risk_reward": ta.get("risk_reward"),
            })
        except Exception:
            pass

    # Run all 50 stocks concurrently
    tasks = [_analyze_one(sym) for sym in NIFTY50_SYMBOLS]
    await asyncio.gather(*tasks)

    if not scored:
        return {
            "budget": budget,
            "recommendations": [],
            "message": "No stocks found within budget or all signals are weak today.",
        }

    # Sort by score descending
    scored.sort(key=lambda x: x["score"], reverse=True)
    top = scored[:top_n]

    # Build portfolio summary
    total_invested = sum(s["cost"] for s in top)
    avg_score      = round(sum(s["score"] for s in top) / len(top), 1)

    # Split budget equally suggestion
    per_stock_budget = round(budget / len(top), 2)
    for s in top:
        s["suggested_qty_equal_split"] = int(per_stock_budget // s["price"])

    return {
        "budget": budget,
        "stocks_analyzed": len(NIFTY50_SYMBOLS),
        "stocks_affordable": len(scored),
        "recommendations": top,
        "summary": {
            "top_pick": top[0]["name"] if top else None,
            "top_pick_symbol": top[0]["symbol"] if top else None,
            "avg_score": avg_score,
            "total_if_all_bought": total_invested,
            "leftover_if_all_bought": round(budget - total_invested, 2),
            "best_grade": top[0]["grade"] if top else None,
        },
    }
