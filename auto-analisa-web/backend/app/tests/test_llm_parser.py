import os
import httpx
import pandas as pd
import pytest

from app.main import app


def _df(n=320, base=100.0):
    ts = list(range(1, n + 1))
    close = [base + i * 0.1 for i in range(n)]
    open_ = [c - 0.05 for c in close]
    high = [c + 0.1 for c in close]
    low = [c - 0.1 for c in close]
    vol = [100 + i for i in range(n)]
    return pd.DataFrame({"ts": ts, "open": open_, "high": high, "low": low, "close": close, "volume": vol})


@pytest.mark.asyncio
async def test_verify_llm_accepts_string_numbers_and_rounds(monkeypatch):
    # Patch market fetch so analyze works without network
    async def fake_fetch(symbol, tf, limit):
        return _df(320, base=100.0)
    import app.routers.market as r_market
    from app import services
    monkeypatch.setattr(r_market, "fetch_klines", fake_fetch, raising=True)
    monkeypatch.setattr(services.market, "fetch_klines", fake_fetch, raising=True)

    # Allow LLM and fake response with numeric strings
    async def allow_llm(db):
        return True, None
    # Patch langsung nama yang dipakai router analyses
    import app.routers.analyses as r_analyses
    monkeypatch.setattr(r_analyses, "should_use_llm", allow_llm, raising=True)
    os.environ["OPENAI_API_KEY"] = "dummy"

    # Round to 0.01 tick explicitly
    import app.services.rounding as rnd
    monkeypatch.setattr(rnd, "_tick_size_for", lambda s: 0.01, raising=True)

    # ask_llm returns SPOT II style with strings for numbers
    payload = {
        "rencana_jual_beli": {
            "entries": [
                {"range": ["100.001", "100.001"], "weight": 0.6},
                {"range": ["98.339", "98.339"], "weight": 0.4},
            ],
            "invalid": "95.001",
        },
        "tp": [
            {"name": "TP1", "range": ["110.004", "110.004"]},
            {"name": "TP2", "range": ["115.008", "115.008"]},
        ],
    }
    import json
    monkeypatch.setattr(r_analyses, "ask_llm", lambda prompt: (json.dumps(payload), {"prompt_tokens": 10, "completion_tokens": 20}), raising=True)

    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        # Auth
        await client.post("/api/auth/register", json={"email": "tllm@example.com", "password": "secret123"})
        r = await client.post("/api/auth/login", json={"email": "tllm@example.com", "password": "secret123"})
        tok = r.json()["token"]
        H = {"Authorization": f"Bearer {tok}"}
        # Analyze to get analysis id
        r = await client.post("/api/analyze", json={"symbol": "OPUSDT"}, headers=H)
        assert r.status_code == 200
        aid = r.json()["id"]
        # Verify LLM
        r = await client.post(f"/api/analyses/{aid}/verify", headers=H)
        assert r.status_code == 200
        ver = r.json()["verification"]
        s2 = ver.get("suggestions") or {}
        # spot2_json rounded is stored separately; we also accept suggestions normalised in cand path
        s2full = ver.get("spot2_json") or {}
        # Check TP and invalid rounded to 2 decimals in spot2_json
        tps = [float((t.get("range") or [0])[0]) for t in (s2full.get("tp") or [])]
        inv = float((s2full.get("rencana_jual_beli") or {}).get("invalid"))
        assert all(abs(x - round(x, 2)) < 1e-9 for x in tps)
        assert abs(inv - round(inv, 2)) < 1e-9


@pytest.mark.asyncio
async def test_verify_llm_missing_entries_or_tp_rejected(monkeypatch):
    # Market monkeypatch
    async def fake_fetch(symbol, tf, limit):
        return _df(320, base=100.0)
    import app.routers.market as r_market
    from app import services
    monkeypatch.setattr(r_market, "fetch_klines", fake_fetch, raising=True)
    monkeypatch.setattr(services.market, "fetch_klines", fake_fetch, raising=True)

    async def allow_llm(db):
        return True, None
    import app.routers.analyses as r_analyses
    monkeypatch.setattr(r_analyses, "should_use_llm", allow_llm, raising=True)
    os.environ["OPENAI_API_KEY"] = "dummy"

    import json
    # ask_llm returns object without tp
    bad1 = {"rencana_jual_beli": {"entries": [{"range": [100, 100], "weight": 1.0}]}}
    # ask_llm returns object without entries
    bad2 = {"tp": [{"name": "TP1", "range": [110, 110]}]}

    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        # Auth
        await client.post("/api/auth/register", json={"email": "tllm2@example.com", "password": "secret123"})
        r = await client.post("/api/auth/login", json={"email": "tllm2@example.com", "password": "secret123"})
        tok = r.json()["token"]
        H = {"Authorization": f"Bearer {tok}"}
        # Analyze to get analysis id
        r = await client.post("/api/analyze", json={"symbol": "OPUSDT"}, headers=H)
        aid = r.json()["id"]

        # Case 1: missing tp
        monkeypatch.setattr(r_analyses, "ask_llm", lambda prompt: (json.dumps(bad1), {"prompt_tokens": 1, "completion_tokens": 1}), raising=True)
        r = await client.post(f"/api/analyses/{aid}/verify", headers=H)
        assert r.status_code == 422

        # Case 2: missing entries — buat user & analysis baru agar tidak kena rate-limit
        await client.post("/api/auth/register", json={"email": "tllm3@example.com", "password": "secret123"})
        r = await client.post("/api/auth/login", json={"email": "tllm3@example.com", "password": "secret123"})
        tok2 = r.json()["token"]
        H2 = {"Authorization": f"Bearer {tok2}"}
        r = await client.post("/api/analyze", json={"symbol": "OPUSDT"}, headers=H2)
        aid2 = r.json()["id"]
        monkeypatch.setattr(r_analyses, "ask_llm", lambda prompt: (json.dumps(bad2), {"prompt_tokens": 1, "completion_tokens": 1}), raising=True)
        r = await client.post(f"/api/analyses/{aid2}/verify", headers=H2)
        assert r.status_code == 422
