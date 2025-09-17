#!/usr/bin/env python3
import asyncio
import argparse
import fcntl
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from app.config import settings
from app.models import Base, Analysis, Watchlist
from app.services.futures import refresh_signals_cache
from sqlalchemy import select


async def main():
    ap = argparse.ArgumentParser(description="Refresh Futures signals cache for symbols")
    ap.add_argument("--symbols", nargs="*", help="Symbols to refresh (default: all from active analyses & watchlist)")
    args = ap.parse_args()

    lock_path = "/tmp/autoanalisa_futures_refresh.lock"
    with open(lock_path, "w") as lf:
        try:
            fcntl.flock(lf, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            print("Another futures_refresh is running.")
            return

        engine = create_async_engine(settings.SQLITE_URL, echo=False, future=True)
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


if __name__ == "__main__":
    asyncio.run(main())

