#!/usr/bin/env python3
import asyncio
import argparse
import fcntl
import os
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from app.config import settings
from app.models import Base, Analysis, Watchlist
from app.services.futures import refresh_signals_cache
from sqlalchemy import select
from app.services.locks import LockService

try:
    from redis.asyncio import Redis  # type: ignore
except Exception:  # pragma: no cover
    Redis = None  # type: ignore


async def main():
    ap = argparse.ArgumentParser(description="Refresh Futures signals cache for symbols")
    ap.add_argument("--symbols", nargs="*", help="Symbols to refresh (default: all from active analyses & watchlist)")
    args = ap.parse_args()

    # Try Redis-based distributed lock first
    rcli = None
    if Redis is not None:
        try:
            rcli = Redis.from_url(os.getenv("REDIS_URL", "redis://localhost:6379/0"))
        except Exception:
            rcli = None
    locks = LockService(rcli)
    got = await locks.acquire("job:futures_refresh", ttl=180)
    if not got:
        print("Another futures_refresh is running (redis lock).")
        return

    lock_path = "/tmp/autoanalisa_futures_refresh.lock"
    with open(lock_path, "w") as lf:
        try:
            fcntl.flock(lf, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            print("Another futures_refresh is running (filelock).")
            await locks.release("job:futures_refresh")
            return

        db_url = getattr(settings, "DATABASE_URL", None) or settings.SQLITE_URL
        kwargs = {"echo": False, "future": True}
        if db_url.startswith("sqlite+"):
            kwargs["connect_args"] = {"timeout": 15}
        else:
            kwargs["pool_pre_ping"] = True
            kwargs["pool_recycle"] = 1800
        engine = create_async_engine(db_url, **kwargs)
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        Session = async_sessionmaker(engine, expire_on_commit=False)
        async with Session() as db:
            symbols = set([s.upper() for s in (args.symbols or [])])
            if not symbols:
                # collect from active analyses & watchlist
                q1 = await db.execute(select(Analysis.symbol).where(Analysis.status == "active"))
                for (sym,) in q1.all():
                    symbols.add(sym.upper())
                try:
                    q2 = await db.execute(select(Watchlist.symbol))
                    for (sym,) in q2.all():
                        symbols.add(sym.upper())
                except Exception:
                    pass
            if not symbols:
                symbols = {"BTCUSDT"}
            for sym in sorted(symbols):
                try:
                    row = await refresh_signals_cache(db, sym)
                    print(f"OK refreshed {sym} at {row.created_at}")
                except Exception as e:
                    print(f"ERR refreshing {sym}: {e}")
        # release redis lock
        await locks.release("job:futures_refresh")


if __name__ == "__main__":
    asyncio.run(main())
