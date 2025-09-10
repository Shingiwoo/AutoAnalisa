import time
from typing import Optional

try:
    from redis.asyncio import Redis
except Exception:  # pragma: no cover
    Redis = None  # type: ignore


class LockService:
    def __init__(self, redis_client: Optional["Redis"], namespace: str = "lock"):
        self.r = redis_client
        self.ns = namespace
        self.local = {}

    async def acquire(self, key: str, ttl: int = 30) -> bool:
        namespaced = f"{self.ns}:{key}"
        if self.r:
            try:
                # returns True if set, None/False if exists
                res = await self.r.set(namespaced, "1", ex=ttl, nx=True)
                return bool(res)
            except Exception:
                # fallback ke local jika Redis down
                pass
        # fallback local
        now = time.time()
        if namespaced in self.local and self.local[namespaced] > now:
            return False
        self.local[namespaced] = now + ttl
        return True

    async def release(self, key: str):
        namespaced = f"{self.ns}:{key}"
        if self.r:
            try:
                await self.r.delete(namespaced)
                return
            except Exception:
                pass
        self.local.pop(namespaced, None)
