# AutoAnalisa Payload & Rules (Spot/Futures)

Ringkas cara pakai CLI dan struktur paket yang ditambahkan oleh patch ini.

- Build payload JSON (REST Binance + indikator ta):
  - python tools/build_payload.py IMXUSDT --market futures --contract perp
  - Output ke folder `payload_out/`.
- Simulasikan rules pullback 1–4% (long-only untuk Spot):
  - python tools/sim_pullback.py payload_out/IMXUSDT_*.json

Fitur utama:
- Datasource REST sinkron untuk Spot/Futures (requests; tanpa kredensial).
- Indikator via `ta` (EMA/BB/RSI/StochRSI/MACD/ATR/Volume stats).
- Fitur struktur (HH/HL/LH/LL) dan S/R sederhana.
- Payload skema Pydantic v2 dan builder terpadu.
- Rules pullback v1: gating dasar + L1 (long) dan S1 (short; di-skip untuk Spot).

Catatan:
- Tanpa API key, account.balance_usdt tidak diisi (None). Risk default 1%.
- Presisi harga/qty diambil dari exchangeInfo (fallback bila tidak ada).
- Semua waktu WIB.

