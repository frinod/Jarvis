from datetime import datetime
try:
    from zoneinfo import ZoneInfo
except ImportError:
    from backports.zoneinfo import ZoneInfo  # type: ignore

from app.market_data.session import get_market_session

IST = ZoneInfo("Asia/Kolkata")


def test_regular_open():
    s = get_market_session(datetime(2026, 10, 1, 10, 0, tzinfo=IST))
    assert s.status == "open"
    assert s.is_regular_open


def test_weekend():
    s = get_market_session(datetime(2026, 10, 3, 10, 0, tzinfo=IST))
    assert s.status == "weekend"
    assert not s.trading_day
