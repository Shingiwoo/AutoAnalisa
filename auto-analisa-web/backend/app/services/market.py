import ccxt
import pandas as pd
from typing import Dict


ex = ccxt.binance()

def _normalize_symbol(sym: str) -> str:
    s = sym.replace(':USDT', '/USDT') if ':USDT' in sym else sym
    if '/' in s:
        return s
    # convert e.g. XRPUSDT -> XRP/USDT
    su = s.upper()
    if su.endswith('USDT') and '/' not in su:
        base = su[:-4]
        return f"{base}/USDT"
    return s


async def fetch_klines(symbol: str, timeframe: str, limit: int = 500) -> pd.DataFrame:
    # catatan: ccxt sync; untuk lokal ok dipanggil di fungsi async
    symbol = _normalize_symbol(symbol)
    ohlcv = ex.fetch_ohlcv(symbol, timeframe=timeframe, limit=limit)
    df = pd.DataFrame(ohlcv, columns=["ts", "open", "high", "low", "close", "volume"])
    return df


async def fetch_bundle(symbol: str, tfs=("4h", "1h", "15m", "5m")) -> Dict[str, pd.DataFrame]:
    out: Dict[str, pd.DataFrame] = {}
    for tf in tfs:
        out[tf] = await fetch_klines(symbol, tf, 300 if tf == "15m" else 600)
    return out
