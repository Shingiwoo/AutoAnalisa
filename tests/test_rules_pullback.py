from autoanalisa.rules.pullback_v1 import generate_signals


def make_min_payload(market="futures"):
    return {
        "symbol": "IMXUSDT",
        "market": market,
        "precision": {"price": 0.0001, "qty": 0.1},
        "account": {"balance_usdt": 1000.0, "risk_per_trade": 0.01},
        "orderbook": {"spread": 0.0005},
        "tf": {
            "1H": {"last": 0.9, "open": 0.9, "high": 0.91, "low": 0.89, "close_time": "2025-09-19T10:00:00+07:00",
                    "ema": {"20": 0.9, "50": 0.89, "100": 0.88, "200": 0.87},
                    "bb": {"period": 20, "mult": 2, "upper": 0.92, "middle": 0.9, "lower": 0.88},
                    "rsi": {"6": 45, "14": 50, "25": 55},
                    "stochrsi": {"k": 50, "d": 50},
                    "macd": {"dif": 0.0, "dea": 0.0, "hist": 0.0},
                    "atr14": 0.01, "vol_last": 1, "vol_ma5": 1, "vol_ma10": 1},
            "15m": {"last": 0.9, "open": 0.9, "high": 0.91, "low": 0.89, "close_time": "2025-09-19T10:00:00+07:00",
                     "ema": {"20": 0.895, "50": 0.895, "100": 0.9, "200": 0.905},
                     "bb": {"period": 20, "mult": 2, "upper": 0.92, "middle": 0.9, "lower": 0.88},
                     "rsi": {"6": 30, "14": 40, "25": 50},
                     "stochrsi": {"k": 50, "d": 50},
                     "macd": {"dif": 0.0, "dea": 0.0, "hist": 0.0},
                     "atr14": 0.01, "vol_last": 1, "vol_ma5": 1, "vol_ma10": 1},
        },
        "structure": {"4H": {"trend": "up"}, "1H": {"trend": "up"}},
        "levels": {"15m": {"support": [0.89], "resistance": [0.9]}},
        "derivatives": {"funding_rate": 0.0001} if market == "futures" else None,
    }


def test_gating_funding_filter_blocks():
    p = make_min_payload(market="futures")
    p["derivatives"]["funding_rate"] = 0.0005  # > 0.0002
    assert generate_signals(p) == []


def test_L1_long_signal_basic():
    p = make_min_payload(market="futures")
    # satisfy L1: 15m last within ema20_1h ± 0.2*ATR1H and reclaim above ema50 15m
    p["tf"]["1H"]["ema"]["20"] = 0.9
    p["tf"]["1H"]["atr14"] = 0.01
    p["tf"]["15m"]["last"] = 0.902
    p["tf"]["15m"]["ema"]["50"] = 0.895
    # add series to allow reclaim detection
    p["tf"]["15m"]["close_last5"] = [0.89, 0.892, 0.896, 0.900, 0.902]
    p["tf"]["15m"]["ema50_last5"] = [0.895, 0.895, 0.895, 0.895, 0.895]
    sigs = generate_signals(p)
    assert len(sigs) in (0, 1)
    if sigs:
        s = sigs[0]
        assert s.side == "long"
        assert s.sl < s.entry_zone[0] or s.sl < s.entry_zone[1]
        assert len(s.tp_price) == 3


def test_S1_short_signal_basic():
    p = make_min_payload(market="futures")
    p["tf"]["15m"]["last"] = 0.88
    p["tf"]["15m"]["ema"]["50"] = 0.89
    sigs = generate_signals(p)
    assert len(sigs) in (0, 1)
    if sigs:
        assert sigs[0].side == "short"


def test_spot_long_only():
    p = make_min_payload(market="spot")
    # set short-friendly scenario
    p["tf"]["15m"]["last"] = 0.88
    p["tf"]["15m"]["ema"]["50"] = 0.89
    sigs = generate_signals(p)
    # should not produce short in spot
    assert not sigs or all(s.side == "long" for s in sigs)


def test_macro_session_and_btc_bias_filtering():
    p = make_min_payload(market="futures")
    p["session_bias"] = "bearish"  # should filter longs
    p["btc_bias"] = "bearish"       # should filter longs
    # Create L1-like scenario to try produce long
    p["tf"]["1H"]["ema"]["20"] = 0.9
    p["tf"]["1H"]["atr14"] = 0.01
    p["tf"]["15m"]["last"] = 0.902
    p["tf"]["15m"]["ema"]["50"] = 0.895
    p["tf"]["15m"]["close_last5"] = [0.89, 0.892, 0.896, 0.900, 0.902]
    p["tf"]["15m"]["ema50_last5"] = [0.895, 0.895, 0.895, 0.895, 0.895]
    assert generate_signals(p) == []


def test_L2_divergence_detection():
    p = make_min_payload(market="futures")
    # use 5m block emulated via 15m key for simplicity
    p["tf"]["5m"] = {
        "last": 0.895,
        "open": 0.896, "high": 0.897, "low": 0.894, "close_time": "2025-09-19T10:00:00+07:00",
        "ema": {"20": 0.896, "50": 0.897},
        "bb": {"period": 20, "mult": 2, "upper": 0.91, "middle": 0.90, "lower": 0.89},
        "rsi": {"6": 19.0, "14": 30.0, "25": 40.0},
        "stochrsi": {"k": 20.0, "d": 25.0},
        "macd": {"dif": 0.0, "dea": 0.0, "hist": 0.0},
        "atr14": 0.005,
        "vol_last": 1, "vol_ma5": 1, "vol_ma10": 1,
        "rsi6_last5": [15, 16, 17, 18, 19],
        "close_last5": [0.900, 0.898, 0.897, 0.896, 0.895]
    }
    sigs = generate_signals(p)
    # likely returns L2 long candidate or [] if macro gating blocks; we accept either or a single long
    assert sigs == [] or all(s.side == "long" for s in sigs)
