import json
import os
import types

import pandas as pd

from autoanalisa.payload.builder import build_payload


def test_build_payload_with_monkeypatch(monkeypatch):
    # prepare CSV data
    base = os.path.dirname(__file__)
    df_1h = pd.read_csv(os.path.join(base, "data", "IMX_1H.csv"))
    df_15 = pd.read_csv(os.path.join(base, "data", "IMX_15m.csv"))

    # convert to tz-aware in builder-like shapes
    for df in (df_1h, df_15):
        for c in ["open", "high", "low", "close", "volume"]:
            df[c] = df[c].astype(float)
        df["open_time"] = pd.to_datetime(df["open_time"], utc=True)
        df["close_time"] = pd.to_datetime(df["close_time"], utc=True)

    # monkeypatch datasource for futures
    import autoanalisa.datasource.binance_futures as bf

    def fake_exchange_info(symbol):
        return {"precision": {"price": 0.0001, "qty": 0.1, "min_notional": 5.0}, "fees": {"maker": 0.0002, "taker": 0.0004}}

    def fake_klines(symbol, interval, limit=300, tz_str="Asia/Jakarta"):
        if interval in ("1h", "4h", "1d"):
            df = df_1h.copy()
        else:
            df = df_15.copy()
        df["open_time"] = pd.to_datetime(df["open_time"], utc=True).dt.tz_convert(tz_str)
        df["close_time"] = pd.to_datetime(df["close_time"], utc=True).dt.tz_convert(tz_str)
        return df

    def fake_depth(symbol, limit=5):
        return {"best_bid": 0.9, "best_ask": 0.901, "spread": 0.001, "ob_imbalance_5": 0.55}

    def fake_mark_index(symbol):
        return {"mark_price": 0.9, "index_price": 0.9}

    def fake_funding(symbol):
        return {"funding_rate": 0.0001, "next_funding_ts": None}

    def fake_oi(symbol):
        return 100000.0

    def fake_lsr(symbol, period="5m", limit=1):
        return 1.0

    monkeypatch.setattr(bf, "get_exchange_info", fake_exchange_info)
    monkeypatch.setattr(bf, "get_klines", fake_klines)
    monkeypatch.setattr(bf, "get_depth", fake_depth)
    monkeypatch.setattr(bf, "get_mark_index", fake_mark_index)
    monkeypatch.setattr(bf, "get_funding", fake_funding)
    monkeypatch.setattr(bf, "get_oi", fake_oi)
    monkeypatch.setattr(bf, "get_long_short_ratio", fake_lsr)

    payload = build_payload("IMXUSDT", market="futures", contract="perp", tfs=["1D", "4H", "1H", "15m"], tz="Asia/Jakarta", use_fvg=False)

    # Asserts
    assert payload["symbol"] == "IMXUSDT"
    assert payload["market"] == "futures"
    for tf in ("1D", "4H", "1H", "15m"):
        assert tf in payload["tf"]
        tfb = payload["tf"][tf]
        assert "ema" in tfb and "bb" in tfb and "rsi" in tfb and "stochrsi" in tfb and "macd" in tfb
        assert "+07:00" in tfb["close_time"]
    assert payload["derivatives"]["funding_rate"] is not None
    assert payload["orderbook"]["spread"] >= 0
    assert payload["insufficient_history"] in (True, False)


def test_insufficient_history_flag(monkeypatch):
    import autoanalisa.datasource.binance_spot as bs
    import pandas as pd
    # short df (<150 rows)
    df = pd.DataFrame({
        "open_time": pd.date_range("2025-09-15", periods=100, freq="15min", tz="Asia/Jakarta"),
        "open": 0.9, "high": 0.91, "low": 0.89, "close": 0.9, "volume": 1000,
        "close_time": pd.date_range("2025-09-15", periods=100, freq="15min", tz="Asia/Jakarta")
    })

    monkeypatch.setattr(bs, "get_exchange_info", lambda s: {"precision": {"price": 0.0001, "qty": 0.1, "min_notional": 5.0}, "fees": {"maker": 0.001, "taker": 0.001}})
    monkeypatch.setattr(bs, "get_klines", lambda symbol, interval, limit=300, tz_str="Asia/Jakarta": df)
    monkeypatch.setattr(bs, "get_depth", lambda symbol, limit=5: {"best_bid": 0.9, "best_ask": 0.901, "spread": 0.001, "ob_imbalance_5": 0.5})

    payload = build_payload("IMXUSDT", market="spot", contract="perp", tfs=["1D", "4H", "1H", "15m"], tz="Asia/Jakarta", use_fvg=False)
    assert payload["insufficient_history"] is True

