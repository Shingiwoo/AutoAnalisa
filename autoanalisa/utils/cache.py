from __future__ import annotations

import time
from functools import wraps
from typing import Callable, Any


def ttl_cache(ttl_seconds: int = 60):
    def deco(fn: Callable):
        cache: dict[tuple, tuple[float, Any]] = {}

        @wraps(fn)
        def wrapper(*args, **kwargs):
            key = (args, tuple(sorted(kwargs.items())))
            now = time.time()
            if key in cache:
                ts, val = cache[key]
                if now - ts <= ttl_seconds:
                    return val
            val = fn(*args, **kwargs)
            cache[key] = (now, val)
            return val

        return wrapper

    return deco

