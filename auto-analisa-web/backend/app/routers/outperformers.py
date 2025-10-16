from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Query

from app.services.outperformer_service import compute_outperformers


router = APIRouter(prefix='/api', tags=['outperformers'])


@router.get('/outperformers')
async def outperformers(
    mode: Literal['fast', 'medium', 'swing'] = Query('fast'),
    market: str = Query('binanceusdm'),
    limit: int = Query(10),
):
    return await compute_outperformers(mode=mode, market=market, limit=limit)

