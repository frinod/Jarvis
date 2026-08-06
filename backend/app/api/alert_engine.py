"""Price Alert Engine — polls watchlist alerts and fires when thresholds are crossed."""
from __future__ import annotations
import asyncio
import httpx
from typing import Dict, List

# In-memory alert registry: { symbol: { "above": float|None, "below": float|None } }
_alerts: Dict[str, Dict] = {}
_triggered: List[Dict] = []  # last 50 triggered alerts
_running = False


def set_alert(symbol: str, above: float = None, below: float = None):
    if above is None and below is None:
        _alerts.pop(symbol, None)
    else:
        _alerts[symbol] = {"above": above, "below": below}


def get_alerts() -> Dict[str, Dict]:
    return dict(_alerts)


def get_triggered() -> List[Dict]:
    return list(_triggered[-50:])


def clear_triggered():
    _triggered.clear()


async def _fetch_price(symbol: str) -> float | None:
    # Priority 1: Angel One real-time tick (0-delay)
    try:
        from app.api.angel_feed import get_feed
        clean = symbol.replace('.NS', '').replace('.BO', '')
        tick = get_feed().latest_ticks.get(clean)
        if tick and tick.get('price'):
            return float(tick['price'])
    except Exception:
        pass

    # Priority 2: Yahoo Finance fallback
    full = symbol if '.' in symbol else f'{symbol}.NS'
    url = f'https://query1.finance.yahoo.com/v8/finance/chart/{full}?interval=1m&range=1d'
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            r = await client.get(url, headers={'User-Agent': 'Mozilla/5.0'})
            data = r.json()
            meta = data['chart']['result'][0]['meta']
            return float(meta.get('regularMarketPrice') or meta.get('previousClose') or 0)
    except Exception:
        return None


async def _poll_loop():
    global _running
    _running = True
    while _running:
        if not _alerts:
            await asyncio.sleep(30)
            continue
        for symbol, thresholds in list(_alerts.items()):
            price = await _fetch_price(symbol)
            if price is None:
                continue
            above = thresholds.get("above")
            below = thresholds.get("below")
            if above and price >= above:
                _triggered.append({"symbol": symbol, "price": price, "type": "above", "threshold": above})
                _alerts.pop(symbol, None)
            elif below and price <= below:
                _triggered.append({"symbol": symbol, "price": price, "type": "below", "threshold": below})
                _alerts.pop(symbol, None)
        await asyncio.sleep(5)  # check every 5s (Angel One ticks are real-time)


def start_alert_engine():
    global _running
    if _running:
        return
    import threading
    def _run():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(_poll_loop())
    t = threading.Thread(target=_run, daemon=True)
    t.start()


def stop_alert_engine():
    global _running
    _running = False
