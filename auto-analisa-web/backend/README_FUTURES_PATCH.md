
# Patch Futures v1

File baru & rute untuk strategi Binance Futures berbasis **trend + pullback + gating sinyal derivatif** dengan opsi _LLM fix-pass_.

### Komponen baru
- `app/services/strategy_futures.py` — generator rencana (entries, TP, invalid) + RR guard ≥ 1.8
- `app/services/filters_futures.py` — gating sinyal funding, LSR, basis, taker delta, spread
- `app/services/position_sizing.py` — kalkulasi size & rounding berbasis Binance USDM (ccxt)
- `app/routers/futures_plan.py` — endpoint `GET /futures/plan/{symbol}`
- `backend/tests/test_strategy_futures.py` — uji smoke

### Cara integrasi cepat
1) Salin file ke dalam `auto-analisa-web/backend/app/...` sesuai struktur.
2) Di `app/main.py` pastikan router baru ter-include:
   ```py
   from .routers import futures_plan as futures_plan_router
   app.include_router(futures_plan_router.router)
   ```
3) Opsional: tambahkan konfigurasi per-symbol di `config/futures_symbol_config.json`.

### Alur strategi (ringkas)
- Side AUTO berdasarkan tumpukan EMA (1H/4H) + _skew_ sinyal futures (taker delta, OI/h1, basis).
- Entry 2-lapis (0.4/0.6): e1 dekat support/MB/ema20; e2 lebih dalam (ema50/level kedua).
- Invalid = di luar swing H1 (±0.8×ATR) dengan auto-adjust hingga **RR ≥ rr_min** (default 1.8).
- TP1/TP2 = level resist + kelipatan ATR; setelah TP1: **SL→BE** dan **trailing** di HL/LH 15m.
- Gating: block kondisi ekstrem (funding, LSR, basis, taker delta, spread lebar).
- Rounding: auto snap tick futures.
