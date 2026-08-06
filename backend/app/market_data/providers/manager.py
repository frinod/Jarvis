"""
Phase 1.9 — Provider Manager
==============================
Manages the ordered list of providers and handles automatic fallback.
Callers never know which provider served the request.

Priority order (configurable via .env):
  1. Angel One  (priority 10)
  2. Yahoo Finance (priority 90)

Future providers (Upstox, Kite, Breeze) can be registered here
without changing any other module.
"""
from __future__ import annotations

import logging
import os
from typing import List, Optional, Dict

from app.market_data.providers.base import (
    MarketDataProvider, Interval, Candle, Quote,
    CandleResult, ProviderStatus,
)

log = logging.getLogger(__name__)


class ProviderManager:
    """
    Manages multiple MarketDataProvider instances.
    Tries providers in priority order, falls back automatically.
    """

    def __init__(self):
        self._providers: List[MarketDataProvider] = []
        self._initialised = False

    def register(self, provider: MarketDataProvider):
        """Register a provider. Lower priority number = tried first."""
        self._providers.append(provider)
        self._providers.sort(key=lambda p: p.priority)
        log.info(f"[ProviderManager] Registered: {provider.name} (priority {provider.priority})")

    async def initialise_all(self):
        """Initialise all registered providers at startup."""
        for p in self._providers:
            try:
                ok = await p.initialise()
                log.info(f"[ProviderManager] {p.name}: {'ready' if ok else 'unavailable'}")
            except Exception as e:
                log.error(f"[ProviderManager] {p.name} init failed: {e}")
        self._initialised = True

    # ── Core data methods with fallback ───────────────────────

    async def fetch_candles(
        self,
        symbol:   str,
        interval: Interval,
        from_ts:  int,
        to_ts:    int,
    ) -> CandleResult:
        """Try providers in priority order until one succeeds."""
        last_error = "No providers registered"
        for provider in self._providers:
            try:
                if not await provider.is_available():
                    log.debug(f"[ProviderManager] {provider.name} unavailable, skipping")
                    continue
                result = await provider.fetch_candles(symbol, interval, from_ts, to_ts)
                if result.ok:
                    if provider.name != self._providers[0].name:
                        log.info(
                            f"[ProviderManager] {symbol} served by fallback: {provider.name}"
                        )
                    return result
                last_error = result.error or "empty result"
                log.debug(f"[ProviderManager] {provider.name} failed for {symbol}: {last_error}")
            except Exception as e:
                last_error = str(e)
                log.warning(f"[ProviderManager] {provider.name} exception: {e}")

        # All providers failed
        return CandleResult(
            symbol=symbol, interval=interval, candles=[],
            source="none", from_ts=from_ts, to_ts=to_ts,
            error=f"All providers failed. Last: {last_error}",
        )

    async def fetch_quote(self, symbol: str) -> Optional[Quote]:
        for provider in self._providers:
            try:
                if not await provider.is_available():
                    continue
                q = await provider.fetch_quote(symbol)
                if q:
                    return q
            except Exception as e:
                log.warning(f"[ProviderManager] fetch_quote {provider.name}: {e}")
        return None

    async def fetch_quotes(self, symbols: List[str]) -> List[Quote]:
        for provider in self._providers:
            try:
                if not await provider.is_available():
                    continue
                quotes = await provider.fetch_quotes(symbols)
                if quotes:
                    return quotes
            except Exception as e:
                log.warning(f"[ProviderManager] fetch_quotes {provider.name}: {e}")
        return []

    async def fetch_indices(self) -> List[Quote]:
        for provider in self._providers:
            try:
                if not await provider.is_available():
                    continue
                indices = await provider.fetch_indices()
                if indices:
                    return indices
            except Exception as e:
                log.warning(f"[ProviderManager] fetch_indices {provider.name}: {e}")
        return []

    # ── Status ────────────────────────────────────────────────

    async def get_all_status(self) -> List[Dict]:
        statuses = []
        for p in self._providers:
            try:
                s = await p.get_status()
                statuses.append({
                    "name":       s.name,
                    "available":  s.available,
                    "logged_in":  s.logged_in,
                    "priority":   p.priority,
                    "last_error": s.last_error,
                })
            except Exception as e:
                statuses.append({"name": p.name, "error": str(e)})
        return statuses

    @property
    def primary(self) -> Optional[MarketDataProvider]:
        return self._providers[0] if self._providers else None

    @property
    def provider_names(self) -> List[str]:
        return [p.name for p in self._providers]


# ── Module-level singleton ────────────────────────────────────
_manager: Optional[ProviderManager] = None


def get_manager() -> ProviderManager:
    """Return the global ProviderManager singleton."""
    global _manager
    if _manager is None:
        _manager = _build_manager()
    return _manager


def _build_manager() -> ProviderManager:
    """
    Build and configure the provider manager from environment settings.
    Provider order is determined by priority values.
    Add new providers here — no other file needs to change.
    """
    from app.market_data.providers.angel_one import AngelOneProvider
    from app.market_data.providers.yahoo import YahooFinanceProvider

    mgr = ProviderManager()

    # Angel One — primary (priority 10)
    # Only register if credentials are present
    api_key  = os.getenv("ANGEL_API_KEY",     "").strip()
    client   = os.getenv("ANGEL_CLIENT_ID",   "").strip()
    password = os.getenv("ANGEL_PASSWORD",    "").strip()
    totp     = os.getenv("ANGEL_TOTP_SECRET", "").strip()

    if all([api_key, client, password, totp]) and len(totp) >= 16:
        mgr.register(AngelOneProvider())
    else:
        log.warning("[ProviderManager] Angel One credentials incomplete — skipping")

    # Yahoo Finance — always registered as fallback (priority 90)
    mgr.register(YahooFinanceProvider())

    return mgr
