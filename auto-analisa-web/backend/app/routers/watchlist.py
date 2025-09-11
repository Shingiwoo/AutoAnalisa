from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
from app.deps import get_db
from app.auth import require_user
from app.models import Watchlist, Plan, Analysis

router = APIRouter(prefix="/api/watchlist", tags=["watchlist"])

MAX_WATCH = 4


@router.get("")
async def get_list(db: AsyncSession = Depends(get_db), user=Depends(require_user)):
    q = await db.execute(select(Watchlist).where(Watchlist.user_id == user.id).order_by(Watchlist.created_at.asc()))
    rows = q.scalars().all()
    return [r.symbol for r in rows]


@router.post("/add")
async def add(symbol: str, db: AsyncSession = Depends(get_db), user=Depends(require_user)):
    sym = symbol.upper()
    q = await db.execute(select(Watchlist).where(Watchlist.user_id == user.id))
    cnt = len(q.scalars().all())
    if cnt >= MAX_WATCH:
        raise HTTPException(429, "Watchlist penuh (4). Hapus dulu item lain.")
    q2 = await db.execute(select(Watchlist).where(Watchlist.user_id == user.id, Watchlist.symbol == sym))
    if q2.scalar_one_or_none() is None:
        db.add(Watchlist(user_id=user.id, symbol=sym))
        await db.commit()
    return {"ok": True}


@router.delete("/{symbol}")
async def remove(symbol: str, db: AsyncSession = Depends(get_db), user=Depends(require_user)):
    sym = symbol.upper()
    # Hapus dari watchlist
    await db.execute(
        delete(Watchlist).where(Watchlist.user_id == user.id, Watchlist.symbol == sym)
    )
    # Sekaligus bersihkan arsip/snapshot terkait simbol ini milik user
    await db.execute(
        delete(Plan).where(Plan.user_id == user.id, Plan.symbol == sym)
    )
    # Jika ada Analysis yang berstatus archived untuk simbol ini, bersihkan juga
    await db.execute(
        delete(Analysis).where(Analysis.user_id == user.id, Analysis.symbol == sym, Analysis.status == "archived")
    )
    await db.commit()
    return {"ok": True}
