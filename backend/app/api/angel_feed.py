"""Angel One SmartAPI - Real-time WebSocket Feed"""
from __future__ import annotations
import asyncio
import os
import pyotp
from dotenv import load_dotenv
load_dotenv()
from typing import Dict, List, Optional, Callable
from SmartApi import SmartConnect
from SmartApi.smartWebSocketV2 import SmartWebSocketV2

# ── Nifty 50 token map (Symbol -> NSE Token) ─────────────────
SYMBOL_TOKEN_MAP = {
    "RELIANCE": "2885", "TCS": "11536", "HDFCBANK": "1333",
    "INFY": "1594", "ICICIBANK": "4963", "HINDUNILVR": "1394",
    "ITC": "1660", "SBIN": "3045", "BHARTIARTL": "10604",
    "KOTAKBANK": "1922", "LT": "11483", "AXISBANK": "5900",
    "ASIANPAINT": "236", "MARUTI": "10999", "SUNPHARMA": "3351",
    "TITAN": "3506", "BAJFINANCE": "317", "WIPRO": "3787",
    "ULTRACEMCO": "11532", "NESTLEIND": "17963", "POWERGRID": "14977",
    "NTPC": "11630", "TECHM": "13538", "HCLTECH": "7229",
    "ONGC": "2475", "TATAMOTORS": "3456", "TATASTEEL": "3499",
    "JSWSTEEL": "11723", "ADANIENT": "25", "ADANIPORTS": "15083",
    "COALINDIA": "20374", "DIVISLAB": "10940", "DRREDDY": "881",
    "EICHERMOT": "910", "GRASIM": "1232", "HEROMOTOCO": "1348",
    "HINDALCO": "1363", "INDUSINDBK": "5258", "M&M": "2031",
    "BAJAJFINSV": "16675", "BAJAJ-AUTO": "16669", "BPCL": "526",
    "BRITANNIA": "547", "CIPLA": "694", "APOLLOHOSP": "157",
    "SBILIFE": "21808", "HDFCLIFE": "467", "UPL": "11287",
    "TATACONSUM": "3432", "SHRIRAMFIN": "4306",
}

TOKEN_SYMBOL_MAP = {v: k for k, v in SYMBOL_TOKEN_MAP.items()}

# ── Session cache ─────────────────────────────────────────────
_session: Optional[Dict] = None
_smart_api: Optional[SmartConnect] = None
_login_ok: bool = False  # True only after a successful login


def _credentials_present() -> bool:
    """Return True only if all credentials look non-trivial."""
    api_key    = (os.getenv("ANGEL_API_KEY")    or "").strip()
    client_id  = (os.getenv("ANGEL_CLIENT_ID")  or "").strip()
    password   = (os.getenv("ANGEL_PASSWORD")   or "").strip()
    totp_secret= (os.getenv("ANGEL_TOTP_SECRET")or "").strip()
    # Reject obviously placeholder values
    if not all([api_key, client_id, password, totp_secret]):
        return False
    if password in ("1234", "0000", "password", "test"):
        return False
    if len(totp_secret) < 16:          # valid TOTP secrets are ≥16 chars
        return False
    return True


def _login() -> Optional[Dict]:
    global _session, _smart_api, _login_ok
    if not _credentials_present():
        return None

    api_key     = os.getenv("ANGEL_API_KEY")
    client_id   = os.getenv("ANGEL_CLIENT_ID")
    password    = os.getenv("ANGEL_PASSWORD")
    totp_secret = os.getenv("ANGEL_TOTP_SECRET")

    try:
        totp = pyotp.TOTP(totp_secret).now()
        obj  = SmartConnect(api_key=api_key)
        data = obj.generateSession(client_id, password, totp)
        if data.get("status"):
            _smart_api = obj
            _session = {
                "auth_token": data["data"]["jwtToken"],
                "feed_token": obj.getfeedToken(),
                "client_id": client_id,
                "api_key": api_key,
            }
            _login_ok = True
            return _session
        print(f"[AngelOne] Login rejected by server: {data.get('message', 'unknown')}")
    except Exception as e:
        print(f"[AngelOne] Login failed: {e}")
    return None


def get_session() -> Optional[Dict]:
    global _session
    if _session:
        return _session
    if not _credentials_present():
        return None
    return _login()


class AngelOneFeed:
    """Real-time tick feed using Angel One SmartWebSocketV2."""

    def __init__(self):
        self.ws: Optional[SmartWebSocketV2] = None
        self.latest_ticks: Dict[str, Dict] = {}
        self.callbacks: List[Callable] = []
        self._running = False
        self._new_tick = False

    def add_callback(self, fn: Callable):
        self.callbacks.append(fn)

    def _on_data(self, wsapp, message):
        try:
            token = str(message.get("token", ""))
            symbol = TOKEN_SYMBOL_MAP.get(token, token)
            ltp = message.get("last_traded_price", 0) / 100  # Angel sends paise
            close = message.get("close_price", 0) / 100
            change = round(ltp - close, 2)
            change_pct = round((change / close * 100), 2) if close else 0

            tick = {
                "symbol": symbol,
                "price": round(ltp, 2),
                "prev_close": round(close, 2),
                "change": change,
                "change_pct": change_pct,
                "volume": message.get("volume_trade_for_the_day", 0),
                "day_high": round(message.get("high_price_of_the_day", 0) / 100, 2),
                "day_low": round(message.get("low_price_of_the_day", 0) / 100, 2),
            }
            self.latest_ticks[symbol] = tick
            self._new_tick = True

            for cb in self.callbacks:
                asyncio.create_task(cb(tick)) if asyncio.get_event_loop().is_running() else None
        except Exception as e:
            print(f"[AngelOne] Tick parse error: {e}")

    def _on_error(self, wsapp, error):
        print(f"[AngelOne] WebSocket error: {error}")

    def _on_close(self, wsapp):
        print("[AngelOne] WebSocket closed")
        self._running = False

    def _on_open(self, wsapp):
        print("[AngelOne] WebSocket connected")
        tokens = [{"exchangeType": 1, "tokens": list(SYMBOL_TOKEN_MAP.values())}]
        self.ws.subscribe("jarvis_feed", 3, tokens)  # mode 3 = SNAP_QUOTE

    def start(self):
        if not _credentials_present():
            print("[AngelOne] Feed skipped — credentials not configured")
            return
        session = get_session()
        if not session:
            print("[AngelOne] Cannot start feed — login failed")
            return

        self.ws = SmartWebSocketV2(
            session["auth_token"],
            session["api_key"],
            session["client_id"],
            session["feed_token"],
        )
        self.ws.on_open = self._on_open
        self.ws.on_data = self._on_data
        self.ws.on_error = self._on_error
        self.ws.on_close = self._on_close
        self._running = True
        try:
            self.ws.connect()
        except Exception as e:
            print(f"[AngelOne] WebSocket connect error: {e}")
            self._running = False

    def stop(self):
        if self.ws:
            self.ws.close_connection()
        self._running = False

    def get_all_ticks(self) -> Dict[str, Dict]:
        return self.latest_ticks


# ── Singleton feed instance ───────────────────────────────────
_feed: Optional[AngelOneFeed] = None


def get_feed() -> AngelOneFeed:
    global _feed
    if _feed is None:
        _feed = AngelOneFeed()
    return _feed


def is_feed_available() -> bool:
    """True if the feed connected successfully and has live ticks."""
    return _login_ok and _feed is not None and _feed._running


def start_feed():
    if not _credentials_present():
        print("[AngelOne] Feed not started — credentials missing or placeholder")
        return
    feed = get_feed()
    if not feed._running:
        import threading
        t = threading.Thread(target=feed.start, daemon=True)
        t.start()
