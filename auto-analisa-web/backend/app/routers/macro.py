from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from app.deps import get_db
from app.models import MacroDaily
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

router = APIRouter(prefix="/api/macro", tags=["macro"])


@router.get("/today")
async def today(db: AsyncSession = Depends(get_db), slot: str | None = Query(None)):
    jkt = ZoneInfo("Asia/Jakarta")
    now_wib = datetime.now(timezone.utc).astimezone(jkt)
    slot = (slot or ("pagi" if now_wib.hour < 12 else "malam")).lower()
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    q = await db.execute(select(MacroDaily).where(MacroDaily.date_utc == today, MacroDaily.slot == slot))
    row = q.scalar_one_or_none()
    if not row:
        # fallback latest available
        q2 = await db.execute(select(MacroDaily).order_by(desc(MacroDaily.created_at)))
        row = q2.scalar_one_or_none()
        if not row:
            return {"date": today, "date_wib": now_wib.date().isoformat(), "slot": slot, "narrative": "", "sources": "", "sections": []}
    # Also provide date_wib for UI convenience
    try:
        jkt = ZoneInfo("Asia/Jakarta")
        dt_utc = datetime.fromisoformat(row.date_utc).replace(tzinfo=timezone.utc)
        date_wib = dt_utc.astimezone(jkt).date().isoformat()
    except Exception:
        date_wib = row.date_utc
    # Include status dan cap waktu terakhir untuk panel status di FE
    try:
        created_wib = row.created_at.astimezone(ZoneInfo("Asia/Jakarta")).isoformat()
    except Exception:
        try:
            created_wib = row.created_at.isoformat()
        except Exception:
            created_wib = None
    return {
        "date": row.date_utc,
        "date_wib": date_wib,
        "slot": getattr(row, "slot", slot),
        "narrative": row.narrative,
        "sources": row.sources,
        "sections": getattr(row, "sections", []),
        "last_run_status": getattr(row, "last_run_status", None),
        "created_at": row.created_at,
        "last_run_wib": created_wib,
    }
