from fastapi import APIRouter, Depends, HTTPException
from app.deps import get_db
from app.auth import require_user
from app.main import locks
from app.services.market import fetch_klines
from app.services.symbols_binance import get_symbols

router = APIRouter(prefix="/api", tags=["market"])


@router.get("/ohlcv")
async def ohlcv(symbol: str, tf: str = "15m", limit: int = 200, market: str = "spot", user=Depends(require_user), db=Depends(get_db)):
    # rate limit sederhana: 3 detik per user+symbol+tf
    key = f"rate:ohlcv:{user.id}:{symbol}:{tf}:{market}"
    ok = await locks.acquire(key, ttl=3)
    if not ok:
        raise HTTPException(429, "Terlalu sering, coba sebentar lagi.")
    try:
        try:
            df = await fetch_klines(symbol, tf, limit, market=market)
        except TypeError:
            df = await fetch_klines(symbol, tf, limit)
    except Exception as e:  # pragma: no cover
        raise HTTPException(400, f"Failed to fetch OHLCV: {e}")
    out = [
        {
            "t": int(row.ts),
            "o": float(row.open),
            "h": float(row.high),
            "l": float(row.low),
            "c": float(row.close),
            "v": float(row.volume),
        }
        for _, row in df.iterrows()
    ]
    return out


@router.get("/symbols/{kind}")
async def symbols(kind: str):
    kind_norm = kind.lower()
    if kind_norm not in {"spot", "futures"}:
        raise HTTPException(400, "kind harus spot atau futures")
    try:
        symbols = get_symbols(kind_norm)
    except Exception as e:
        raise HTTPException(500, f"Gagal memuat simbol: {e}")
    return {"ok": True, "kind": kind_norm, "symbols": symbols}
