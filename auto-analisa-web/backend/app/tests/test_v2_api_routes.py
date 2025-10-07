import pytest

import app.routers.v2 as v2router
from app.v2_schemas.market import MarketSnapshot, IndicatorSet, Candle


@pytest.fixture(autouse=True)
def patch_analyze_route(monkeypatch):
    async def fake_analyze(payload):
        return {
            "symbol": payload.symbol,
            "timeframe": payload.timeframe,
            "structure": "range",
            "momentum": "neutral",
            "key_levels": [
                {"label": "support_1", "price": payload.last_price - 10},
                {"label": "resistance_1", "price": payload.last_price + 10},
            ],
            "plan": {
                "bias": "neutral",
                "entries": [
                    {"label": "pullback", "price": payload.last_price - 5},
                    {"label": "breakout", "price": payload.last_price + 5},
                ],
                "take_profits": [
                    {"label": "tp1", "price": payload.last_price + 15},
                    {"label": "tp2", "price": payload.last_price + 30},
                ],
                "stop_loss": {"label": "sl", "price": payload.last_price - 15},
                "rationale": "stub",
                "timeframe_alignment": ["1h"],
                "risk_note": None,
            },
        }

    # Patch symbol imported in router
    monkeypatch.setattr(v2router, "analyze_orchestrator", fake_analyze)


@pytest.mark.asyncio
async def test_v2_analyze_route_ok():
    payload = MarketSnapshot(
        symbol="ETHUSDT",
        timeframe="1h",
        last_price=100.0,
        candles=[Candle(ts=1, open=99.0, high=101.0, low=98.0, close=100.0, volume=1000)],
        indicators=IndicatorSet(
            ema5=100.1,
            ema20=99.5,
            ema50=98.0,
            rsi14=50.0,
            macd=0.1,
            macd_signal=0.05,
            bb_up=102.0,
            bb_mid=100.0,
            bb_low=98.0,
        ),
    )
    data = await v2router.analyze_market(payload)
    assert data["symbol"] == "ETHUSDT"
    assert "plan" in data and data["plan"]["stop_loss"]["price"]


@pytest.mark.asyncio
async def test_v2_health():
    res = await v2router.health()
    assert res.get("status") == "ok"
