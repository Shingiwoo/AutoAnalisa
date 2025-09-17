from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.deps import get_db
from app.auth import require_user
from app.models import Analysis, FuturesSignalsCache, Settings
from app.services.market import fetch_bundle
from app.services.rules import Features, score_symbol
from app.services.planner import build_plan_async, build_spot2_from_plan

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
    invalids = {
        "tactical_5m": _f(rjb.get("invalid")),  # fallback single invalid
        "soft_15m": None,
        "hard_1h": _f(rjb.get("invalid")),
        "struct_4h": None,
    }
    # risk and guard defaults
    lev_min = int(getattr(s, "futures_leverage_min", 3) or 3)
    lev_max = int(getattr(s, "futures_leverage_max", 10) or 10)
    risk_pct = float(getattr(s, "futures_risk_per_trade_pct", 0.5) or 0.5)
    liq_buf_k = float(getattr(s, "futures_liq_buffer_k_atr15m", 0.5) or 0.5)

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

    fut = {
        "version": 1,
        "symbol": symbol.upper(),
        "contract": "PERP",
        "side": "LONG" if (base_plan.get("mode") or "PB").upper() == "PB" else "LONG",
        "tf_base": "1h",
        "bias": base_plan.get("bias", ""),
        "support": base_plan.get("support", [])[:2],
        "resistance": base_plan.get("resistance", [])[:2],
        "mode": (base_plan.get("mode") or "PB").upper(),
        "entries": [ {"range": [e or None, e or None], "weight": w, "type": t} for (e,w,t) in entries ],
        "tp": [ {"name": name, "range": [val, val], "reduce_only_pct": (40 if i == 0 else 60)} for i,(name,val) in enumerate(tp_nodes) if val is not None ],
        "invalids": invalids,
        "leverage_suggested": {"isolated": True, "x": max(lev_min, min(lev_max, 5))},
        "risk": {"risk_per_trade_pct": risk_pct, "rr_min": ">=1.5", "fee_bp": 3, "slippage_bp": 2, "liq_price_est": None, "liq_buffer_pct": f">={liq_buf_k} * ATR15m", "max_addons": 1, "pyramiding": "on_retest"},
        "futures_signals": futures_signals,
        "mtf_summary": spot2.get("mtf_summary") or {},
        "jam_pantau_wib": [],
        "notes": [],
    }
    return fut


@router.post("/{aid}/futures/verify")
async def verify_futures_llm(aid: int, db: AsyncSession = Depends(get_db), user=Depends(require_user)):
    # Placeholder endpoint for verification flow (not yet implemented)
    raise HTTPException(501, "Verify futures belum diimplementasikan")

