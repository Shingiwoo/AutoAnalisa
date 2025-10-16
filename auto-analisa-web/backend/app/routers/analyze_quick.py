from __future__ import annotations

from typing import Dict, Literal

from fastapi import APIRouter
from pydantic import BaseModel

from app.services.analyze_v2 import build_quick_analysis


router = APIRouter(prefix='/api', tags=['analyze'])


class QuickReq(BaseModel):
    symbol: str
    mode: Literal['fast', 'medium', 'swing']
    tf_map: Dict[str, str]
    use_context: bool = True
    market: str = 'futures'


@router.post('/quick-analyze')
async def quick_analyze(req: QuickReq):
    return await build_quick_analysis(
        symbol=req.symbol,
        mode=req.mode,
        tf_map=req.tf_map,
        use_context=req.use_context,
        market=req.market,
    )

