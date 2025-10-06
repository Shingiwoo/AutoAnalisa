from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.deps import get_db
from app.auth import require_user
from app.models import JournalEntry
import datetime as dt


router = APIRouter(prefix="/api/journal", tags=["journal"])


def _serialize(e: JournalEntry) -> dict:
    return {
        "id": e.id,
        "title": e.title,
        "content": e.content,
        "created_at": e.created_at,
        "updated_at": e.updated_at,
    }


@router.get("")
async def list_entries(db: AsyncSession = Depends(get_db), user=Depends(require_user)):
    q = await db.execute(
        select(JournalEntry).where(JournalEntry.user_id == user.id).order_by(JournalEntry.created_at.desc())
    )
    rows = q.scalars().all()
    return [_serialize(r) for r in rows]


@router.post("")
async def create_entry(payload: dict, db: AsyncSession = Depends(get_db), user=Depends(require_user)):
    title = str(payload.get("title") or "").strip()
    content = str(payload.get("content") or "")
    e = JournalEntry(user_id=user.id, title=title, content=content)
    db.add(e)
    await db.commit()
    await db.refresh(e)
    return _serialize(e)


@router.get("/{eid}")
async def get_entry(eid: int, db: AsyncSession = Depends(get_db), user=Depends(require_user)):
    e = await db.get(JournalEntry, eid)
    if not e or e.user_id != user.id:
        raise HTTPException(404, "Not found")
    return _serialize(e)


@router.put("/{eid}")
async def update_entry(eid: int, payload: dict, db: AsyncSession = Depends(get_db), user=Depends(require_user)):
    e = await db.get(JournalEntry, eid)
    if not e or e.user_id != user.id:
        raise HTTPException(404, "Not found")
    if "title" in payload:
        e.title = str(payload.get("title") or "").strip()
    if "content" in payload:
        e.content = str(payload.get("content") or "")
    e.updated_at = dt.datetime.now(dt.timezone.utc)
    await db.commit()
    await db.refresh(e)
    return _serialize(e)


@router.delete("/{eid}")
async def delete_entry(eid: int, db: AsyncSession = Depends(get_db), user=Depends(require_user)):
    e = await db.get(JournalEntry, eid)
    if not e or e.user_id != user.id:
        raise HTTPException(404, "Not found")
    await db.delete(e)
    await db.commit()
    return {"ok": True}

