from __future__ import annotations
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from typing import Any, Dict, Optional, Literal
from sqlalchemy.ext.asyncio import AsyncSession

from app.deps import get_db
from app.auth import require_user
from app.services.gpt_service import build_prompt, call_gpt
from app.services.llm import should_use_llm
from app.services.usage import get_today_usage, inc_usage
from app.services.budget import get_or_init_settings
import os


class AnalyzeBody(BaseModel):
    symbol: str
    mode: Literal['scalping', 'swing'] = Field('scalping')
    payload: Dict[str, Any]
    opts: Optional[Dict[str, Any]] = None


router = APIRouter(prefix="/gpt/futures", tags=["gpt-futures"])


@router.post("/analyze")
async def gpt_analyze(body: AnalyzeBody, db: AsyncSession = Depends(get_db), user=Depends(require_user)):
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

    # Compose payload with opts for the template
    template_payload = {"payload": body.payload, "opts": (body.opts or {})}
    prompt = build_prompt(body.symbol.upper(), body.mode, template_payload)
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
    except Exception:
        pass

    return data

