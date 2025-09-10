from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from ..services.market import fetch_bundle
from ..services.rules import Features, score_symbol
from ..services.planner import build_plan
from ..services.llm import ask_llm
from ..services.budget import (
    get_or_init_settings,
    add_usage,
    check_budget_and_maybe_off,
)
from ..models import Analysis, User
import json
import os


MAX_ACTIVE_CARDS = 4


async def run_analysis(db: AsyncSession, user: User, symbol: str) -> Analysis:
    # enforce max 4 active analyses per user
    q = await db.execute(
        select(func.count()).select_from(Analysis).where(
            Analysis.user_id == user.id, Analysis.status == "active"
        )
    )
    active_cnt = q.scalar_one()
    if active_cnt >= MAX_ACTIVE_CARDS:
        raise HTTPException(409, "Maksimum 4 analisa aktif per user. Arsipkan salah satu dulu.")

    # compute baseline plan using existing rules engine
    bundle = await fetch_bundle(symbol, ("4h", "1h", "15m"))
    feat = Features(bundle).enrich()
    score = score_symbol(feat)
    plan = build_plan(bundle, feat, score, "auto")

    # ask LLM for narrative if enabled
    s = await get_or_init_settings(db)
    if s.use_llm and os.getenv("OPENAI_API_KEY"):
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

    # save analysis
    # compute next version per user+symbol
    q2 = await db.execute(
        select(func.max(Analysis.version)).where(
            Analysis.user_id == user.id, Analysis.symbol == symbol.upper()
        )
    )
    ver = (q2.scalar_one() or 0) + 1
    a = Analysis(
        user_id=user.id,
        symbol=symbol.upper(),
        version=ver,
        payload_json=plan,
        status="active",
    )
    db.add(a)
    await db.commit()
    await db.refresh(a)
    return a
