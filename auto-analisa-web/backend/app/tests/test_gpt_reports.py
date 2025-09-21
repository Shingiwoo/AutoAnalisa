import os
import datetime as dt
import pytest
import httpx

from app.main import app
from app.config import settings
from app.models import GPTReport
from app.storage.db import SessionLocal


@pytest.mark.asyncio
async def test_gpt_analyze_persist_and_fetch(monkeypatch):
    settings.REQUIRE_LOGIN = False
    os.environ["OPENAI_API_KEY"] = "test-key"

    async def _should_use_llm(db):
        return True, None

    async def _get_today_usage(db, user_id, kind, limit_override=None):
        return {"remaining": 5}

    async def _inc_usage(db, **kwargs):
        return None

    class _Settings:
        llm_daily_limit_futures = 40

    async def _get_or_init_settings(db):
        return _Settings()

    def _call_gpt(prompt):
        return (
            {
                "text": {
                    "section_scalping": {
                        "posisi": "LONG",
                        "tp": [1.1, 1.2, 1.3],
                        "sl": 0.9,
                        "strategi_singkat": ["Entry di support"],
                        "fundamental": ["BTC kuat"],
                    }
                },
                "overlay": {
                    "tf": "15m",
                    "lines": [
                        {"type": "TP", "label": "TP1", "price": 1.1},
                        {"type": "SL", "label": "SL", "price": 0.9},
                    ],
                    "zones": [],
                },
                "meta": {"engine": "unit-test"},
            },
            {"prompt_tokens": 10, "completion_tokens": 5},
        )

    monkeypatch.setattr("app.routers.gpt_analyze.should_use_llm", _should_use_llm)
    monkeypatch.setattr("app.routers.gpt_analyze.get_today_usage", _get_today_usage)
    monkeypatch.setattr("app.routers.gpt_analyze.inc_usage", _inc_usage)
    monkeypatch.setattr("app.routers.gpt_analyze.get_or_init_settings", _get_or_init_settings)
    monkeypatch.setattr("app.routers.gpt_analyze.call_gpt", _call_gpt)

    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(
            "/api/gpt/futures/analyze",
            json={"symbol": "btcusdt", "mode": "scalping", "payload": {}, "opts": {}},
        )
        assert resp.status_code == 200
        payload = resp.json()
        assert payload["report_id"] > 0
        assert payload["meta"]["engine"] == "unit-test"
        created_at = dt.datetime.fromisoformat(payload["created_at"])
        assert created_at.tzinfo is not None

        # Ensure tersimpan di DB
        async with SessionLocal() as session:
            row = await session.get(GPTReport, payload["report_id"])
            assert row is not None
            assert row.symbol == "BTCUSDT"
            assert row.mode == "scalping"
            assert row.text["section_scalping"]["posisi"] == "LONG"

        # GET cache sukses
        r2 = await client.get("/api/gpt/futures/report", params={"symbol": "BTCUSDT", "mode": "scalping"})
        assert r2.status_code == 200
        data = r2.json()
        assert data["report_id"] == payload["report_id"]
        assert data["text"]["section_scalping"]["posisi"] == "LONG"
        assert data["ttl"] == payload["ttl"]

        # nocache memaksa 404
        r3 = await client.get(
            "/api/gpt/futures/report",
            params={"symbol": "BTCUSDT", "mode": "scalping", "nocache": 1},
        )
        assert r3.status_code == 404

        # manipulasi TTL -> expired
        async with SessionLocal() as session:
            row = await session.get(GPTReport, payload["report_id"])
            row.created_at = (row.created_at or dt.datetime.now(dt.timezone.utc)) - dt.timedelta(hours=2)
            await session.commit()

        r4 = await client.get("/api/gpt/futures/report", params={"symbol": "BTCUSDT", "mode": "scalping"})
        assert r4.status_code == 404
