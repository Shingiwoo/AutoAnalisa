import os
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models import Settings, ApiUsage


def month_key(dt: datetime | None = None) -> str:
    dt = dt or datetime.utcnow()
    return f"{dt.year:04d}-{dt.month:02d}"


async def get_or_init_settings(db: AsyncSession) -> Settings:
    q = await db.execute(select(Settings))
    s = q.scalar_one_or_none()
    if s:
        return s
    s = Settings(
        use_llm=(os.getenv("USE_LLM", "true").lower() == "true"),
        registration_enabled=(os.getenv("REGISTRATION_ENABLED", "true").lower() == "true"),
        input_usd_per_1k=float(os.getenv("OPENAI_INPUT_USD_PER_1K", "0.005")),
        output_usd_per_1k=float(os.getenv("OPENAI_OUTPUT_USD_PER_1K", "0.015")),
        budget_monthly_usd=float(os.getenv("LLM_BUDGET_MONTHLY_USD", "20")),
        auto_off_at_budget=(os.getenv("LLM_AUTO_OFF_AT_BUDGET", "true").lower() == "true"),
    )
    db.add(s)
    await db.commit()
    await db.refresh(s)
    return s


async def add_usage(
    db: AsyncSession,
    user_id: str,
    model: str,
    prompt_toks: int,
    completion_toks: int,
    in_usd_per_1k: float,
    out_usd_per_1k: float,
):
    usd = (prompt_toks / 1000.0) * in_usd_per_1k + (completion_toks / 1000.0) * out_usd_per_1k
    # record usage row
    row = ApiUsage(
        user_id=user_id,
        model=model,
        prompt_tokens=prompt_toks,
        completion_tokens=completion_toks,
        usd_cost=usd,
        month_key=month_key(),
    )
    db.add(row)
    # update settings.budget_used_usd to current-month sum (auto-reset monthly)
    mk = month_key()
    from sqlalchemy import select, func
    q = await db.execute(select(func.sum(ApiUsage.usd_cost)).where(ApiUsage.month_key == mk))
    month_total = float(q.scalar() or 0.0)
    s = await get_or_init_settings(db)
    s.budget_used_usd = month_total
    await db.commit()
    return usd, s.budget_used_usd


async def check_budget_and_maybe_off(db: AsyncSession) -> bool:
    """Return True if LLM turned off due to monthly limit reached.
    Ensures check uses current-month spend, not cumulative.
    """
    from sqlalchemy import select, func
    s = await get_or_init_settings(db)
    mk = month_key()
    q = await db.execute(select(func.sum(ApiUsage.usd_cost)).where(ApiUsage.month_key == mk))
    month_total = float(q.scalar() or 0.0)
    # keep settings in sync for UI
    s.budget_used_usd = month_total
    if s.auto_off_at_budget and month_total >= s.budget_monthly_usd:
        s.use_llm = False
        await db.commit()
        return True
    await db.commit()
    return False
