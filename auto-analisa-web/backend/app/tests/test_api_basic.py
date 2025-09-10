import pytest
import httpx
from app.main import app


@pytest.mark.asyncio
async def test_health():
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app, lifespan="on"), base_url="http://test") as client:
        r = await client.get("/api/health")
        assert r.status_code == 200
        assert r.json().get("ok") is True


# Catatan: tes /api/analyze idealnya memock fetch_klines untuk hindari jaringan.
