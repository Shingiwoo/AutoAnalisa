import numpy as np
import pandas as pd


def ema(series: pd.Series, n: int):
    return series.ewm(span=n, adjust=False).mean()


def bb(series: pd.Series, n: int = 20, k: float = 2.0):
    mb = series.rolling(n).mean()
    sd = series.rolling(n).std(ddof=0)
    ub, dn = mb + k * sd, mb - k * sd
    return mb, ub, dn


def rsi(series: pd.Series, n: int = 14):
    delta = series.diff()
    gain = np.where(delta > 0, delta, 0.0)
    loss = np.where(delta < 0, -delta, 0.0)
    roll_up = pd.Series(gain, index=series.index).rolling(n).mean()
    roll_down = pd.Series(loss, index=series.index).rolling(n).mean()
    rs = roll_up / (roll_down + 1e-9)
    rsi_val = 100 - (100 / (1 + rs))
    return pd.Series(rsi_val, index=series.index)


def rsi_n(series: pd.Series, n: int) -> pd.Series:
    """Helper to compute RSI with arbitrary period.
    This mirrors rsi(series, n) but provides a clearer semantic for callers.
    """
    return rsi(series, n)


def macd(series: pd.Series):
    ema12 = series.ewm(span=12, adjust=False).mean()
    ema26 = series.ewm(span=26, adjust=False).mean()
    macd_val = ema12 - ema26
    signal = macd_val.ewm(span=9, adjust=False).mean()
    hist = macd_val - signal
    return macd_val, signal, hist


def atr(df: pd.DataFrame, n: int = 14):
    high, low, close = df["high"], df["low"], df["close"]
    prev_close = close.shift(1)
    tr = pd.concat(
        [
            (high - low),
            (high - prev_close).abs(),
            (low - prev_close).abs(),
        ],
        axis=1,
    ).max(axis=1)
    return tr.rolling(n).mean()
