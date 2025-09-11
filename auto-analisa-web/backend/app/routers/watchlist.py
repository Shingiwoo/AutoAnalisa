from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
from app.deps import get_db
from app.routers.auth import get_user_from_auth
from app.models import Watchlist

router = APIRouter(prefix="/api/watchlist", tags=["watchlist"])

MAX_WATCH = 4


@router.get("")
async def get_list(db: AsyncSession = Depends(get_db), user=Depends(get_user_from_auth)):
    q = await db.execute(select(Watchlist).where(Watchlist.user_id == user.id).order_by(Watchlist.created_at.asc()))
    rows = q.scalars().all()
    return [r.symbol for r in rows]


@router.post("/add")
async def add(symbol: str, db: AsyncSession = Depends(get_db), user=Depends(get_user_from_auth)):
    sym = symbol.upper()
    q = await db.execute(select(Watchlist).where(Watchlist.user_id == user.id))
    cnt = len(q.scalars().all())
    if cnt >= MAX_WATCH:
        raise HTTPException(400, "Limit 4 symbols per user")
    q2 = await db.execute(select(Watchlist).where(Watchlist.user_id == user.id, Watchlist.symbol == sym))
    if q2.scalar_one_or_none() is None:
        db.add(Watchlist(user_id=user.id, symbol=sym))
        await db.commit()
    return {"ok": True}


@router.delete("/{symbol}")
async def remove(symbol: str, db: AsyncSession = Depends(get_db), user=Depends(get_user_from_auth)):
    sym = symbol.upper()
    await db.execute(
        delete(Watchlist).where(Watchlist.user_id == user.id, Watchlist.symbol == sym)
    )
    await db.commit()
    return {"ok": True}
