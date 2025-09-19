from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional

import yaml

from .time import now_tz


def load_macro_schedule(path: str) -> dict:
    with open(path, "r") as f:
        return yaml.safe_load(f) or {}


def session_bias_from_schedule(schedule: dict, now: Optional[datetime] = None, tz_str: str = "Asia/Jakarta") -> Literal["bullish", "bearish", "neutral"]:
    dt = now or now_tz(tz_str)
    hm = dt.hour * 60 + dt.minute
    windows = (schedule or {}).get("windows", [])
    for w in windows:
        start = w.get("start", "00:00")
        end = w.get("end", "00:00")
        bias = w.get("bias", "neutral").lower()
        try:
            sh, sm = map(int, start.split(":"))
            eh, em = map(int, end.split(":"))
        except Exception:
            continue
        s_hm = sh * 60 + sm
        e_hm = eh * 60 + em
        if e_hm >= s_hm:
            in_win = s_hm <= hm < e_hm
        else:
            in_win = hm >= s_hm or hm < e_hm
        if in_win:
            if bias in ("bullish", "bearish", "neutral"):
                return bias
    return "neutral"

