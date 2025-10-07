from app.v2_payloads.build import build
from app.v2_schemas.market import MarketSnapshot, IndicatorSet, Candle


def _snap():
    return MarketSnapshot(
        symbol="XRPUSDT",
        timeframe="1h",
        last_price=3.05,
        candles=[
            Candle(ts=1, open=3.0, high=3.1, low=2.9, close=3.05, volume=1_000)
        ],
        indicators=IndicatorSet(
            ema5=3.02,
            ema20=3.0,
            ema50=2.95,
            rsi14=58.0,
            macd=0.01,
            macd_signal=0.008,
            bb_up=3.10,
            bb_mid=3.00,
            bb_low=2.90,
        ),
    )


def test_build_has_schema():
    p = build(_snap())
    assert isinstance(p.json_schema, dict)
    assert "properties" in p.json_schema

