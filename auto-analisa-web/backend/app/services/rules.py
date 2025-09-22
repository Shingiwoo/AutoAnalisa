from .indicators import ema, bb, rsi, macd, atr, rsi_n
import numpy as np


class Features:
    def __init__(self, bundle):
        self.b = bundle  # dict tf->df

    def enrich(self):
        for tf, df in self.b.items():
            df["ema5"] = ema(df.close, 5)
            df["ema20"] = ema(df.close, 20)
            df["ema50"] = ema(df.close, 50)
            df["ema100"] = ema(df.close, 100)
            df["ema200"] = ema(df.close, 200)
            df["mb"], df["ub"], df["dn"] = bb(df.close)
            df["rsi14"] = rsi(df.close, 14)
            # Short RSI window for scalping (e.g., divergence checks on 5m)
            try:
                df["rsi6"] = rsi_n(df.close, 6)
            except Exception:
                df["rsi6"] = df["rsi14"]
            m, s, h = macd(df.close)
            df["macd"], df["signal"], df["hist"] = m, s, h
            df["atr14"] = atr(df, 14)
        return self

    def latest(self, tf):
        return self.b[tf].iloc[-1]


def score_symbol(feat: "Features") -> int:
    f4, f1, f15 = feat.latest("4h"), feat.latest("1h"), feat.latest("15m")
    ts = sum(
        [
            f15.ema5 > f15.ema20 > f15.ema50 > f15.ema100 > f15.ema200,
            f1.ema5 > f1.ema20 > f1.ema50 > f1.ema100 > f1.ema200,
        ]
    ) * 5  # 0,5,10
    loc = 0
    loc += 5 if f1.close > f1.mb else 0
    loc += 5 if f4.close < f4.ub else 0
    mom = 5 if 55 <= f1.rsi14 <= 68 else (3 if 50 <= f1.rsi14 < 55 else 1)
    vol = 5  # placeholder; bisa pakai MA-volume
    cl = 5  # placeholder: akan naik bila RR ok
    return int(ts + loc + mom + vol + cl)


def _swing_points(df, kind: str = "high", lookback: int = 120, count: int = 3) -> list[float]:
    try:
        series = df[kind].tail(lookback)
        if series.empty:
            return []
        if kind == "high":
            vals = series.nlargest(count * 2).unique()[: count * 2]
            vals = sorted(vals)[-count:]
        else:
            vals = series.nsmallest(count * 2).unique()[: count * 2]
            vals = sorted(vals)[:count]
        return [round(float(v), 6) for v in vals if np.isfinite(v)]
    except Exception:
        return []


def make_levels(feat: "Features"):
    f1, f15, f4 = feat.latest("1h"), feat.latest("15m"), feat.latest("4h")
    support1 = round(float(max(min(f15.mb, f15.ema20), min(f1.mb, f1.ema20))), 6)
    support2 = round(float(min(f15.ema50, f1.ema50)), 6)
    support3 = round(float(min(f4.mb, getattr(f4, "ema100", f4.ema50))), 6)
    res1 = round(float(max(f1.ub, f1.high)), 6)
    res2 = round(float(max(f4.ub, f4.high)), 6)
    res3 = round(float(max(f4.high * 1.01, getattr(f4, "ema200", f4.ub))), 6)
    swing_highs = _swing_points(feat.b["15m"], "high", 160, 3)
    if len(swing_highs) < 3:
        swing_highs = (_swing_points(feat.b["1h"], "high", 120, 3) + swing_highs)[-3:]
    swing_lows = _swing_points(feat.b["15m"], "low", 160, 3)
    return {
        "support": [support1, support2, support3],
        "resistance": [res1, res2, res3],
        "swing_highs": swing_highs,
        "swing_lows": swing_lows,
    }


# Optional helper for 5-bar lookback (used by scalping setups)
def last5(series):
    try:
        vals = series.tail(5).tolist()
    except Exception:
        try:
            vals = list(series)[-5:]
        except Exception:
            vals = []
    return [float(x) for x in vals]
