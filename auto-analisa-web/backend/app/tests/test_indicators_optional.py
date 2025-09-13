import pandas as pd
from app.services.fvg import detect_fvg
from app.services.supply_demand import detect_zones


def _df_from_ohlc(ohlc):
    # ohlc: list of tuples (o,h,l,c)
    ts = list(range(len(ohlc)))
    open_, high, low, close = zip(*ohlc)
    return pd.DataFrame({"ts": ts, "open": open_, "high": high, "low": low, "close": close})


def test_fvg_detect_bull_gap():
    # Create a 3-candle bullish FVG: high[0] < low[2]
    ohlc = [
        (100, 101, 99, 100.5),
        (100.6, 101.2, 100.2, 101.0),
        (102.0, 102.5, 101.8, 102.3),  # low[2]=101.8 > high[0]=101.0 => FVG
        (102.2, 102.4, 101.7, 101.9),
    ]
    df = _df_from_ohlc(ohlc)
    out = detect_fvg(df)
    assert any(b.get("type") == "bull" for b in out), out


def test_supply_demand_detect_basic_zones():
    # Build swings: highs then lows
    ohlc = [
        (100, 101, 99.5, 100.5),
        (100.6, 101.5, 100.4, 101.0),  # potential swing high
        (101.0, 101.2, 100.6, 100.7),
        (100.6, 100.8, 100.1, 100.2),  # potential swing low
        (100.3, 100.7, 100.0, 100.5),
        (100.6, 101.0, 100.2, 100.8),
    ]
    df = _df_from_ohlc(ohlc)
    zones = detect_zones(df)
    assert isinstance(zones, list)
    assert any(z["type"] in ("supply", "demand") for z in zones)

