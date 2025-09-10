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
    db.add(
        ApiUsage(
            user_id=user_id,
            model=model,
            prompt_tokens=prompt_toks,
            completion_tokens=completion_toks,
            usd_cost=usd,
            month_key=month_key(),
        )
    )
    s = await get_or_init_settings(db)
    s.budget_used_usd += usd
    await db.commit()
    return usd, s.budget_used_usd


async def check_budget_and_maybe_off(db: AsyncSession) -> bool:
    s = await get_or_init_settings(db)
    if s.auto_off_at_budget and s.budget_used_usd >= s.budget_monthly_usd:
        s.use_llm = False
        await db.commit()
        return True
    return False

