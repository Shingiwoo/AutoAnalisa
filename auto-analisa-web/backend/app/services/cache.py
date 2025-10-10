from __future__ import annotations

import time
from typing import Any, Dict, Tuple


class MarketCache:
    def __init__(self):
        self._m: Dict[Tuple[str, str, int, str], Tuple[float, Any]] = {}

    def get(self, key: Tuple[str, str, int, str], ttl: float) -> Any | None:
        ts, val = self._m.get(key, (0.0, None))
        if val is None:
            return None
        return val if (time.time() - ts) <= ttl else None

    def set(self, key: Tuple[str, str, int, str], value: Any) -> None:
        self._m[key] = (time.time(), value)


class SnapshotStore:
    def __init__(self):
        self._s: Dict[str, Dict[str, Any]] = {}

    def put(self, sid: str, payload: Dict[str, Any]) -> None:
        self._s[sid] = {"ts": time.time(), **payload}

    def get(self, sid: str) -> Dict[str, Any] | None:
        return self._s.get(sid)

