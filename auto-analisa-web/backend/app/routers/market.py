from fastapi import APIRouter, Depends, HTTPException
from app.deps import get_db
from app.routers.auth import get_user_from_auth
from app.services.market import fetch_klines

router = APIRouter(prefix="/api", tags=["market"])


@router.get("/ohlcv")
async def ohlcv(symbol: str, tf: str = "15m", limit: int = 200, user=Depends(get_user_from_auth), db=Depends(get_db)):
    try:
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

