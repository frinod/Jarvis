"""Backtesting Engine — replay historical candles, test strategies, measure performance."""
from __future__ import annotations
import time
import math
from typing import Dict, List, Any, Optional

# ── Strategy Definitions ──────────────────────────────────────

STRATEGIES = {
    "trend_following":   "Trend Following — EMA crossover + Supertrend",
    "mean_reversion":    "Mean Reversion — RSI oversold/overbought + BB bounce",
    "momentum":          "Momentum — RSI 50-70 + volume surge + EMA alignment",
    "breakout":          "Breakout — Donchian channel + BOS confirmation",
    "swing":             "Swing Trading — S/R levels + candlestick patterns",
    "ai_hybrid":         "AI Hybrid — full TA score + multi-indicator confluence",
}

PERIODS = {
    "1m":  30,   "3m":  90,   "6m": 180,
    "1y": 365,   "3y": 1095,  "5y": 1825,
}


# ── Strategy Signal Generators ────────────────────────────────

def _signal_trend_following(ta: Dict) -> str:
    ind = ta.get("indicators", {})
    e9  = ind.get("ema9")  or 0
    e21 = ind.get("ema21") or 0
    st  = ind.get("supertrend_direction")
    price = ta.get("current_price", 0)
    if e9 > e21 and st == "bullish" and price > e9:
        return "BUY"
    if e9 < e21 and st == "bearish" and price < e9:
        return "SELL"
    return "HOLD"


def _signal_mean_reversion(ta: Dict) -> str:
    ind = ta.get("indicators", {})
    rsi = ind.get("rsi") or 50
    price = ta.get("current_price", 0)
    bb_l  = ind.get("bb_lower") or 0
    bb_u  = ind.get("bb_upper") or 0
    if rsi < 30 and price <= bb_l:
        return "BUY"
    if rsi > 70 and price >= bb_u:
        return "SELL"
    return "HOLD"


def _signal_momentum(ta: Dict) -> str:
    ind = ta.get("indicators", {})
    rsi = ind.get("rsi") or 50
    vol = ind.get("volume_ratio") or 1
    trend = ta.get("trend", "")
    if 50 < rsi < 70 and vol > 1.3 and "up" in trend:
        return "BUY"
    if 30 < rsi < 50 and vol > 1.3 and "down" in trend:
        return "SELL"
    return "HOLD"


def _signal_breakout(ta: Dict) -> str:
    ind = ta.get("indicators", {})
    price  = ta.get("current_price", 0)
    dc_u   = ind.get("donchian_upper") or price
    dc_l   = ind.get("donchian_lower") or price
    bos    = ta.get("bos_choch", [])
    bull_bos = any(e["type"] == "BOS" and e["direction"] == "bullish" for e in bos)
    bear_bos = any(e["type"] == "BOS" and e["direction"] == "bearish" for e in bos)
    if price >= dc_u and bull_bos:
        return "BUY"
    if price <= dc_l and bear_bos:
        return "SELL"
    return "HOLD"


def _signal_swing(ta: Dict) -> str:
    sr    = ta.get("support_resistance", {})
    price = ta.get("current_price", 0)
    supports    = sr.get("support", [])
    resistances = sr.get("resistance", [])
    cp = ta.get("candlestick_patterns", [])
    bull_cp = any(p["type"] == "bullish" for p in cp)
    bear_cp = any(p["type"] == "bearish" for p in cp)
    near_sup = supports and abs(price - supports[0]) / price < 0.015
    near_res = resistances and abs(price - resistances[0]) / price < 0.015
    if near_sup and bull_cp:
        return "BUY"
    if near_res and bear_cp:
        return "SELL"
    return "HOLD"


def _signal_ai_hybrid(ta: Dict) -> str:
    return ta.get("overall_signal", "HOLD")


STRATEGY_FN = {
    "trend_following": _signal_trend_following,
    "mean_reversion":  _signal_mean_reversion,
    "momentum":        _signal_momentum,
    "breakout":        _signal_breakout,
    "swing":           _signal_swing,
    "ai_hybrid":       _signal_ai_hybrid,
}


# ── Backtest Engine ───────────────────────────────────────────

async def run_backtest(
    symbol: str,
    strategy: str,
    period: str = "1y",
    initial_capital: float = 100000.0,
    trade_mode: str = "delivery",
) -> Dict[str, Any]:
    """
    Run a full backtest for a symbol + strategy over a historical period.
    Returns equity curve, trade log, and performance metrics.
    """
    from app.market_data.service import fetch_candles
    from app.api.technical_analysis import compute_technical_analysis
    from app.api.paper_trading import calculate_charges, _max_drawdown, _sharpe_ratio, _volatility

    if strategy not in STRATEGY_FN:
        return {"error": f"Unknown strategy: {strategy}. Valid: {list(STRATEGIES.keys())}"}

    days_map = {"1m": 30, "3m": 90, "6m": 180, "1y": 365, "3y": 1095, "5y": 1825}
    days     = days_map.get(period, 365)
    full_sym = symbol if "." in symbol else f"{symbol}.NS"

    chart = await fetch_candles(full_sym, interval="1d", days=days)
    if chart.get("error") or len(chart.get("candles", [])) < 30:
        return {"error": "insufficient_historical_data", "symbol": symbol}

    candles = chart["candles"]
    signal_fn = STRATEGY_FN[strategy]

    # ── Replay candle by candle ───────────────────────────────
    cash     = initial_capital
    position = 0       # shares held
    avg_buy  = 0.0
    trades: List[Dict] = []
    equity_curve: List[Dict] = []
    total_charges = 0.0

    for i in range(30, len(candles)):
        window = candles[:i+1]
        ta = compute_technical_analysis(window)
        if ta.get("error"):
            continue

        # Signal generated at close of bar i — execute at OPEN of bar i+1
        # to avoid look-ahead bias (cannot trade at the close that generated the signal)
        if i + 1 >= len(candles):
            continue
        price  = candles[i + 1]["o"]
        date   = _ts_to_date(candles[i + 1]["t"])
        signal = signal_fn(ta)

        # Entry
        if signal == "BUY" and position == 0 and cash > price:
            qty = int(cash * 0.95 / price)   # use 95% of cash
            if qty < 1:
                continue
            charges = calculate_charges(price, qty, "BUY", trade_mode)
            cost = price * qty + charges
            if cost > cash:
                qty -= 1
                charges = calculate_charges(price, qty, "BUY", trade_mode)
                cost = price * qty + charges
            if qty < 1:
                continue
            cash -= cost
            position = qty
            avg_buy  = price
            total_charges += charges
            trades.append({
                "date": date, "type": "BUY", "price": price,
                "qty": qty, "charges": charges, "pnl": None,
            })

        # Exit
        elif signal == "SELL" and position > 0:
            charges  = calculate_charges(price, position, "SELL", trade_mode)
            proceeds = price * position - charges
            pnl      = round(proceeds - avg_buy * position, 2)
            cash    += proceeds
            total_charges += charges
            trades.append({
                "date": date, "type": "SELL", "price": price,
                "qty": position, "charges": charges, "pnl": pnl,
            })
            position = 0
            avg_buy  = 0.0

        # Record equity
        portfolio_value = cash + position * price
        equity_curve.append({"date": date, "value": round(portfolio_value, 2)})

    # Close any open position at last available price (next bar open after signal)
    if position > 0:
        last_price = candles[-1]["o"] if len(candles) > 0 else candles[-1]["c"]
        charges    = calculate_charges(last_price, position, "SELL", trade_mode)
        proceeds   = last_price * position - charges
        pnl        = round(proceeds - avg_buy * position, 2)
        cash      += proceeds
        total_charges += charges
        trades.append({
            "date": _ts_to_date(candles[-1]["t"]),
            "type": "SELL", "price": last_price,
            "qty": position, "charges": charges, "pnl": pnl,
            "note": "position_closed_at_end",
        })

    final_value = cash
    closed_trades = [t for t in trades if t["pnl"] is not None]
    wins   = [t for t in closed_trades if (t["pnl"] or 0) > 0]
    losses = [t for t in closed_trades if (t["pnl"] or 0) < 0]

    values = [e["value"] for e in equity_curve]
    total_return = round((final_value - initial_capital) / initial_capital * 100, 2)

    # Annualised return
    days = PERIODS.get(period, 365)
    ann_return = round(((final_value / initial_capital) ** (365 / max(days, 1)) - 1) * 100, 2) if days > 0 else 0

    return {
        "symbol": symbol,
        "strategy": strategy,
        "strategy_name": STRATEGIES[strategy],
        "period": period,
        "initial_capital": initial_capital,
        "final_value": round(final_value, 2),
        "total_return_pct": total_return,
        "annualised_return_pct": ann_return,
        "total_trades": len(trades),
        "winning_trades": len(wins),
        "losing_trades": len(losses),
        "win_rate": round(len(wins) / len(closed_trades) * 100, 1) if closed_trades else 0,
        "avg_profit": round(sum(t["pnl"] for t in wins) / len(wins), 2) if wins else 0,
        "avg_loss": round(sum(t["pnl"] for t in losses) / len(losses), 2) if losses else 0,
        "profit_factor": round(
            abs(sum(t["pnl"] for t in wins)) / abs(sum(t["pnl"] for t in losses)), 2
        ) if losses and wins else 0,
        "max_drawdown_pct": _max_drawdown(values),
        "sharpe_ratio": _sharpe_ratio(values),
        "volatility_pct": _volatility(values),
        "total_charges": round(total_charges, 2),
        "equity_curve": equity_curve[-252:],   # last 252 trading days for chart
        "trades": trades[-50:],                 # last 50 trades
        "candles_used": len(candles),
        "generated_at": time.time(),
    }


async def compare_strategies(
    symbol: str,
    period: str = "1y",
    initial_capital: float = 100000.0,
) -> Dict[str, Any]:
    """Run all strategies on the same symbol/period and compare."""
    import asyncio
    tasks = [
        run_backtest(symbol, s, period, initial_capital)
        for s in STRATEGIES
    ]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    comparison = []
    for strategy, result in zip(STRATEGIES.keys(), results):
        if isinstance(result, Exception) or result.get("error"):
            comparison.append({"strategy": strategy, "error": True})
        else:
            comparison.append({
                "strategy": strategy,
                "strategy_name": STRATEGIES[strategy],
                "total_return_pct": result["total_return_pct"],
                "annualised_return_pct": result["annualised_return_pct"],
                "win_rate": result["win_rate"],
                "sharpe_ratio": result["sharpe_ratio"],
                "max_drawdown_pct": result["max_drawdown_pct"],
                "total_trades": result["total_trades"],
                "profit_factor": result["profit_factor"],
            })
    comparison.sort(key=lambda x: x.get("total_return_pct", -999), reverse=True)
    return {
        "symbol": symbol,
        "period": period,
        "initial_capital": initial_capital,
        "comparison": comparison,
        "best_strategy": comparison[0]["strategy"] if comparison else None,
    }


# ── Helpers ───────────────────────────────────────────────────

def _ts_to_date(ts_ms: float) -> str:
    import datetime
    return datetime.datetime.utcfromtimestamp(ts_ms / 1000).strftime("%Y-%m-%d")
