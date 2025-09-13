import pytest
import httpx
import pandas as pd
from datetime import datetime, timezone, timedelta

from app.main import app


def _make_ts_hours_utc(start_dt: datetime, hours: int, hour_utc: int):
    # produce timestamps at a fixed UTC hour across many days
    base = start_dt.replace(minute=0, second=0, microsecond=0, tzinfo=timezone.utc)
    out = []
    d = base
    for i in range(hours):
        out.append(int(d.replace(hour=hour_utc).timestamp() * 1000))
        d = d + timedelta(days=1)
    return out


@pytest.mark.asyncio
async def test_sessions_btc_wib_significant(monkeypatch):
    # Build 80 samples for WIB hour=9 (UTC hour=2), all positive returns
    ts = _make_ts_hours_utc(datetime(2024,1,1,0,0,0), 80, 2)
    open_ = [100.0 for _ in ts]
    close = [100.3 for _ in ts]  # +0.3% per bar
    high = [c+0.1 for c in close]
    low = [o-0.1 for o in open_]
    vol = [1000 for _ in ts]
    df = pd.DataFrame({"ts": ts, "open": open_, "high": high, "low": low, "close": close, "volume": vol})

    async def fake_fetch(symbol, tf, limit):
        return df
    # Patch fetch_klines used by sessions service via market module
    import app.services.sessions as sess
    monkeypatch.setattr(sess, "fetch_klines", fake_fetch, raising=True)

    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        r = await client.get("/api/sessions/btc/wib")
        assert r.status_code == 200
        buckets = r.json()
        # Should include hour 9 (WIB)
        hours = [b["hour"] for b in buckets]
        assert 9 in hours
