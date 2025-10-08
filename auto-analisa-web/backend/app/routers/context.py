from fastapi import APIRouter, Query
from ..services.context.context_rules import build_context_json

router = APIRouter(prefix='/api', tags=['context'])


@router.get('/context')
async def get_context(symbol: str, mode: str = Query('fast', pattern='^(fast|medium|swing)$')):
    return await build_context_json(symbol, mode)

