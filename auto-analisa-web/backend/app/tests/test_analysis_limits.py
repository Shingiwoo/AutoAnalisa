import os
import sys

import pytest
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy import select, func, delete

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.models import Base, User, Analysis
from app.workers.analyze_worker import run_analysis


@pytest.mark.asyncio
async def test_run_analysis_limits_per_trade_type(monkeypatch):
    """Spot dan futures harus punya limit terpisah dan simbol bisa dobel."""

    async def fake_fetch_bundle(symbol, tfs, market="spot"):
        return {tf: [] for tf in tfs}

    class DummyFeatures:
        def __init__(self, bundle):
            self.bundle = bundle

        def enrich(self):
            return self

    async def fake_build_plan_async(db, bundle, feat, score, mode):
        return {"entries": [], "tp": [], "invalid": None}

    async def fake_build_spot2_from_plan(db, sym, plan):
        return {"rencana_jual_beli": {}, "tp": []}

    def fake_round_plan_prices(sym, plan):
        return plan

    monkeypatch.setattr("app.workers.analyze_worker.fetch_bundle", fake_fetch_bundle)
    monkeypatch.setattr("app.workers.analyze_worker.Features", DummyFeatures)
    monkeypatch.setattr("app.workers.analyze_worker.score_symbol", lambda feat: 50)
    monkeypatch.setattr("app.workers.analyze_worker.build_plan_async", fake_build_plan_async)
    monkeypatch.setattr("app.workers.analyze_worker.build_spot2_from_plan", fake_build_spot2_from_plan)
    monkeypatch.setattr("app.workers.analyze_worker.round_plan_prices", fake_round_plan_prices)

    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async_session = sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

    async with async_session() as session:
        user = User(id="u-1", email="user@example.com", password_hash="hash")
        session.add(user)
        await session.commit()
        await session.refresh(user)

        # Spot dan futures untuk simbol yang sama harus bisa dibuat
        spot = await run_analysis(session, user, "BTCUSDT", trade_type="spot")
        fut = await run_analysis(session, user, "BTCUSDT", trade_type="futures")
        assert spot.trade_type == "spot"
        assert fut.trade_type == "futures"

        # Tambah simbol lain sampai limit tercapai per tipe
        await run_analysis(session, user, "ETHUSDT", trade_type="spot")
        await run_analysis(session, user, "BNBUSDT", trade_type="spot")
        await run_analysis(session, user, "ADAUSDT", trade_type="spot")
        with pytest.raises(HTTPException):
            await run_analysis(session, user, "XRPUSDT", trade_type="spot")

        await run_analysis(session, user, "ETHUSDT", trade_type="futures")
        await run_analysis(session, user, "BNBUSDT", trade_type="futures")
        await run_analysis(session, user, "ADAUSDT", trade_type="futures")
        with pytest.raises(HTTPException):
            await run_analysis(session, user, "XRPUSDT", trade_type="futures")

        # Pastikan total baris aktif sesuai dan simbol BTC muncul dua kali dengan tipe berbeda
        res = await session.execute(select(func.count()).select_from(Analysis))
        assert res.scalar_one() == 8

        res_btc = await session.execute(
            select(Analysis.trade_type).where(Analysis.symbol == "BTCUSDT")
        )
        assert set(res_btc.scalars().all()) == {"spot", "futures"}

        # bersihkan supaya test lain tidak terpengaruh
        await session.execute(delete(Analysis))
        await session.execute(delete(User))
        await session.commit()

    await engine.dispose()
