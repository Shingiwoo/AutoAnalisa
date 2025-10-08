from fastapi import APIRouter
import pandas as pd
from app.v2_schemas.market import MarketSnapshot
from app.v2_schemas.llm_output import LlmOutput
from app.v2_orchestrator.analyze import analyze as analyze_orchestrator
from app.services.market import fetch_klines
from app.services.indicators import ema, rsi as rsi14, macd as macd_ind, bb as bbands
from app.v2_schemas.market import Candle, IndicatorSet
from app.services_v2.btc_bias import infer_btc_bias_from_exchange


router = APIRouter(prefix="/api/v2", tags=["v2"])


@router.post("/analyze", response_model=LlmOutput)
async def analyze_market(payload: MarketSnapshot, follow_btc_bias: bool = True):
    return await analyze_orchestrator(payload, follow_btc_bias=follow_btc_bias)


@router.get("/health")
async def health():
    return {"status": "ok"}


@router.get("/snapshot", response_model=MarketSnapshot)
async def snapshot(symbol: str, timeframe: str = "1h"):
    df = await fetch_klines(symbol, timeframe, 320, market="spot")
    if df is None or df.empty:
        # minimal empty snapshot
        snap = MarketSnapshot(
            symbol=symbol,
            timeframe=timeframe if timeframe in {"15m","1h","4h","1d"} else "1h",
            last_price=0.0,
            candles=[],
            indicators=IndicatorSet(),
        )
        return snap
    # Compute indicators
    close = pd.to_numeric(df["close"], errors="coerce").fillna(method="ffill").fillna(method="bfill")
    ema5 = float(ema(close, 5).iloc[-1])
    ema10 = float(ema(close, 10).iloc[-1])
    ema20 = float(ema(close, 20).iloc[-1])
    ema50 = float(ema(close, 50).iloc[-1])
    ema100 = float(ema(close, 100).iloc[-1]) if len(close) >= 120 else None
    ema200 = float(ema(close, 200).iloc[-1]) if len(close) >= 220 else None
    rsi14_v = float(rsi14(close, 14).iloc[-1])
    macd_val, macd_sig, _ = macd_ind(close)
    macd_v = float(macd_val.iloc[-1])
    macd_s = float(macd_sig.iloc[-1])
    mb, ub, lb = bbands(close, 20, 2.0)
    bb_up = float(ub.iloc[-1])
    bb_mid = float(mb.iloc[-1])
    bb_low = float(lb.iloc[-1])

    # Map candles (use last 60 rows)
    candles = [
        Candle(ts=int(r.ts), open=float(r.open), high=float(r.high), low=float(r.low), close=float(r.close), volume=float(r.volume))
        for r in df.tail(60).itertuples(index=False)
    ]
    last_price = float(close.iloc[-1])
    # BTC bias inference (best effort)
    btc_bias, _ = await infer_btc_bias_from_exchange("BTCUSDT", "1h", 320)
    snap = MarketSnapshot(
        symbol=symbol,
        timeframe=timeframe if timeframe in {"15m","1h","4h","1d"} else "1h",
        last_price=last_price,
        candles=candles,
        indicators=IndicatorSet(
            ema5=ema5, ema10=ema10, ema20=ema20, ema50=ema50,
            ema100=ema100, ema200=ema200,
            rsi14=rsi14_v,
            macd=macd_v, macd_signal=macd_s,
            bb_up=bb_up, bb_mid=bb_mid, bb_low=bb_low,
        ),
        btc_bias=btc_bias,
        btc_context=None,
    )
    return snap
