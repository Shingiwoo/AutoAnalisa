import json
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.deps import get_db
from app.auth import require_user
from app.schemas import AnalyzeIn
from app.workers.analyze_worker import run_analysis
from app.models import Analysis
from sqlalchemy import update
from app.main import locks


router = APIRouter(prefix="/api", tags=["analyze"])


@router.post("/analyze")
async def analyze(payload: AnalyzeIn, db: AsyncSession = Depends(get_db), user=Depends(require_user)):
    # rate limit sederhana: 1 permintaan/2 detik per user
    ok = await locks.acquire(f"rate:analyze:{user.id}", ttl=2)
    if not ok:
        raise HTTPException(429, "Terlalu sering, coba lagi sebentar.")
    a = await run_analysis(db, user, payload.symbol)
    return {
        "id": a.id,
        "user_id": a.user_id,
        "symbol": a.symbol,
        "version": a.version,
        "payload": a.payload_json,
        "created_at": a.created_at.isoformat(),
    }


@router.post("/archive/{analysis_id}")
async def archive(analysis_id: int, db: AsyncSession = Depends(get_db), user=Depends(require_user)):
    # set status to archived only for owner's analysis
    await db.execute(
        update(Analysis).where(Analysis.id == analysis_id, Analysis.user_id == user.id).values(status="archived")
    )
    await db.commit()
    return {"ok": True}
