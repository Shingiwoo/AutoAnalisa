"use client"
import { useEffect, useMemo, useState } from "react"
import { api } from "../api"
import Spark from "../(components)/Spark"
import type { SignalRow } from "../../lib/types/signal"

type Mode = "fast" | "medium" | "swing"

// using shared type for clarity

export default function SignalBetaPage(){
  const [mode, setMode] = useState<Mode>("medium")
  const [symbols, setSymbols] = useState<string>("BTCUSDT,ETHUSDT,BNBUSDT")
  const [loading, setLoading] = useState(false)
  const [rows, setRows] = useState<SignalRow[]>([])
  const [autoRefresh, setAutoRefresh] = useState<boolean>(true)
  const [error, setError] = useState<string>("")

  async function fetchSignals(){
    setLoading(true)
    setError("")
    try {
      const res = await api.get("/mtf-signals", { params: { mode, symbols } })
      const data = res?.data?.results || []
      setRows(data)
    } catch (e: any) {
      setError("Gagal memuat sinyal.")
    } finally {
      setLoading(false)
    }
  }

  useEffect(()=>{
    fetchSignals()
    if (!autoRefresh) return
    const id = setInterval(fetchSignals, mode === "fast" ? 25000 : mode === "medium" ? 60000 : 15*60*1000)
    return () => clearInterval(id)
  }, [mode, symbols, autoRefresh])

  return (
    <div className="min-h-screen bg-slate-950 text-white">
      <div className="mx-auto max-w-7xl px-4 md:px-6 py-6">
        <h1 className="text-xl font-semibold tracking-tight">Signal (Beta)</h1>
        <p className="text-sm text-zinc-400 mt-1">Sinyal MTF mengikuti bias BTC. Versi awal berbasis Supertrend.</p>

        <div className="mt-4 grid gap-3 md:grid-cols-4">
          <div className="flex flex-col gap-1">
            <label className="text-xs text-zinc-400">Mode</label>
            <select value={mode} onChange={e=>setMode(e.target.value as Mode)} className="rounded bg-transparent px-3 py-2 ring-1 ring-inset ring-white/10 focus:outline-none focus:ring-2 focus:ring-cyan-500">
              <option value="fast">Fast</option>
              <option value="medium">Medium</option>
              <option value="swing">Swing</option>
            </select>
          </div>
          <div className="md:col-span-2 flex flex-col gap-1">
            <label className="text-xs text-zinc-400">Symbols (pisahkan dengan koma)</label>
            <input value={symbols} onChange={e=>setSymbols(e.target.value)} className="rounded bg-transparent px-3 py-2 ring-1 ring-inset ring-white/10 focus:outline-none focus:ring-2 focus:ring-cyan-500" placeholder="BTCUSDT,ETHUSDT,BNBUSDT" />
          </div>
          <div className="flex items-end gap-2">
            <button onClick={fetchSignals} disabled={loading} className="rounded px-3 py-2 bg-cyan-600 hover:bg-cyan-500 disabled:opacity-50">{loading?"Memuat...":"Refresh"}</button>
            <label className="inline-flex items-center gap-2 text-sm text-zinc-300">
              <input type="checkbox" checked={autoRefresh} onChange={e=>setAutoRefresh(e.target.checked)} />
              Auto refresh
            </label>
          </div>
        </div>

        {error && <div className="mt-3 text-red-300 text-sm">{error}</div>}

        <div className="mt-6 overflow-x-auto">
          <table className="min-w-full text-sm">
            <thead>
              <tr className="text-left text-zinc-400">
                <th className="px-2 py-2">Symbol</th>
                <th className="px-2 py-2">Side</th>
                <th className="px-2 py-2">Strength</th>
                <th className="px-2 py-2">Conf</th>
                <th className="px-2 py-2">Total</th>
                <th className="px-2 py-2">BTC Bias</th>
                <th className="px-2 py-2">Trend</th>
                <th className="px-2 py-2">Pattern</th>
                <th className="px-2 py-2">Trigger</th>
                <th className="px-2 py-2">Detail</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((r) => {
                const side = r?.signal?.side || (r.error?"ERROR":"NO_TRADE")
                const strength = r?.signal?.strength || "-"
                const conf = r?.signal?.confidence ?? 0
                const total = r?.total_score ?? 0
                const bias = r?.btc_bias?.direction || "-"
                const sc = r?.scores || {trend: 0, pattern: 0, trigger: 0}
                const color = side === "LONG" ? "text-emerald-300" : side === "SHORT" ? "text-rose-300" : "text-zinc-300"
                return (
                  <tr key={r.symbol} className="border-t border-white/5">
                    <td className="px-2 py-2 font-medium">{r.symbol}</td>
                    <td className={`px-2 py-2 font-semibold ${color}`}>{side}</td>
                    <td className="px-2 py-2">{strength}</td>
                    <td className="px-2 py-2">{conf}</td>
                    <td className="px-2 py-2">{total.toFixed? total.toFixed(2): total}</td>
                    <td className="px-2 py-2">{bias}</td>
                    <td className="px-2 py-2">{sc.trend}</td>
                    <td className="px-2 py-2">{sc.pattern}</td>
                    <td className="px-2 py-2">{sc.trigger}</td>
                    <td className="px-2 py-2">
                      <details>
                        <summary className="cursor-pointer text-cyan-300">Lihat</summary>
                        <div className="mt-2 grid grid-cols-1 md:grid-cols-3 gap-6 text-xs text-zinc-300">
                          <div>
                            <div className="font-semibold text-zinc-200 mb-1">Trend ({r?.tf_map?.trend})</div>
                            <Spark symbol={r.symbol} tf={r?.tf_map?.trend} mode={r.mode} kind="st_line" />
                            <div className="mt-2">trend: {r?.st?.trend?.trend} • signal: {r?.st?.trend?.signal}</div>
                            <div>ST: {r?.indicators?.trend?.ST}, EMA50: {r?.indicators?.trend?.EMA50}, RSI: {r?.indicators?.trend?.RSI}, MACD: {r?.indicators?.trend?.MACD}</div>
                          </div>
                          <div>
                            <div className="font-semibold text-zinc-200 mb-1">Pattern ({r?.tf_map?.pattern})</div>
                            <Spark symbol={r.symbol} tf={r?.tf_map?.pattern} mode={r.mode} kind="st_line" />
                            <div className="mt-2">trend: {r?.st?.pattern?.trend} • signal: {r?.st?.pattern?.signal}</div>
                            <div>ST: {r?.indicators?.pattern?.ST}, RSI: {r?.indicators?.pattern?.RSI}, MACD: {r?.indicators?.pattern?.MACD}, EMA50: {r?.indicators?.pattern?.EMA50}</div>
                          </div>
                          <div>
                            <div className="font-semibold text-zinc-200 mb-1">Trigger ({r?.tf_map?.trigger})</div>
                            <Spark symbol={r.symbol} tf={r?.tf_map?.trigger} mode={r.mode} kind="st_line" />
                            <div className="mt-2">trend: {r?.st?.trigger?.trend} • signal: {r?.st?.trigger?.signal}</div>
                            <div>ST: {r?.indicators?.trigger?.ST}, EMA50: {r?.indicators?.trigger?.EMA50}, RSI: {r?.indicators?.trigger?.RSI}, MACD: {r?.indicators?.trigger?.MACD}</div>
                          </div>
                        </div>
                      </details>
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
          <div className="mt-6 space-y-2 text-sm leading-6 text-zinc-300">
            <h3 className="font-semibold text-zinc-100">Cara menggunakan Signal (Beta)</h3>
            <ul className="list-disc ml-5">
              <li><b>Mode Fast/Medium/Swing</b> memakai kombinasi TF: Fast (15m/5m/1m), Medium (1h/15m/5m), Swing (1D/4h/15m) untuk <i>Trend/Pattern/Trigger</i>.</li>
              <li><b>BTC Bias</b> bersifat <i>strict gate</i>: jika arah sinyal berlawanan dengan bias BTC, hasil menjadi <b>NO_TRADE</b>.</li>
              <li><b>Total</b> adalah skor gabungan (-1..+1). <b>Strength</b> dipetakan dari |Total|: WEAK [0.20–0.35), MEDIUM [0.35–0.55), STRONG [0.55–0.75), EXTREME ≥0.75.</li>
              <li><b>Detail Trend/Pattern/Trigger</b>: setiap panel menampilkan sparkline <i>Supertrend line</i> pada TF terkait. Jika data tidak cukup/flat, sistem fallback ke harga <i>close</i>.</li>
              <li>Baru open posisi bila <b>side ≠ NO_TRADE</b> dan strength ≥ <b>MEDIUM</b>. Untuk scalping cepat, perhatikan <i>Trigger</i> flip (signal=±1).</li>
              <li>Keputusan dibuat pada <b>bar close</b> untuk menghindari repaint. Auto-refresh menyesuaikan TF terpendek.</li>
            </ul>
            <p className="opacity-80">Catatan: nilai indikator lain (EMA/RSI/MACD) ditampilkan di bawah sparkline. Parameter dapat diatur pada preset.</p>
          </div>
        </div>
      </div>
    </div>
  )
}
