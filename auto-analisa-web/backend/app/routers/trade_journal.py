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
from app.services.trade_calc import auto_fields, calc_pnl_pct, calc_rr


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
        raise HTTPException(409, "Maksimal 4 posisi OPEN. Tutup sebagian sebelum menambah.")

    try:
        entry_at = _parse_dt(payload.get("entry_at"))
        if not entry_at:
            raise ValueError("entry_at wajib")
    except Exception:
        raise HTTPException(422, "Format entry_at tidak valid")

    pair = str(payload.get("pair") or "").upper()
    arah = str(payload.get("arah") or "LONG").upper()

    data = dict(payload)
    data.update({"pair": pair, "arah": arah})
    autos = auto_fields(data)

    t = TradeJournal(
        user_id=user.id,
        entry_at=entry_at,
        exit_at=_parse_dt(payload.get("exit_at")),
        saldo_awal=payload.get("saldo_awal"),
        margin=payload.get("margin"),
        leverage=payload.get("leverage"),
        sisa_saldo=payload.get("sisa_saldo") or autos.get("sisa_saldo") or 0.0,
        pair=pair,
        arah=arah,
        entry_price=payload.get("entry_price"),
        exit_price=payload.get("exit_price"),
        sl_price=payload.get("sl_price"),
        be_price=payload.get("be_price"),
        tp1_price=payload.get("tp1_price"),
        tp2_price=payload.get("tp2_price"),
        tp3_price=payload.get("tp3_price"),
        tp1_status=(payload.get("tp1_status") or "PENDING").upper(),
        tp2_status=(payload.get("tp2_status") or "PENDING").upper(),
        tp3_status=(payload.get("tp3_status") or "PENDING").upper(),
        sl_status=(payload.get("sl_status") or "PENDING").upper(),
        be_status=(payload.get("be_status") or "PENDING").upper(),
        risk_reward=payload.get("risk_reward") or autos.get("risk_reward"),
        winloss=(payload.get("winloss") or "WAITING").upper(),
        pnl_pct=float(payload.get("pnl_pct") or autos.get("pnl_pct") or 0.0),
        equity_balance=payload.get("equity_balance"),
        strategy=payload.get("strategy"),
        market_condition=payload.get("market_condition"),
        notes=payload.get("notes") or "",
        open_qty=float(payload.get("open_qty") or 1.0),
        status=(payload.get("status") or "OPEN").upper(),
    )
    # Auto-close logic if exit_at and exit_price present
    if t.exit_at and t.exit_price is not None:
        pnl = calc_pnl_pct(t.arah, t.entry_price, t.exit_price)
        if pnl is not None:
            t.pnl_pct = pnl
            t.status = "CLOSED"
            t.winloss = "WIN" if pnl > 0 else "LOSS"
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
        "saldo_awal","margin","leverage","sisa_saldo","entry_price","exit_price","sl_price","be_price","tp1_price","tp2_price","tp3_price",
        "equity_balance","strategy","market_condition","notes","open_qty"
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
    for st in ["tp1_status","tp2_status","tp3_status","sl_status","be_status","winloss","status"]:
        if st in payload and payload.get(st) is not None:
            setattr(t, st, str(payload.get(st)).upper())
    # Recalc autos
    data = {
        "saldo_awal": t.saldo_awal,
        "margin": t.margin,
        "arah": t.arah,
        "entry_price": t.entry_price,
        "exit_price": t.exit_price,
        "sl_price": t.sl_price,
        "tp1_price": t.tp1_price,
        "tp2_price": t.tp2_price,
        "tp3_price": t.tp3_price,
    }
    autos = auto_fields(data)
    if "sisa_saldo" not in payload and "sisa_saldo" in autos and autos["sisa_saldo"] is not None:
        t.sisa_saldo = autos["sisa_saldo"]
    if "risk_reward" in payload:
        t.risk_reward = payload.get("risk_reward")
    else:
        t.risk_reward = autos.get("risk_reward")
    if "pnl_pct" in payload and payload.get("pnl_pct") is not None:
        t.pnl_pct = float(payload.get("pnl_pct"))
    else:
        pnl = autos.get("pnl_pct")
        if pnl is not None:
            t.pnl_pct = pnl
    # Auto-close if exit present
    if t.exit_at and t.exit_price is not None:
        pnl = calc_pnl_pct(t.arah, t.entry_price, t.exit_price)
        if pnl is not None:
            t.pnl_pct = pnl
            t.status = "CLOSED"
            t.winloss = "WIN" if pnl > 0 else "LOSS"
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
