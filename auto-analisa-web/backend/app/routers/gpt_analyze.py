from __future__ import annotations
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from typing import Any, Dict, Optional, Literal
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
import datetime as dt

from app.deps import get_db
from app.auth import require_user
from app.services.gpt_service import build_prompt, call_gpt
from app.services.preprompt import evaluate_pre_signal
from app.services.llm import should_use_llm
from app.services.usage import get_today_usage, inc_usage
from app.services.budget import get_or_init_settings
from app.models import GPTReport
import os

def _utcnow() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)

def _get_mode_ttl(mode: Literal["scalping","swing"]) -> int:
    """
    TTL default per mode, overrideable via env:
    GPT_TTL_SCALPING_SECONDS (default 7200 = 2 jam)
    GPT_TTL_SWING_SECONDS   (default 43200 = 12 jam)
    """
    if mode == "swing":
        return int(os.getenv("GPT_TTL_SWING_SECONDS", 43200) or 43200)
    return int(os.getenv("GPT_TTL_SCALPING_SECONDS", 7200) or 7200)


class AnalyzeBody(BaseModel):
    symbol: str
    mode: Literal['scalping', 'swing'] = Field('scalping')
    payload: Dict[str, Any]
    opts: Optional[Dict[str, Any]] = None


router = APIRouter(prefix="/api/gpt/futures", tags=["gpt-futures"])


@router.get("/report")
async def get_latest_report(
    symbol: str,
    mode: Literal["scalping", "swing"] = "scalping",
    nocache: int = Query(0, ge=0, le=1),
    db: AsyncSession = Depends(get_db),
    user=Depends(require_user),
):
    sym = symbol.upper()
    if nocache:
        raise HTTPException(
            404, detail={"error_code": "nocache", "message": "Cache dilewati"}
        )
    stmt = (
        select(GPTReport)
        .where(GPTReport.symbol == sym, GPTReport.mode == mode)
        .order_by(GPTReport.created_at.desc())
    )
    res = await db.execute(stmt)
    item = res.scalars().first()
    if not item:
        raise HTTPException(
            404, detail={"error_code": "report_not_found", "message": "Belum ada report"}
        )
    # Hormati TTL yang tersimpan; jika kosong gunakan TTL per mode
    ttl = int(getattr(item, "ttl", 0) or 0) or _get_mode_ttl(mode)
    created = getattr(item, "created_at", None) or _utcnow()
    if created.tzinfo is None:
        created = created.replace(tzinfo=dt.timezone.utc)
    if created + dt.timedelta(seconds=ttl) < _utcnow():
        raise HTTPException(
            404, detail={"error_code": "report_expired", "message": "Report kedaluwarsa"}
        )
    return {
        "report_id": item.id,
        "symbol": item.symbol,
        "mode": item.mode,
        "text": item.text or {},
        "overlay": item.overlay or {},
        "meta": item.meta or {},
        "created_at": created.isoformat(),
        "ttl": ttl,
    }


@router.post("/analyze")
async def gpt_analyze(body: AnalyzeBody, db: AsyncSession = Depends(get_db), user=Depends(require_user)):
    sym = body.symbol.upper()
    allowed, reason = await should_use_llm(db)
    if not allowed:
        raise HTTPException(409, detail={"error_code": "llm_disabled", "message": reason or "LLM nonaktif"})
    if not os.getenv("OPENAI_API_KEY"):
        raise HTTPException(409, detail={"error_code": "server_config", "message": "OPENAI_API_KEY belum diisi"})
    sset = await get_or_init_settings(db)
    limit = int(getattr(sset, "llm_daily_limit_futures", 40) or 40)
    today = await get_today_usage(db, user_id=user.id, kind="futures", limit_override=limit)
    if today["remaining"] <= 0:
        raise HTTPException(409, detail={"error_code": "quota_exceeded", "message": "Limit harian LLM (futures) tercapai"})

    # Compose payload with opts for the template + pre-decision
    template_payload = {"payload": body.payload, "opts": (body.opts or {})}
    pre = None
    if os.getenv("PREPROMPT_ENABLE", "1") not in ("0", "false", "False"):
        try:
            pre = evaluate_pre_signal({"payload": body.payload})
            template_payload["pre"] = pre
        except Exception:
            pre = None

    # Optional short-circuit when pre says NO-TRADE
    strict = os.getenv("PREPROMPT_STRICT_NO_TRADE", "0") in ("1", "true", "True")
    if strict and pre and pre.get("decision") == "NO-TRADE":
        data = {
            "text": {
                f"section_{body.mode}": {
                    "posisi": "NO-TRADE",
                    "tp": [],
                    "sl": None,
                    "strategi_singkat": [
                        "Tidak ada setup valid berdasarkan pra-skor (anti-bias)",
                        "Tunggu sweep & reclaim atau break & hold yang jelas",
                    ],
                    "fundamental": [],
                    "bybk": [],
                    "bo": [],
                }
            },
            "overlay": {"tf": "15m", "lines": [], "zones": [], "markers": [], "mode": body.mode},
            "meta": {"engine": os.getenv("OPENAI_MODEL", "gpt-5-chat-latest"), "pre": pre},
        }
        usage = {"prompt_tokens": 0, "completion_tokens": 0}
    else:
        prompt = build_prompt(sym, body.mode, template_payload)
        data, usage = call_gpt(prompt)
    if not isinstance(data, dict) or not data:
        raise HTTPException(502, detail={"error_code": "bad_llm_output", "message": "Jawaban GPT tidak valid (bukan JSON)"})

    # Count usage best-effort
    try:
        model = os.getenv("OPENAI_MODEL", "gpt-5-chat-latest")
        in_price = float(os.getenv("LLM_PRICE_INPUT_USD_PER_MTOK", 0.625))
        out_price = float(os.getenv("LLM_PRICE_OUTPUT_USD_PER_MTOK", 5.0))
        usd_daily = (int(usage.get("prompt_tokens") or 0)/1_000_000.0)*in_price + (int(usage.get("completion_tokens") or 0)/1_000_000.0)*out_price
        await inc_usage(db, user_id=user.id, model=model, input_tokens=int(usage.get("prompt_tokens") or 0), output_tokens=int(usage.get("completion_tokens") or 0), cost_usd=usd_daily, add_call=True, kind="futures")
        await db.commit()
    except Exception:  # pragma: no cover
        pass

    # Attach meta
    try:
        meta = data.setdefault("meta", {}) if isinstance(data, dict) else {}
        meta.setdefault("engine", os.getenv("OPENAI_MODEL", "gpt-5-chat-latest"))
        if pre:
            meta["pre"] = pre
    except Exception:
        meta = {}

    # Persist ke tabel cache
    try:
        overlay = data.get("overlay") if isinstance(data, dict) else {}
        text = data.get("text") if isinstance(data, dict) else {}
    except Exception:
        overlay = {}
        text = {}
    report = GPTReport(
         symbol=sym,
         mode=body.mode,
         text=text or {},
         overlay=overlay or {},
         meta=meta or {},
        ttl=_get_mode_ttl(body.mode),
    )
    db.add(report)
    await db.flush()
    try:
        await db.commit()
        await db.refresh(report)
    except Exception:
        await db.rollback()
        raise
    created = report.created_at or _utcnow()
    if created.tzinfo is None:
        created = created.replace(tzinfo=dt.timezone.utc)
    data["report_id"] = report.id
    meta_out = data.setdefault("meta", {})
    meta_out.setdefault("engine", os.getenv("OPENAI_MODEL", "gpt-5-chat-latest"))
    meta_out["cached_at"] = created.isoformat()
    meta_out["ttl_seconds"] = int(report.ttl or _get_mode_ttl(body.mode))
    data["created_at"] = created.isoformat()
    data["ttl"] = report.ttl or _get_mode_ttl(body.mode)
    return data
