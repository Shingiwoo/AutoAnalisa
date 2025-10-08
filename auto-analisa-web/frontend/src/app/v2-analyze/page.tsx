"use client"

import { useEffect, useMemo, useState } from "react"
import api from "../api"

type V4 = {
  symbol: string
  timeframe: "15m" | "1h" | "4h" | "1d"
  price: { open: number; high: number; low: number; close: number }
  ema?: Record<string, number>
  rsi?: { "14"?: number }
  macd?: { hist?: number; signal?: number }
  boll?: { upper?: number; lower?: number; mid?: number }
  volume?: number
  oi?: number
  btc_bias?: "bullish_overbought" | "bullish_cooling" | "neutral" | "bearish_mild"
}

const SAMPLE_V4: V4 = {
  symbol: "WLFIUSDT",
  timeframe: "1h",
  price: { open: 0.2004, high: 0.2022, low: 0.1974, close: 0.1999 },
  ema: { "5": 0.2004, "10": 0.2003, "20": 0.2002 },
  rsi: { "14": 48.1 },
  macd: { hist: 0.0001 },
  boll: { upper: 0.2046, lower: 0.1985 },
  volume: 14981078,
  oi: 1280000000,
  btc_bias: "bullish_cooling",
}

function convertV4ToV2(v4: V4) {
  const now = Date.now()
  return {
    symbol: v4.symbol,
    timeframe: v4.timeframe,
    last_price: v4.price?.close ?? 0,
    candles: [
      {
        ts: now,
        open: v4.price?.open ?? v4.price?.close ?? 0,
        high: v4.price?.high ?? v4.price?.close ?? 0,
        low: v4.price?.low ?? v4.price?.close ?? 0,
        close: v4.price?.close ?? 0,
        volume: typeof v4.volume === "number" ? v4.volume : 0,
      },
    ],
    indicators: {
      ema5: v4.ema?.["5"],
      ema10: v4.ema?.["10"],
      ema20: v4.ema?.["20"],
      ema50: v4.ema?.["50"],
      ema100: v4.ema?.["100"],
      ema200: v4.ema?.["200"],
      rsi14: v4.rsi?.["14"],
      macd: v4.macd?.hist,
      macd_signal: v4.macd?.signal,
      bb_up: v4.boll?.upper,
      bb_mid: v4.boll?.mid,
      bb_low: v4.boll?.lower,
    },
    btc_bias: v4.btc_bias,
    btc_context: undefined,
  }
}

export default function V2AnalyzePage() {
  const [text, setText] = useState<string>(JSON.stringify(SAMPLE_V4, null, 2))
  const [followBias, setFollowBias] = useState<boolean>(() => {
    if (typeof window === "undefined") return true
    const s = localStorage.getItem("follow_btc_bias")
    return s === null ? true : s === "1"
  })
  const [busy, setBusy] = useState(false)
  const [result, setResult] = useState<any | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    try {
      if (typeof window !== "undefined")
        localStorage.setItem("follow_btc_bias", followBias ? "1" : "0")
    } catch {}
  }, [followBias])

  const badge = useMemo(() => {
    const bias = (result?.btc_bias_used || "").toString()
    const align = (result?.btc_alignment || "").toString()
    const biasColor = bias.startsWith("bullish")
      ? "bg-emerald-600"
      : bias.startsWith("bearish")
      ? "bg-rose-600"
      : "bg-zinc-500"
    const alignColor = align === "conflict" ? "bg-rose-600" : align === "aligned" ? "bg-emerald-600" : "bg-zinc-500"
    const biasIcon = bias.startsWith("bullish") ? "⬆" : bias.startsWith("bearish") ? "⬇" : "◦"
    return { bias, align, biasColor, alignColor, biasIcon }
  }, [JSON.stringify(result)])

  async function analyze() {
    setBusy(true)
    setError(null)
    setResult(null)
    try {
      const v4 = JSON.parse(text) as V4
      const v2 = convertV4ToV2(v4)
      const { data } = await api.post("v2/analyze", v2, { params: { follow_btc_bias: followBias } })
      setResult(data)
    } catch (e: any) {
      const msg = e?.response?.data?.detail || e?.message || "Gagal menganalisa"
      setError(typeof msg === "string" ? msg : JSON.stringify(msg))
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="max-w-4xl mx-auto p-6 space-y-4 text-zinc-900">
      <h1 className="text-xl font-semibold">V2 Analyze (Tanpa Screenshot)</h1>
      <div className="text-sm text-zinc-600">Masukkan JSON v4 (contoh tersedia), toggle ikuti bias BTC, lalu klik Analyze.</div>
      <div className="flex items-center gap-3">
        <label className="flex items-center gap-2 text-sm">
          <input type="checkbox" checked={followBias} onChange={(e) => setFollowBias(e.target.checked)} />
          Ikuti Bias BTC
        </label>
        <button
          className="px-3 py-1.5 rounded bg-zinc-800 text-white text-sm hover:bg-zinc-700"
          onClick={() => setText(JSON.stringify(SAMPLE_V4, null, 2))}
        >
          Muat Contoh v4
        </button>
      </div>
      <textarea
        className="w-full h-56 border rounded p-3 font-mono text-sm"
        value={text}
        onChange={(e) => setText(e.target.value)}
      />
      <div className="flex items-center gap-2">
        <button
          disabled={busy}
          className="px-4 py-2 rounded bg-cyan-600 text-white hover:bg-cyan-500 disabled:opacity-50"
          onClick={analyze}
        >
          {busy ? "Menganalisa…" : "Analyze v2"}
        </button>
      </div>

      {error && (
        <div className="rounded-xl ring-1 ring-rose-500/30 bg-rose-500/10 p-3 text-sm text-rose-700">{error}</div>
      )}

      {result && (
        <div className="space-y-2">
          <div className="flex items-center gap-2 text-sm">
            <span className="font-medium">Hasil</span>
            {badge.bias && (
              <span className={`px-1.5 py-0.5 rounded text-white text-[11px] ${badge.biasColor}`} title="BTC Bias">
                {badge.biasIcon} {badge.bias.replace("_", " ")}
              </span>
            )}
            {badge.align && (
              <span className={`px-1.5 py-0.5 rounded text-white text-[11px] ${badge.alignColor}`} title="Kesesuaian">
                {badge.align === "conflict" ? "Konflik" : badge.align === "aligned" ? "Selaras" : "Netral"}
              </span>
            )}
          </div>
          <div className="rounded bg-zinc-900 text-zinc-100 p-3 text-xs overflow-auto">
            <pre>{JSON.stringify(result, null, 2)}</pre>
          </div>
        </div>
      )}
    </div>
  )
}

