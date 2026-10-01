"""Unified deep Indian-market intelligence endpoint used by the HUD."""
from __future__ import annotations

import asyncio
import time
from typing import Optional


async def deep_intelligence(symbol: str, horizon: int = 30) -> dict:
    from app.market_data.session import session_payload
    from app.api.forecaster import forecast
    from app.api.market_regime import get_market_regime
    from app.api.mtf_analysis import get_mtf_analysis
    from app.api.market_intelligence import get_market_news
    from app.api.stock_data import (
        fetch_fundamentals,
        fetch_quarterly_financials,
        fetch_shareholding,
        fetch_peers,
    )

    full = symbol if "." in symbol else f"{symbol}.NS"
    clean = full.replace(".NS", "")
    started = time.time()

    # Forecast owns freshness/quality/model validation. Fundamental APIs are
    # slower and independent, so gather them concurrently.
    results = await asyncio.gather(
        forecast(clean, horizon=horizon),
        get_market_regime(),
        get_mtf_analysis(clean),
        get_market_news(clean, limit=20),
        fetch_fundamentals(full),
        fetch_quarterly_financials(full),
        fetch_shareholding(full),
        fetch_peers(full),
        return_exceptions=True,
    )

    names = ["forecast", "regime", "mtf", "news", "fundamentals", "financials", "shareholding", "peers"]
    evidence = {}
    for name, result in zip(names, results):
        evidence[name] = {"error": str(result)} if isinstance(result, Exception) else result

    fc = evidence.get("forecast", {})
    return {
        "symbol": full,
        "generated_at": int(time.time()),
        "elapsed_ms": round((time.time() - started) * 1000, 2),
        "market_session": session_payload(),
        "forecast": fc,
        "regime": evidence.get("regime"),
        "mtf": evidence.get("mtf"),
        "news": evidence.get("news"),
        "fundamentals": evidence.get("fundamentals"),
        "financials": evidence.get("financials"),
        "shareholding": evidence.get("shareholding"),
        "peers": evidence.get("peers"),
        "provenance": {
            "forecast_engine": "XGBoost",
            "forecast_validation": fc.get("validation") if isinstance(fc, dict) else None,
            "data_quality": fc.get("data_quality") if isinstance(fc, dict) else None,
            "intraday_live_gate": True,
            "trade_execution": "human_confirmation_required",
        },
    }
