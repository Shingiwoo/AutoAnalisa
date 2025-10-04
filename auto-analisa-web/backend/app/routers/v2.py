from fastapi import APIRouter
from app.v2_schemas.market import MarketSnapshot
from app.v2_schemas.llm_output import LlmOutput
from app.v2_orchestrator.analyze import analyze as analyze_orchestrator


router = APIRouter(prefix="/api/v2", tags=["v2"])


@router.post("/analyze", response_model=LlmOutput)
async def analyze_market(payload: MarketSnapshot):
    return await analyze_orchestrator(payload)


@router.get("/health")
async def health():
    return {"status": "ok"}

