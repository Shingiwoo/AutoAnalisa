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

