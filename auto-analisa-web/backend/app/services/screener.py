from __future__ import annotations

from typing import Dict, List, Any
import numpy as np
import pandas as pd

from .signal_mtf import load_signal_config
from .market import fetch_klines


async def _load_close(symbol: str, tf: str, limit: int = 240, market: str = 'futures') -> pd.Series:
    df = await fetch_klines(symbol, tf, limit=limit, market=market)
    s = pd.to_numeric(df['close'], errors='coerce')
    s.index = pd.to_datetime(df['ts'], unit='ms', utc=True)
    return s


def _pct_change(s: pd.Series, n: int) -> float:
    if s is None or len(s) <= n:
        return 0.0
    a = float(s.iloc[-n])
    b = float(s.iloc[-1])
    return 0.0 if a == 0 else (b - a) / a


def _zscore(x: np.ndarray) -> float:
    x = np.asarray(x, dtype='float64')
    if x.size < 3:
        return 0.0
    m = np.nanmean(x)
    sd = np.nanstd(x) or 1.0
    return float((x[-1] - m) / sd)


async def screener_outperformers(symbols: List[str], mode: str = 'medium', market: str = 'futures', top: int = 20) -> Dict[str, Any]:
    cfg = load_signal_config().get('outperformer', {})
    windows = cfg.get('windows', { 'short':'1h', 'mid':'4h', 'long':'1D' })
    weights = cfg.get('weights', { 'rs':0.45, 'alpha':0.25, 'ratio_breakout':0.20, 'vol_oi':0.10 })
    thr = cfg.get('thresholds', { 'score_min': 0.35, 'alpha_z_min': 0.5 })

    out: List[Dict[str, Any]] = []
    # Load BTC closes once per window
    btc_s: Dict[str, pd.Series] = {}
    for _, tf in windows.items():
        if tf not in btc_s:
            btc_s[tf] = await _load_close('BTCUSDT', tf, limit=240, market=market)

    for sym in symbols:
        try:
            row: Dict[str, Any] = { 'symbol': sym.upper() }
            # returns
            rs_score = 0.0
            rs_parts = []
            for label, tf in windows.items():
                alt = await _load_close(sym, tf, limit=240, market=market)
                btc = btc_s[tf]
                # align indices
                joined = pd.concat([alt.rename('alt'), btc.rename('btc')], axis=1).dropna()
                if joined.empty:
                    continue
                # simple beta via covariance/variance
                if len(joined) >= 30:
                    r_alt = joined['alt'].pct_change().dropna().values
                    r_btc = joined['btc'].pct_change().dropna().values
                    n = min(len(r_alt), len(r_btc))
                    r_alt, r_btc = r_alt[-n:], r_btc[-n:]
                    beta = float(np.cov(r_alt, r_btc)[0,1] / (np.var(r_btc) or 1.0))
                    rs = float(r_alt[-1] - beta * r_btc[-1])
                else:
                    # fallback: last change difference
                    rs = float(joined['alt'].pct_change().iloc[-1] - joined['btc'].pct_change().iloc[-1])
                row[f'rs_{label}'] = rs
                rs_parts.append(rs)
            # aggregate RS
            if rs_parts:
                rs_score = float(np.nanmean(rs_parts))
            # alpha z (rough): residual mean z-score
            alpha_z = float(_zscore(np.array(rs_parts))) if rs_parts else 0.0
            row['alpha_z'] = alpha_z
            # ratio breakout
            try:
                ratio = (await _load_close(sym, windows.get('mid','4h'), limit=120, market=market)) / (btc_s[windows.get('mid','4h')])
                ratio = ratio.dropna()
                ma = ratio.rolling(50, min_periods=10).mean()
                sd = ratio.rolling(50, min_periods=10).std()
                ratio_break = bool(len(ratio) and ratio.iloc[-1] > (ma.iloc[-1] + 2.0*(sd.iloc[-1] or 0)))
            except Exception:
                ratio_break = False
            row['ratio_break'] = ratio_break
            # score
            score = (
                weights.get('rs',0.45) * rs_score +
                weights.get('alpha',0.25) * (alpha_z/3.0) +
                weights.get('ratio_breakout',0.20) * (1.0 if ratio_break else 0.0)
            )
            row['score'] = float(score)
            out.append(row)
        except Exception:
            continue

    out_sorted = sorted(out, key=lambda x: x.get('score', 0.0), reverse=True)[:int(top or 20)]
    return { 'results': out_sorted }

