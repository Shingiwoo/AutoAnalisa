from __future__ import annotations

from datetime import datetime, timezone, timedelta
from dateutil import tz
from typing import Literal


def now_tz(tz_str: str = "Asia/Jakarta") -> datetime:
    tzinfo = tz.gettz(tz_str)
    return datetime.now(tzinfo)


def to_tz(dt: datetime, tz_str: str = "Asia/Jakarta") -> datetime:
    tzinfo = tz.gettz(tz_str)
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc).astimezone(tzinfo)
    return dt.astimezone(tzinfo)


def tf_to_binance_interval(tf: str) -> str:
    mapping = {"1D": "1d", "4H": "4h", "1H": "1h", "15m": "15m", "5m": "5m"}
    if tf not in mapping:
        raise ValueError(f"Unsupported TF: {tf}")
    return mapping[tf]


def tf_duration_seconds(tf: str) -> int:
    durations = {
        "1D": 60 * 60 * 24,
        "4H": 60 * 60 * 4,
        "1H": 60 * 60,
        "15m": 60 * 15,
        "5m": 60 * 5,
    }
    if tf not in durations:
        raise ValueError(f"Unsupported TF: {tf}")
    return durations[tf]


def isoformat_wtz(dt: datetime, tz_str: str = "Asia/Jakarta") -> str:
    return to_tz(dt, tz_str).isoformat()


def current_session_bias(now: datetime | None = None, tz_str: str = "Asia/Jakarta") -> Literal["bullish", "bearish", "neutral"]:
    dt = now or now_tz(tz_str)
    hour = dt.hour
    minute = dt.minute
    hm = hour * 60 + minute
    # Static windows (can be moved to config):
    # 01:00–08:00 WIB => bullish
    # 12:00–17:00 WIB => bullish
    # 22:00–01:00 WIB => bearish
    # 17:00–22:00 WIB => bearish
    # 08:00–12:00 WIB => neutral

    def in_range(start_hm: int, end_hm: int) -> bool:
        # supports wrap around midnight when end < start
        if end_hm >= start_hm:
            return start_hm <= hm < end_hm
        # wrap
        return hm >= start_hm or hm < end_hm

    b_bull = (
        in_range(1 * 60, 8 * 60) or  # 01:00-08:00
        in_range(12 * 60, 17 * 60)   # 12:00-17:00
    )
    b_bear = (
        in_range(22 * 60, 24 * 60) or  # 22:00-24:00
        in_range(0, 1 * 60) or         # 00:00-01:00
        in_range(17 * 60, 22 * 60)     # 17:00-22:00
    )
    if b_bull and not b_bear:
        return "bullish"
    if b_bear and not b_bull:
        return "bearish"
    return "neutral"
