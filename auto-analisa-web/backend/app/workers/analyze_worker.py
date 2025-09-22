from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from ..services.market import fetch_bundle
from ..services.rules import Features, score_symbol
from ..services.planner import build_plan_async, build_spot2_from_plan
from ..services.budget import (
    get_or_init_settings,
)
from ..services.rounding import round_plan_prices
from ..models import Analysis, User
from datetime import datetime, timezone
import json
import os


MAX_ACTIVE_CARDS: dict[str, int] = {"spot": 4, "futures": 4}


def _normalize_trade_type(value: str | None) -> str:
    try:
        if str(value).lower() == "futures":
            return "futures"
    except Exception:
        pass
    return "spot"


async def run_analysis(db: AsyncSession, user: User, symbol: str, trade_type: str = "spot") -> Analysis:
    # Check if analysis for this symbol already exists (active)
    sym = symbol.upper()
    tt = _normalize_trade_type(trade_type)
    q_exist = await db.execute(
        select(Analysis).where(
            Analysis.user_id == user.id,
            Analysis.symbol == sym,
            func.coalesce(Analysis.trade_type, "spot") == tt,
        )
    )
    existing = q_exist.scalar_one_or_none()

    # Enforce max 4 active analyses only when creating new symbol
    if not existing:
        limit = MAX_ACTIVE_CARDS.get(tt, MAX_ACTIVE_CARDS["spot"])
        q = await db.execute(
            select(func.count()).select_from(Analysis).where(
                Analysis.user_id == user.id,
                Analysis.status == "active",
                func.coalesce(Analysis.trade_type, "spot") == tt,
            )
        )
        active_cnt = q.scalar_one()
        if active_cnt >= limit:
            label = "Futures" if tt == "futures" else "Spot"
            raise HTTPException(
                409,
                f"Maksimum {limit} analisa aktif {label} per user. Arsipkan salah satu dulu.",
            )

    # compute baseline plan using existing rules engine
    bundle = await fetch_bundle(
        symbol,
        ("4h", "1h", "15m", "5m"),
        market=("futures" if tt == "futures" else "spot"),
    )
    feat = Features(bundle).enrich()
    score = score_symbol(feat)
    plan = await build_plan_async(db, bundle, feat, score, "auto")
    try:
        spot2 = await build_spot2_from_plan(db, sym, plan, bundle=bundle)
        plan["spot2"] = spot2
    except Exception:
        pass
    # Snap prices to tick size if available
    try:
        plan = round_plan_prices(sym, plan)
    except Exception:
        pass

    # No auto LLM narrative: keep rules-only plan per blueprint

    # save analysis
    # compute next version per user+symbol
    q2 = await db.execute(
        select(func.max(Analysis.version)).where(
            Analysis.user_id == user.id,
            Analysis.symbol == sym,
            func.coalesce(Analysis.trade_type, "spot") == tt,
        )
    )
    ver = (q2.scalar_one() or 0) + 1

    # If a row already exists for this user+symbol (unique), update it; else insert
    if existing:
        existing.version = ver
        existing.payload_json = plan
        existing.status = "active"
        existing.trade_type = tt
        # bump timestamp so FE shows fresh time
        existing.created_at = datetime.now(timezone.utc)
        a = existing
    else:
        a = Analysis(
            user_id=user.id,
            symbol=sym,
            trade_type=tt,
            version=ver,
            payload_json=plan,
            status="active",
        )
        db.add(a)
    await db.commit()
    await db.refresh(a)
    return a


async def refresh_analysis_rules_only(db: AsyncSession, user: User, analysis: Analysis) -> Analysis:
    """Recompute plan using rules engine only (no LLM), bump version and timestamp."""
    sym = analysis.symbol.upper()
    tt = _normalize_trade_type(getattr(analysis, "trade_type", "spot"))
    bundle = await fetch_bundle(
        sym,
        ("4h", "1h", "15m", "5m"),
        market=("futures" if tt == "futures" else "spot"),
    )
    feat = Features(bundle).enrich()
    score = score_symbol(feat)
    plan = await build_plan_async(db, bundle, feat, score, "auto")
    try:
        spot2 = await build_spot2_from_plan(db, sym, plan, bundle=bundle)
        plan["spot2"] = spot2
    except Exception:
        pass
    try:
        plan = round_plan_prices(sym, plan)
    except Exception:
        pass

    # compute next version per user+symbol and update
    q2 = await db.execute(
        select(func.max(Analysis.version)).where(
            Analysis.user_id == user.id,
            Analysis.symbol == sym,
            func.coalesce(Analysis.trade_type, "spot") == tt,
        )
    )
    ver = (q2.scalar_one() or 0) + 1
    analysis.version = ver
    analysis.payload_json = plan
    analysis.created_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(analysis)
    return analysis
