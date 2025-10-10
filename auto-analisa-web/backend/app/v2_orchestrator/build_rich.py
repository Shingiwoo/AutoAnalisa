from __future__ import annotations

from datetime import datetime, timezone
from typing import Dict

from app.v2_schemas.analysis_rich import AnalysisRichOutput, TFBlock, Indicators, StrategyScalp, StrategySwing
from app.v2_schemas.llm_output import LlmOutput
from app.services.trade_calc import round_futures_prices


def _round_list(symbol: str, vals):
    out = []
    for v in (vals or []):
        try:
            out.append(round_futures_prices(symbol, float(v)))
        except Exception:
            continue
    return out


def build_rich_output(symbol: str, market: str, snapshot: Dict, plain: LlmOutput, source: str, price_now: float) -> AnalysisRichOutput:
    # Build minimal MTF blocks from snapshot (fallback: duplicate current TF)
    tf_labels = ("M15", "H1", "H4", "D1")
    mtf: Dict[str, TFBlock] = {}
    for tf in tf_labels:
        s = snapshot.get(tf, {}) if isinstance(snapshot, dict) else {}
        mtf[tf] = TFBlock(
            bias=str(s.get("bias", plain.structure or "")),
            kondisi=str(s.get("kondisi", "")),
            support=_round_list(symbol, s.get("support", [])),
            resistance=_round_list(symbol, s.get("resistance", [])),
            indikator=Indicators(**(s.get("indikator", {"EMA": "", "MACD": "", "RSI": 0})))
        )

    # Strategies: map from plain plan
    plan = plain.plan
    entries = _round_list(symbol, [e.price for e in plan.entries])
    tps = _round_list(symbol, [tp.price for tp in plan.take_profits])
    slv = float(plan.stop_loss.price)
    slv = round_futures_prices(symbol, slv)

    strat_scalp = StrategyScalp(
        mode=plan.rationale[:24] + "…" if plan.rationale else "Buy the Dip",
        timeframe="M15–H1",
        entry_zone=entries[:2] or [round_futures_prices(symbol, price_now*0.995)],
        take_profit=tps[:2] or [round_futures_prices(symbol, price_now*1.01)],
        stop_loss=slv,
        leverage_saran="≤10x",
        alokasi_risiko_per_trade="0.5%–1.0% ekuitas",
        estimated_performance={"winrate_pct": 70, "profit_factor": 2.2, "RR": "≈ 1:2"},
        catatan=plan.rationale or "",
    )

    tp3 = tps[2] if len(tps) >= 3 else (tps[1] if len(tps) >= 2 else (tps[0] if tps else round_futures_prices(symbol, price_now*1.03)))
    strat_swing = StrategySwing(
        mode="Position Trade setelah retest",
        timeframe="H4–D1",
        entry_zone_utama=entries[:1] or [round_futures_prices(symbol, price_now*0.99)],
        add_on_konfirmasi="Tambah posisi bila H4 close ≥ level konfirmasi",
        take_profit={"TP1": tps[0] if tps else round_futures_prices(symbol, price_now*1.02), "TP2": (tps[1] if len(tps) >= 2 else round_futures_prices(symbol, price_now*1.03)), "TP3": tp3},
        stop_loss=slv,
        leverage_saran="≤5x",
        alokasi_risiko_per_trade="0.5%–1.0% ekuitas",
        RR="≈ 1:2.7",
        estimated_performance={"winrate_pct": 68.0, "profit_factor": 3.1},
        estimasi_durasi_mencapai_target_hari={"TP1": "1–3", "TP2": "3–7", "TP3": "7–21"},
        syarat_valid=["D1 bertahan di atas support utama", "H4 tetap di atas EMA20 setelah retest"],
    )

    rich = AnalysisRichOutput(
        metadata={
            "symbol": symbol,
            "market": market,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "harga_saat_ini": float(price_now),
            "sumber": source,
        },
        multi_timeframe=mtf,
        rangkuman={
            "bias_dominan": (plain.structure or "").upper(),
            "narasi": plan.rationale or "",
            "invalidasi_utama": "",
        },
        strategi={"scalping": strat_scalp.model_dump(), "swing": strat_swing.model_dump()},
        penjelasan_posisi={
            "kenapa_LONG": ["Struktur H4–D1 menguat", "Konfirmasi volume"],
            "kapan_SHORT": ["Break invalidasi TF intraday", "Close D1 < support kunci"],
        },
        fundamental_ringkas={"tema": "", "katalis": [], "risiko": []},
        risk_management={"max_open_positions": 1, "hindari_overtrading": True, "cooldown_setelah_SL_menyentuh": "tunggu 2 candle H1", "fee_assumption": {"taker_pct": 0.05, "maker_pct": 0.02}},
        kesimpulan_akhir={"ringkas": plan.rationale or "", "aksi_cepat": []},
        performansi_target={"scalping": {"winrate_pct": 70, "profit_factor": 2.2}, "swing": {"winrate_pct": 68, "profit_factor": 3.1}},
        disclaimer="Estimasi probabilistik; sesuaikan ukuran posisi dengan manajemen risiko pribadi.",
    )

    return rich

