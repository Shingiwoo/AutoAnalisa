from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.deps import get_db
from app.auth import require_user
from app.models import Analysis, FuturesSignalsCache, Settings
from app.services.market import fetch_bundle
from app.services.rules import Features, score_symbol
from app.services.planner import build_plan_async, build_spot2_from_plan
from app.services.futures import latest_signals
from app.services.sessions import btc_wib_buckets

router = APIRouter(prefix="/api/analyses", tags=["futures"])


def _f(x):
    try:
        return float(x)
    except Exception:
        return None


@router.get("/{symbol}/futures")
async def get_futures_plan(symbol: str, db: AsyncSession = Depends(get_db), user=Depends(require_user)):
    # Feature-flag
    s = await db.get(Settings, 1)
    # if no row id=1, fallback to reading via helper (avoiding import cycle)
    if not s:
        from app.services.budget import get_or_init_settings
        s = await get_or_init_settings(db)
    if not getattr(s, "enable_futures", False):
        raise HTTPException(404, "Futures dinonaktifkan oleh admin")

    # Build a baseline spot plan and adapt to futures format
    bundle = await fetch_bundle(symbol, ("4h", "1h", "15m", "5m"))
    feat = Features(bundle).enrich()
    score = score_symbol(feat)
    base_plan = await build_plan_async(db, bundle, feat, score, "auto")
    spot2 = await build_spot2_from_plan(db, symbol.upper(), base_plan)
    # Pick representative values
    rjb = dict(spot2.get("rencana_jual_beli") or {})
    entries = [(_f((e.get("range") or [None])[0]), float(e.get("weight") or 0.0), (e.get("type") or "PB")) for e in (rjb.get("entries") or [])]
    tp_nodes = [(t.get("name") or f"TP{i+1}", _f((t.get("range") or [None])[0])) for i, t in enumerate(spot2.get("tp") or [])]
    # map spot2 invalids if available
    inv_map = dict(spot2.get("invalids") or {})
    invalids = {
        "tactical_5m": _f(inv_map.get("m5") if inv_map else rjb.get("invalid")),
        "soft_15m": _f(inv_map.get("m15")) if inv_map else None,
        "hard_1h": _f(inv_map.get("h1") if inv_map else rjb.get("invalid")),
        "struct_4h": _f(inv_map.get("h4")) if inv_map else None,
    }
    # risk and guard defaults
    lev_min = int(getattr(s, "futures_leverage_min", 3) or 3)
    lev_max = int(getattr(s, "futures_leverage_max", 10) or 10)
    risk_pct = float(getattr(s, "futures_risk_per_trade_pct", 0.5) or 0.5)
    liq_buf_k = float(getattr(s, "futures_liq_buffer_k_atr15m", 0.5) or 0.5)
    lev = max(lev_min, min(lev_max, 5))

    # Signals cache (best-effort, empty in this skeleton)
    q = await db.execute(select(FuturesSignalsCache).where(FuturesSignalsCache.symbol == symbol.upper()).order_by(FuturesSignalsCache.created_at.desc()))
    sig = q.scalars().first()
    futures_signals = {
        "funding": {"now": getattr(sig, "funding_now", None), "next": getattr(sig, "funding_next", None), "time": getattr(sig, "next_funding_time", None)},
        "oi": {"now": getattr(sig, "oi_now", None), "d1": getattr(sig, "oi_d1", None)},
        "lsr": {"accounts": getattr(sig, "lsr_accounts", None), "positions": getattr(sig, "lsr_positions", None)},
        "basis": {"now": getattr(sig, "basis_now", None)},
        "taker_delta": {"m5": getattr(sig, "taker_delta_m5", None), "m15": getattr(sig, "taker_delta_m15", None), "h1": getattr(sig, "taker_delta_h1", None)},
    }

    # Side heuristic sederhana (trend 1H): LONG bila ema5>ema20>ema50; else SHORT
    side = "LONG"
    try:
        df1h = bundle.get("1h")
        last = df1h.iloc[-1]
        if not (float(getattr(last, "ema5", 0)) > float(getattr(last, "ema20", 0)) > float(getattr(last, "ema50", 0))):
            side = "SHORT"
    except Exception:
        side = "LONG"

    # Perkiraan harga likuidasi (linear perp, isolated): approx entry*(1 - 0.97/lev) untuk LONG dan entry*(1 + 0.97/lev) untuk SHORT
    try:
        e0 = entries[0][0] if entries and entries[0][0] is not None else None
        liq_est = None
        if e0 is not None and lev:
            if side == "LONG":
                liq_est = float(e0) * (1.0 - 0.97/float(lev))
            else:
                liq_est = float(e0) * (1.0 + 0.97/float(lev))
    except Exception:
        liq_est = None

    # Jam pantau WIB dari buckets signifikan
    try:
        buckets = await btc_wib_buckets(days=120, timeframe="1h")
        jam_pantau = [b["hour"] for b in (buckets or [])]
    except Exception:
        jam_pantau = []

    fut = {
        "version": 1,
        "symbol": symbol.upper(),
        "contract": "PERP",
        "side": side,
        "tf_base": "1h",
        "bias": base_plan.get("bias", ""),
        "support": base_plan.get("support", [])[:2],
        "resistance": base_plan.get("resistance", [])[:2],
        "mode": (base_plan.get("mode") or "PB").upper(),
        "entries": [ {"range": [e or None, e or None], "weight": w, "type": t} for (e,w,t) in entries ],
        "tp": [ {"name": name, "range": [val, val], "reduce_only_pct": (40 if i == 0 else 60)} for i,(name,val) in enumerate(tp_nodes) if val is not None ],
        "invalids": invalids,
        "leverage_suggested": {"isolated": True, "x": lev},
        "risk": {"risk_per_trade_pct": risk_pct, "rr_min": ">=1.5", "fee_bp": 3, "slippage_bp": 2, "liq_price_est": liq_est, "liq_buffer_pct": f">={liq_buf_k} * ATR15m", "max_addons": 1, "pyramiding": "on_retest", "funding_window_min": int(getattr(s, "futures_funding_avoid_minutes", 10) or 10), "funding_threshold_bp": float(getattr(s, "futures_funding_threshold_bp", 3.0) or 3.0)},
        "futures_signals": futures_signals,
        "mtf_summary": spot2.get("mtf_summary") or {},
        "jam_pantau_wib": jam_pantau,
        "notes": [],
    }
    return fut


@router.post("/{aid}/futures/verify")
async def verify_futures_llm(aid: int, db: AsyncSession = Depends(get_db), user=Depends(require_user)):
    # Placeholder endpoint for verification flow (not yet implemented)
    raise HTTPException(501, "Verify futures belum diimplementasikan")
