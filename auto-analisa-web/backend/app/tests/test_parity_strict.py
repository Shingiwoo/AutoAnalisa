import pandas as pd
from app.services.fvg import detect_fvg
from app.services.supply_demand import detect_zones
from app.services.parity import fvg_parity_stats, zones_parity_stats


def _df(ohlc):
    ts = list(range(len(ohlc)))
    o, h, l, c = zip(*ohlc)
    return pd.DataFrame({"ts": ts, "open": o, "high": h, "low": l, "close": c})


def test_fvg_parity_strict_identical():
    # Construct a clear bullish FVG pattern (high[0] < low[2])
    ohlc = [
        (100.0, 101.0, 99.5, 100.5),
        (100.6, 101.2, 100.4, 101.0),
        (102.0, 102.4, 101.8, 102.2),  # low[2]=101.8 > high[0]=101.0 => bull FVG
        (101.9, 102.1, 101.5, 101.7),
        (102.2, 102.6, 101.9, 102.0),
    ]
    df = _df(ohlc)
    ref = detect_fvg(df)
    got = detect_fvg(df)
    stats = fvg_parity_stats(ref, got, tol_price=1e-9, tol_idx=0)
    assert stats["f1"] == 1.0 and stats["precision"] == 1.0 and stats["recall"] == 1.0


def test_zones_parity_strict_identical():
    # Construct visible swing high and low
    ohlc = [
        (100.0, 101.0, 99.8, 100.8),
        (100.9, 101.6, 100.7, 101.3),  # likely swing high
        (101.2, 101.3, 100.9, 101.0),
        (100.8, 101.0, 100.2, 100.3),  # likely swing low
        (100.4, 100.9, 100.1, 100.7),
        (100.7, 101.1, 100.5, 100.9),
    ]
    df = _df(ohlc)
    ref = detect_zones(df)
    got = detect_zones(df)
    stats = zones_parity_stats(ref, got, tol_idx=0, min_iou=0.99)
    assert stats["f1"] == 1.0 and stats["precision"] == 1.0 and stats["recall"] == 1.0

