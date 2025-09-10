# Tujuan
Membuat **webpage analisa otomatis** (tanpa kirim screenshot) untuk SPOT crypto. User memilih koin (mis. XRPUSDT, DOGEUSDT, OPUSDT, SUIUSDT), sistem menarik data market, menghitung indikator & level, lalu menghasilkan **Analisa SPOT I** siap eksekusi (1–2 TP , TP 3 jika di aktifkan). Webpage mendukung **1–4 user aktif** **tanpa saling bertabrakan**.

---

## Ringkas Fitur Utama
- **Pilih Koin & TF**: 4H–1H–15m (default); bisa ganti 1D bila perlu.  
- **Analisa Otomatis**: Bias, Level Kunci, Rencana Eksekusi (PB/BO), Invalidasi, TP1–TP2, Bacaan Sinyal, Fundamental 24–48 jam singkat.  
- **Tombol Update**: hitung ulang + menyimpan versi hasil (audit trail).  
- **Multi‑User Isolasi**: setiap user punya _workspace_ sendiri, tidak mengubah rencana user lain.  
- **Gating & Fail‑safe**: filter BTC/DXY/news, rate‑limit, time‑window.  
- **Export**: salin teks/JSON, dan cetak PDF.

---

## Arsitektur (Sederhana & Tangguh)
**Front‑end**: Next.js/React + Tailwind (atau Streamlit untuk MVP cepat).  
**Back‑end API**: FastAPI (Python) + Uvicorn.  
**Data Market**: Binance (REST + WebSocket) via **ccxt** atau **python‑binance**.  
**Cache/Queue**: Redis untuk antrian job & _lock_.  
**DB**: SQLite/PostgreSQL (menyimpan histori analisa).  
**Auth ringan**: magic‑link / token per user (1–4 user).  
**Notif opsional**: Telegram bot (update TP1/TP2 kena).  

> Catatan: Binance API gratis dengan batasan rate; Redis memastikan tidak ada _race condition_.

Diagram alur singkat:
```
User ➜ FE (Next.js) ➜ BE (FastAPI)
              ↘︎ Redis (queue+lock) ➜ Worker (analisa) ➜ DB/Cache
FE polling/WS ◀︎──────── result + versi ────────────◀︎ BE
```

---

## Alur Kerja End‑to‑End
1) **Login** (token/OTP) → backend memberi `user_id`.  
2) **Pilih Koin** + opsi (TF, risk_pct, mode PB/BO=auto).  
3) **Submit** → BE membuat **job** `{user_id, symbol, options}` dan **_lock (user_id:symbol)_** di Redis (TTL 30–60 dtk) agar **user 1–4** tidak saling menimpa.  
4) **Worker** menarik data klines (4H/1H/15m), hitung indikator (EMA, Bollinger, RSI, MACD, ATR, MA‑vol), lakukan **scoring & konfluensi**.  
5) Buat **level kunci** (Support/Resistance) + deteksi **PB/BO** + **Invalidasi** + **TP1/TP2**.  
6) (Opsional) Ringkas narasi via LLM (atau _rules engine_ murni).  
7) Simpan **hasil versi** ke DB, rilis **lock**.  
8) FE menampilkan **Analisa SPOT I** + tombol **Update** (membuat job baru & versi baru).  

---

## Isolasi Multi‑User (Anti Tabrakan)
- **Lock per pasangan**: key `lock:{user_id}:{symbol}` saat job berjalan; user lain **tidak dapat** menulis ke pasangan yang sama **untuk user tersebut**, namun boleh analisa koin yang sama pada user berbeda.  
- **Namespace per user**: tabel/kolom `user_id` pada semua penyimpanan (plans, runs, logs).  
- **Versi hasil**: `plans(id, user_id, symbol, version, created_at, payload_json)`.  
- **Rate‑limit**: max 1 job per user per 10–20 detik; max 30 job/hari.  
- **Antrian**: `queue:{env}` FIFO; worker paralel 1–2 agar stabil.

---

## Logika Analisa (Rules Engine)
### 1) Ekstraksi Fitur
- Posisi harga vs **EMA5/20/50/100/200** per TF.  
- Bollinger (MB/UB/DN), **jarak ke UB/DN** (ruang).  
- **RSI14** (tren/momentum), **StochRSI** (timing), **MACD** (konfirmasi).  
- **Volume** vs MA‑Vol (validasi breakout).  

### 2) Skoring (0–50)
- **Trend Stack (0–10)**, **Location (0–10)**, **Momentum (0–10)**, **Volume (0–10)**, **Clean Levels & RR (0–10)**.  
- Threshold: **≥34** layak, **≥40** prioritas.

### 3) Penentuan Level & Skenario
- **Support1** = konfluensi 15m.MB / EMA20 / top‑box retest.  
- **Support2** = 15m.EMA50 / HL minor.  
- **Resistance1** = 1H.UB / swing‑high.  
- **Resistance2** = 4H.UB / res historis berikutnya.  
- **Invalidasi** = 15m close < Support2.  
- **PB Buy**: dua harga bertingkat (60/40).  
- **BO Buy**: stop‑limit di atas box + retest rule.  
- **TP**: 2 target (R1 & R2).  

### 4) Gating & Fail‑safe
- **BTC Gate**: 15m BTC harus di atas EMA20 & tidak dump >0.8%/15m.  
- **News Window**: jeda 10 mnt sekitar rilis besar.  
- **Spread & Depth**: spread < 0.15%.  
- **Daily Max Loss**: 2× risk_amount.  

---

## Format Output Analisa (SPOT I) — yang ditampilkan di Webpage
**Bias Dominan :**  
<teks otomatis, contoh: _Bullish intraday selama struktur 1H bertahan di atas 112.0k–111.7k…_>

**Level Kunci**  
Support: a · b · c  
Resistance: x · y  

**Rencana Eksekusi (spot)**  
1) **Pullback buy (aman)**  
Beli bertahap: <PB1> (60%) · <PB2> (40%)  
Invalidasi intraday: 1H/15m close < <lvl>.  
**TP:** **TP1**, **TP2**.

2) **Breakout buy (agresif)**  
Stop‑limit buy: <trig‑lim>.  
Tambah saat retest <zona> bertahan.  
**SL cepat**: <lvl>.

**Bacaan Sinyal :** ringkas (volume, wick, konfirmasi MACD/RSI).  
**Fundamental Singkat (24–48 jam) :** ringkas (jadwal, DXY, BTC gate).  

> Tombol **Update** menjalankan ulang alur & menyimpan **versi** (v1, v2, …) agar bisa dibandingkan.

---

## Komponen UI (Webpage)
1. **Header**: pilih koin (autocomplete), TF preset, risk_pct, tombol `Analisa`.  
2. **Panel Hasil**: blok **Analisa SPOT I** + badge skor + waktu generate + **[Update]**.  
3. **Riwayat Versi**: daftar v1..vN (bisa expand).  
4. **Export**: copy text, unduh JSON/PDF.  
5. **Batasan & Aturan** (footer kartu):
   - Edukasi, **bukan** saran keuangan; DYOR.  
   - Hanya 1 job aktif per user; rate‑limit; waktu _cooldown_.  
   - TP/SL dihitung untuk **spot**; tidak untuk futures/leverage.  
   - Data dari exchange → kemungkinan delay; pastikan koneksi stabil.  
   - _Fail‑safe_ aktif (BTC gate, news window).  

---

## API & Estimasi Biaya (perkiraan sederhana)
> Harga bisa berubah; gunakan ini sebagai **estimasi awal**.

**1) Binance Exchange (market data & trading)**  
- **Biaya API**: **$0** (gratis), dibatasi rate (REST & WS).  
- **Biaya trading**: fee bursa (mis. 0.1% spot; bisa turun dengan BNB atau VIP).  
- **Catatan**: patuhi _rate limit_ (gunakan cache & _backoff_).

**2) LLM untuk Ringkasan Narasi (opsional)**  
- Alternatif A: **Tanpa LLM** (murni template rules) → **$0**.  
- Alternatif B: **LLM ringkas** (model hemat) → kira‑kira **$1–$10/bulan** untuk 1–4 user ringan (tergantung jumlah analisa/hari).  

**3) Data Makro/News (opsional)**  
- Gunakan sumber gratis (kalender makro publik) → **$0**; atau layanan berbayar (variasi **$10–$49/bulan**).  

**4) Hosting**  
- VPS 1–2 vCPU, 1–2 GB RAM, 20 GB SSD → **$5–$10/bulan** (cukup untuk 1–4 user).  
- Redis (docker di VPS sama) → **$0** tambahan.

> Total estimasi **tanpa LLM**: ± **$5–$10/bulan**.  
> Dengan LLM hemat: **$6–$20/bulan**, tergantung pemakaian.

---

## Skema Data & Endpoint
**Tabel utama**
- `users(id, email, role)`
- `plans(id, user_id, symbol, version, options_json, payload_json, created_at)`
- `locks(key, ttl)` (Redis)

**Endpoint**
- `POST /api/analyze` → body `{symbol, tf, risk_pct, mode}` ➜ return `plan_id, version, payload`.  
- `POST /api/update` → body `{plan_id}` ➜ buat versi baru.  
- `GET /api/plan/{id}` → detail versi.  
- `GET /api/plans?symbol=...` → list versi per user.  
- `GET /api/health` → health check.

---

## Pseudocode Inti (Worker)
```python
def analyze(symbol, tf=('4h','1h','15m'), opts):
    data = fetch_klines_bundle(symbol, tf)
    feats = compute_features(data)  # ema/bb/rsi/macd/atr/vol
    score = score_symbol(feats)
    levels = make_levels(feats)
    plan = build_plan(levels, feats, score, opts)  # PB/BO, invalid, TP1/TP2
    if opts.get('use_llm'):
        plan['narrative'] = llm_summarize(plan, feats)
    save_version(user_id, symbol, plan)
    return plan
```

---

## Aturan/Batasan Operasional (ditampilkan di halaman)
1. **Analisa edukasi**; kamu bertanggung jawab atas keputusan trading.  
2. Maks **1 job aktif** per user; _cooldown_ 10–20 detik antar job.  
3. Maks **30 analisa/hari/user** (konfigurabel).  
4. Mode default **SPOT** (tanpa leverage).  
5. Eksekusi hanya jika **BTC gate** & _news window_ aman.  
6. Data & waktu dalam **WIB** (konfigurabel).  
7. **Privasi**: hasil user hanya dapat dilihat oleh user tersebut.  

---

## Rencana Implementasi (Sprint)
**Sprint 1 (MVP 2–3 hari):**  
- FastAPI + fetch klines + kalkulasi indikator + rules engine + rencana SPOT I + Next.js UI dasar (pilih koin, tampil hasil, tombol Update).  
- Redis lock & versi plan; auth sederhana.  

**Sprint 2:**  
- Export PDF/JSON, riwayat versi, Telegram notifikasi, skor.  
- BTC gate & news window sederhana.  

**Sprint 3:**  
- Mode _multi‑symbol queue_, profil risiko per user, _websocket_ live hints, opsi LLM ringkas.

---

## Template Analisa (dipakai di UI)
> Diisi otomatis oleh engine; contoh format sama seperti permintaan kamu.

**Bias Dominan :**  
Bullish intraday selama struktur 1H bertahan di atas <S1–S2>. Daily pemulihan (reclaim EMA20 D1 ~<x>, EMA50 D1 ~<y> masih di atas).

**Level Kunci**  
Support: <S1> · <S2> · <S3>  
Resistance: <R1> · <R2>

**Rencana Eksekusi (spot)**
1) **Pullback buy (aman)**  
Beli bertahap: <PB1> (60%) · <PB2> (40%)  
Invalidasi intraday: 1H/15m close < <Inv>.  
**TP:** **TP1**, **TP2**.

2) **Breakout buy (agresif)**  
Stop‑limit buy: <TRIG–LIM>.  
Tambah saat retest <Zona> bertahan.  
**SL cepat**: <SL>.

**Bacaan Sinyal :** <Volume/Wick/RSI/MACD>.  
**Fundamental Singkat (24–48 jam) :** <Jendela likuiditas, DXY/BTC, event>.

---

### Penutup
Blueprint ini siap untuk di‑kodekan. Setelah kamu oke, aku bisa lanjutkan **pembuatan kode** (FE Next.js + BE FastAPI + modul analisa) berikut **Dockerfile**, `.env.example`, dan _install guide_ agar bisa langsung jalan di VPS kecil untuk 1–4 user tanpa saling mengganggu.

