
import os, sys, types
import pandas as pd
import numpy as np
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from app.services.strategy_futures import build_plan_futures
from app.services.rules import Features

def _mkdf(n=200, start=100.0, drift=0.02):
    ts = pd.date_range("2025-01-01", periods=n, freq="15min")
    close = np.cumsum(np.random.randn(n)*0.2 + drift) + start
    high = close + np.abs(np.random.randn(n)*0.1)
    low = close - np.abs(np.random.randn(n)*0.1)
    open_ = close + np.random.randn(n)*0.05
    return pd.DataFrame({"ts": ts, "open": open_, "high": high, "low": low, "close": close, "volume": np.random.rand(n)*1000})

def test_build_plan_futures_smoke():
    bundle = {"15m": _mkdf(), "1h": _mkdf(n=200, start=100, drift=0.01).rename_axis(index="ts"),
              "4h": _mkdf(n=200, start=100, drift=0.005)}
    feat = Features(bundle); feat.enrich()
    sig = {"funding":{"now":0.0001},"basis":{"bp":10.0},"taker_delta":{"m15":0.05},"lsr":{"positions":1.2},"orderbook":{"spread_bp":1.2}}
    plan = build_plan_futures(bundle, feat, side_hint="AUTO", fut_signals=sig, symbol="BTCUSDT")
    assert isinstance(plan, dict) and "entries" in plan and "invalids" in plan and "tp" in plan
    assert len(plan["entries"]) == 2 and len(plan["tp"]) == 2
    assert plan["metrics"]["rr_min"] >= 1.0
