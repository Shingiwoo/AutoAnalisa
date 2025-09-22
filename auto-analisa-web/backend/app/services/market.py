import ccxt
import os
import pandas as pd
from typing import Dict


ex = ccxt.binance()
ex_usdm = ccxt.binanceusdm()

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


async def fetch_klines(symbol: str, timeframe: str, limit: int = 500, market: str = "spot") -> pd.DataFrame:
    # catatan: ccxt sync; untuk lokal ok dipanggil di fungsi async
    symbol = _normalize_symbol(symbol)
    # Force offline synthetic data if env set (e.g., ISP blocks Binance DNS)
    if os.getenv("MARKET_OFFLINE", "").strip().lower() in {"1", "true", "yes", "on"}:
        try:
            import time
            import numpy as np
            now = int(time.time() * 1000)
            step = {
                "5m": 5 * 60 * 1000,
                "15m": 15 * 60 * 1000,
                "1h": 60 * 60 * 1000,
                "4h": 4 * 60 * 60 * 1000,
            }.get(timeframe, 60 * 60 * 1000)
            n = int(limit or 200)
            ts = np.array([now - step * (n - i) for i in range(n)], dtype=np.int64)
            # Anchor synthetic base near spot price when possible
            base = 100.0
            try:
                t = ex.fetch_ticker(symbol)
                last = t.get("last") or t.get("close")
                if isinstance(last, (int, float)) and last > 0:
                    base = float(last)
            except Exception:
                pass
            close = base + np.linspace(0, n * 0.05, n) + np.sin(np.linspace(0, 6.28, n)) * 0.5
            open_ = close - 0.05
            high = close + 0.1
            low = close - 0.1
            vol = np.linspace(100, 100 + n, n)
            df = pd.DataFrame({"ts": ts, "open": open_, "high": high, "low": low, "close": close, "volume": vol})
            return df
        except Exception:
            pass
    try:
        client = ex if str(market).lower() != "futures" else ex_usdm
        ohlcv = client.fetch_ohlcv(symbol, timeframe=timeframe, limit=limit)
        df = pd.DataFrame(ohlcv, columns=["ts", "open", "high", "low", "close", "volume"])
        return df
    except Exception:
        # If futures failed, try spot OHLCV as a close visual proxy
        try:
            alt = ex.fetch_ohlcv(symbol, timeframe=timeframe, limit=limit)
            df = pd.DataFrame(alt, columns=["ts", "open", "high", "low", "close", "volume"])
            return df
        except Exception:
            # OFFLINE fallback: synth data anchored near spot ticker when available
            import time
            import numpy as np
            now = int(time.time() * 1000)
            step = {
                "5m": 5 * 60 * 1000,
                "15m": 15 * 60 * 1000,
                "1h": 60 * 60 * 1000,
                "4h": 4 * 60 * 60 * 1000,
            }.get(timeframe, 60 * 60 * 1000)
            n = int(limit or 200)
            ts = np.array([now - step * (n - i) for i in range(n)], dtype=np.int64)
            base = 100.0
            try:
                t = ex.fetch_ticker(symbol)
                last = t.get("last") or t.get("close")
                if isinstance(last, (int, float)) and last > 0:
                    base = float(last)
            except Exception:
                pass
            close = base + np.linspace(0, n * 0.05, n) + np.sin(np.linspace(0, 6.28, n)) * 0.5
            open_ = close - 0.05
            high = close + 0.1
            low = close - 0.1
            vol = np.linspace(100, 100 + n, n)
            df = pd.DataFrame({"ts": ts, "open": open_, "high": high, "low": low, "close": close, "volume": vol})
            return df


async def fetch_bundle(symbol: str, tfs=("4h", "1h", "15m", "5m", "1m"), market: str = "spot") -> Dict[str, pd.DataFrame]:
    out: Dict[str, pd.DataFrame] = {}
    for tf in tfs:
        try:
            out[tf] = await fetch_klines(symbol, tf, 300 if tf == "15m" else 600, market=market)
        except TypeError:
            # compatibility with tests that monkeypatch fetch_klines(symbol, tf, limit)
            out[tf] = await fetch_klines(symbol, tf, 300 if tf == "15m" else 600)
    return out


async def fetch_spread(symbol: str, market: str = "futures") -> float:
    """Fetch absolute spread (best_ask - best_bid) from order book.
    Falls back to 0.0 on failure. This is synchronous under ccxt, so
    calling from async is acceptable for local use.
    """
    try:
        client = ex_usdm if str(market).lower() == "futures" else ex
        ob = client.fetch_order_book(_normalize_symbol(symbol), limit=5)
        best_ask = float(ob['asks'][0][0]) if ob.get('asks') else None
        best_bid = float(ob['bids'][0][0]) if ob.get('bids') else None
        if best_ask is None or best_bid is None:
            return 0.0
        return max(0.0, best_ask - best_bid)
    except Exception:
        return 0.0
