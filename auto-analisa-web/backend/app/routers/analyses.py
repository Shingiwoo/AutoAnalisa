from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.deps import get_db
from app.auth import require_user
from app.models import Analysis, Plan

router = APIRouter(prefix="/api/analyses", tags=["analyses"])


@router.get("")
async def list_analyses(status: str = "active", db: AsyncSession = Depends(get_db), user=Depends(require_user)):
    if status == "active":
        q = await db.execute(
            select(Analysis).where(Analysis.user_id == user.id, Analysis.status == "active").order_by(Analysis.created_at.desc())
        )
        rows = q.scalars().all()
        return [
            {
                "id": r.id,
                "symbol": r.symbol,
                "version": r.version,
                "payload": r.payload_json,
                "created_at": r.created_at,
            }
            for r in rows
        ]
    else:
        q = await db.execute(
            select(Plan).where(Plan.user_id == user.id).order_by(Plan.created_at.desc())
        )
        rows = q.scalars().all()
        return [
            {
                "id": r.id,
                "symbol": r.symbol,
                "version": r.version,
                "payload": r.payload_json,
                "created_at": r.created_at,
            }
            for r in rows
        ]


@router.post("/{aid}/save")
async def save_snapshot(aid: int, db: AsyncSession = Depends(get_db), user=Depends(require_user)):
    a = await db.get(Analysis, aid)
    if not a or a.user_id != user.id:
        raise HTTPException(404, "Not found")
    # Create a snapshot in Plan table and keep current Analysis active
    snap = Plan(user_id=user.id, symbol=a.symbol, version=a.version, payload_json=a.payload_json)
    db.add(snap)
    await db.commit()
    return {"ok": True, "active_id": a.id}
