from fastapi import APIRouter, Query
from typing import List
from ..services.screener import screener_outperformers

router = APIRouter(prefix='/api/screener', tags=['screener'])


@router.get('/outperformers')
async def outperformers(
    symbols: str = Query("BTCUSDT,ETHUSDT,BNBUSDT"),
    mode: str = Query('medium'),
    market: str = Query('futures'),
    top: int = Query(20)
):
    syms: List[str] = [s.strip().upper() for s in symbols.split(',') if s.strip()]
    return await screener_outperformers(syms, mode=mode, market=market, top=top)

