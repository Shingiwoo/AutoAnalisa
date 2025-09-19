from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional
from datetime import datetime

import pandas as pd

from ..utils.time import now_tz, tf_to_binance_interval, tf_duration_seconds
from ..utils.num import round_to
from ..indicators.mtf_indicators import (
    ema_dict,
    bb_dict,
    rsi_dict,
    stochrsi_dict,
    macd_dict,
    atr_last,
    volume_stats,
)
from ..features.structure import infer_trend, last_hh_hl_lh_ll
from ..features.levels import sr_levels, distance_tol, confidence_from_tags
from ..features.fvg import detect_fvg
from ..datasource import binance_spot, binance_futures
from ..schemas.payload_v1 import PayloadV1, Precision, Fees, Account, TFIndicators, StructureTF, LevelsTF, LevelsContainer, Derivatives, Orderbook


DEFAULT_TFS = ("1D", "4H", "1H", "15m")


@dataclass
class BuilderConfig:
    symbol: str
    market: str = "futures"
    contract: str = "perp"
    tz: str = "Asia/Jakarta"
    use_fvg: bool = False
    tfs: List[str] = None


class PayloadBuilder:
    def __init__(self, symbol: str, market: str = "futures", contract: str = "perp", tz: str = "Asia/Jakarta", use_fvg: bool = False, tfs: Optional[List[str]] = None,
                 override_risk: Optional[float] = None, override_lev: Optional[int] = None, news: Optional[list] = None,
                 session_bias: Optional[str] = None, btc_bias: Optional[str] = None):
        self.cfg = BuilderConfig(symbol=symbol, market=market, contract=contract, tz=tz, use_fvg=use_fvg, tfs=tfs or list(DEFAULT_TFS))
        if market not in ("spot", "futures"):
            raise ValueError("market must be 'spot' or 'futures'")

        if self.cfg.market == "spot":
            self.ds = binance_spot
            self.exchange = "BINANCE"
        else:
            self.ds = binance_futures
            self.exchange = "BINANCE"

        # exchange info
        ex = self.ds.get_exchange_info(self.cfg.symbol)
        precision = ex.get("precision", {"price": 0.0001, "qty": 0.1, "min_notional": 5.0})
        fees = ex.get("fees", {"maker": 0.0002, "taker": 0.0005})
        self.precision = Precision(price=precision.get("price", 0.0001), qty=precision.get("qty", 0.1), min_notional=precision.get("min_notional", 5.0))
        self.fees = Fees(maker=fees.get("maker", 0.0002), taker=fees.get("taker", 0.0005))
        self._insufficient_history = False
        self._override_risk = override_risk
        self._override_lev = override_lev
        self._news = news or None
        self._session_bias = session_bias
        self._btc_bias = btc_bias

    def _build_tf_block(self, tf: str) -> TFIndicators:
        interval = tf_to_binance_interval(tf)
        df = self.ds.get_klines(self.cfg.symbol, interval, limit=300, tz_str=self.cfg.tz)
        if len(df) < 150:
            self._insufficient_history = True
        # Ensure closed bar; get last close_time
        last_close_time = pd.to_datetime(df["close_time"].iloc[-1])
        # compute indicators on df
        ema = ema_dict(df)
        bb = bb_dict(df)
        rsi = rsi_dict(df)
        stoch = stochrsi_dict(df)
        macd = macd_dict(df)
        atr = atr_last(df)
        vol = volume_stats(df)
        # recent series
        try:
            from ta.trend import EMAIndicator
            from ta.momentum import RSIIndicator
            ema50_series = EMAIndicator(close=df["close"], window=50).ema_indicator().dropna().iloc[-5:].tolist()
            rsi6_series = RSIIndicator(close=df["close"], window=6).rsi().dropna().iloc[-5:].tolist()
        except Exception:
            ema50_series, rsi6_series = None, None
        close_last5 = df["close"].iloc[-5:].tolist() if len(df) >= 5 else None

        return TFIndicators(
            last=float(df["close"].iloc[-1]),
            open=float(df["open"].iloc[-1]),
            high=float(df["high"].iloc[-1]),
            low=float(df["low"].iloc[-1]),
            close_time=last_close_time.isoformat(),
            ema=ema,
            bb=bb,
            rsi=rsi,
            stochrsi=stoch,
            macd=macd,
            atr14=atr,
            vol_last=vol["vol_last"],
            vol_ma5=vol["vol_ma5"],
            vol_ma10=vol["vol_ma10"],
            rsi6_last5=rsi6_series,
            close_last5=close_last5,
            ema50_last5=ema50_series,
        )

    def _structure_for_tf(self, tf: str, tf_block: TFIndicators) -> StructureTF:
        # To derive structure, re-fetch the df quickly; could optimize by passing previous df if needed
        interval = tf_to_binance_interval(tf)
        df = self.ds.get_klines(self.cfg.symbol, interval, limit=300, tz_str=self.cfg.tz)
        ema50 = tf_block.ema.get("50")
        ema200 = tf_block.ema.get("200")
        trend = infer_trend(df, ema50=ema50, ema200=ema200)
        swings = last_hh_hl_lh_ll(df)
        return StructureTF(trend=trend, hh=swings.get("last_hh"), hl=swings.get("last_hl"), lh=swings.get("last_lh"), ll=swings.get("last_ll"))

    def _levels_for_tf(self, tf: str) -> LevelsTF:
        interval = tf_to_binance_interval(tf)
        df = self.ds.get_klines(self.cfg.symbol, interval, limit=300, tz_str=self.cfg.tz)
        piv = sr_levels(df)
        return LevelsTF(**piv)

    def _levels_confluence(self, levels_map: Dict[str, LevelsTF], tf_blocks: Dict[str, TFIndicators]) -> list[dict]:
        import os, yaml
        # Load confluence config if exists
        cfg_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "config", "rules_pullback.yaml")
        cfg = {}
        if os.path.exists(cfg_path):
            try:
                with open(cfg_path, "r") as f:
                    cfg = yaml.safe_load(f) or {}
            except Exception:
                cfg = {}
        c_cfg = cfg.get("confluence", {})
        tol_pct_min_5_15m = float(c_cfg.get("tol_pct_min_5_15m", 0.0005))
        tol_pct_min_1h_4h = float(c_cfg.get("tol_pct_min_1h_4h", 0.0003))
        tol_atr_mult_5_15m = float(c_cfg.get("tol_atr_mult_5_15m", 0.15))
        tol_atr_mult_1h_4h = float(c_cfg.get("tol_atr_mult_1h_4h", 0.10))
        ticksize_mult = float(c_cfg.get("ticksize_mult", 2.0))
        weights = c_cfg.get("weights", {})
        results: list[dict] = []
        def tag_tf(label: str, tf: str) -> str:
            if label.startswith("EMA"):
                return f"{label}-{tf}"
            if label in ("BB-mid", "pivot"):
                return f"{label}-{tf}"
            return label
        def near_round(price: float, step: float = 0.05, tol: float = 0.001) -> bool:
            nearest = round(price / step) * step
            return abs(price - nearest) / max(nearest, 1e-9) < tol
        for tf, lvl in levels_map.items():
            tb = tf_blocks.get(tf)
            if not tb:
                continue
            ema = tb.ema
            bb_obj = tb.bb
            bb = bb_obj.model_dump() if hasattr(bb_obj, 'model_dump') else bb_obj
            piv = {"support": lvl.support, "resistance": lvl.resistance}
            atr15 = float(tf_blocks.get("15m").atr14) if tf_blocks.get("15m") else 0.0
            atr1h = float(tf_blocks.get("1H").atr14) if tf_blocks.get("1H") else 0.0
            tick = float(self.precision.price)
            for p in (lvl.support[:2] + lvl.resistance[:2]):
                # Collect tags using dynamic tolerance
                tags_base: list[str] = []
                best_distance = None
                # EMA
                for k, v in (ema or {}).items():
                    if v:
                        dist, tol = distance_tol(float(p), float(v), tf, atr15, atr1h, tick,
                                                 tol_pct_min_5_15m, tol_pct_min_1h_4h, tol_atr_mult_5_15m, tol_atr_mult_1h_4h, ticksize_mult)
                        if dist <= tol:
                            tags_base.append(f"EMA{k}")
                            best_distance = dist if best_distance is None else min(best_distance, dist)
                # BB-mid
                mid = (bb or {}).get("middle") if isinstance(bb, dict) else None
                if mid:
                    dist_mid, tol_mid = distance_tol(float(p), float(mid), tf, atr15, atr1h, tick,
                                                     tol_pct_min_5_15m, tol_pct_min_1h_4h, tol_atr_mult_5_15m, tol_atr_mult_1h_4h, ticksize_mult)
                    if dist_mid <= tol_mid:
                        tags_base.append("BB-mid")
                        best_distance = dist_mid if best_distance is None else min(best_distance, dist_mid)
                # Pivot tag if price equals one of SR (trivially true; ensure tag present)
                # We already loop over SR prices; include pivot tag by default
                tags_base.append("pivot")
                # Round number
                if near_round(p):
                    tags_base.append("round-number")

                if tags_base:
                    labeled = [tag_tf(t, tf) for t in tags_base]
                    # Use tol computed from last check; pick representative tol: use tol at EMA20 if exists else mid
                    # Fallback tol calculation directly on price to itself
                    d_rep, tol_rep = distance_tol(float(p), float(p), tf, atr15, atr1h, tick,
                                                  tol_pct_min_5_15m, tol_pct_min_1h_4h, tol_atr_mult_5_15m, tol_atr_mult_1h_4h, ticksize_mult)
                    conf = confidence_from_tags(labeled, best_distance or 0.0, tol_rep, weights, scale=5.0, cap=100)
                    results.append({
                        "tf": tf,
                        "price": float(p),
                        "tags": labeled,
                        "confidence": conf,
                        "distance": float(best_distance or 0.0),
                        "tol": float(tol_rep),
                    })
        # FVG-edge tagging when enabled
        if self.cfg.use_fvg:
            for tf in tf_blocks.keys():
                try:
                    interval = tf_to_binance_interval(tf)
                    df_tf = self.ds.get_klines(self.cfg.symbol, interval, limit=300, tz_str=self.cfg.tz)
                except Exception:
                    df_tf = None
                if df_tf is None or len(df_tf) < 3:
                    continue
                fvgs = detect_fvg(df_tf, max_lookback=50, tf=tf)
                if not fvgs:
                    continue
                tb = tf_blocks.get(tf)
                if not tb:
                    continue
                atr15 = float(tf_blocks.get("15m").atr14) if tf_blocks.get("15m") else 0.0
                atr1h = float(tf_blocks.get("1H").atr14) if tf_blocks.get("1H") else 0.0
                tick = float(self.precision.price)
                last_price = float(tb.last)
                for f in fvgs[-5:]:  # only recent few
                    for edge in (float(f.get("top")), float(f.get("bottom"))):
                        dist, tol = distance_tol(last_price, edge, tf, atr15, atr1h, tick,
                                                 tol_pct_min_5_15m, tol_pct_min_1h_4h, tol_atr_mult_5_15m, tol_atr_mult_1h_4h, ticksize_mult)
                        if dist <= tol:
                            tags = ["FVG-edge", f"FVG-{f.get('dir')}", f"FVG-{tf}"]
                            conf = confidence_from_tags(tags, dist, tol, weights, scale=5.0, cap=100)
                            results.append({
                                "tf": tf,
                                "price": edge,
                                "tags": tags,
                                "confidence": conf,
                                "distance": dist,
                                "tol": tol,
                            })

        return results

        

    def build(self) -> dict:
        tf_blocks: Dict[str, TFIndicators] = {}
        for tf in self.cfg.tfs:
            tf_blocks[tf] = self._build_tf_block(tf)

        structure: Dict[str, StructureTF] = {}
        for tf in ("4H", "1H", "15m"):
            if tf in tf_blocks:
                structure[tf] = self._structure_for_tf(tf, tf_blocks[tf])

        levels_map: Dict[str, LevelsTF] = {}
        for tf in ("1H", "15m"):
            if tf in tf_blocks:
                levels_map[tf] = self._levels_for_tf(tf)

        levels_confluence = self._levels_confluence(levels_map, tf_blocks)

        derivatives = None
        orderbook = None
        # Depth/orderbook
        try:
            d = self.ds.get_depth(self.cfg.symbol, limit=5)
            orderbook = Orderbook(**d)
        except Exception:
            orderbook = Orderbook()

        # Futures-only derivatives
        if self.cfg.market == "futures":
            try:
                markidx = binance_futures.get_mark_index(self.cfg.symbol)
                funding = binance_futures.get_funding(self.cfg.symbol)
                oi = binance_futures.get_oi(self.cfg.symbol)
                lsr = binance_futures.get_long_short_ratio(self.cfg.symbol)
                derivatives = Derivatives(
                    funding_rate=funding.get("funding_rate"),
                    next_funding_ts=funding.get("next_funding_ts"),
                    oi=oi,
                    long_short_ratio=lsr,
                    mark_price=markidx.get("mark_price"),
                    index_price=markidx.get("index_price"),
                )
            except Exception:
                derivatives = Derivatives()

        meta = {"version": "v1.0", "generated_at": now_tz(self.cfg.tz).isoformat()}
        account = Account(
            balance_usdt=None,  # unknown without keys; downstream can fill
            fee_maker=self.fees.maker,
            fee_taker=self.fees.taker,
            risk_per_trade=self._override_risk if self._override_risk is not None else 0.01,
            leverage=1 if self.cfg.market == "spot" else (self._override_lev if self._override_lev is not None else 10),
            margin_mode="cross" if self.cfg.market == "futures" else None,
        )

        payload = PayloadV1(
            meta=meta,
            symbol=self.cfg.symbol,
            exchange=self.exchange,
            market=self.cfg.market,  # "spot" | "futures"
            contract=self.cfg.contract,
            timezone=self.cfg.tz,
            precision=self.precision,
            fees=self.fees,
            account=account,
            tf=tf_blocks,
            structure=structure,
            levels=LevelsContainer(**{tf: levels_map[tf].model_dump() for tf in levels_map}, confluence=levels_confluence),
            derivatives=derivatives,
            orderbook=orderbook,
            orderflow=None,
            news=self._news,
            session_bias=self._session_bias,
            btc_bias=self._btc_bias,
            insufficient_history=self._insufficient_history,
            notes=None,
        )

        return payload.model_dump(mode="python", by_alias=False)


def build_payload(symbol: str, market: str = "futures", contract: str = "perp", tfs: Optional[List[str]] = None, tz: str = "Asia/Jakarta", use_fvg: bool = False,
                  override_risk: Optional[float] = None, override_lev: Optional[int] = None, news: Optional[list] = None,
                  session_bias: Optional[str] = None, btc_bias: Optional[str] = None) -> dict:
    builder = PayloadBuilder(symbol=symbol, market=market, contract=contract, tz=tz, use_fvg=use_fvg, tfs=tfs,
                             override_risk=override_risk, override_lev=override_lev, news=news,
                             session_bias=session_bias, btc_bias=btc_bias)
    return builder.build()
