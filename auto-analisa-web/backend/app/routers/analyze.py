import json
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.deps import get_db
from app.routers.auth import get_user_from_auth
from app.schemas import AnalyzeIn
from app.workers.analyze_worker import run_analysis
from app.models import Analysis
from sqlalchemy import update


router = APIRouter(prefix="/api", tags=["analyze"])


@router.post("/analyze")
async def analyze(payload: AnalyzeIn, db: AsyncSession = Depends(get_db), user=Depends(get_user_from_auth)):
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
async def archive(analysis_id: int, db: AsyncSession = Depends(get_db), user=Depends(get_user_from_auth)):
    # set status to archived only for owner's analysis
    await db.execute(
        update(Analysis).where(Analysis.id == analysis_id, Analysis.user_id == user.id).values(status="archived")
    )
    await db.commit()
    return {"ok": True}
