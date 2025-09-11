from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from ..services.market import fetch_bundle
from ..services.rules import Features, score_symbol
from ..services.planner import build_plan
from ..services.llm import ask_llm, should_use_llm
from ..services.budget import (
    get_or_init_settings,
    add_usage,
    check_budget_and_maybe_off,
)
from ..models import Analysis, User
from datetime import datetime
import json
import os


MAX_ACTIVE_CARDS = 4


async def run_analysis(db: AsyncSession, user: User, symbol: str) -> Analysis:
    # Check if analysis for this symbol already exists (active)
    sym = symbol.upper()
    q_exist = await db.execute(
        select(Analysis).where(Analysis.user_id == user.id, Analysis.symbol == sym)
    )
    existing = q_exist.scalar_one_or_none()

    # Enforce max 4 active analyses only when creating new symbol
    if not existing:
        q = await db.execute(
            select(func.count()).select_from(Analysis).where(
                Analysis.user_id == user.id, Analysis.status == "active"
            )
        )
        active_cnt = q.scalar_one()
        if active_cnt >= MAX_ACTIVE_CARDS:
            raise HTTPException(409, "Maksimum 4 analisa aktif per user. Arsipkan salah satu dulu.")

    # compute baseline plan using existing rules engine
    bundle = await fetch_bundle(symbol, ("4h", "1h", "15m", "5m"))
    feat = Features(bundle).enrich()
    score = score_symbol(feat)
    plan = build_plan(bundle, feat, score, "auto")

    # ask LLM for narrative if enabled
    s = await get_or_init_settings(db)
    use_llm, reason = await should_use_llm(db)
    if use_llm and os.getenv("OPENAI_API_KEY"):
        try:
            prompt = (
                "Buat narasi ringkas (2-3 kalimat) berdasarkan data berikut dalam bahasa Indonesia. "
                "Fokus pada bias, alasan utama, dan peringatan risk.\n"
                f"DATA: {json.dumps(plan, ensure_ascii=False)}"
            )
            text, usage = ask_llm(prompt)
            plan["narrative"] = (plan.get("narrative", "") + "\n" + text.strip()).strip()
            # record cost
            await add_usage(
                db,
                user.id,
                os.getenv("OPENAI_MODEL", "gpt-5"),
                int(usage.get("prompt_tokens", 0)),
                int(usage.get("completion_tokens", 0)),
                s.input_usd_per_1k,
                s.output_usd_per_1k,
            )
            # auto-off if budget reached
            if await check_budget_and_maybe_off(db):
                plan["notice"] = "LLM otomatis dimatikan karena budget bulanan tercapai."
        except Exception as e:  # pragma: no cover
            msg = str(e).lower()
            if "insufficient_quota" in msg or " 429" in msg or "rate limit" in msg:
                # Matikan LLM agar tidak terus error, beri notifikasi ramah pengguna
                s.use_llm = False
                await db.commit()
                plan["notice"] = (
                    "LLM dinonaktifkan sementara: kuota OpenAI habis atau kena rate limit. "
                    "Admin dapat menambah kredit/limit lalu mengaktifkan kembali di halaman Admin."
                )
                # Jangan bocorkan detail error ke pengguna akhir
                plan["narrative"] = (
                    plan.get("narrative", "")
                    + "\n[Narasi otomatis] LLM sementara tidak tersedia; gunakan rencana berbasis aturan."
                ).strip()
            else:
                plan["narrative"] = (
                    plan.get("narrative", "") + "\n[LLM fallback] Terjadi kendala pada LLM; gunakan hasil aturan."
                ).strip()
    elif not use_llm and reason:
        # record user-friendly notice when LLM disabled upfront
        plan["notice"] = (
            "LLM dinonaktifkan: " + reason.replace("LLM ", "").capitalize()
        )

    # save analysis
    # compute next version per user+symbol
    q2 = await db.execute(
        select(func.max(Analysis.version)).where(
            Analysis.user_id == user.id, Analysis.symbol == sym
        )
    )
    ver = (q2.scalar_one() or 0) + 1

    # If a row already exists for this user+symbol (unique), update it; else insert
    if existing:
        existing.version = ver
        existing.payload_json = plan
        existing.status = "active"
        # bump timestamp so FE shows fresh time
        existing.created_at = datetime.utcnow()
        a = existing
    else:
        a = Analysis(
            user_id=user.id,
            symbol=sym,
            version=ver,
            payload_json=plan,
            status="active",
        )
        db.add(a)
    await db.commit()
    await db.refresh(a)
    return a
