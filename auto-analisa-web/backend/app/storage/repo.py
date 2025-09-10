from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from ..models import Plan


async def save_plan(db: AsyncSession, user_id: str, symbol: str, payload: dict) -> Plan:
    q = await db.execute(
        select(func.max(Plan.version)).where(Plan.user_id == user_id, Plan.symbol == symbol)
    )
    ver = (q.scalar() or 0) + 1
    p = Plan(user_id=user_id, symbol=symbol, version=ver, payload_json=payload)
    db.add(p)
    await db.commit()
    await db.refresh(p)
    return p


async def get_plan(db: AsyncSession, plan_id: int) -> Plan | None:
    return await db.get(Plan, plan_id)

