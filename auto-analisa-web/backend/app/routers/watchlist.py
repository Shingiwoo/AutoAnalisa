from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
from app.deps import get_db
from app.auth import require_user
from app.models import Watchlist, Plan, Analysis

router = APIRouter(prefix="/api/watchlist", tags=["watchlist"])

MAX_WATCH = 4


@router.get("")
async def get_list(db: AsyncSession = Depends(get_db), user=Depends(require_user), trade_type: str = Query("spot")):
    tt = (trade_type or "spot").lower()
    if tt not in {"spot", "futures"}:
        tt = "spot"
    q = await db.execute(select(Watchlist).where(Watchlist.user_id == user.id, Watchlist.trade_type == tt).order_by(Watchlist.created_at.asc()))
    rows = q.scalars().all()
    return [r.symbol for r in rows]


@router.post("/add")
async def add(symbol: str, db: AsyncSession = Depends(get_db), user=Depends(require_user), trade_type: str = Query("spot")):
    sym = symbol.upper()
    tt = (trade_type or "spot").lower()
    if tt not in {"spot", "futures"}:
        tt = "spot"
    q = await db.execute(select(Watchlist).where(Watchlist.user_id == user.id, Watchlist.trade_type == tt))
    cnt = len(q.scalars().all())
    if cnt >= MAX_WATCH:
        raise HTTPException(429, "Watchlist penuh (4). Hapus dulu item lain.")
    q2 = await db.execute(select(Watchlist).where(Watchlist.user_id == user.id, Watchlist.symbol == sym, Watchlist.trade_type == tt))
    if q2.scalar_one_or_none() is None:
        db.add(Watchlist(user_id=user.id, symbol=sym, trade_type=tt))
        await db.commit()
    return {"ok": True}


@router.delete("/{symbol}")
async def remove(symbol: str, db: AsyncSession = Depends(get_db), user=Depends(require_user), trade_type: str = Query("spot")):
    sym = symbol.upper()
    tt = (trade_type or "spot").lower()
    if tt not in {"spot", "futures"}:
        tt = "spot"
    # Hapus dari watchlist tipe terkait
    await db.execute(
        delete(Watchlist).where(Watchlist.user_id == user.id, Watchlist.symbol == sym, Watchlist.trade_type == tt)
    )
    # Bersihkan arsip/snapshot untuk trade_type terkait saja
    await db.execute(
        delete(Plan).where(Plan.user_id == user.id, Plan.symbol == sym, Plan.trade_type == tt)
    )
    await db.execute(
        delete(Analysis).where(Analysis.user_id == user.id, Analysis.symbol == sym, Analysis.trade_type == tt)
    )
    await db.commit()
    return {"ok": True}
