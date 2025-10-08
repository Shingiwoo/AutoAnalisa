from __future__ import annotations

from typing import Any, Dict, Tuple
import math

from .funding_service import FundingService
from .btcd_service import BTCDService
from .oi_service import OIService
from ..signal_mtf import load_signal_config, build_tf_map, _tf_key, _tf_normalize, _load_tf, compute_supertrend
from ..aggregator import weighted_avg
from ..indicators import ema, rsi, macd, atr
from ..scorer import score_supertrend, score_ema50, score_rsi, score_macd


FUND = FundingService()
BTCD = BTCDService()
OI = OIService()


def _cfg() -> Dict[str, Any]:
    cfg = load_signal_config()
    return cfg.get('context', {})


def funding_score(symbol: str) -> Tuple[int, float]:
    c = _cfg()
    eps = float(c.get('funding', {}).get('eps', 0.00005))
    v = float(FUND.get(symbol) or 0.0)
    if v > eps:
        return 1, v
    if v < -eps:
        return -1, v
    return 0, v


async def _trend_score(symbol: str, mode: str, market_type: str = 'futures') -> float:
    cfg = load_signal_config()
    P = cfg['presets'].get(mode, cfg['presets']['medium'])
    tf = P['tf']['trend']
    df = await _load_tf(symbol, tf, market_type=market_type, limit=600)
    st = compute_supertrend(df,
                            period=int((P.get('supertrend',{}).get('period',{}).get('trend') or P.get('supertrend',{}).get('period',{}).get('all',10))),
                            multiplier=float((P.get('supertrend',{}).get('multiplier',{}).get('trend') or P.get('supertrend',{}).get('multiplier',{}).get('all',3.0))),
                            src=str(P.get('supertrend',{}).get('src','hl2')),
                            change_atr=bool(P.get('supertrend',{}).get('change_atr',True)))
    w_ind = P['weights']['indicators']['trend']
    ema50_last = float(ema(df['close'], 50).iloc[-1]) if not df.empty else 0.0
    atr14_last = float(atr(df, 14).iloc[-1]) if not df.empty else 0.0
    rsi14_last = float(rsi(df['close'], 14).iloc[-1]) if not df.empty else 50.0
    m_line, s_line, _ = macd(df['close']) if not df.empty else (None, None, None)
    m_last = float(m_line.iloc[-1]) if m_line is not None else 0.0
    s_last = float(s_line.iloc[-1]) if s_line is not None else 0.0
    close_last = float(df['close'].iloc[-1]) if not df.empty else 0.0
    sc = {
        'ST': score_supertrend(int(st.trend.iloc[-1]) if not df.empty else -1),
        'EMA50': score_ema50(close_last, ema50_last, atr14_last, k_atr=float(cfg.get('indicators',{}).get('ema50',{}).get('k_atr',0.05))),
        'RSI': score_rsi(rsi14_last, cfg.get('indicators',{}).get('rsi',{}).get('bands_default',{})),
        'MACD': score_macd(m_last, s_last, eps=float(cfg.get('indicators',{}).get('macd',{}).get('eps',0.0))),
    }
    return float(weighted_avg(sc, w_ind))


def _bucket_from_score(x: float, thr_bull: float, thr_bear: float) -> str:
    if x > thr_bull:
        return 'BULL'
    if x < thr_bear:
        return 'BEAR'
    return 'SIDE'


async def alt_btc_matrix(symbol: str, mode: str) -> Dict[str, Any]:
    cfg = load_signal_config()
    C = cfg.get('context', {}).get('alt_btc_matrix', {})
    thr_bull = float(C.get('thr_trend_bull', 0.25))
    thr_bear = float(C.get('thr_trend_bear', -0.25))
    boosts = C.get('boosts', { 'long_max': 0.12, 'long': 0.08, 'warn': 0.02, 'short_max': -0.12, 'short': -0.08, 'pullback_warn': -0.02 })

    alt = await _trend_score(symbol, mode)
    btc = await _trend_score('BTCUSDT', mode)
    alt_b = _bucket_from_score(alt, thr_bull, thr_bear)
    btc_b = _bucket_from_score(btc, thr_bull, thr_bear)

    # Matrix mapping → label/dir/boost/risk
    if alt_b == 'BULL' and btc_b == 'BULL':
        return { 'label': 'LONG MAKSIMAL', 'dir': 'LONG', 'boost': float(boosts.get('long_max', 0.12)), 'risk_mult': 1.25 }
    if alt_b == 'BULL' and btc_b == 'SIDE':
        return { 'label': 'LONG', 'dir': 'LONG', 'boost': float(boosts.get('long', 0.08)), 'risk_mult': 1.10 }
    if alt_b == 'BULL' and btc_b == 'BEAR':
        return { 'label': 'WASPADA', 'dir': 'LONG', 'boost': float(boosts.get('warn', 0.02)), 'risk_mult': 0.90 }
    if alt_b == 'BEAR' and btc_b == 'BEAR':
        return { 'label': 'SHORT MAMPUS', 'dir': 'SHORT', 'boost': float(boosts.get('short_max', -0.12)), 'risk_mult': 1.25 }
    if alt_b == 'BEAR' and btc_b == 'SIDE':
        return { 'label': 'SHORT', 'dir': 'SHORT', 'boost': float(boosts.get('short', -0.08)), 'risk_mult': 1.10 }
    if alt_b == 'BEAR' and btc_b == 'BULL':
        return { 'label': 'AWAS KETARIK', 'dir': 'SHORT', 'boost': float(boosts.get('pullback_warn', -0.02)), 'risk_mult': 0.85 }
    return { 'label': 'NEUTRAL', 'dir': 'NEUTRAL', 'boost': 0.0, 'risk_mult': 1.0 }


async def btcd_bias(mode: str) -> Dict[str, Any]:
    cfg = load_signal_config()
    gamma = float(cfg.get('context', {}).get('btcd',{}).get('gamma', 0.06))
    trend_tf = build_tf_map(mode)['trend']
    btcd_dir = BTCD.get_trend(tf=trend_tf)
    # btc direction via trend bucket
    btc = await _trend_score('BTCUSDT', mode)
    if abs(btc) <= 0.25:
        btc_dir = 0
    else:
        btc_dir = 1 if btc > 0 else -1
    # Matrix per spesifikasi
    # btcd up (+1)
    if btcd_dir == 1 and btc_dir == 1:
        # Alts turun → SHORT bias
        return { 'dir': 'SHORT', 'boost': -gamma }
    if btcd_dir == 1 and btc_dir == -1:
        # Alts turun drastis
        return { 'dir': 'SHORT', 'boost': -gamma }
    if btcd_dir == 1 and btc_dir == 0:
        return { 'dir': 'NEUTRAL', 'boost': 0.0 }
    # btcd down (-1)
    if btcd_dir == -1 and btc_dir == 1:
        # Alts naik drastis
        return { 'dir': 'LONG', 'boost': gamma }
    if btcd_dir == -1 and btc_dir == -1:
        return { 'dir': 'NEUTRAL', 'boost': 0.0 }
    if btcd_dir == -1 and btc_dir == 0:
        return { 'dir': 'LONG', 'boost': gamma }
    return { 'dir': 'NEUTRAL', 'boost': 0.0 }


async def price_oi_correlation(symbol: str, mode: str) -> Dict[str, Any]:
    cfg = load_signal_config()
    C = cfg.get('context',{}).get('price_oi', {})
    p_eps = float(C.get('p_eps', 0.001))
    oi_eps = float(C.get('oi_eps', 0.001))
    boosts = C.get('boosts', { 'up_strong': 0.08, 'up_weak': 0.03, 'down_strong': -0.08, 'down_weak': -0.03 })
    # price change on trend TF
    tf = build_tf_map(mode)['trend']
    df = await _load_tf(symbol, tf, market_type='futures', limit=600)
    if df is None or df.empty or len(df) < 3:
        return { 'label': 'NAIK LEMAH', 'boost': 0.0 }
    close = df['close']
    # pick lookback by tf
    lb = 20 if tf.upper() == '1D' else 48 if tf in {'1h','1H'} else 96 if tf in {'15m','15M'} else 48
    lb = min(lb, max(1, len(close)-1))
    p0 = float(close.iloc[-lb])
    p1 = float(close.iloc[-1])
    pchg = (p1 - p0) / p0 if p0 > 0 else 0.0
    oi = float(OI.get_change(symbol, lookback_h=24))
    # bucket
    pdir = 1 if pchg > p_eps else (-1 if pchg < -p_eps else 0)
    oidir = 1 if oi > oi_eps else (-1 if oi < -oi_eps else 0)
    if pdir >= 0 and oidir > 0:
        return { 'label': 'NAIK KUAT', 'boost': float(boosts.get('up_strong', 0.08)) }
    if pdir >= 0 and oidir <= 0:
        return { 'label': 'NAIK LEMAH', 'boost': float(boosts.get('up_weak', 0.03)) }
    if pdir < 0 and oidir > 0:
        return { 'label': 'TURUN KUAT', 'boost': float(boosts.get('down_strong', -0.08)) }
    return { 'label': 'TURUN LEMAH', 'boost': float(boosts.get('down_weak', -0.03)) }


def is_alt(symbol: str) -> bool:
    return symbol.upper().strip() not in { 'BTCUSDT', 'BTC/USD', 'BTC/USDT' }


async def build_context_json(symbol: str, mode: str) -> Dict[str, Any]:
    fs, rate = funding_score(symbol)
    mx = await alt_btc_matrix(symbol, mode)
    btcd = await btcd_bias(mode) if is_alt(symbol) else None
    poi = await price_oi_correlation(symbol, mode)
    return {
        'funding': { 'rate': rate, 'score': int(fs) },
        'alt_btc': mx,
        'btcd': btcd,
        'price_oi': poi,
    }

