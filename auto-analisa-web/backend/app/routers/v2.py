from fastapi import APIRouter
import time, uuid
from typing import List, Optional
import pandas as pd
from app.v2_schemas.market import MarketSnapshot
from app.v2_schemas.llm_output import LlmOutput
from app.v2_orchestrator.build_rich import build_rich_output
from app.v2_orchestrator.analyze import analyze as analyze_orchestrator
from app.services.market import fetch_klines
from app.services.indicators import ema, rsi as rsi14, macd as macd_ind, bb as bbands
from app.v2_schemas.market import Candle, IndicatorSet
from app.services_v2.btc_bias import infer_btc_bias_from_exchange
from app.services.cache import SnapshotStore


router = APIRouter(prefix="/api/v2", tags=["v2"])
_SNAP = SnapshotStore()


@router.post("/analyze")
async def analyze_market(payload: MarketSnapshot, follow_btc_bias: bool = True, profile: str | None = None, format: str | None = None):
    plain = await analyze_orchestrator(payload, follow_btc_bias=follow_btc_bias, profile=profile)
    if (format or '').lower() == 'rich':
        snap = { 'H1': {}, 'M15': {}, 'H4': {}, 'D1': {} }
        return build_rich_output(payload.symbol, 'futures', snap, plain, source='direct', price_now=payload.last_price).model_dump()
    return plain


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


@router.post("/snapshot/batch")
async def snapshot_batch(symbols: List[str], mode: Optional[str] = None):
    ts = int(time.time())
    sid = str(uuid.uuid4())
    snaps: List[dict] = []
    # map mode to timeframe for quick snapshot
    tf = "1h"
    if (mode or "").lower() == "fast": tf = "15m"
    if (mode or "").lower() == "swing": tf = "1d"
    for sym in symbols:
        try:
            s = await snapshot(sym, tf)
            snaps.append(s.model_dump())
        except Exception:
            continue
    _SNAP.put(sid, {"generated_at": ts, "mode": (mode or None), "tf": tf, "snaps": snaps})
    return {"snapshot_id": sid, "generated_at": ts, "mode": mode, "count": len(snaps)}


@router.post("/analyze_snapshot")
async def analyze_snapshot(snapshot_id: str, index: int = 0, follow_btc_bias: bool = True, profile: str | None = None, format: str | None = None):
    obj = _SNAP.get(snapshot_id)
    if not obj:
        raise RuntimeError("snapshot not found")
    snaps = obj.get("snaps") or []
    if not snaps:
        raise RuntimeError("empty snapshot")
    idx = max(0, min(index, len(snaps)-1))
    ms = MarketSnapshot.model_validate(snaps[idx])
    plain = await analyze_orchestrator(ms, follow_btc_bias=follow_btc_bias, profile=profile)
    if (format or '').lower() == 'rich':
        snap = { 'H1': {}, 'M15': {}, 'H4': {}, 'D1': {} }  # placeholder blocks
        return build_rich_output(ms.symbol, 'futures', snap, plain, source='snapshot', price_now=ms.last_price).model_dump()
    return plain


@router.post("/analyze_batch")
async def analyze_batch(snapshot_id: str, count: int = 10, follow_btc_bias: bool = True, profile: str | None = None, format: str | None = None):
    obj = _SNAP.get(snapshot_id)
    if not obj:
        raise RuntimeError("snapshot_id invalid")
    snaps = obj.get('snaps') or []
    n = max(0, min(int(count or 0), len(snaps)))
    out = []
    for i in range(n):
        ms = MarketSnapshot.model_validate(snaps[i])
        plain = await analyze_orchestrator(ms, follow_btc_bias=follow_btc_bias, profile=profile)
        if (format or '').lower() == 'rich':
            snap = { 'H1': {}, 'M15': {}, 'H4': {}, 'D1': {} }
            out.append({ 'symbol': ms.symbol, 'result': build_rich_output(ms.symbol, 'futures', snap, plain, source='snapshot', price_now=ms.last_price).model_dump() })
        else:
            out.append({ 'symbol': ms.symbol, 'result': plain.model_dump() })
    return { 'snapshot_id': snapshot_id, 'results': out }
