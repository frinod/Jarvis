"""Canonical NSE market-session awareness for JARVIS.

The assistant must know whether it is allowed to treat data as live before
it polls providers or asks the forecast engine to infer from intraday data.
Holiday dates are injectable through NSE_HOLIDAYS so the deployment can keep
its exchange calendar current without hard-coding a stale year.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
try:
    from zoneinfo import ZoneInfo
except ImportError:
    from backports.zoneinfo import ZoneInfo  # type: ignore
import os

IST = ZoneInfo("Asia/Kolkata")
PRE_OPEN = (time(9, 0), time(9, 15))
REGULAR = (time(9, 15), time(15, 30))
POST_MARKET = (time(15, 30), time(16, 0))


@dataclass(frozen=True)
class MarketSession:
    status: str
    label: str
    now_ist: datetime
    next_open: datetime | None
    next_close: datetime | None
    trading_day: bool
    reason: str

    @property
    def is_regular_open(self) -> bool:
        return self.status == "open"


def _holidays() -> set[str]:
    raw = os.getenv("NSE_HOLIDAYS", "")
    return {x.strip() for x in raw.split(",") if x.strip()}


def _next_trading_day(day: date, holidays: set[str]) -> date:
    candidate = day + timedelta(days=1)
    while candidate.weekday() >= 5 or candidate.isoformat() in holidays:
        candidate += timedelta(days=1)
    return candidate


def get_market_session(now: datetime | None = None) -> MarketSession:
    now = (now or datetime.now(IST)).astimezone(IST)
    holidays = _holidays()
    key = now.date().isoformat()

    if now.weekday() >= 5:
        nxt = _next_trading_day(now.date(), holidays)
        return MarketSession("weekend", "NSE weekend", now,
            datetime.combine(nxt, REGULAR[0], tzinfo=IST), None, False,
            "Saturday/Sunday")

    if key in holidays:
        nxt = _next_trading_day(now.date(), holidays)
        return MarketSession("holiday", "NSE trading holiday", now,
            datetime.combine(nxt, REGULAR[0], tzinfo=IST), None, False,
            "Configured NSE holiday")

    local = now.timetz().replace(tzinfo=None)
    if PRE_OPEN[0] <= local < PRE_OPEN[1]:
        return MarketSession("pre_market", "NSE pre-open", now,
            datetime.combine(now.date(), REGULAR[0], tzinfo=IST),
            datetime.combine(now.date(), PRE_OPEN[1], tzinfo=IST), True,
            "Pre-open session")

    if REGULAR[0] <= local <= REGULAR[1]:
        return MarketSession("open", "NSE market open", now, None,
            datetime.combine(now.date(), REGULAR[1], tzinfo=IST), True,
            "Regular equity session")

    if POST_MARKET[0] <= local <= POST_MARKET[1]:
        nxt = _next_trading_day(now.date(), holidays)
        return MarketSession("post_market", "NSE post-market", now,
            datetime.combine(nxt, REGULAR[0], tzinfo=IST), None, True,
            "Post-market window")

    nxt_day = now.date() if local < PRE_OPEN[0] else _next_trading_day(now.date(), holidays)
    return MarketSession("closed", "NSE market closed", now,
        datetime.combine(nxt_day, REGULAR[0], tzinfo=IST), None, True,
        "Outside configured exchange session")


def session_payload(now: datetime | None = None) -> dict:
    s = get_market_session(now)
    return {
        "status": s.status,
        "label": s.label,
        "reason": s.reason,
        "now_ist": s.now_ist.isoformat(),
        "trading_day": s.trading_day,
        "next_open": s.next_open.isoformat() if s.next_open else None,
        "next_close": s.next_close.isoformat() if s.next_close else None,
        "regular_hours": "09:15-15:30 IST",
    }
