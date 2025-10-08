from __future__ import annotations
from dataclasses import dataclass
from typing import Dict, List, Literal, Tuple, Any, Optional
import pandas as pd
from .supertrend import compute_supertrend
from . import market
import time
import os
from pathlib import Path

from .indicators import ema, rsi, macd, atr
from .scorer import score_supertrend, score_ema50, score_rsi, score_macd
from .aggregator import weighted_avg, EmaSmoother, bucket_strength

Mode = Literal["fast", "medium", "swing"]

_SMOOTHERS: Dict[str, EmaSmoother] = {}


def _now_iso() -> str:
    try:
        return pd.Timestamp.utcnow().isoformat()
    except Exception:
        import datetime as _dt
        return _dt.datetime.utcnow().isoformat()


def _load_yaml_safe(path: Path) -> Optional[Dict[str, Any]]:
    try:
        import yaml  # type: ignore
    except Exception:
        return None
    try:
        with path.open("r", encoding="utf-8") as f:
            return yaml.safe_load(f)
    except Exception:
        return None


def load_signal_config() -> Dict[str, Any]:
    base = Path(__file__).resolve().parents[1]  # app/
    cfg_path = base / "config" / "signal_config.yaml"
    data = _load_yaml_safe(cfg_path)
    if isinstance(data, dict):
        return data
    # Fallback defaults (mirror YAML)
    return {
        "presets": {
            "fast": {
                "tf": {"trend": "15m", "pattern": "5m", "trigger": "1m"},
                "thresholds": {"tau_entry": 0.25, "theta_bias": 0.20, "alpha": 0.30},
                "strict_bias": True,
                "weights": {
                    "indicators": {
                        "trend": {"ST": 0.60, "EMA50": 0.20, "RSI": 0.10, "MACD": 0.10},
                        "pattern": {"ST": 0.50, "RSI": 0.25, "MACD": 0.15, "EMA50": 0.10},
                        "trigger": {"ST": 0.70, "EMA": 0.15, "RSI": 0.10, "MACD": 0.05},
                    },
                    "groups": {"trend": 0.50, "pattern": 0.30, "trigger": 0.20},
                },
                "supertrend": {"period": {"trend": 10, "pattern": 10, "trigger": 7}, "multiplier": {"all": 3.0}, "src": "hl2", "change_atr": True},
            },
            "medium": {
                "tf": {"trend": "1h", "pattern": "15m", "trigger": "5m"},
                "thresholds": {"tau_entry": 0.25, "theta_bias": 0.20, "alpha": 0.25},
                "strict_bias": True,
                "weights": {
                    "indicators": {
                        "trend": {"ST": 0.60, "EMA50": 0.20, "RSI": 0.10, "MACD": 0.10},
                        "pattern": {"ST": 0.50, "RSI": 0.25, "MACD": 0.15, "EMA50": 0.10},
                        "trigger": {"ST": 0.70, "EMA": 0.15, "RSI": 0.10, "MACD": 0.05},
                    },
                    "groups": {"trend": 0.60, "pattern": 0.25, "trigger": 0.15},
                },
                "supertrend": {"period": {"all": 10}, "multiplier": {"all": 3.0}, "src": "hl2", "change_atr": True},
            },
            "swing": {
                "tf": {"trend": "1D", "pattern": "4h", "trigger": "15m"},
                "thresholds": {"tau_entry": 0.30, "theta_bias": 0.20, "alpha": 0.20},
                "strict_bias": True,
                "weights": {
                    "indicators": {
                        "trend": {"ST": 0.60, "EMA50": 0.20, "RSI": 0.10, "MACD": 0.10},
                        "pattern": {"ST": 0.50, "RSI": 0.25, "MACD": 0.15, "EMA50": 0.10},
                        "trigger": {"ST": 0.70, "EMA": 0.15, "RSI": 0.10, "MACD": 0.05},
                    },
                    "groups": {"trend": 0.70, "pattern": 0.20, "trigger": 0.10},
                },
                "supertrend": {"period": {"all": 10}, "multiplier": {"all": 3.0}, "src": "hl2", "change_atr": True},
            },
        },
        "indicators": {
            "ema50": {"k_atr": 0.05},
            "rsi": {"bands_default": {"long_lo": 55, "long_hi": 70, "short_hi": 45, "short_lo": 30, "mid_lo": 45, "mid_hi": 55}},
            "macd": {"eps": 0.0},
        },
    }


def build_tf_map(mode: Mode) -> Dict[str, str]:
    if mode == "fast":
        return {"trend": "15m", "pattern": "5m", "trigger": "1m"}
    if mode == "medium":
        return {"trend": "1h", "pattern": "15m", "trigger": "5m"}
    if mode == "swing":
        return {"trend": "1D", "pattern": "4h", "trigger": "15m"}
    # default safe
    return {"trend": "1h", "pattern": "15m", "trigger": "5m"}


def default_thresholds(mode: Mode) -> Dict[str, float]:
    if mode == "swing":
        return {"tau_entry": 0.30, "theta_bias": 0.20, "alpha": 0.20}
    if mode == "medium":
        return {"tau_entry": 0.25, "theta_bias": 0.20, "alpha": 0.25}
    return {"tau_entry": 0.25, "theta_bias": 0.20, "alpha": 0.30}


def group_weights(mode: Mode) -> Dict[str, float]:
    if mode == "swing":
        return {"trend": 0.70, "pattern": 0.20, "trigger": 0.10}
    if mode == "medium":
        return {"trend": 0.60, "pattern": 0.25, "trigger": 0.15}
    return {"trend": 0.50, "pattern": 0.30, "trigger": 0.20}


def _strength_bucket(abs_total: float) -> str:
    if abs_total >= 0.75:
        return "EXTREME"
    if abs_total >= 0.55:
        return "STRONG"
    if abs_total >= 0.35:
        return "MEDIUM"
    return "WEAK"


async def _load_tf(symbol: str, tf: str, market_type: str = "futures", limit: int = 600) -> pd.DataFrame:
    df = await market.fetch_klines(symbol, tf, limit=limit, market=market_type)
    df = df.copy()
    df["ts"] = pd.to_datetime(df["ts"], unit="ms", utc=True)
    df.set_index("ts", inplace=True)
    return df


async def compute_btc_bias(mode: Mode, market_type: str = "futures") -> Tuple[str, float]:
    cfg = load_signal_config()
    P = cfg["presets"].get(mode, cfg["presets"]["medium"])  # fallback
    tf_trend = P["tf"]["trend"]
    df = await _load_tf("BTCUSDT", tf_trend, market_type=market_type, limit=600)
    # indicators
    st = compute_supertrend(
        df,
        period=int((P.get("supertrend", {}).get("period", {}).get("trend") or P.get("supertrend", {}).get("period", {}).get("all", 10))),
        multiplier=float((P.get("supertrend", {}).get("multiplier", {}).get("trend") or P.get("supertrend", {}).get("multiplier", {}).get("all", 3.0))),
        src=str(P.get("supertrend", {}).get("src", "hl2")),
        change_atr=bool(P.get("supertrend", {}).get("change_atr", True)),
    )
    ema50_last = float(ema(df["close"], 50).iloc[-1]) if not df.empty else 0.0
    atr14_last = float(atr(df, 14).iloc[-1]) if not df.empty else 0.0
    rsi14_last = float(rsi(df["close"], 14).iloc[-1]) if not df.empty else 50.0
    macd_line, signal_line, _ = macd(df["close"]) if not df.empty else (pd.Series([0]), pd.Series([0]), pd.Series([0]))
    macd_line_last = float(macd_line.iloc[-1])
    signal_line_last = float(signal_line.iloc[-1])

    bands = cfg.get("indicators", {}).get("rsi", {}).get("bands_default", {})
    k_atr = float(cfg.get("indicators", {}).get("ema50", {}).get("k_atr", 0.05))
    eps = float(cfg.get("indicators", {}).get("macd", {}).get("eps", 0.0))

    sc = {
        "ST": score_supertrend(int(st.trend.iloc[-1]) if not df.empty else -1),
        "EMA50": score_ema50(float(df["close"].iloc[-1]) if not df.empty else 0.0, ema50_last, atr14_last, k_atr=k_atr),
        "RSI": score_rsi(rsi14_last, bands),
        "MACD": score_macd(macd_line_last, signal_line_last, eps=eps),
    }
    w_trend = P["weights"]["indicators"]["trend"]
    score = float(weighted_avg(sc, w_trend))
    direction = "NEUTRAL"
    if abs(score) >= float(P["thresholds"]["theta_bias"]):
        direction = "LONG" if score > 0 else "SHORT"
    return direction, score


async def calc_symbol_signal(symbol: str, mode: Mode, market_type: str = "futures",
                             preset: Optional[str] = None,
                             tau_entry: Optional[float] = None,
                             alpha: Optional[float] = None,
                             strict_bias: Optional[bool] = None) -> Dict:
    cfg = load_signal_config()
    P = cfg["presets"].get(mode, cfg["presets"]["medium"])  # base preset
    if preset and preset in cfg.get("presets", {}):
        P = cfg["presets"][preset]
    # allow query overrides
    if tau_entry is not None:
        P = {**P, "thresholds": {**P.get("thresholds", {}), "tau_entry": float(tau_entry)}}
    if alpha is not None:
        P = {**P, "thresholds": {**P.get("thresholds", {}), "alpha": float(alpha)}}
    if strict_bias is not None:
        P = {**P, "strict_bias": bool(strict_bias)}

    tf_map = dict(P["tf"])

    # Load data per TF
    df_tr = await _load_tf(symbol, tf_map["trend"], market_type=market_type, limit=600)
    df_pa = await _load_tf(symbol, tf_map["pattern"], market_type=market_type, limit=600)
    df_tg = await _load_tf(symbol, tf_map["trigger"], market_type=market_type, limit=600)

    # ST params
    def _st_cfg(kind: str) -> Dict[str, Any]:
        per = P.get("supertrend", {}).get("period", {})
        mul = P.get("supertrend", {}).get("multiplier", {})
        return {
            "period": int(per.get(kind) or per.get("all", 10)),
            "multiplier": float(mul.get(kind) or mul.get("all", 3.0)),
            "src": str(P.get("supertrend", {}).get("src", "hl2")),
            "change_atr": bool(P.get("supertrend", {}).get("change_atr", True)),
        }

    # Compute Supertrend blocks
    st_tr = compute_supertrend(df_tr, **_st_cfg("trend"))
    st_pa = compute_supertrend(df_pa, **_st_cfg("pattern"))
    st_tg = compute_supertrend(df_tg, **_st_cfg("trigger"))

    # Compute indicators per TF
    def _indicators_scores(df: pd.DataFrame, st_obj) -> Dict[str, int]:
        if df is None or df.empty:
            return {"ST": 0, "EMA50": 0, "RSI": 0, "MACD": 0}
        ema50_last = float(ema(df["close"], 50).iloc[-1])
        atr14_last = float(atr(df, 14).iloc[-1])
        rsi14_last = float(rsi(df["close"], 14).iloc[-1])
        m_line, s_line, _ = macd(df["close"])  # 12,26,9
        m_last, s_last = float(m_line.iloc[-1]), float(s_line.iloc[-1])
        bands = cfg.get("indicators", {}).get("rsi", {}).get("bands_default", {})
        k_atr = float(cfg.get("indicators", {}).get("ema50", {}).get("k_atr", 0.05))
        eps = float(cfg.get("indicators", {}).get("macd", {}).get("eps", 0.0))
        close_last = float(df["close"].iloc[-1])
        return {
            "ST": score_supertrend(int(st_obj.trend.iloc[-1])),
            "EMA50": score_ema50(close_last, ema50_last, atr14_last, k_atr=k_atr),
            "RSI": score_rsi(rsi14_last, bands),
            "MACD": score_macd(m_last, s_last, eps=eps),
        }

    sc_trend = _indicators_scores(df_tr, st_tr)
    sc_pattern = _indicators_scores(df_pa, st_pa)
    sc_trigger = _indicators_scores(df_tg, st_tg)

    # GroupScore per preset weights
    w_ind = P["weights"]["indicators"]
    gs_trend = float(weighted_avg(sc_trend, w_ind["trend"]))
    gs_pattern = float(weighted_avg(sc_pattern, w_ind["pattern"]))
    gs_trigger = float(weighted_avg(sc_trigger, w_ind["trigger"]))

    # Total with group weights
    wg = P["weights"]["groups"]
    total_raw = wg["trend"] * gs_trend + wg["pattern"] * gs_pattern + wg["trigger"] * gs_trigger

    # Smoothing per symbol+mode
    key = f"{symbol.upper()}:{mode}"
    sm = _SMOOTHERS.setdefault(key, EmaSmoother(float(P["thresholds"].get("alpha", 0.3))))
    total = float(sm.update(total_raw))

    btc_dir, btc_score = await compute_btc_bias(mode, market_type=market_type)
    side = "NO_TRADE"
    if abs(total) >= float(P["thresholds"]["tau_entry"]):
        proposed = "LONG" if total > 0 else "SHORT"
        if bool(P.get("strict_bias", True)) and btc_dir != "NEUTRAL" and proposed != btc_dir:
            side = "NO_TRADE"
        else:
            side = proposed

    strength = bucket_strength(total) if side != "NO_TRADE" else "WEAK"
    confidence = int(round(100 * abs(total)))

    def _last_flip(df: pd.DataFrame, st) -> Dict:
        sig = st.signal
        idxs = sig[sig != 0].index
        if len(idxs) == 0:
            return {"ts": None, "side": None, "price": None}
        ts = idxs[-1]
        side_s = "BUY" if int(sig.loc[ts]) == 1 else "SELL"
        price = float(df.loc[ts, "close"]) if ts in df.index else None
        return {"ts": str(ts), "side": side_s, "price": price}

    def _mini(df: pd.DataFrame, n: int = 60) -> List[Dict[str, float]]:
        if df is None or df.empty:
            return []
        tail = df.tail(n)
        return [{"ts": int(ts.value // 10**6), "close": float(row["close"])} for ts, row in tail.iterrows()]

    result = {
        "symbol": symbol.upper(),
        "mode": mode,
        "timestamp": _now_iso(),
        "tf_map": tf_map,
        "btc_bias": {"score": btc_score, "direction": btc_dir, "threshold": float(P["thresholds"]["theta_bias"])},
        "st": {
            "trend": {
                "tf": tf_map["trend"],
                "trend": int(st_tr.trend.iloc[-1]) if not df_tr.empty else 0,
                "signal": int(st_tr.signal.iloc[-1]) if not df_tr.empty else 0,
                "line": float(st_tr.supertrend.iloc[-1]) if not df_tr.empty else 0.0,
                "up": float(st_tr.up.iloc[-1]) if not df_tr.empty else 0.0,
                "dn": float(st_tr.dn.iloc[-1]) if not df_tr.empty else 0.0,
                "last_flip": _last_flip(df_tr, st_tr) if not df_tr.empty else {"ts": None, "side": None, "price": None},
                "mini": _mini(df_tr),
            },
            "pattern": {
                "tf": tf_map["pattern"],
                "trend": int(st_pa.trend.iloc[-1]) if not df_pa.empty else 0,
                "signal": int(st_pa.signal.iloc[-1]) if not df_pa.empty else 0,
                "line": float(st_pa.supertrend.iloc[-1]) if not df_pa.empty else 0.0,
                "up": float(st_pa.up.iloc[-1]) if not df_pa.empty else 0.0,
                "dn": float(st_pa.dn.iloc[-1]) if not df_pa.empty else 0.0,
                "last_flip": _last_flip(df_pa, st_pa) if not df_pa.empty else {"ts": None, "side": None, "price": None},
                "mini": _mini(df_pa),
            },
            "trigger": {
                "tf": tf_map["trigger"],
                "trend": int(st_tg.trend.iloc[-1]) if not df_tg.empty else 0,
                "signal": int(st_tg.signal.iloc[-1]) if not df_tg.empty else 0,
                "line": float(st_tg.supertrend.iloc[-1]) if not df_tg.empty else 0.0,
                "up": float(st_tg.up.iloc[-1]) if not df_tg.empty else 0.0,
                "dn": float(st_tg.dn.iloc[-1]) if not df_tg.empty else 0.0,
                "last_flip": _last_flip(df_tg, st_tg) if not df_tg.empty else {"ts": None, "side": None, "price": None},
                "mini": _mini(df_tg),
            },
        },
        "indicators": {
            "trend": sc_trend,
            "pattern": sc_pattern,
            "trigger": sc_trigger,
        },
        "scores": {
            "trend": round(gs_trend, 4),
            "pattern": round(gs_pattern, 4),
            "trigger": round(gs_trigger, 4),
        },
        "weights": {
            "groups": P["weights"]["groups"],
            "indicators": P["weights"]["indicators"],
        },
        "total_score": round(total, 4),
        "signal": {"side": side, "strength": strength, "confidence": confidence},
        "metadata": {"strict_bias": bool(P.get("strict_bias", True))},
    }
    return result


async def compute_signals_bulk(symbols: List[str], mode: Mode, preset: Optional[str] = None,
                               tau_entry: Optional[float] = None, alpha: Optional[float] = None,
                               strict_bias: Optional[bool] = None,
                               market_type: str = "futures") -> Dict[str, Any]:
    out = []
    for sym in symbols:
        try:
            out.append(
                await calc_symbol_signal(sym, mode, market_type=market_type, preset=preset, tau_entry=tau_entry, alpha=alpha, strict_bias=strict_bias)
            )
        except Exception as e:
            out.append({"symbol": sym, "mode": mode, "error": str(e)})
    return {"results": out}


async def compute_btc_bias_json(mode: Mode, market_type: str = "futures") -> Dict[str, Any]:
    direction, score = await compute_btc_bias(mode, market_type=market_type)
    return {"mode": mode, "direction": direction, "score": score}
