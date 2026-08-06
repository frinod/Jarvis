"""Market Intelligence — movers, heatmap, AI discovery, news, calendar, depth."""
from __future__ import annotations
import asyncio
import time
from typing import Dict, List, Any, Optional
from app.api.stock_universe import NIFTY50_SYMBOLS, NAME_MAP, SECTOR_MAP, UNIVERSE_MAP

# ── Simple in-memory cache ────────────────────────────────────
_cache: Dict[str, Any] = {}
_cache_ts: Dict[str, float] = {}


def _cached(key: str, ttl: int = 60) -> Optional[Any]:
    if key in _cache and (time.time() - _cache_ts.get(key, 0)) < ttl:
        return _cache[key]
    return None


def _set_cache(key: str, value: Any):
    _cache[key] = value
    _cache_ts[key] = time.time()


# ── Market Movers ─────────────────────────────────────────────

async def get_market_movers(universe: str = "nifty50") -> Dict[str, Any]:
    """Top gainers, losers, most active, volume leaders."""
    cached = _cached(f"movers_{universe}", ttl=30)
    if cached:
        return cached

    from app.api.stock_fetcher import get_all_stocks
    data = await get_all_stocks(universe)
    stocks = data.get("stocks", [])

    gainers  = sorted(stocks, key=lambda x: x.get("change_pct", 0), reverse=True)[:10]
    losers   = sorted(stocks, key=lambda x: x.get("change_pct", 0))[:10]
    active   = sorted(stocks, key=lambda x: x.get("volume", 0), reverse=True)[:10]

    # Volume leaders: volume * price = turnover
    for s in stocks:
        s["turnover"] = round(s.get("volume", 0) * s.get("price", 0) / 1e7, 2)  # in Cr
    volume_leaders = sorted(stocks, key=lambda x: x.get("turnover", 0), reverse=True)[:10]

    result = {
        "gainers": gainers,
        "losers": losers,
        "most_active": active,
        "volume_leaders": volume_leaders,
        "total_stocks": len(stocks),
        "advancing": sum(1 for s in stocks if s.get("change_pct", 0) > 0),
        "declining": sum(1 for s in stocks if s.get("change_pct", 0) < 0),
        "unchanged": sum(1 for s in stocks if s.get("change_pct", 0) == 0),
    }
    _set_cache(f"movers_{universe}", result)
    return result


# ── Sector Heatmap ────────────────────────────────────────────

async def get_sector_heatmap(universe: str = "nifty50") -> Dict[str, Any]:
    """Aggregate sector performance for heatmap visualization."""
    cached = _cached(f"heatmap_{universe}", ttl=60)
    if cached:
        return cached

    from app.api.stock_fetcher import get_all_stocks
    data = await get_all_stocks(universe)
    stocks = data.get("stocks", [])

    sector_data: Dict[str, Dict] = {}
    for s in stocks:
        sec = s.get("sector", "Other")
        if sec not in sector_data:
            sector_data[sec] = {"stocks": [], "total_change": 0, "count": 0}
        sector_data[sec]["stocks"].append(s)
        sector_data[sec]["total_change"] += s.get("change_pct", 0)
        sector_data[sec]["count"] += 1

    heatmap = []
    for sec, d in sector_data.items():
        avg_change = round(d["total_change"] / d["count"], 2) if d["count"] else 0
        top_stock = max(d["stocks"], key=lambda x: abs(x.get("change_pct", 0)), default=None)
        heatmap.append({
            "sector": sec,
            "avg_change_pct": avg_change,
            "stock_count": d["count"],
            "advancing": sum(1 for s in d["stocks"] if s.get("change_pct", 0) > 0),
            "declining": sum(1 for s in d["stocks"] if s.get("change_pct", 0) < 0),
            "top_mover": top_stock["symbol"] if top_stock else None,
            "top_mover_pct": top_stock.get("change_pct", 0) if top_stock else 0,
            "stocks": [{"symbol": s["symbol"], "change_pct": s.get("change_pct", 0), "price": s.get("price", 0)} for s in d["stocks"]],
        })

    heatmap.sort(key=lambda x: x["avg_change_pct"], reverse=True)
    result = {"sectors": heatmap, "universe": universe}
    _set_cache(f"heatmap_{universe}", result)
    return result


# ── AI Stock Discovery ────────────────────────────────────────

async def get_ai_discovery(category: str = "all", universe: str = "nifty50") -> Dict[str, Any]:
    cache_key = f"discovery_{category}_{universe}"
    cached = _cached(cache_key, ttl=300)
    if cached:
        return cached

    from app.api.stock_fetcher import get_all_stocks
    from app.market_data.service import fetch_candles as _fetch_candles
    from app.api.technical_analysis import compute_technical_analysis
    from app.api.budget_advisor import score_stock
    from app.api.data_quality import clean_candles
    from app.api.market_regime import get_market_regime, apply_regime_filter

    data   = await get_all_stocks(universe)
    stocks = data.get("stocks", [])
    regime = await get_market_regime()

    async def _analyze(stock: Dict) -> Optional[Dict]:
        try:
            sym   = stock["symbol"] + ".NS"
            chart = await _fetch_candles(sym, interval="15m", days=5)
            if chart.get("error") or len(chart.get("candles", [])) < 26:
                return None

            candles, quality = clean_candles(chart["candles"])
            if len(candles) < 26 or quality.get("quality_score", 0) < 40:
                return None

            ta = compute_technical_analysis(candles)
            if ta.get("error"):
                return None

            price    = stock.get("price", candles[-1]["c"])
            base     = score_stock(ta, price)
            ind      = ta.get("indicators", {})
            cat_score = base["score"]
            cat_reason = base["top_reasons"][:2]

            # Apply regime filter to raw signal
            raw_signal = ta.get("overall_signal", "HOLD")
            regime_result = apply_regime_filter(raw_signal, regime)
            filtered_signal = regime_result["signal"]

            # Skip stocks where regime suppressed the signal
            if regime_result.get("regime_adjusted") and filtered_signal == "HOLD":
                cat_score = max(0, cat_score - 20)  # penalise, don’t remove entirely

            if category == "intraday":
                vol_ratio = ind.get("volume_ratio") or 1
                rsi       = ind.get("rsi") or 50
                atr       = ind.get("atr") or 0
                atr_pct   = (atr / price * 100) if price else 0
                if vol_ratio > 1.5:       cat_score += 10
                if 40 < rsi < 65:         cat_score += 8
                if 0.5 < atr_pct < 2.5:  cat_score += 7

            elif category == "swing":
                sr = ta.get("support_resistance", {})
                supports = sr.get("support", [])
                if supports and abs(price - supports[0]) / price < 0.02:
                    cat_score += 15
                    cat_reason.append("Price near key support — swing entry")

            elif category == "momentum":
                rsi   = ind.get("rsi") or 50
                if 50 < rsi < 70 and ta.get("trend") in ("uptrend", "strong_uptrend"):
                    cat_score += 20
                    cat_reason.append("Momentum: RSI 50-70 in uptrend")

            elif category == "breakout":
                dc_upper = ind.get("donchian_upper") or price
                if abs(price - dc_upper) / price < 0.01:
                    cat_score += 20
                    cat_reason.append("Near 20-period high — breakout candidate")
                bos = [e for e in ta.get("bos_choch", []) if e["type"] == "BOS" and e["direction"] == "bullish"]
                if bos:
                    cat_score += 10
                    cat_reason.append("BOS bullish confirmed")
                # Penalise breakouts in sideways/high-vol regime
                if regime.get("avoid_breakouts"):
                    cat_score = max(0, cat_score - 15)
                    cat_reason.append(f"Caution: breakouts unreliable in {regime.get('regime')} regime")

            elif category == "value":
                rsi = ind.get("rsi") or 50
                if rsi < 40:
                    cat_score += 15
                    cat_reason.append(f"RSI {rsi:.0f} — oversold value zone")

            elif category == "growth":
                if ta.get("trend") == "strong_uptrend":
                    cat_score += 20
                    cat_reason.append("Strong uptrend — growth momentum")

            elif category == "dividend":
                atr     = ind.get("atr") or 0
                atr_pct = (atr / price * 100) if price else 0
                if atr_pct < 1.5:
                    cat_score += 15
                    cat_reason.append("Low volatility — stable dividend candidate")

            elif category == "longterm":
                e200 = ind.get("ema200") or price
                if price > e200:
                    cat_score += 20
                    cat_reason.append("Price above EMA200 — long-term uptrend")

            cat_score = round(min(100, max(0, cat_score)), 1)

            return {
                "symbol":       stock["symbol"],
                "name":         stock.get("name", stock["symbol"]),
                "sector":       stock.get("sector", "Other"),
                "price":        price,
                "change_pct":   stock.get("change_pct", 0),
                "score":        cat_score,
                "grade":        base["grade"],
                "signal":       filtered_signal,
                "trend":        ta.get("trend"),
                "confidence":   ta.get("confidence"),
                "stop_loss":    ta.get("stop_loss"),
                "target1":      ta.get("target1"),
                "target2":      ta.get("target2"),
                "risk_reward":  ta.get("risk_reward"),
                "reasons":      cat_reason[:3],
                "volume_ratio": ind.get("volume_ratio"),
                "rsi":          ind.get("rsi"),
                "atr":          ind.get("atr"),
                "category":     category,
                "data_quality": quality.get("quality_score"),
                "regime_note":  regime_result.get("warning"),
            }
        except Exception:
            return None

    results = []
    batch_size = 10
    for i in range(0, len(stocks), batch_size):
        batch = stocks[i:i + batch_size]
        batch_results = await asyncio.gather(*[_analyze(s) for s in batch], return_exceptions=True)
        results.extend([r for r in batch_results if r and not isinstance(r, Exception)])
        await asyncio.sleep(0.2)

    results.sort(key=lambda x: x["score"], reverse=True)
    top = results[:25]

    result = {
        "category":      category,
        "universe":      universe,
        "total_scanned": len(stocks),
        "recommendations": top,
        "regime":        {"regime": regime.get("regime"), "label": regime.get("label")},
        "generated_at":  int(time.time()),
    }
    _set_cache(cache_key, result)
    return result


# ── Market Depth (simulated from Yahoo bid/ask) ───────────────

async def get_market_depth(symbol: str) -> Dict[str, Any]:
    """Fetch bid/ask depth from Yahoo Finance quote."""
    try:
        import httpx
        from app.api.stock_fetcher import HEADERS
        full_sym = symbol if "." in symbol else f"{symbol}.NS"
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{full_sym}?interval=1m&range=1d"
        async with httpx.AsyncClient(headers=HEADERS, timeout=10) as client:
            r = await client.get(url)
            if r.status_code != 200:
                return {"error": "fetch_failed"}
            meta = r.json().get("chart", {}).get("result", [{}])[0].get("meta", {})

        price = meta.get("regularMarketPrice", 0)
        bid   = meta.get("bid", price * 0.9995)
        ask   = meta.get("ask", price * 1.0005)
        spread = round(ask - bid, 2) if ask and bid else 0

        # Simulate depth levels around current price (Yahoo doesn't provide full depth)
        depth_levels = 5
        tick = round(price * 0.0005, 2) or 0.05
        bids = [{"price": round(bid - i * tick, 2), "qty": max(100, int(5000 / (i + 1)))} for i in range(depth_levels)]
        asks = [{"price": round(ask + i * tick, 2), "qty": max(100, int(5000 / (i + 1)))} for i in range(depth_levels)]

        return {
            "symbol": symbol,
            "price": price,
            "bid": bid,
            "ask": ask,
            "spread": spread,
            "bids": bids,
            "asks": asks,
            "note": "Simulated depth — connect Angel One for real order book",
        }
    except Exception as e:
        return {"error": str(e)}


# ── News Intelligence (NSE/BSE announcements via RSS) ─────────

_NEWS_FEEDS = [
    ("NSE Corporate", "https://www.nseindia.com/api/corporate-announcements?index=equities"),
    ("Economic Times", "https://economictimes.indiatimes.com/markets/rssfeeds/1977021501.cms"),
    ("Moneycontrol", "https://www.moneycontrol.com/rss/marketreports.xml"),
    ("Business Standard", "https://www.business-standard.com/rss/markets-106.rss"),
    ("LiveMint", "https://www.livemint.com/rss/markets"),
]

_news_cache: List[Dict] = []
_news_ts: float = 0


async def get_market_news(symbol: Optional[str] = None, limit: int = 30) -> Dict[str, Any]:
    """Fetch financial news from RSS feeds with sentiment classification."""
    global _news_cache, _news_ts

    if _news_cache and (time.time() - _news_ts) < 300:  # 5 min cache
        news = _news_cache
    else:
        news = await _fetch_rss_news()
        _news_cache = news
        _news_ts = time.time()

    if symbol:
        sym_clean = symbol.replace(".NS", "").upper()
        news = [n for n in news if sym_clean in n.get("title", "").upper() or sym_clean in n.get("summary", "").upper()]

    return {"news": news[:limit], "total": len(news), "symbol": symbol}


async def _fetch_rss_news() -> List[Dict]:
    """Parse RSS feeds for financial news."""
    import httpx
    import xml.etree.ElementTree as ET

    news_items = []
    headers = {"User-Agent": "Mozilla/5.0 (compatible; JarvisBot/1.0)"}

    async def _fetch_feed(name: str, url: str):
        try:
            async with httpx.AsyncClient(headers=headers, timeout=8, follow_redirects=True) as client:
                r = await client.get(url)
                if r.status_code != 200:
                    return []
                root = ET.fromstring(r.text)
                items = []
                for item in root.iter("item"):
                    title   = (item.findtext("title") or "").strip()
                    link    = (item.findtext("link") or "").strip()
                    summary = (item.findtext("description") or "").strip()[:200]
                    pub     = (item.findtext("pubDate") or "").strip()
                    if title:
                        sentiment = _classify_sentiment(title + " " + summary)
                        items.append({
                            "source": name,
                            "title": title,
                            "link": link,
                            "summary": summary,
                            "published": pub,
                            "sentiment": sentiment,
                            "impact": _estimate_impact(title),
                        })
                return items[:10]
        except Exception:
            return []

    results = await asyncio.gather(*[_fetch_feed(n, u) for n, u in _NEWS_FEEDS], return_exceptions=True)
    for r in results:
        if isinstance(r, list):
            news_items.extend(r)

    # Sort by recency (best effort)
    return news_items


def _classify_sentiment(text: str) -> str:
    text_lower = text.lower()
    positive_words = ["surge", "rally", "gain", "profit", "growth", "record", "high", "buy", "upgrade",
                      "beat", "strong", "positive", "rise", "jump", "soar", "bullish", "outperform"]
    negative_words = ["fall", "drop", "loss", "decline", "crash", "sell", "downgrade", "miss",
                      "weak", "negative", "cut", "plunge", "bearish", "underperform", "concern", "risk"]
    pos = sum(1 for w in positive_words if w in text_lower)
    neg = sum(1 for w in negative_words if w in text_lower)
    if pos > neg:
        return "positive"
    elif neg > pos:
        return "negative"
    return "neutral"


def _estimate_impact(title: str) -> str:
    title_lower = title.lower()
    high_impact = ["rbi", "sebi", "budget", "gdp", "inflation", "rate", "policy", "result", "earnings", "merger", "acquisition"]
    if any(w in title_lower for w in high_impact):
        return "high"
    medium_impact = ["quarterly", "annual", "dividend", "bonus", "split", "buyback", "ipo"]
    if any(w in title_lower for w in medium_impact):
        return "medium"
    return "low"


# ── Economic Calendar ─────────────────────────────────────────

def get_economic_calendar() -> Dict[str, Any]:
    """Static economic calendar with key Indian market events."""
    import datetime
    today = datetime.date.today()

    # Key recurring events
    events = [
        {"date": "Every Month Last Week", "event": "RBI Monetary Policy Committee Meeting", "impact": "high", "category": "monetary_policy"},
        {"date": "Every Quarter", "event": "Quarterly Earnings Season (Nifty 50)", "impact": "high", "category": "earnings"},
        {"date": "Every Month 1st", "event": "GST Collection Data", "impact": "medium", "category": "economic"},
        {"date": "Every Month 12th", "event": "CPI Inflation Data", "impact": "high", "category": "economic"},
        {"date": "Every Month 14th", "event": "WPI Inflation Data", "impact": "medium", "category": "economic"},
        {"date": "Every Month Last Day", "event": "F&O Expiry (Monthly)", "impact": "high", "category": "derivatives"},
        {"date": "Every Thursday", "event": "F&O Expiry (Weekly Nifty)", "impact": "medium", "category": "derivatives"},
        {"date": "February", "event": "Union Budget", "impact": "high", "category": "fiscal_policy"},
        {"date": "March 31", "event": "Financial Year End", "impact": "high", "category": "fiscal"},
        {"date": "April 1", "event": "New Financial Year Begins", "impact": "medium", "category": "fiscal"},
    ]

    # Upcoming NSE holidays (approximate)
    holidays = [
        {"date": "2025-01-26", "name": "Republic Day"},
        {"date": "2025-03-14", "name": "Holi"},
        {"date": "2025-04-14", "name": "Dr. Ambedkar Jayanti"},
        {"date": "2025-04-18", "name": "Good Friday"},
        {"date": "2025-05-01", "name": "Maharashtra Day"},
        {"date": "2025-08-15", "name": "Independence Day"},
        {"date": "2025-10-02", "name": "Gandhi Jayanti"},
        {"date": "2025-10-24", "name": "Dussehra"},
        {"date": "2025-11-05", "name": "Diwali Laxmi Puja"},
        {"date": "2025-12-25", "name": "Christmas"},
    ]

    return {
        "events": events,
        "holidays": holidays,
        "market_hours": {
            "pre_open": "09:00 - 09:15 IST",
            "regular": "09:15 - 15:30 IST",
            "post_close": "15:40 - 16:00 IST",
            "currency": "09:00 - 17:00 IST",
        },
    }


# ── Intraday Assistant ────────────────────────────────────────

async def get_intraday_assistant(symbol: str, timeframe: str = "5m") -> Dict[str, Any]:
    """Real-time intraday trading assistant for a specific stock."""
    from app.market_data.service import fetch_candles
    from app.api.technical_analysis import compute_technical_analysis
    from app.api.data_quality import clean_candles
    from app.api.market_regime import get_market_regime, apply_regime_filter
    from app.api.mtf_analysis import get_mtf_analysis

    TF_MAP = {
        "1m": ("1m", 1), "3m": ("3m", 1), "5m": ("5m", 1),
        "10m": ("5m", 1), "15m": ("15m", 5), "30m": ("30m", 5),
        "45m": ("30m", 5), "1h": ("1h", 30),
    }
    interval, days = TF_MAP.get(timeframe, ("5m", 1))
    full_sym = symbol if "." in symbol else f"{symbol}.NS"

    chart = await fetch_candles(full_sym, interval=interval, days=days)
    if chart.get("error") or len(chart.get("candles", [])) < 26:
        return {"error": "insufficient_data", "symbol": symbol}

    candles, quality = clean_candles(chart["candles"])
    if len(candles) < 26:
        return {"error": "insufficient_clean_data", "symbol": symbol}

    ta = compute_technical_analysis(candles)
    if ta.get("error"):
        return {"error": ta["error"], "symbol": symbol}

    price = candles[-1]["c"]
    ind = ta.get("indicators", {})
    sr  = ta.get("support_resistance", {})
    atr = ind.get("atr") or price * 0.01

    # Market regime filter
    regime = await get_market_regime()
    raw_signal = ta.get("overall_signal", "HOLD")
    regime_result = apply_regime_filter(raw_signal, regime)
    signal = regime_result["signal"]

    # ATR-adaptive stops — widen during high volatility
    stop_mult = 2.0 if regime.get("reduce_size") else 1.5

    if signal == "BUY":
        entry  = price
        sl     = round(price - stop_mult * atr, 2)
        t1     = round(price + 2 * atr, 2)
        t2     = round(price + 3.5 * atr, 2)
        action = "ENTER LONG"
    elif signal == "SELL":
        entry  = price
        sl     = round(price + stop_mult * atr, 2)
        t1     = round(price - 2 * atr, 2)
        t2     = round(price - 3.5 * atr, 2)
        action = "ENTER SHORT / EXIT LONG"
    else:
        entry  = price
        sl     = round(price - atr, 2)
        t1     = round(price + atr, 2)
        t2     = round(price + 2 * atr, 2)
        action = "WAIT / HOLD"

    rsi       = ind.get("rsi") or 50
    vol_ratio = ind.get("volume_ratio") or 1
    momentum  = "strong" if vol_ratio > 1.5 and 40 < rsi < 70 else "weak" if vol_ratio < 0.8 else "moderate"

    return {
        "symbol":             symbol,
        "timeframe":          timeframe,
        "price":              price,
        "action":             action,
        "signal":             signal,
        "original_signal":    raw_signal,
        "regime_adjusted":    regime_result.get("regime_adjusted"),
        "regime_warning":     regime_result.get("warning"),
        "regime":             regime.get("regime"),
        "confidence":         ta.get("confidence"),
        "entry":              entry,
        "stop_loss":          sl,
        "target1":            t1,
        "target2":            t2,
        "risk_reward":        ta.get("risk_reward"),
        "trend":              ta.get("trend"),
        "momentum":           momentum,
        "volume_confirmation": vol_ratio > 1.2,
        "rsi":                rsi,
        "nearest_support":    sr.get("support", [None])[0],
        "nearest_resistance": sr.get("resistance", [None])[0],
        "signals":            ta.get("signals", [])[:5],
        "patterns":           ta.get("candlestick_patterns", [])[-3:],
        "data_quality":       quality.get("quality_score"),
        "updated_at":         int(time.time()),
    }
