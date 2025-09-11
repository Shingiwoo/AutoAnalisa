import pytest
import httpx
import asyncio
import pandas as pd

from app.main import app
from app.storage.db import SessionLocal
from app.models import User


@pytest.mark.asyncio
async def test_auth_register_login_me():
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        # Register
        r = await client.post("/api/auth/register", json={"email":"u1@example.com","password":"secret123"})
        assert r.status_code in (200, 409)  # may exist from previous run
        # Login
        r = await client.post("/api/auth/login", json={"email":"u1@example.com","password":"secret123"})
        assert r.status_code == 200
        tok = r.json()["token"]
        # Me
        r = await client.get("/api/auth/me", headers={"Authorization": f"Bearer {tok}"})
        assert r.status_code == 200
        me = r.json()
        assert me.get("email") == "u1@example.com"


@pytest.mark.asyncio
async def test_watchlist_crud_and_limit(monkeypatch):
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        # Ensure user and token
        await client.post("/api/auth/register", json={"email":"w1@example.com","password":"secret123"})
        r = await client.post("/api/auth/login", json={"email":"w1@example.com","password":"secret123"})
        tok = r.json()["token"]
        H = {"Authorization": f"Bearer {tok}"}
        # clear existing entries if any (idempotent for re-runs)
        rr = await client.get("/api/watchlist", headers=H)
        if rr.status_code == 200:
            for s in rr.json():
                await client.delete(f"/api/watchlist/{s}", headers=H)
        # Add up to 4 entries
        for s in ["AAAUSDT","BBBUSDT","CCCUSDT","DDDUSDT"]:
            rr = await client.post("/api/watchlist/add", params={"symbol": s}, headers=H)
            assert rr.status_code == 200
        # 5th should be 429 (limit reached)
        rr = await client.post("/api/watchlist/add", params={"symbol": "EEEUSDT"}, headers=H)
        assert rr.status_code == 429
        # List and delete
        rr = await client.get("/api/watchlist", headers=H)
        assert rr.status_code == 200 and len(rr.json()) == 4
        rr = await client.delete("/api/watchlist/CCCUSDT", headers=H)
        assert rr.status_code == 200


def _df(n=300, base=100.0):
    ts = list(range(1, n+1))
    close = [base + i*0.1 for i in range(n)]
    open_ = [c-0.05 for c in close]
    high = [c+0.1 for c in close]
    low = [c-0.1 for c in close]
    vol = [100+i for i in range(n)]
    return pd.DataFrame({"ts":ts, "open":open_, "high":high, "low":low, "close":close, "volume":vol})


@pytest.mark.asyncio
async def test_analyze_and_save_snapshot(monkeypatch):
    # Mock market and LLM
    async def fake_fetch(symbol, tf, limit):
        return _df(320, base=100.0)
    # Router ohlcv mengimpor fetch_klines langsung, patch di lokasi router
    import app.routers.market as r_market
    monkeypatch.setattr(r_market, "fetch_klines", fake_fetch, raising=True)
    from app import services
    # patch analyze worker path via services.market
    monkeypatch.setattr(services.market, "fetch_klines", fake_fetch, raising=True)
    monkeypatch.setattr(services.llm, "ask_llm", lambda prompt: ("narasi uji", {"prompt_tokens":0, "completion_tokens":0, "total_tokens":0}), raising=True)
    monkeypatch.setattr(services.llm, "ask_llm", lambda prompt: ("narasi uji", {"prompt_tokens":0, "completion_tokens":0, "total_tokens":0}), raising=True)

    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        # Auth
        await client.post("/api/auth/register", json={"email":"a1@example.com","password":"secret123"})
        r = await client.post("/api/auth/login", json={"email":"a1@example.com","password":"secret123"})
        tok = r.json()["token"]
        H = {"Authorization": f"Bearer {tok}"}
        # Analyze
        r = await client.post("/api/analyze", json={"symbol":"OPUSDT"}, headers=H)
        assert r.status_code == 200
        aid = r.json()["id"]
        # List active
        r = await client.get("/api/analyses", headers=H)
        assert r.status_code == 200 and len(r.json()) >= 1
        # Save snapshot
        r = await client.post(f"/api/analyses/{aid}/save", headers=H)
        assert r.status_code == 200


@pytest.mark.asyncio
async def test_ohlcv_endpoint_mock(monkeypatch):
    async def fake_fetch(symbol, tf, limit):
        return _df(30, base=50.0)
    import app.routers.market as r_market
    monkeypatch.setattr(r_market, "fetch_klines", fake_fetch, raising=True)

    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        await client.post("/api/auth/register", json={"email":"m1@example.com","password":"secret123"})
        r = await client.post("/api/auth/login", json={"email":"m1@example.com","password":"secret123"})
        tok = r.json()["token"]
        H = {"Authorization": f"Bearer {tok}"}
        r = await client.get("/api/ohlcv", params={"symbol":"OPUSDT","tf":"15m","limit":30}, headers=H)
        assert r.status_code == 200 and isinstance(r.json(), list) and len(r.json()) > 0


@pytest.mark.asyncio
async def test_macro_generate_and_today(monkeypatch):
    from app import services
    monkeypatch.setattr(services.llm, "ask_llm", lambda prompt: ("Ringkasan makro uji", {"prompt_tokens":0,"completion_tokens":0,"total_tokens":0}), raising=True)

    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        # Create user and make admin
        await client.post("/api/auth/register", json={"email":"admin@example.com","password":"secret123"})
        r = await client.post("/api/auth/login", json={"email":"admin@example.com","password":"secret123"})
        tok = r.json()["token"]
        # get id and promote
        r = await client.get("/api/auth/me", headers={"Authorization": f"Bearer {tok}"})
        uid = r.json()["id"]
        async with SessionLocal() as s:
            u = await s.get(User, uid)
            u.role = "admin"
            await s.commit()
        # call admin macro
        H = {"Authorization": f"Bearer {tok}"}
        r = await client.post("/api/admin/macro/generate", headers=H)
        assert r.status_code == 200
        r = await client.get("/api/macro/today")
        assert r.status_code == 200 and "narrative" in r.json()
