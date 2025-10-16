from __future__ import annotations

from typing import List, Dict

import pandas as pd
import ccxt  # type: ignore

from .market import fetch_klines


EX_STABLES = {"USDT", "USDC", "BUSD", "FDUSD", "DAI", "TUSD"}
WINDOWS_H = {"fast": 12, "medium": 24, "swing": 24 * 7}  # hours


async def _load_symbols_usdt(market: str = 'binanceusdm') -> List[str]:
    market = (market or 'binanceusdm').lower()
    if 'usdm' in market or 'futures' in market:
        ex = ccxt.binanceusdm()
    else:
        ex = ccxt.binance()
    try:
        mkts = ex.load_markets()
        syms: List[str] = []
        for m in mkts.values():
            try:
                if not m.get('active', True):
                    continue
                base = str(m.get('base') or '').upper()
                quote = str(m.get('quote') or '').upper()
                if quote != 'USDT':
                    continue
                # Skip stables
                if base in EX_STABLES:
                    continue
                # Use unified symbol without slash (e.g., BTCUSDT) for consistency
                syms.append(f"{base}USDT")
            except Exception:
                continue
        # Deduplicate
        return sorted(list(dict.fromkeys(syms)))
    except Exception:
        # Fallback minimal universe
        return ["BTCUSDT", "ETHUSDT", "BNBUSDT", "XRPUSDT"]


async def compute_outperformers(mode: str, market: str = 'binanceusdm', limit: int = 10) -> List[Dict]:
    lookback_h = WINDOWS_H.get(str(mode), 24)
    market_type = 'futures' if ('usdm' in str(market).lower() or 'futures' in str(market).lower()) else 'spot'

    syms = await _load_symbols_usdt(market=market)

    # Benchmark BTC ret over the same 1h horizon
    btc_df = await fetch_klines('BTCUSDT', '1h', limit=max(lookback_h + 1, 2), market=market_type)
    if btc_df is None or len(btc_df) < 2:
        return []
    btc_ret = float(btc_df['close'].iloc[-1] / btc_df['close'].iloc[0] - 1.0)

    rows = []
    for s in syms:
        try:
            df = await fetch_klines(s, '1h', limit=max(lookback_h + 1, 2), market=market_type)
            if df is None or len(df) < 2:
                continue
            ret = float(df['close'].iloc[-1] / df['close'].iloc[0] - 1.0)
            rs = ret - btc_ret
            rows.append({'symbol': s, 'ret': ret, 'rs': rs})
        except Exception:
            continue

    if not rows:
        return []

    df = pd.DataFrame(rows)
    # alpha z-score on RS
    try:
        mu = float(df['rs'].mean())
        sd = float(df['rs'].std(ddof=0) or 1.0)
        df['alpha_z'] = (df['rs'] - mu) / sd
    except Exception:
        df['alpha_z'] = 0.0

    # Composite score (simple): emphasize RS, add alpha_z gently
    df['score'] = df['rs'] + 0.10 * df['alpha_z']
    df.sort_values('score', ascending=False, inplace=True)

    out: List[Dict] = []
    for _, r in df.head(int(limit or 10)).iterrows():
        out.append({
            'symbol': str(r['symbol']),
            'score': round(float(r['score']), 6),
            'rsh': round(float(r['ret']), 6),
            'alpha_z': round(float(r['alpha_z']), 2),
        })
    return out

