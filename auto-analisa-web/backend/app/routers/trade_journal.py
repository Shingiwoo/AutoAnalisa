from __future__ import annotations
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc
from datetime import datetime
from typing import Optional

from app.deps import get_db
from app.auth import require_user
from app.models import TradeJournal
from app.services.trade_calc import auto_fields, calc_pnl_pct, derive_targets, calc_equity_balance


router = APIRouter(prefix="/api/trade-journal", tags=["trade-journal"])


def _to_iso(dtobj: Optional[datetime]) -> Optional[str]:
    if not dtobj:
        return None
    try:
        return dtobj.isoformat()
    except Exception:
        return str(dtobj)


def _serialize(t: TradeJournal) -> dict:
    return {
        "id": t.id,
        "entry_at": _to_iso(t.entry_at),
        "exit_at": _to_iso(t.exit_at),
        "saldo_awal": t.saldo_awal,
        "margin": t.margin,
        "leverage": t.leverage,
        "sisa_saldo": t.sisa_saldo,
        "pair": t.pair,
        "arah": t.arah,
        "entry_price": t.entry_price,
        "exit_price": t.exit_price,
        "sl_price": t.sl_price,
        "be_price": t.be_price,
        "tp1_price": t.tp1_price,
        "tp2_price": t.tp2_price,
        "tp3_price": t.tp3_price,
        "tp1_status": t.tp1_status,
        "tp2_status": t.tp2_status,
        "tp3_status": t.tp3_status,
        "sl_status": t.sl_status,
        "be_status": t.be_status,
        "risk_reward": t.risk_reward,
        "winloss": t.winloss,
        "pnl_pct": t.pnl_pct,
        "equity_balance": t.equity_balance,
        "strategy": t.strategy,
        "market_condition": t.market_condition,
        "notes": t.notes,
        "open_qty": t.open_qty,
        "status": t.status,
        "created_at": _to_iso(t.created_at),
        "updated_at": _to_iso(t.updated_at),
    }


def _parse_dt(s: Optional[str]) -> Optional[datetime]:
    if not s:
        return None
    try:
        return datetime.fromisoformat(s)
    except Exception:
        return None


@router.get("")
async def list_entries(
    db: AsyncSession = Depends(get_db),
    user=Depends(require_user),
    pair: Optional[str] = None,
    status: Optional[str] = None,
    start: Optional[str] = None,
    end: Optional[str] = None,
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=200),
):
    conds = [TradeJournal.user_id == user.id]
    if pair:
        conds.append(func.upper(TradeJournal.pair) == pair.upper())
    if status:
        conds.append(func.upper(TradeJournal.status) == status.upper())
    ds = _parse_dt(start)
    de = _parse_dt(end)
    if ds:
        conds.append(TradeJournal.entry_at >= ds)
    if de:
        conds.append(TradeJournal.entry_at <= de)
    q = await db.execute(select(TradeJournal).where(*conds).order_by(desc(TradeJournal.entry_at)).limit(limit).offset((page-1)*limit))
    rows = q.scalars().all()
    return [_serialize(r) for r in rows]


@router.post("")
async def create_entry(payload: dict, db: AsyncSession = Depends(get_db), user=Depends(require_user)):
    # Enforce max 4 OPEN trades per user
    c = await db.execute(select(func.count()).select_from(TradeJournal).where(TradeJournal.user_id == user.id, TradeJournal.status == "OPEN"))
    open_cnt = c.scalar() or 0
    if open_cnt >= 4:
        raise HTTPException(409, "Maksimum 4 posisi OPEN per pengguna")

    # Required fields
    entry_at = _parse_dt(payload.get("entry_at"))
    if not entry_at:
        raise HTTPException(422, "entry_at wajib (datetime ISO)")
    try:
        pair = str(payload.get("pair") or "").upper().strip()
        arah = str(payload.get("arah") or "LONG").upper().strip()
        saldo_awal = float(payload.get("saldo_awal"))
        margin = float(payload.get("margin"))
        leverage = float(payload.get("leverage"))
        entry_price = float(payload.get("entry_price"))
        sl_price = float(payload.get("sl_price"))
    except Exception:
        raise HTTPException(422, "Field wajib tidak lengkap atau format angka salah")

    if arah not in ("LONG","SHORT"):
        raise HTTPException(422, "Arah harus LONG atau SHORT")
    if arah == "LONG" and not (sl_price < entry_price):
        raise HTTPException(422, "Untuk LONG: SL harus < Entry")
    if arah == "SHORT" and not (sl_price > entry_price):
        raise HTTPException(422, "Untuk SHORT: SL harus > Entry")

    # Auto fields
    autos = auto_fields({
        "saldo_awal": saldo_awal,
        "margin": margin,
        "arah": arah,
        "entry_price": entry_price,
        "sl_price": sl_price,
        "exit_price": payload.get("exit_price"),
    })
    custom_tp = bool(payload.get("custom_tp"))
    # If custom TP provided, honor them; otherwise derive
    targets = None
    if custom_tp and any(payload.get(k) is not None for k in ("tp1_price","tp2_price","tp3_price")):
        tp1 = payload.get("tp1_price")
        tp2 = payload.get("tp2_price")
        tp3 = payload.get("tp3_price")
        be = entry_price
        from app.services.trade_calc import calc_rr
        rr = calc_rr(entry_price, sl_price, tp1, tp2, tp3) or ""
        targets = {"be_price": be, "tp1_price": tp1 or be, "tp2_price": tp2 or be, "tp3_price": tp3 or be, "risk_reward": rr}
    else:
        targets = derive_targets(arah, entry_price, sl_price)

    t = TradeJournal(
        user_id=user.id,
        entry_at=entry_at,
        exit_at=_parse_dt(payload.get("exit_at")),
        saldo_awal=saldo_awal,
        margin=margin,
        leverage=leverage,
        sisa_saldo=float(autos.get("sisa_saldo") or 0.0),
        pair=pair,
        arah=arah,
        entry_price=entry_price,
        exit_price=float(payload.get("exit_price")) if payload.get("exit_price") is not None else None,
        sl_price=sl_price,
        be_price=targets["be_price"],
        tp1_price=targets["tp1_price"],
        tp2_price=targets["tp2_price"],
        tp3_price=targets["tp3_price"],
        tp1_status="PENDING",
        tp2_status="PENDING",
        tp3_status="PENDING",
        sl_status="PENDING",
        be_status="PENDING",
        risk_reward=targets["risk_reward"],
        winloss="WAITING",
        pnl_pct=float(autos.get("pnl_pct") or 0.0),
        equity_balance=None,
        strategy=payload.get("strategy"),
        market_condition=payload.get("market_condition"),
        notes=str(payload.get("notes") or ""),
        open_qty=float(payload.get("open_qty") or 1.0),
        status="OPEN",
    )
    # Auto-close logic if exit_at and exit_price present
    if t.exit_at and t.exit_price is not None:
        pnl = calc_pnl_pct(t.arah, t.entry_price, t.exit_price)
        if pnl is not None:
            t.pnl_pct = pnl
            eq = calc_equity_balance(t.saldo_awal, t.margin, t.leverage, t.arah, t.entry_price, t.exit_price)
            t.equity_balance = eq
            t.status = "CLOSED"
            t.winloss = "WIN" if pnl > 0 else ("LOSS" if pnl < 0 else "WAITING")
    db.add(t)
    await db.commit()
    await db.refresh(t)
    return _serialize(t)


@router.put("/{tid}")
async def update_entry(tid: int, payload: dict, db: AsyncSession = Depends(get_db), user=Depends(require_user)):
    t = await db.get(TradeJournal, tid)
    if not t or t.user_id != user.id:
        raise HTTPException(404, "Not found")
    # Update mutable fields
    for k in [
        "saldo_awal","margin","leverage","sisa_saldo","exit_price",
        "equity_balance","strategy","market_condition","notes","open_qty","status"
    ]:
        if k in payload:
            setattr(t, k, payload.get(k))
    if "pair" in payload:
        t.pair = str(payload.get("pair") or t.pair).upper()
    if "arah" in payload:
        t.arah = str(payload.get("arah") or t.arah).upper()
    if "entry_at" in payload:
        dtv = _parse_dt(payload.get("entry_at"))
        if dtv:
            t.entry_at = dtv
    if "exit_at" in payload:
        t.exit_at = _parse_dt(payload.get("exit_at"))
    for st in ["tp1_status","tp2_status","tp3_status","sl_status","be_status","winloss"]:
        if st in payload and payload.get(st) is not None:
            setattr(t, st, str(payload.get(st)).upper())
    # Optional automation flags
    auto_move_sl_to_be = bool(payload.get("auto_move_sl_to_be"))
    auto_lock_tp1 = bool(payload.get("auto_lock_tp1"))
    # Recalc autos + targets if entry/sl changed via previous data (we keep entry/sl read-only by UI, but handle gracefully if changed elsewhere)
    custom_tp = bool(payload.get("custom_tp"))
    # If custom_tp, update TP prices if provided; else re-derive from entry/sl
    if custom_tp and any(k in payload for k in ("tp1_price","tp2_price","tp3_price")):
        if "tp1_price" in payload and payload.get("tp1_price") is not None:
            t.tp1_price = float(payload.get("tp1_price"))
        if "tp2_price" in payload and payload.get("tp2_price") is not None:
            t.tp2_price = float(payload.get("tp2_price"))
        if "tp3_price" in payload and payload.get("tp3_price") is not None:
            t.tp3_price = float(payload.get("tp3_price"))
        # keep BE = entry
        t.be_price = float(t.entry_price)
        from app.services.trade_calc import calc_rr
        rr = calc_rr(t.entry_price, t.sl_price, t.tp1_price, t.tp2_price, t.tp3_price)
        t.risk_reward = rr or t.risk_reward
    else:
        targets = derive_targets(t.arah, float(t.entry_price), float(t.sl_price))
        t.be_price = targets["be_price"]
        t.tp1_price = targets["tp1_price"]
        t.tp2_price = targets["tp2_price"]
        t.tp3_price = targets["tp3_price"]
        t.risk_reward = targets["risk_reward"]

    # Auto SL adjust by level hits
    if auto_move_sl_to_be and str(t.tp1_status).upper() == 'HIT':
        t.sl_status = 'PASS'
        t.sl_price = t.be_price
    if auto_lock_tp1 and str(t.tp2_status).upper() == 'HIT':
        t.sl_price = t.tp1_price

    # Auto fields for saldo
    autos = auto_fields({
        "saldo_awal": t.saldo_awal,
        "margin": t.margin,
        "arah": t.arah,
        "entry_price": t.entry_price,
        "exit_price": t.exit_price,
        "sl_price": t.sl_price,
    })
    if "sisa_saldo" not in payload and autos.get("sisa_saldo") is not None:
        t.sisa_saldo = autos["sisa_saldo"]
    # PnL & equity if closed or exit present
    if t.exit_at and t.exit_price is not None:
        pnl = calc_pnl_pct(t.arah, t.entry_price, t.exit_price)
        if pnl is not None:
            t.pnl_pct = pnl
            t.equity_balance = calc_equity_balance(t.saldo_awal, t.margin, t.leverage, t.arah, t.entry_price, t.exit_price)
            t.status = "CLOSED"
            t.winloss = "WIN" if pnl > 0 else ("LOSS" if pnl < 0 else "WAITING")
    await db.commit()
    await db.refresh(t)
    return _serialize(t)


@router.delete("/{tid}")
async def delete_entry(tid: int, db: AsyncSession = Depends(get_db), user=Depends(require_user)):
    t = await db.get(TradeJournal, tid)
    if not t or t.user_id != user.id:
        raise HTTPException(404, "Not found")
    await db.delete(t)
    await db.commit()
    return {"ok": True}


@router.get("/export")
async def export_csv(
    db: AsyncSession = Depends(get_db),
    user=Depends(require_user),
    pair: Optional[str] = None,
    status: Optional[str] = None,
    start: Optional[str] = None,
    end: Optional[str] = None,
):
    conds = [TradeJournal.user_id == user.id]
    if pair:
        conds.append(func.upper(TradeJournal.pair) == pair.upper())
    if status:
        conds.append(func.upper(TradeJournal.status) == status.upper())
    ds = _parse_dt(start)
    de = _parse_dt(end)
    if ds:
        conds.append(TradeJournal.entry_at >= ds)
    if de:
        conds.append(TradeJournal.entry_at <= de)
    q = await db.execute(select(TradeJournal).where(*conds).order_by(desc(TradeJournal.entry_at)))
    rows = q.scalars().all()
    # CSV header
    cols = [
        "id","entry_at","exit_at","pair","arah","status","saldo_awal","margin","leverage","sisa_saldo","entry_price","exit_price",
        "sl_price","be_price","tp1_price","tp2_price","tp3_price","tp1_status","tp2_status","tp3_status","sl_status","be_status",
        "risk_reward","winloss","pnl_pct","equity_balance","strategy","market_condition","notes","open_qty","created_at","updated_at"
    ]
    def row_to_csv(t: TradeJournal) -> str:
        vals = _serialize(t)
        out = []
        for c in cols:
            v = vals.get(c)
            s = "" if v is None else str(v).replace("\n"," ").replace("\r"," ")
            if "," in s or "\"" in s:
                s = '"' + s.replace('"','""') + '"'
            out.append(s)
        return ",".join(out)
    content = ",".join(cols) + "\n" + "\n".join(row_to_csv(r) for r in rows)
    return Response(content=content, media_type="text/csv", headers={"Content-Disposition": "attachment; filename=trade_journal.csv"})
