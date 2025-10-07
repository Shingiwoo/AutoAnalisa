import asyncio
import types

import pytest

from app.v2_schemas.market import MarketSnapshot, IndicatorSet, Candle
from app.v2_orchestrator import analyze as orch


def _snap():
    return MarketSnapshot(
        symbol="BTCUSDT",
        timeframe="1h",
        last_price=61000.0,
        candles=[Candle(ts=1, open=60900, high=61200, low=60700, close=61000, volume=12345)],
        indicators=IndicatorSet(
            ema5=61010,
            ema20=60900,
            ema50=60500,
            rsi14=55.0,
            macd=1.2,
            macd_signal=0.9,
            bb_up=61500,
            bb_mid=60900,
            bb_low=60300,
        ),
    )


@pytest.mark.asyncio
async def test_analyze_monkeypatched_llm(monkeypatch):
    async def fake_structured_response(self, system: str, user: str, json_schema: dict) -> dict:
        return {
            "symbol": "BTCUSDT",
            "timeframe": "1h",
            "structure": "uptrend",
            "momentum": "strong",
            "key_levels": [
                {"label": "support_1", "price": 60800.0},
                {"label": "resistance_1", "price": 61500.0},
            ],
            "plan": {
                "bias": "bullish",
                "entries": [
                    {"label": "pullback", "price": 60900.0},
                    {"label": "breakout", "price": 61550.0},
                ],
                "take_profits": [
                    {"label": "tp1", "price": 61700.0},
                    {"label": "tp2", "price": 62200.0},
                ],
                "stop_loss": {"label": "sl", "price": 60600.0},
                "rationale": "EMA stack up, RSI>50",
                "timeframe_alignment": ["1h", "4h"],
                "risk_note": "manage leverage",
            },
        }

    class FakeClient:
        async def structured_response(self, system: str, user: str, json_schema: dict) -> dict:  # pragma: no cover
            return await fake_structured_response(self, system, user, json_schema)

    # Patch the LlmClient symbol inside orchestrator module
    monkeypatch.setattr(orch, "LlmClient", lambda: FakeClient())

    out = await orch.analyze(_snap())
    assert out.symbol == "BTCUSDT"
    assert out.plan.entries and out.plan.stop_loss


@pytest.mark.asyncio
async def test_analyze_alignment_bullish(monkeypatch):
    async def fake_structured_response(self, system: str, user: str, json_schema: dict) -> dict:
        return {
            "symbol": "ETHUSDT",
            "timeframe": "1h",
            "structure": "uptrend",
            "momentum": "strong",
            "key_levels": [],
            "plan": {
                "bias": "bullish",
                "entries": [],
                "take_profits": [],
                "stop_loss": {"label": "sl", "price": 1.0},
                "rationale": "",
                "timeframe_alignment": ["1h"],
            },
        }

    class FakeClient:
        async def structured_response(self, system: str, user: str, json_schema: dict) -> dict:  # pragma: no cover
            return await fake_structured_response(self, system, user, json_schema)

    monkeypatch.setattr(orch, "LlmClient", lambda: FakeClient())

    snap = _snap().model_copy(update={"symbol": "ETHUSDT", "btc_bias": "bullish_cooling"})
    out = await orch.analyze(snap)
    assert out.btc_alignment == "aligned"


@pytest.mark.asyncio
async def test_analyze_alignment_conflict(monkeypatch):
    async def fake_structured_response(self, system: str, user: str, json_schema: dict) -> dict:
        return {
            "symbol": "ETHUSDT",
            "timeframe": "1h",
            "structure": "downtrend",
            "momentum": "weak",
            "key_levels": [],
            "plan": {
                "bias": "bullish",
                "entries": [],
                "take_profits": [],
                "stop_loss": {"label": "sl", "price": 1.0},
                "rationale": "",
                "timeframe_alignment": ["1h"],
            },
        }

    class FakeClient:
        async def structured_response(self, system: str, user: str, json_schema: dict) -> dict:  # pragma: no cover
            return await fake_structured_response(self, system, user, json_schema)

    monkeypatch.setattr(orch, "LlmClient", lambda: FakeClient())

    snap = _snap().model_copy(update={"symbol": "ETHUSDT", "btc_bias": "bearish_mild"})
    out = await orch.analyze(snap)
    assert out.btc_alignment == "conflict"
