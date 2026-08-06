"""JARVIS OS - API Routes"""
from __future__ import annotations
import asyncio
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, validator
from typing import Optional, List

router = APIRouter()


class ChatRequest(BaseModel):
    message: str
    user_id: str = "default"
    stream: bool = False
    selected_stock: Optional[str] = None  # currently open stock on market page


class ToolRequest(BaseModel):
    tool_name: str
    params: dict
    confirmed: bool = False


class ApprovalRequest(BaseModel):
    approval_id: str
    approved: bool


class AlertRequest(BaseModel):
    symbol: str
    above: float = None
    below: float = None


def get_orchestrator():
    from app.main import get_orchestrator as _get
    return _get()


@router.post("/chat")
async def chat(req: ChatRequest):
    orch = get_orchestrator()
    if req.stream:
        async def stream_gen():
            async for token in orch.process_stream(req.message, req.user_id, req.selected_stock):
                yield f"data: {token}\n\n"
            yield "data: [DONE]\n\n"
        return StreamingResponse(stream_gen(), media_type="text/event-stream")

    response = await orch.process_message(req.message, req.user_id, req.selected_stock)
    return {"response": response, "status": orch.get_status()}


@router.get("/status")
async def status():
    orch = get_orchestrator()
    info = orch.get_status()
    info["llm_provider"] = orch.llm.default_provider or "none (fallback mode)"
    info["llm_providers_available"] = list(orch.llm.providers.keys())
    return info


@router.get("/llm/providers")
async def list_llm_providers():
    orch = get_orchestrator()
    return {
        "active": orch.llm.default_provider or "none",
        "available": list(orch.llm.providers.keys()),
    }


@router.post("/llm/provider/{name}")
async def switch_llm_provider(name: str):
    orch = get_orchestrator()
    if name not in orch.llm.providers:
        return {"error": f"Provider '{name}' not available. Available: {list(orch.llm.providers.keys())}"}
    orch.llm.default_provider = name
    return {"active": name, "available": list(orch.llm.providers.keys())}


# ─── Stock Market Routes ──────────────────────────────────────

@router.get("/stocks")
async def get_stocks(universe: str = "nifty50"):
    from app.api.stock_fetcher import get_all_stocks
    return await get_all_stocks(universe)


@router.get("/stocks/chart/{symbol}")
async def get_stock_chart(symbol: str, interval: str = "5m", range: str = "1d"):
    from app.market_data.service import fetch_candles
    from app.api.stock_universe import NAME_MAP
    _rd = {"1d": 1, "2d": 2, "5d": 5, "10d": 10, "1mo": 30, "3mo": 90, "6mo": 180, "1y": 365, "2y": 730}
    full_symbol = symbol if "." in symbol else f"{symbol}.NS"
    result = await fetch_candles(full_symbol, interval=interval, days=_rd.get(range, 5))
    if result.get("error"):
        return {"error": result["error"]}
    return {"symbol": full_symbol, "name": NAME_MAP.get(full_symbol, symbol), "candles": result["candles"], "source": result.get("source")}


@router.get("/stocks/search/{query}")
async def search_stocks(query: str):
    from app.api.stock_universe import NAME_MAP, UNIVERSE_MAP
    from app.api.stock_fetcher import fetch_quote
    import httpx
    q = query.upper()
    results = []
    # Search known universe first
    for sym in UNIVERSE_MAP["all"]:
        name = NAME_MAP.get(sym, sym)
        if q in sym.upper() or q in name.upper():
            results.append({"symbol": sym.replace(".NS", ""), "name": name, "full_symbol": sym})
    # If no results, try direct Yahoo Finance symbol lookup
    if not results:
        for suffix in [".NS", ".BO"]:
            full_sym = q + suffix
            async with httpx.AsyncClient(timeout=5) as client:
                quote = await fetch_quote(full_sym, client)
            if quote:
                results.append({"symbol": q, "name": quote.get("name", q), "full_symbol": full_sym})
                break
    return {"results": results[:15]}


@router.get("/stocks/fundamentals/{symbol}")
async def get_fundamentals(symbol: str):
    from app.api.stock_data import fetch_fundamentals
    full_symbol = symbol if "." in symbol else f"{symbol}.NS"
    return await fetch_fundamentals(full_symbol)


@router.get("/stocks/financials/{symbol}")
async def get_financials(symbol: str):
    from app.api.stock_data import fetch_quarterly_financials
    full_symbol = symbol if "." in symbol else f"{symbol}.NS"
    return await fetch_quarterly_financials(full_symbol)


@router.get("/stocks/shareholding/{symbol}")
async def get_shareholding(symbol: str):
    from app.api.stock_data import fetch_shareholding
    full_symbol = symbol if "." in symbol else f"{symbol}.NS"
    return await fetch_shareholding(full_symbol)


@router.get("/stocks/peers/{symbol}")
async def get_peers(symbol: str):
    from app.api.stock_data import fetch_peers
    full_symbol = symbol if "." in symbol else f"{symbol}.NS"
    peers = await fetch_peers(full_symbol)
    return {"peers": peers}


@router.get("/stocks/analyze/{symbol}")
async def analyze_stock(symbol: str, interval: str = "15m", range: str = "5d"):
    """Full technical analysis + AI-powered Buy/Sell/Hold signal."""
    from app.market_data.service import fetch_candles
    from app.api.stock_data import fetch_fundamentals
    from app.api.stock_universe import NAME_MAP
    from app.api.technical_analysis import compute_technical_analysis
    from app.api.ai_analyst import generate_ai_analysis
    full_symbol = symbol if "." in symbol else f"{symbol}.NS"
    _rd = {"1d": 1, "5d": 5, "1mo": 30, "3mo": 90, "6mo": 180, "1y": 365}

    # Fallback chain: try requested interval first, then widen if too few candles
    fallbacks = [(interval, _rd.get(range, 5)), ("15m", 30), ("1h", 90), ("1d", 365)]
    chart = {"error": "no_data"}
    candles = []
    used_interval = interval
    for iv, days in fallbacks:
        chart = await fetch_candles(full_symbol, interval=iv, days=days)
        candles = chart.get("candles", [])
        if not chart.get("error") and len(candles) >= 26:
            used_interval = iv
            break

    if chart.get("error") or len(candles) < 26:
        return {"error": "insufficient_data", "symbol": symbol,
                "hint": "Yahoo Finance returned too few candles. Market may be closed or symbol invalid."}

    ta = compute_technical_analysis(candles)
    if ta.get("error"):
        return ta

    fundamentals = await fetch_fundamentals(full_symbol)
    name = NAME_MAP.get(full_symbol, symbol)

    orch = get_orchestrator()
    ai_result = await generate_ai_analysis(full_symbol, name, ta, fundamentals, orch.llm)

    return {
        "symbol": full_symbol,
        "name": name,
        "interval_used": used_interval,
        "candles_used": len(candles),
        "technical": ta,
        "ai_analysis": ai_result,
    }


@router.get("/stocks/forecast/{symbol}")
async def forecast_stock(symbol: str, horizon: int = 30):
    """XGBoost price direction forecast. horizon=15 or 30 minutes."""
    from app.api.forecaster import forecast
    return await forecast(symbol, horizon=horizon)


@router.get("/stocks/overlays/{symbol}")
async def get_chart_overlays(symbol: str, interval: str = "5m", range: str = "1d"):
    """Return full indicator arrays for chart overlay rendering."""
    from app.market_data.service import fetch_candles
    from app.api.technical_analysis import (
        _ema, _bollinger, _atr, _supertrend, _fibonacci, find_support_resistance
    )
    _rd = {"1d": 1, "2d": 2, "5d": 5, "10d": 10, "1mo": 30, "3mo": 90, "6mo": 180, "1y": 365}
    full_symbol = symbol if "." in symbol else f"{symbol}.NS"
    chart = await fetch_candles(full_symbol, interval=interval, days=_rd.get(range, 1))
    if chart.get("error"):
        return {"error": chart["error"]}
    candles = chart.get("candles", [])
    if len(candles) < 26:
        return {"error": "insufficient_data"}

    closes = [c["c"] for c in candles]
    highs  = [c["h"] for c in candles]
    lows   = [c["l"] for c in candles]

    bb     = _bollinger(closes)
    st     = _supertrend(highs, lows, closes)
    fib    = _fibonacci(highs, lows)
    sr     = find_support_resistance(candles)

    return {
        "ema9":        _ema(closes, 9),
        "ema21":       _ema(closes, 21),
        "ema50":       _ema(closes, 50),
        "ema200":      _ema(closes, 200),
        "bb_upper":    bb["upper"],
        "bb_mid":      bb["mid"],
        "bb_lower":    bb["lower"],
        "supertrend":  st["supertrend"],
        "st_direction": st["direction"],
        "fibonacci":   fib,
        "support":     sr.get("support", []),
        "resistance":  sr.get("resistance", []),
        "pivot":       sr.get("pivot"),
        "candle_count": len(candles),
    }


@router.get("/stocks/recommend")
async def recommend_stocks(budget: float, top_n: int = 5):
    """Budget-based stock recommendation — best Nifty 50 picks for your budget today."""
    from app.api.budget_advisor import recommend
    return await recommend(budget, top_n)


# ─── Market Intelligence Routes ───────────────────────────────

@router.get("/market/movers")
async def market_movers(universe: str = "nifty50"):
    from app.api.market_intelligence import get_market_movers
    return await get_market_movers(universe)


@router.get("/market/heatmap")
async def sector_heatmap(universe: str = "nifty50"):
    from app.api.market_intelligence import get_sector_heatmap
    return await get_sector_heatmap(universe)


@router.get("/market/discovery")
async def ai_discovery(category: str = "all", universe: str = "nifty50"):
    from app.api.market_intelligence import get_ai_discovery
    return await get_ai_discovery(category, universe)


@router.get("/market/depth/{symbol}")
async def market_depth(symbol: str):
    from app.api.market_intelligence import get_market_depth
    return await get_market_depth(symbol)


@router.get("/market/news")
async def market_news(symbol: str = None, limit: int = 30):
    from app.api.market_intelligence import get_market_news
    return await get_market_news(symbol, limit)


@router.get("/market/calendar")
async def economic_calendar():
    from app.api.market_intelligence import get_economic_calendar
    return get_economic_calendar()


@router.get("/market/intraday/{symbol}")
async def intraday_assistant(symbol: str, timeframe: str = "5m"):
    from app.api.market_intelligence import get_intraday_assistant
    return await get_intraday_assistant(symbol, timeframe)


@router.get("/market/regime")
async def market_regime(force: bool = False):
    """Current market regime — bull/bear/sideways/high-vol etc."""
    from app.api.market_regime import get_market_regime
    return await get_market_regime(force_refresh=force)


@router.get("/market/mtf/{symbol}")
async def mtf_analysis(symbol: str):
    """Multi-timeframe analysis — 1h/4h/1d confluence for a symbol."""
    from app.api.mtf_analysis import get_mtf_analysis
    return await get_mtf_analysis(symbol)


@router.get("/market/model-accuracy")
async def model_accuracy_summary():
    """Historical prediction accuracy across all tracked symbols."""
    from app.api.model_validator import get_all_accuracy_summary
    return get_all_accuracy_summary()


@router.get("/market/confluence/{symbol}")
async def multi_timeframe_confluence(symbol: str):
    """Multi-timeframe confluence panel — 5m/15m/30m/1h signals for same stock."""
    from app.api.market_intelligence import get_intraday_assistant
    import asyncio
    full_symbol = symbol if "." in symbol else f"{symbol}.NS"
    tfs = ["5m", "15m", "30m", "1h"]
    results = await asyncio.gather(
        *[get_intraday_assistant(full_symbol, tf) for tf in tfs],
        return_exceptions=True
    )
    confluence = []
    buy_count = sell_count = hold_count = 0
    for tf, r in zip(tfs, results):
        if isinstance(r, Exception) or (isinstance(r, dict) and r.get("error")):
            confluence.append({"timeframe": tf, "error": True})
        else:
            sig = r.get("signal", "HOLD")
            if sig in ("BUY", "STRONG_BUY"): buy_count += 1
            elif sig in ("SELL", "STRONG_SELL"): sell_count += 1
            else: hold_count += 1
            confluence.append({
                "timeframe": tf,
                "signal": sig,
                "confidence": r.get("confidence", 0),
                "trend": r.get("trend", "neutral"),
                "rsi": r.get("rsi"),
                "entry": r.get("entry"),
                "stop_loss": r.get("stop_loss"),
                "target1": r.get("target1"),
                "risk_reward": r.get("risk_reward"),
                "momentum": r.get("momentum", "neutral"),
                "volume_confirmation": r.get("volume_confirmation", False),
            })
    # Overall confluence verdict
    if buy_count >= 3:
        verdict = "STRONG_BUY"
    elif buy_count >= 2:
        verdict = "BUY"
    elif sell_count >= 3:
        verdict = "STRONG_SELL"
    elif sell_count >= 2:
        verdict = "SELL"
    else:
        verdict = "MIXED"
    return {
        "symbol": full_symbol,
        "confluence": confluence,
        "verdict": verdict,
        "buy_count": buy_count,
        "sell_count": sell_count,
        "hold_count": hold_count,
    }


@router.get("/market/top-picks")
async def top_picks(universe: str = "nifty50"):
    """Daily top 20 intraday + 10 swing + 10 long-term AI picks with hold duration."""
    from app.api.stock_fetcher import get_all_stocks
    from app.market_data.service import fetch_candles
    from app.api.technical_analysis import compute_technical_analysis
    from app.api.stock_universe import NAME_MAP
    import asyncio
    from datetime import datetime

    all_data = await get_all_stocks(universe)
    stocks = all_data.get("stocks", [])
    if not stocks:
        return {"error": "no_stocks"}

    # Fetch 15m charts for all stocks concurrently (batch of 30 max)
    batch = stocks[:60]  # limit to avoid rate limiting

    async def analyze_stock(stock):
        sym = stock["symbol"]
        full_sym = sym if "." in sym else f"{sym}.NS"
        try:
            chart = await fetch_candles(full_sym, interval="15m", days=5)
            candles = chart.get("candles", [])
            if len(candles) < 26:
                return None
            ta = compute_technical_analysis(candles)
            if ta.get("error"):
                return None
            return {"stock": stock, "ta": ta, "symbol": sym, "full_sym": full_sym}
        except Exception:
            return None

    # Run in batches of 20
    results = []
    for i in range(0, len(batch), 20):
        chunk = batch[i:i+20]
        chunk_results = await asyncio.gather(*[analyze_stock(s) for s in chunk], return_exceptions=True)
        results.extend([r for r in chunk_results if r and not isinstance(r, Exception)])

    def make_pick(r, category):
        ta = r["ta"]
        stock = r["stock"]
        price = ta["current_price"]
        atr = ta["indicators"].get("atr") or price * 0.01
        signal = ta["overall_signal"]
        confidence = ta["confidence"]
        score = ta["score"]
        rsi = ta["indicators"].get("rsi")
        vol_ratio = ta["indicators"].get("volume_ratio")

        # Hold duration based on category and ATR
        if category == "intraday":
            # Estimate hours based on ATR and price move needed
            move_needed = abs(ta["target1"] - price)
            avg_move_per_hour = atr * 0.5  # rough estimate
            hours = round(move_needed / avg_move_per_hour, 1) if avg_move_per_hour > 0 else 2.0
            hours = max(0.5, min(hours, 6.0))  # cap at 6h (market hours)
            hold_duration = f"~{hours}h intraday"
        elif category == "swing":
            days = round(abs(ta["target1"] - price) / (atr * 1.5), 0)
            days = max(2, min(int(days), 10))
            hold_duration = f"~{days} days"
            hours = days * 6.5
        else:  # longterm
            weeks = round(abs(ta["target2"] - price) / (atr * 3), 0)
            weeks = max(4, min(int(weeks), 52))
            hold_duration = f"~{weeks} weeks"
            hours = weeks * 5 * 6.5

        reasons = [s["reason"] for s in ta.get("signals", [])[:4]]
        grade = "A+" if score >= 4 else "A" if score >= 2.5 else "B" if score >= 1 else "C"

        return {
            "rank": 0,
            "symbol": r["symbol"],
            "name": NAME_MAP.get(r["full_sym"], r["symbol"]),
            "sector": stock.get("sector", "Other"),
            "price": round(price, 2),
            "change_pct": round(stock.get("change_pct", 0), 2),
            "signal": signal,
            "confidence": confidence,
            "score": round(abs(score) * 10, 1),
            "grade": grade,
            "trend": ta["trend"],
            "rsi": round(rsi, 1) if rsi else None,
            "volume_ratio": vol_ratio,
            "buy_price": round(price, 2),
            "stop_loss": ta["stop_loss"],
            "target1": ta["target1"],
            "target2": ta["target2"],
            "risk_reward": ta["risk_reward"],
            "hold_duration": hold_duration,
            "hold_hours": hours,
            "reasons": reasons,
            "category": category,
        }

    # Sort by score descending, filter by signal
    buy_results = sorted(
        [r for r in results if r["ta"]["overall_signal"] == "BUY"],
        key=lambda x: x["ta"]["score"], reverse=True
    )
    sell_results = sorted(
        [r for r in results if r["ta"]["overall_signal"] == "SELL"],
        key=lambda x: x["ta"]["score"]
    )

    # Intraday: top 20 (mix of buy/sell)
    intraday_pool = buy_results[:15] + sell_results[:5]
    intraday_pool.sort(key=lambda x: abs(x["ta"]["score"]), reverse=True)
    intraday = [make_pick(r, "intraday") for r in intraday_pool[:20]]
    for i, p in enumerate(intraday): p["rank"] = i + 1

    # Swing: top 10 buys with good R:R
    swing_pool = [r for r in buy_results if r["ta"]["risk_reward"] >= 1.5][:10]
    swing = [make_pick(r, "swing") for r in swing_pool]
    for i, p in enumerate(swing): p["rank"] = i + 1

    # Long-term: top 10 by trend strength
    lt_pool = [r for r in buy_results if "strong" in r["ta"]["trend"]][:10]
    if len(lt_pool) < 5:
        lt_pool = buy_results[:10]
    longterm = [make_pick(r, "longterm") for r in lt_pool[:10]]
    for i, p in enumerate(longterm): p["rank"] = i + 1

    bullish_count = len(buy_results)
    bearish_count = len(sell_results)
    mood = "bullish" if bullish_count > bearish_count * 1.5 else "bearish" if bearish_count > bullish_count * 1.5 else "neutral"

    return {
        "generated_at": datetime.now().isoformat(),
        "market_date": datetime.now().strftime("%d %b %Y"),
        "intraday": intraday,
        "swing": swing,
        "longterm": longterm,
        "summary": {
            "total_scanned": len(results),
            "bullish_count": bullish_count,
            "bearish_count": bearish_count,
            "market_mood": mood,
        },
    }


@router.get("/stocks/screener")
async def screener(
    min_pe: float = None, max_pe: float = None,
    min_roe: float = None, max_debt_equity: float = None,
    min_market_cap: float = None, min_profit_margin: float = None,
    sector: str = None, universe: str = "nifty50"
):
    """Screen stocks by fundamental criteria."""
    from app.api.stock_fetcher import get_all_stocks
    from app.api.stock_data import fetch_fundamentals

    all_data = await get_all_stocks(universe)
    stocks = all_data.get("stocks", [])

    # Filter by sector first (fast)
    if sector:
        stocks = [s for s in stocks if s.get("sector", "").lower() == sector.lower()]

    # Fetch fundamentals for filtered stocks concurrently
    symbols = [s["symbol"] + ".NS" for s in stocks]
    fund_tasks = [fetch_fundamentals(sym) for sym in symbols]
    fund_results = await asyncio.gather(*fund_tasks, return_exceptions=True)

    def to_float(v):
        try:
            if isinstance(v, str):
                v = v.replace("%", "").replace(",", "").replace("B", "e9").replace("T", "e12").replace("M", "e6").replace("K", "e3")
            return float(v)
        except Exception:
            return None

    results = []
    for stock, fund in zip(stocks, fund_results):
        if isinstance(fund, Exception) or not fund or fund.get("error"):
            continue
        pe = to_float(fund.get("pe_ratio"))
        roe = to_float(fund.get("roe"))
        de = to_float(fund.get("debt_to_equity"))
        mc = to_float(fund.get("market_cap"))
        pm = to_float(fund.get("profit_margin"))

        if min_pe is not None and (pe is None or pe < min_pe): continue
        if max_pe is not None and (pe is None or pe > max_pe): continue
        if min_roe is not None and (roe is None or roe * 100 < min_roe): continue
        if max_debt_equity is not None and (de is None or de > max_debt_equity): continue
        if min_market_cap is not None and (mc is None or mc < min_market_cap): continue
        if min_profit_margin is not None and (pm is None or pm * 100 < min_profit_margin): continue

        results.append({
            **stock,
            "pe_ratio": fund.get("pe_ratio"),
            "roe": fund.get("roe"),
            "debt_to_equity": fund.get("debt_to_equity"),
            "market_cap": fund.get("market_cap"),
            "profit_margin": fund.get("profit_margin"),
            "eps": fund.get("eps"),
            "dividend_yield": fund.get("dividend_yield"),
            "pb_ratio": fund.get("pb_ratio"),
        })

    return {"results": results, "count": len(results)}


# ─── Price Alert Routes ──────────────────────────────────────

@router.post("/alerts/set")
async def set_price_alert(req: AlertRequest):
    from app.api.alert_engine import set_alert
    sym = req.symbol if "." in req.symbol else f"{req.symbol}.NS"
    set_alert(sym, req.above, req.below)
    return {"status": "ok", "symbol": sym, "above": req.above, "below": req.below}


@router.get("/alerts/active")
async def get_active_alerts():
    from app.api.alert_engine import get_alerts
    return {"alerts": get_alerts()}


@router.get("/alerts/triggered")
async def get_triggered_alerts():
    from app.api.alert_engine import get_triggered
    return {"triggered": get_triggered()}


@router.delete("/alerts/triggered")
async def clear_triggered_alerts():
    from app.api.alert_engine import clear_triggered
    clear_triggered()
    return {"status": "cleared"}


@router.websocket("/ws/stocks")
async def stocks_live_stream(websocket: WebSocket):
    """Push real-time stock tick data. Uses Angel One if credentials set, else Yahoo Finance polling."""
    await websocket.accept()
    from app.api.stock_fetcher import get_all_stocks
    from app.api.angel_feed import get_feed, get_session

    # Send initial snapshot immediately
    try:
        initial = await get_all_stocks("nifty50")
        await websocket.send_json({**initial, "source": "yahoo_snapshot"})
    except Exception:
        pass

    # Try Angel One real-time feed
    session = get_session()
    feed = get_feed()

    if session and feed._running:
        # Angel One path — push on every new tick
        from app.api.stock_universe import NAME_MAP, SECTOR_MAP
        try:
            while True:
                ticks = feed.get_all_ticks()
                if ticks and feed._new_tick:
                    feed._new_tick = False
                    stocks = []
                    for symbol, tick in ticks.items():
                        full_sym = f"{symbol}.NS"
                        stocks.append({
                            **tick,
                            "full_symbol": full_sym,
                            "name": NAME_MAP.get(full_sym, symbol),
                            "sector": SECTOR_MAP.get(full_sym, "Other"),
                            "currency": "INR",
                            "market_state": "REGULAR",
                        })
                    stocks.sort(key=lambda x: x.get("change_pct", 0), reverse=True)
                    await websocket.send_json({"stocks": stocks, "source": "angel_one"})
                await asyncio.sleep(0.1)
        except WebSocketDisconnect:
            pass
        except Exception:
            pass
    else:
        # Yahoo Finance fallback — poll every 15s
        try:
            while True:
                await asyncio.sleep(15)
                data = await get_all_stocks("nifty50")
                await websocket.send_json({**data, "source": "yahoo_poll"})
        except WebSocketDisconnect:
            pass
        except Exception:
            pass


# ─── Paper Trading Routes ───────────────────────────────────

class TradeRequest(BaseModel):
    symbol: str
    trade_type: str          # BUY | SELL
    qty: int
    trade_mode: str = "delivery"
    source: str = "user"
    notes: str = ""

    @validator('symbol')
    def symbol_must_be_alphanumeric(cls, v):
        import re
        if not re.match(r'^[A-Za-z0-9&_\-\.]{1,20}$', v):
            raise ValueError('symbol must be 1-20 alphanumeric characters')
        return v.upper()

    @validator('trade_type')
    def trade_type_must_be_valid(cls, v):
        if v.upper() not in ('BUY', 'SELL'):
            raise ValueError('trade_type must be BUY or SELL')
        return v.upper()

    @validator('qty')
    def qty_must_be_positive(cls, v):
        if v < 1 or v > 10_000:
            raise ValueError('qty must be between 1 and 10000')
        return v


class CreatePortfolioRequest(BaseModel):
    name: str
    balance: float = 100000.0
    owner: str = "user"


@router.post("/paper/portfolio")
async def create_paper_portfolio(req: CreatePortfolioRequest):
    from app.api.paper_trading import create_portfolio
    p = create_portfolio(req.name, req.balance, req.owner)
    return p.to_dict()


@router.get("/paper/portfolios")
async def list_paper_portfolios():
    from app.api.paper_trading import list_portfolios
    return {"portfolios": list_portfolios()}


@router.get("/paper/portfolio/{pid}")
async def get_paper_portfolio(pid: str):
    from app.api.paper_trading import get_portfolio, update_positions
    return await update_positions(pid)


@router.delete("/paper/portfolio/{pid}")
async def delete_paper_portfolio(pid: str):
    from app.api.paper_trading import delete_portfolio
    ok = delete_portfolio(pid)
    return {"status": "deleted" if ok else "not_found"}


@router.post("/paper/trade/{pid}")
async def paper_trade(pid: str, req: TradeRequest):
    from app.api.paper_trading import execute_trade
    return await execute_trade(
        portfolio_id=pid,
        symbol=req.symbol,
        trade_type=req.trade_type,
        qty=req.qty,
        trade_mode=req.trade_mode,
        source=req.source,
        notes=req.notes,
    )


class AITradeRequest(BaseModel):
    symbol: str
    budget_per_trade: float = 10000.0


class AITradeConfirmRequest(BaseModel):
    confirmation_id: str
    approved: bool


@router.post("/paper/ai-trade/{pid}")
async def paper_ai_trade(pid: str, req: AITradeRequest):
    """Analyse stock and return a trade proposal. Does NOT execute — requires confirmation."""
    from app.api.paper_trading import ai_auto_trade
    return await ai_auto_trade(pid, req.symbol, req.budget_per_trade)


@router.post("/paper/ai-trade/confirm")
async def paper_ai_trade_confirm(req: AITradeConfirmRequest):
    """Execute or cancel a pending AI trade proposal after manual confirmation."""
    from app.api.paper_trading import confirm_ai_trade
    return await confirm_ai_trade(req.confirmation_id, req.approved)


@router.get("/paper/performance/{pid}")
async def paper_performance(pid: str):
    from app.api.paper_trading import get_performance_stats
    return get_performance_stats(pid)


@router.get("/paper/compare")
async def paper_compare(ids: Optional[List[str]] = Query(default=None), pids: Optional[str] = None):
    from app.api.paper_trading import compare_portfolios
    id_list = ids if ids else (pids.split(",") if pids else [])
    return compare_portfolios(id_list)


@router.get("/paper/ai-evaluation")
async def ai_self_evaluation():
    from app.api.paper_trading import get_ai_self_evaluation
    return get_ai_self_evaluation()


@router.get("/paper/trades/{pid}")
async def get_trade_history(pid: str):
    from app.api.paper_trading import get_portfolio
    p = get_portfolio(pid)
    if not p:
        return {"error": "not_found"}
    return {"trades": [t.to_dict() for t in reversed(p.trades)]}


# ─── Auto-Trader Test Routes ────────────────────────────────

class AutoTestRequest(BaseModel):
    portfolio_id: Optional[str] = None


@router.post("/paper/autotest/run")
async def autotest_run(req: AutoTestRequest):
    """Launch fully autonomous paper-trade test (price≤500, min 3 stocks, 15m hold, 60s poll)."""
    from app.api.auto_trader import run_autotest
    asyncio.create_task(run_autotest(req.portfolio_id))
    return {"status": "started", "message": "AutoTest v2 launched. Poll /api/paper/autotest/status for live updates."}


@router.get("/paper/autotest/status")
async def autotest_status():
    """Get live status, log tail, trade results, P&L summary and patches applied."""
    from app.api.auto_trader import get_autotest_status
    return get_autotest_status()


@router.post("/paper/autotest/reset")
async def autotest_reset():
    """Force-kill any stuck autotest session immediately."""
    from app.api.auto_trader import force_reset
    force_reset()
    return {"status": "reset", "message": "AutoTest session cleared."}


@router.post("/paper/autotest/patch")
async def autotest_patch(updates: dict):
    """Live-patch _cfg thresholds without restarting backend."""
    from app.api.auto_trader import apply_cfg_patch
    return apply_cfg_patch(updates)


@router.post("/paper/autotest/loop/start")
async def autotest_loop_start(req: AutoTestRequest):
    """Start the autonomous self-healing loop: trade -> analyse -> patch -> repeat."""
    from app.api.auto_trader import run_autonomous_loop, get_loop_status
    status = get_loop_status()
    if status["running"]:
        return {"status": "already_running", "iteration": status["iteration"]}
    asyncio.create_task(run_autonomous_loop(req.portfolio_id))
    return {"status": "started", "message": "Autonomous loop launched. Poll /api/paper/autotest/loop/status"}


@router.get("/paper/autotest/loop/status")
async def autotest_loop_status():
    """Live status of the autonomous loop: iteration, history, patches, log."""
    from app.api.auto_trader import get_loop_status
    return get_loop_status()


@router.post("/paper/autotest/loop/stop")
async def autotest_loop_stop():
    """Signal the autonomous loop to stop after current session."""
    from app.api.auto_trader import stop_loop
    stop_loop()
    return {"status": "stop_requested", "message": "Loop will stop after current session completes."}


# ─── Backtesting Routes ───────────────────────────────────────

@router.get("/backtest/run")
async def backtest_run(
    symbol: str,
    strategy: str = "ai_hybrid",
    period: str = "1y",
    capital: float = 100000.0,
):
    from app.api.backtesting import run_backtest
    return await run_backtest(symbol, strategy, period, capital)


@router.get("/backtest/compare")
async def backtest_compare(symbol: str, period: str = "1y", capital: float = 100000.0):
    from app.api.backtesting import compare_strategies
    return await compare_strategies(symbol, period, capital)


@router.get("/backtest/strategies")
async def list_strategies():
    from app.api.backtesting import STRATEGIES
    return {"strategies": STRATEGIES}


# ─── Other Routes ─────────────────────────────────────────────

@router.post("/tools/execute")
async def execute_tool(req: ToolRequest):
    orch = get_orchestrator()
    return await orch.execute_tool(req.tool_name, req.params, req.confirmed)


@router.get("/tools")
async def list_tools():
    orch = get_orchestrator()
    return {"tools": orch.tools.list_tools()}


@router.post("/approval")
async def handle_approval(req: ApprovalRequest):
    orch = get_orchestrator()
    if req.approved:
        success = orch.security.approve(req.approval_id)
    else:
        success = orch.security.deny(req.approval_id)
    return {"success": success}


@router.get("/approvals/pending")
async def pending_approvals():
    orch = get_orchestrator()
    return {"pending": orch.security.get_pending_approvals()}


@router.get("/memory/summary")
async def memory_summary():
    orch = get_orchestrator()
    return orch.memory.get_short_term_summary()


@router.get("/agents")
async def list_agents():
    orch = get_orchestrator()
    return {"agents": orch.agents.get_available_agents()}


@router.websocket("/ws/chat")
async def websocket_chat(websocket: WebSocket):
    await websocket.accept()
    orch = get_orchestrator()
    try:
        while True:
            try:
                data = await websocket.receive_json()
            except WebSocketDisconnect:
                break

            message = data.get("message", "")
            user_id = data.get("user_id", "default")
            selected_stock = data.get("selected_stock", None)

            try:
                async for token in orch.process_stream(message, user_id, selected_stock):
                    await websocket.send_json({"type": "token", "content": token})

                status = orch.get_status()
                from app.api.paper_trading import _pending_trade_confirmations
                trade_proposal = None
                if _pending_trade_confirmations:
                    last_key = list(_pending_trade_confirmations.keys())[-1]
                    trade_proposal = _pending_trade_confirmations[last_key]
                status["trade_proposal"] = trade_proposal
                await websocket.send_json({"type": "done", "status": status})
            except Exception as e:
                print(f"[JARVIS] WS stream error: {e}")
                try:
                    await websocket.send_json({"type": "done", "status": {}})
                except Exception:
                    break
    except WebSocketDisconnect:
        pass
    except Exception:
        pass
