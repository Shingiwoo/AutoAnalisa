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
from ..features.levels import sr_levels
from ..features.fvg import detect_fvg
from ..datasource import binance_spot, binance_futures
from ..schemas.payload_v1 import PayloadV1, Precision, Fees, Account, TFIndicators, StructureTF, LevelsTF, Derivatives, Orderbook


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
    def __init__(self, symbol: str, market: str = "futures", contract: str = "perp", tz: str = "Asia/Jakarta", use_fvg: bool = False, tfs: Optional[List[str]] = None):
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

    def _build_tf_block(self, tf: str) -> TFIndicators:
        interval = tf_to_binance_interval(tf)
        df = self.ds.get_klines(self.cfg.symbol, interval, limit=300, tz_str=self.cfg.tz)
        if len(df) < 150:
            self._insufficient_history = True
        # Ensure closed bar; Binance returns closed bars; still optional drop if too fresh
        last_close_time = pd.to_datetime(df["close_time"].iloc[-1])
        # compute indicators on df
        ema = ema_dict(df)
        bb = bb_dict(df)
        rsi = rsi_dict(df)
        stoch = stochrsi_dict(df)
        macd = macd_dict(df)
        atr = atr_last(df)
        vol = volume_stats(df)

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

    def build(self) -> dict:
        tf_blocks: Dict[str, TFIndicators] = {}
        for tf in self.cfg.tfs:
            tf_blocks[tf] = self._build_tf_block(tf)

        structure: Dict[str, StructureTF] = {}
        for tf in ("4H", "1H", "15m"):
            if tf in tf_blocks:
                structure[tf] = self._structure_for_tf(tf, tf_blocks[tf])

        levels: Dict[str, LevelsTF] = {}
        for tf in ("1H", "15m"):
            if tf in tf_blocks:
                levels[tf] = self._levels_for_tf(tf)

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
            risk_per_trade=0.01,
            leverage=None if self.cfg.market == "spot" else 10,
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
            levels=levels,
            derivatives=derivatives,
            orderbook=orderbook,
            insufficient_history=self._insufficient_history,
            notes=None,
        )

        return payload.model_dump(mode="python", by_alias=False)


def build_payload(symbol: str, market: str = "futures", contract: str = "perp", tfs: Optional[List[str]] = None, tz: str = "Asia/Jakarta", use_fvg: bool = False) -> dict:
    builder = PayloadBuilder(symbol=symbol, market=market, contract=contract, tz=tz, use_fvg=use_fvg, tfs=tfs)
    return builder.build()
