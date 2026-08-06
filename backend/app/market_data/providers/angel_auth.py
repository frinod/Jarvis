"""
Phase 1.3 — Angel One Provider: Authentication & Session Management
====================================================================
Handles login, token storage, auto-refresh on expiry, and
re-login on session failure. All other Angel One capabilities
(candles, quotes) build on top of this session layer.
"""
from __future__ import annotations

import asyncio
import concurrent.futures
import logging
import os
import time
from typing import Optional, Dict

_executor = concurrent.futures.ThreadPoolExecutor(max_workers=4)


def _run_sync(loop, fn, *args):
    """Run blocking fn in thread pool — Python 3.7 compatible."""
    return loop.run_in_executor(_executor, fn, *args)

import pyotp
from dotenv import load_dotenv

log = logging.getLogger(__name__)

# Load .env relative to this file
_ENV = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "..", "..", "..", ".env"
)
load_dotenv(os.path.normpath(_ENV), override=False)


class AngelSession:
    """
    Manages a single Angel One SmartAPI session.
    Thread-safe via asyncio lock.
    Auto-refreshes JWT before expiry.
    Re-logins if refresh fails.
    """

    # JWT tokens expire after ~6 hours; refresh at 5h to be safe
    _REFRESH_BEFORE_SECS = 3600   # refresh 1h before expiry
    _TOKEN_LIFETIME_SECS = 6 * 3600

    def __init__(self):
        self._api_key     = os.getenv("ANGEL_API_KEY",     "").strip()
        self._client_id   = os.getenv("ANGEL_CLIENT_ID",   "").strip()
        self._password    = os.getenv("ANGEL_PASSWORD",    "").strip()
        self._totp_secret = os.getenv("ANGEL_TOTP_SECRET", "").strip()

        self._smart_api   = None
        self._jwt:         Optional[str] = None
        self._refresh_tok: Optional[str] = None
        self._feed_tok:    Optional[str] = None
        self._logged_in:   bool = False
        self._login_at:    float = 0.0
        self._last_error:  Optional[str] = None
        self._lock = asyncio.Lock()

    # ── Public API ────────────────────────────────────────────

    @property
    def is_logged_in(self) -> bool:
        return self._logged_in and self._jwt is not None

    @property
    def jwt(self) -> Optional[str]:
        return self._jwt

    @property
    def feed_token(self) -> Optional[str]:
        return self._feed_tok

    @property
    def client_id(self) -> str:
        return self._client_id

    @property
    def api_key(self) -> str:
        return self._api_key

    @property
    def smart_api(self):
        """Return the authenticated SmartConnect instance."""
        return self._smart_api

    @property
    def last_error(self) -> Optional[str]:
        return self._last_error

    def credentials_present(self) -> bool:
        return all([
            self._api_key,
            self._client_id,
            self._password,
            self._totp_secret,
            len(self._totp_secret) >= 16,
        ])

    async def ensure_logged_in(self) -> bool:
        """
        Ensure a valid session exists. Logs in if not authenticated.
        Refreshes token if nearing expiry. Thread-safe.
        Returns True if session is valid.
        """
        async with self._lock:
            if not self.credentials_present():
                self._last_error = "Credentials missing or incomplete"
                return False

            # Already logged in and token is fresh
            if self._logged_in and self._jwt:
                age = time.time() - self._login_at
                if age < (self._TOKEN_LIFETIME_SECS - self._REFRESH_BEFORE_SECS):
                    return True
                # Token nearing expiry — try refresh first
                if await self._refresh_token():
                    return True
                # Refresh failed — fall through to full re-login

            return await self._login()

    async def invalidate(self):
        """Force re-login on next request (e.g. after 401 error)."""
        async with self._lock:
            self._logged_in = False
            self._jwt = None
            log.info("[AngelOne] Session invalidated — will re-login on next request")

    # ── Internal ──────────────────────────────────────────────

    async def _login(self) -> bool:
        """Perform full login. Must be called with lock held."""
        try:
            from SmartApi import SmartConnect
            totp = pyotp.TOTP(self._totp_secret).now()

            self._smart_api = SmartConnect(api_key=self._api_key)
            loop = asyncio.get_event_loop()
            resp = await loop.run_in_executor(
                _executor,
                lambda: self._smart_api.generateSession(
                    self._client_id, self._password, totp
                )
            )

            if not resp or resp.get("status") is not True:
                msg = resp.get("message", "unknown") if resp else "no response"
                self._last_error = f"Login failed: {msg}"
                self._logged_in  = False
                log.error(f"[AngelOne] {self._last_error}")
                return False

            data = resp.get("data", {})
            jwt  = data.get("jwtToken", "")

            # Strip "Bearer " prefix if present — we add it ourselves
            self._jwt         = jwt.replace("Bearer ", "").strip()
            self._refresh_tok = data.get("refreshToken", "")
            self._feed_tok    = data.get("feedToken", "")
            self._logged_in   = True
            self._login_at    = time.time()
            self._last_error  = None

            # Set token on the SmartConnect instance
            self._smart_api.setAccessToken(self._jwt)

            log.info(f"[AngelOne] Login successful — client: {self._client_id}")
            return True

        except Exception as e:
            self._last_error = str(e)
            self._logged_in  = False
            log.error(f"[AngelOne] Login exception: {e}")
            return False

    async def _refresh_token(self) -> bool:
        """Attempt JWT refresh using refresh token. Must be called with lock held."""
        if not self._refresh_tok or not self._smart_api:
            return False
        try:
            loop = asyncio.get_event_loop()
            resp = await loop.run_in_executor(
                _executor,
                lambda: self._smart_api.generateToken(self._refresh_tok)
            )
            if resp and resp.get("data", {}).get("jwtToken"):
                new_jwt = resp["data"]["jwtToken"].replace("Bearer ", "").strip()
                self._jwt      = new_jwt
                self._feed_tok = resp["data"].get("feedToken", self._feed_tok)
                self._login_at = time.time()
                self._smart_api.setAccessToken(self._jwt)
                log.info("[AngelOne] Token refreshed successfully")
                return True
        except Exception as e:
            log.warning(f"[AngelOne] Token refresh failed: {e}")
        return False

    def get_status_dict(self) -> Dict:
        age = int(time.time() - self._login_at) if self._login_at else 0
        return {
            "logged_in":    self._logged_in,
            "client_id":    self._client_id,
            "session_age_s": age,
            "token_present": self._jwt is not None,
            "feed_token":   self._feed_tok is not None,
            "last_error":   self._last_error,
            "credentials":  self.credentials_present(),
        }


# ── Module-level singleton ────────────────────────────────────
_session = AngelSession()


def get_session() -> AngelSession:
    """Return the global Angel One session singleton."""
    return _session
