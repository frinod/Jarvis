"""
Phase 1.2 — Instrument Master
================================
Downloads the Angel One instrument master CSV (~50,000 symbols),
builds a symbol→token map, and refreshes it daily.

No hardcoded token map. Every NSE/BSE symbol is supported automatically.
"""
from __future__ import annotations

import csv
import io
import json
import logging
import os
import time
from typing import Dict, Optional, Tuple

import httpx

log = logging.getLogger(__name__)

# ── Paths ─────────────────────────────────────────────────────
_BASE_DIR    = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_CACHE_FILE  = os.path.join(_BASE_DIR, "..", "..", "instruments_cache.json")
_CACHE_FILE  = os.path.normpath(_CACHE_FILE)
_CACHE_TTL   = 24 * 3600   # refresh once per day

# Angel One instrument master URL (public, no auth required)
_INSTRUMENT_URL = "https://margincalculator.angelbroking.com/OpenAPI_File/files/OpenAPIScripMaster.json"

# ── In-memory maps ────────────────────────────────────────────
# symbol → {"token": str, "exchange": str, "trading_symbol": str}
_nse_map:  Dict[str, Dict] = {}   # NSE equities
_bse_map:  Dict[str, Dict] = {}   # BSE equities
_index_map: Dict[str, Dict] = {}  # Indices (NIFTY 50, SENSEX, etc.)
_loaded_at: float = 0.0
_total_instruments: int = 0

# Known index tokens (always available as fallback)
_KNOWN_INDICES = {
    "NIFTY 50":    {"token": "99926000", "exchange": "NSE"},
    "NIFTY":       {"token": "99926000", "exchange": "NSE"},
    "^NSEI":       {"token": "99926000", "exchange": "NSE"},
    "SENSEX":      {"token": "99919000", "exchange": "BSE"},
    "^BSESN":      {"token": "99919000", "exchange": "BSE"},
    "BANKNIFTY":   {"token": "99926009", "exchange": "NSE"},
    "NIFTY BANK":  {"token": "99926009", "exchange": "NSE"},
    "NIFTYMIDCAP": {"token": "99926011", "exchange": "NSE"},
    "FINNIFTY":    {"token": "99926037", "exchange": "NSE"},
}


def _cache_fresh() -> bool:
    if not os.path.exists(_CACHE_FILE):
        return False
    try:
        mtime = os.path.getmtime(_CACHE_FILE)
        return (time.time() - mtime) < _CACHE_TTL
    except OSError:
        return False


def _load_from_cache() -> bool:
    global _nse_map, _bse_map, _index_map, _loaded_at, _total_instruments
    try:
        with open(_CACHE_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        _nse_map   = data.get("nse", {})
        _bse_map   = data.get("bse", {})
        _index_map = data.get("indices", {})
        _loaded_at = data.get("loaded_at", 0.0)
        _total_instruments = len(_nse_map) + len(_bse_map)
        log.info(f"[Instruments] Loaded from cache: {_total_instruments} instruments")
        return True
    except Exception as e:
        log.warning(f"[Instruments] Cache load failed: {e}")
        return False


def _save_to_cache():
    try:
        with open(_CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump({
                "nse":       _nse_map,
                "bse":       _bse_map,
                "indices":   _index_map,
                "loaded_at": _loaded_at,
            }, f)
        log.info(f"[Instruments] Saved {_total_instruments} instruments to cache")
    except Exception as e:
        log.warning(f"[Instruments] Cache save failed: {e}")


async def _download_and_parse() -> bool:
    """Download instrument master JSON from Angel One and parse it."""
    global _nse_map, _bse_map, _index_map, _loaded_at, _total_instruments

    log.info(f"[Instruments] Downloading instrument master from Angel One...")
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            r = await client.get(_INSTRUMENT_URL)
            if r.status_code != 200:
                log.error(f"[Instruments] Download failed: HTTP {r.status_code}")
                return False
            instruments = r.json()
    except Exception as e:
        log.error(f"[Instruments] Download exception: {e}")
        return False

    nse: Dict[str, Dict] = {}
    bse: Dict[str, Dict] = {}
    idx: Dict[str, Dict] = {}

    for item in instruments:
        try:
            exch    = item.get("exch_seg", "")
            token   = item.get("token", "")
            symbol  = item.get("symbol", "").strip()
            name    = item.get("name", "").strip()
            itype   = item.get("instrumenttype", "").strip()
            trading = item.get("symbol", "").strip()

            if not token or not symbol:
                continue

            entry = {
                "token":          token,
                "exchange":       exch,
                "trading_symbol": trading,
                "name":           name,
                "itype":          itype,
            }

            # NSE equities — symbol ends with -EQ
            if exch == "NSE" and trading.endswith("-EQ"):
                clean = trading.replace("-EQ", "").upper()
                nse[clean] = entry
                # Also map with .NS suffix (Yahoo-style)
                nse[clean + ".NS"] = entry

            # BSE equities — numeric symbol
            elif exch == "BSE" and itype == "":
                clean = symbol.upper()
                bse[clean] = entry
                bse[clean + ".BO"] = entry

            # Indices
            elif exch == "NSE" and itype == "AMXIDX":
                idx[symbol.upper()] = entry

        except Exception:
            continue

    # Always include known indices as fallback
    for k, v in _KNOWN_INDICES.items():
        idx[k.upper()] = v

    _nse_map   = nse
    _bse_map   = bse
    _index_map = idx
    _loaded_at = time.time()
    _total_instruments = len(nse) + len(bse)

    log.info(f"[Instruments] Parsed: {len(nse)} NSE + {len(bse)} BSE + {len(idx)} indices")
    _save_to_cache()
    return True


async def ensure_loaded() -> bool:
    """
    Ensure instrument master is loaded. Uses cache if fresh,
    downloads otherwise. Safe to call multiple times.
    """
    global _nse_map

    # Already loaded in memory and fresh
    if _nse_map and (time.time() - _loaded_at) < _CACHE_TTL:
        return True

    # Try loading from disk cache first (fast)
    if _cache_fresh() and _load_from_cache():
        return True

    # Download fresh copy
    ok = await _download_and_parse()
    if not ok:
        # Last resort: load stale cache rather than fail completely
        if os.path.exists(_CACHE_FILE):
            log.warning("[Instruments] Download failed — using stale cache")
            return _load_from_cache()
        # Absolute fallback: use hardcoded Nifty 50 tokens
        _load_hardcoded_fallback()
        return True

    return True


def resolve(symbol: str) -> Optional[Tuple[str, str]]:
    """
    Resolve a symbol to (token, exchange).

    Accepts:
      "RELIANCE"      → NSE equity
      "RELIANCE.NS"   → NSE equity (Yahoo-style)
      "RELIANCE.BO"   → BSE equity
      "^NSEI"         → NIFTY 50 index
      "NIFTY 50"      → NIFTY 50 index

    Returns (token, exchange) or None if not found.
    """
    s = symbol.strip().upper()

    # Check index map first
    idx_entry = _index_map.get(s) or _KNOWN_INDICES.get(s)
    if idx_entry:
        return idx_entry["token"], idx_entry.get("exchange", "NSE")

    # BSE suffix
    if s.endswith(".BO"):
        entry = _bse_map.get(s) or _bse_map.get(s.replace(".BO", ""))
        if entry:
            return entry["token"], "BSE"

    # NSE suffix or plain
    entry = _nse_map.get(s) or _nse_map.get(s.replace(".NS", ""))
    if entry:
        return entry["token"], "NSE"

    # BSE plain fallback
    entry = _bse_map.get(s)
    if entry:
        return entry["token"], "BSE"

    return None


def get_stats() -> Dict:
    return {
        "nse_count":   len(_nse_map) // 2,   # divided by 2 because .NS duplicates
        "bse_count":   len(_bse_map) // 2,
        "index_count": len(_index_map),
        "loaded_at":   _loaded_at,
        "cache_file":  _CACHE_FILE,
        "cache_fresh": _cache_fresh(),
    }


def _load_hardcoded_fallback():
    """Absolute last resort — hardcoded Nifty 50 tokens."""
    global _nse_map, _index_map, _loaded_at
    NIFTY50 = {
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
    for sym, token in NIFTY50.items():
        entry = {"token": token, "exchange": "NSE",
                 "trading_symbol": sym + "-EQ", "name": sym, "itype": ""}
        _nse_map[sym] = entry
        _nse_map[sym + ".NS"] = entry

    _index_map.update({k.upper(): v for k, v in _KNOWN_INDICES.items()})
    _loaded_at = time.time()
    log.warning("[Instruments] Using hardcoded Nifty 50 fallback (50 symbols only)")
