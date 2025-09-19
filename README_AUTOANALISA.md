# AutoAnalisa Payload & Rules (Spot/Futures)

Ringkas cara pakai CLI dan struktur paket yang ditambahkan oleh patch ini.

- Build payload JSON (REST Binance + indikator ta):
  - python tools/build_payload.py IMXUSDT --market futures --contract perp --risk 0.008 --leverage 10 --news-json instruksi/news.sample.json --macro-yaml config/macro_sessions.yaml --btc-bias bull
  - Output ke folder `payload_out/`.
- Simulasikan rules pullback 1–4% (long-only untuk Spot):
  - python tools/sim_pullback.py payload_out/IMXUSDT_*.json

Fitur utama:
- Datasource REST sinkron untuk Spot/Futures (requests; tanpa kredensial).
- Indikator via `ta` (EMA/BB/RSI/StochRSI/MACD/ATR/Volume stats).
- Fitur struktur (HH/HL/LH/LL) dan S/R sederhana.
- Payload skema Pydantic v2 dan builder terpadu.
- Rules pullback v1: gating dasar + L1/L2/L3 (long) dan S1/S2/S3 (short; short di-skip untuk Spot). Termasuk filter bias sesi WIB dan penyesuaian skor (+/−10).

Confluence & Confidence:
- levels.confluence[] berisi objek: { tf, price, tags, confidence, distance, tol }
- Toleransi dinamis per-TF: gabungan min% vs ATR-rasio vs tick.
- Confidence dihitung dari bobot tag dan decay jarak; digunakan untuk bonus skor sinyal (hingga +15) atau penalti (−5) jika tidak ada confluence dekat entry.

Catatan:
- Tanpa API key, account.balance_usdt tidak diisi (None). Risk default 1%.
- Presisi harga/qty diambil dari exchangeInfo (fallback bila tidak ada).
- Semua waktu WIB.

Testing:
- Jalankan tes unit untuk modul baru: `pytest -q tests`

Samples:
- Contoh payload: samples/payload.sample.json
- Contoh signal: samples/signal.sample.json
