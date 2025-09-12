from __future__ import annotations
from datetime import datetime, timezone
from uuid import uuid4
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import LLMUsage
from app.config import settings


def _today_utc():
    return datetime.now(timezone.utc).date()


def _month_str(d):
    return f"{d.year:04d}-{d.month:02d}"


async def inc_usage(
    db: AsyncSession,
    *,
    user_id: str,
    model: str,
    input_tokens: int,
    output_tokens: int,
    cost_usd: float,
    add_call: bool = True,
) -> None:
    today = _today_utc()
    month = _month_str(today)

    q = select(LLMUsage).where(LLMUsage.user_id == user_id, LLMUsage.day == today)
    row = (await db.execute(q)).scalar_one_or_none()

    if row is None:
        row = LLMUsage(
            id=str(uuid4()),
            user_id=user_id,
            day=today,
            month=month,
            model=model,
            calls=0,
            input_tokens=0,
            output_tokens=0,
            cost_usd=0.0,
        )
        db.add(row)
        await db.flush()

    if add_call:
        row.calls = int(row.calls or 0) + 1
    row.input_tokens = int(row.input_tokens or 0) + int(input_tokens or 0)
    row.output_tokens = int(row.output_tokens or 0) + int(output_tokens or 0)
    row.cost_usd = float(row.cost_usd or 0.0) + float(cost_usd or 0.0)


async def get_today_usage(db: AsyncSession, *, user_id: str) -> dict:
    today = _today_utc()
    q = select(LLMUsage).where(LLMUsage.user_id == user_id, LLMUsage.day == today)
    row = (await db.execute(q)).scalar_one_or_none()
    calls = int(row.calls) if row else 0
    limit = int(getattr(settings, "LLM_DAILY_LIMIT", 40) or 40)
    return {"calls": calls, "limit": limit, "remaining": max(0, limit - calls)}


async def get_monthly_spend(db: AsyncSession) -> float:
    month = _month_str(_today_utc())
    q = select(LLMUsage.cost_usd).where(LLMUsage.month == month)
    rows = (await db.execute(q)).scalars().all()
    return float(sum(rows or []))

