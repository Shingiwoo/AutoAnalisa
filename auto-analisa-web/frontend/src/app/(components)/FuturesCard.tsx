"use client"

import { useCallback, useEffect, useMemo, useState } from "react"
import { api } from "../../app/api"
import ChartOHLCV from "./ChartOHLCV"
import { GptReportBox } from "./LLMReport"

import type { AxiosError } from "axios"

type Tf = "5m" | "15m" | "1h" | "4h"
type Mode = "scalping" | "swing"

type Props = {
  symbol: string
  llmEnabled?: boolean
  llmRemaining?: number
  onRefreshQuota?: () => void
}

type GptReport = {
  report_id?: number
  text?: any
  overlay?: any
  meta?: any
  created_at?: string
  ttl?: number
  cached_at?: string
}

type FuturesPlan = any

type OverlaySummary = {
  sl?: number
  tp?: number[]
  entries?: number[]
  bybk?: { range: [number, number]; note?: string }[]
  bo?: { price?: number; note?: string; direction?: "above" | "below" }[]
}

const LOCAL_PREFIX = "gpt_report"
// Fallback TTL (dipakai hanya jika report tidak membawa ttl dari backend)
const DEFAULT_SCALPING_TTL =
  Number(process.env.NEXT_PUBLIC_GPT_TTL_SCALPING_SECONDS ?? 3600) || 3600
const DEFAULT_SWING_TTL =
  Number(process.env.NEXT_PUBLIC_GPT_TTL_SWING_SECONDS ?? 43200) || 43200

export default function FuturesCard({ symbol, llmEnabled, llmRemaining, onRefreshQuota }: Props) {
  const [tab, setTab] = useState<Tf>("15m")
  const [ohlcv, setOhlcv] = useState<any[]>([])
  const [loadingOhlcv, setLoadingOhlcv] = useState(false)
  const [plan, setPlan] = useState<FuturesPlan | null>(null)
  const [planErr, setPlanErr] = useState<string>("")
  const [mode, setMode] = useState<Mode>("scalping")
  const [reports, setReports] = useState<{ scalping?: GptReport | null; swing?: GptReport | null }>({})
  const [reportLoading, setReportLoading] = useState(false)
  const [busy, setBusy] = useState(false)
  const [message, setMessage] = useState<string>("")
  const [applied, setApplied] = useState<OverlaySummary | null>(null)
  // v2 analyze (beta)
  const [v2Busy, setV2Busy] = useState(false)
  const [v2Result, setV2Result] = useState<any | null>(null)
  const [followBias, setFollowBias] = useState<boolean>(() => {
    if (typeof window === "undefined") return true
    const s = localStorage.getItem("follow_btc_bias")
    return s === null ? true : s === "1"
  })

  const tf = tab
  const activeReport = (reports[mode] ?? null) as GptReport | null
  const overlayTf = activeReport?.overlay?.tf
  const srExtra = useSRExtra(tab, ohlcv)

  const planBase = useMemo(() => {
    if (!plan) return null
    if (tab === "1h" || tab === "4h") {
      return (plan.variants && (plan.variants as any).swing) ? (plan.variants as any).swing : plan
    }
    return plan
  }, [plan, tab])

  // Default mode mengikuti tab
  useEffect(() => {
    if (tab === "5m" || tab === "15m") setMode((prev) => (prev === "scalping" ? prev : "scalping"))
    else setMode((prev) => (prev === "swing" ? prev : "swing"))
  }, [tab])

  // Fetch futures baseline plan
  useEffect(() => {
    let cancelled = false
    async function loadPlan() {
      try {
        setPlanErr("")
        const { data } = await api.get(`analyses/${symbol}/futures`)
        if (!cancelled) {
          setPlan(data)
        }
      } catch (e: any) {
        const msg = e?.response?.data?.detail || "Gagal memuat data futures"
        if (!cancelled) {
          setPlan(null)
          setPlanErr(msg)
        }
      }
    }
    loadPlan()
    return () => {
      cancelled = true
    }
  }, [symbol])

  // Fetch OHLCV data
  useEffect(() => {
    let cancelled = false
    async function loadOhlcv() {
      try {
        setLoadingOhlcv(true)
        const { data } = await api.get("ohlcv", { params: { symbol, tf, limit: 200, market: "futures" } })
        if (!cancelled) setOhlcv(data)
      } catch (e) {
        if (!cancelled) setOhlcv([])
      } finally {
        if (!cancelled) setLoadingOhlcv(false)
      }
    }
    loadOhlcv()
    return () => {
      cancelled = true
    }
  }, [symbol, tf])

  // Hydrate dari localStorage
  useEffect(() => {
    if (typeof window === "undefined") return
    const next: { scalping?: GptReport | null; swing?: GptReport | null } = {}
    next.scalping = loadLocalReport(symbol, "scalping")
    next.swing = loadLocalReport(symbol, "swing")
    setReports(next)
    setMessage("")
    setApplied(null)
  }, [symbol])

  // Fetch cache terbaru saat mode berubah
  useEffect(() => {
    let cancelled = false
    async function fetchCache() {
      if (!symbol) return
      try {
        setReportLoading(true)
        const { data } = await api.get("gpt/futures/report", { params: { symbol, mode } })
        if (cancelled) return
        const normalized = normalizeReport(data)
        setReports((prev) => ({ ...prev, [mode]: normalized }))
        saveLocalReport(symbol, mode, normalized)
        logEngine(normalized?.meta)
        setMessage(checkNoTrade(normalized, mode))
      } catch (err) {
        if (!cancelled) {
          const ax = err as AxiosError<any>
          if (ax?.response?.status === 404) {
            setReports((prev) => ({ ...prev, [mode]: null }))
          }
        }
      } finally {
        if (!cancelled) setReportLoading(false)
      }
    }
    fetchCache()
    return () => {
      cancelled = true
    }
  }, [symbol, mode])

  const decimals = useMemo(() => {
    const d = planBase?.price_decimals
    if (typeof d === "number" && d >= 0) return d
    try {
      const sample = (() => {
        const arr: number[] = []
        ;(planBase?.entries || []).forEach((e: any) => {
          const v = Array.isArray(e?.range) ? e.range[0] : undefined
          if (typeof v === "number") arr.push(v)
        })
        if (typeof planBase?.invalids?.hard_1h === "number") arr.push(planBase.invalids.hard_1h)
        return arr.find((x) => typeof x === "number") ?? 1
      })()
      if (sample >= 1000) return 2
      if (sample >= 100) return 2
      if (sample >= 10) return 3
      if (sample >= 1) return 4
      if (sample >= 0.1) return 5
      return 6
    } catch {
      return 5
    }
  }, [planBase])

  const tickSize = useMemo(() => {
    if (planBase?.precision?.tickSize && typeof planBase.precision.tickSize === "number") {
      return planBase.precision.tickSize
    }
    return Math.pow(10, -decimals)
  }, [planBase, decimals])

  const overlayInfo = useMemo(() => {
    if (!activeReport) return extractOverlay(null, tickSize, decimals)
    return extractOverlay(activeReport.overlay, tickSize, decimals)
  }, [activeReport, tickSize, decimals])

  const chartOverlays = useMemo(() => {
    const sr = [...(planBase?.support || []), ...(planBase?.resistance || []), ...srExtra]
    const invalids = planBase?.invalids || {}
    // JANGAN tampilkan TP & Entry default.
    // Tampilkan hanya saat user klik “Terapkan Saran” (pakai ‘applied’)
    // atau setelah Tanya GPT (overlay LLM digambar via llm).
    const entriesFromApplied = applied?.entries && applied.entries.length ? applied.entries : undefined
    const tpFromApplied = applied?.tp && applied.tp.length ? applied.tp : undefined
    // v2 ghost overlay from last result
    let ghost: any = undefined
    try{
      const entriesV2 = Array.isArray((v2Result?.plan||{}).entries) ? (v2Result.plan.entries as any[]).map((e:any)=> typeof e?.price==='number'? e.price : undefined).filter((x:any)=> typeof x==='number') : []
      const tpV2 = Array.isArray((v2Result?.plan||{}).take_profits) ? (v2Result.plan.take_profits as any[]).map((t:any)=> typeof t?.price==='number'? t.price : undefined).filter((x:any)=> typeof x==='number') : []
      const slV2 = typeof v2Result?.plan?.stop_loss?.price === 'number' ? v2Result.plan.stop_loss.price : undefined
      if ((entriesV2 && entriesV2.length) || (tpV2 && tpV2.length) || typeof slV2 === 'number') {
        ghost = { entries: entriesV2 || undefined, tp: tpV2 || undefined, invalid: slV2 }
      }
    }catch{}
    return {
      sr,
      invalid: invalids,
      entries: entriesFromApplied,     // <— bukan plan default
      tp: tpFromApplied,               // <— bukan plan default
      liq: planBase?.risk?.liq_price_est,  // Liq tetap ditampilkan
      llm: activeReport?.overlay ? activeReport.overlay : null,
      ghost,
    }
  }, [planBase, applied, tab, ohlcv, activeReport, srExtra, v2Result])

  const handleAnalyze = useCallback(async () => {
    if (!llmEnabled || (typeof llmRemaining === "number" && llmRemaining <= 0)) {
      alert("LLM tidak tersedia atau kuota habis.")
      return
    }
    try {
      setBusy(true)
      const planForMode = mode === "swing" ? (plan?.variants?.swing || planBase || plan) : (planBase || plan)
      const payload: any = {
        symbol,
        tf,
        futures: planForMode,
      }
      if (tf !== "15m") {
        try {
          const { data } = await api.get("ohlcv", { params: { symbol, tf: "15m", limit: 200, market: "futures" } })
          payload.ohlcv15m = data
        } catch {}
      }
      if (mode === "scalping") {
        try {
          const { data } = await api.get("ohlcv", { params: { symbol, tf: "5m", limit: 200, market: "futures" } })
          payload.ohlcv5m = data
        } catch {}
      }
      const opts = {
        timezone: "Asia/Jakarta",
        tick_size: tickSize,
        step_size: plan?.precision?.stepSize,
        round: true,
      }
      const { data } = await api.post("gpt/futures/analyze", {
        symbol,
        mode,
        payload,
        opts,
      })
      const normalized = normalizeReport(data)
      setReports((prev) => ({ ...prev, [mode]: normalized }))
      saveLocalReport(symbol, mode, normalized)
      logEngine(normalized?.meta)
      setMessage(checkNoTrade(normalized, mode))
      setApplied(null)
      onRefreshQuota?.()
    } catch (e: any) {
      const msg = e?.response?.data?.detail?.message || e?.response?.data?.detail || e?.message || "Gagal memanggil GPT"
      alert(msg)
    } finally {
      setBusy(false)
    }
  }, [symbol, mode, tf, plan, tickSize, llmEnabled, llmRemaining, onRefreshQuota])

  const handleApply = useCallback(() => {
    const info = overlayInfo
    if (!info || (!info.tp || info.tp.length === 0) || !activeReport) {
      alert("Overlay belum tersedia.")
      return
    }
    setApplied(info)
    setMessage(checkNoTrade(activeReport, mode))
  }, [overlayInfo, activeReport, mode])

  const handleAnalyzeV2 = useCallback(async () => {
    try {
      setV2Busy(true)
      setV2Result(null)
      try { if (typeof window !== 'undefined') localStorage.setItem('follow_btc_bias', followBias ? '1' : '0') } catch {}
      const { data: snap } = await api.get('v2/snapshot', { params: { symbol, timeframe: tf } })
      const { data } = await api.post('v2/analyze', snap, { params: { follow_btc_bias: followBias } })
      setV2Result(data)
    } catch (e: any) {
      const msg = e?.response?.data?.detail || e?.message || 'Gagal Analyze v2'
      alert(typeof msg === 'string' ? msg : JSON.stringify(msg))
    } finally {
      setV2Busy(false)
    }
  }, [symbol, tf, followBias])

  const handleApplyV2 = useCallback(() => {
    try {
      const entries = Array.isArray((v2Result?.plan || {}).entries)
        ? (v2Result!.plan.entries as any[])
            .map((e: any) => (typeof e?.price === 'number' ? e.price : undefined))
            .filter((x: any) => typeof x === 'number')
        : []
      const tp = Array.isArray((v2Result?.plan || {}).take_profits)
        ? (v2Result!.plan.take_profits as any[])
            .map((t: any) => (typeof t?.price === 'number' ? t.price : undefined))
            .filter((x: any) => typeof x === 'number')
        : []
      const sl = typeof v2Result?.plan?.stop_loss?.price === 'number' ? v2Result!.plan.stop_loss.price : undefined
      if ((!entries || entries.length === 0) && (!tp || tp.length === 0) && typeof sl !== 'number') {
        alert('Hasil v2 belum memiliki entries/TP/SL yang cukup')
        return
      }
      setApplied({ entries: entries || undefined, tp: tp || undefined, sl: sl })
    } catch {
      alert('Gagal menerapkan hasil v2')
    }
  }, [v2Result])

  const appliedPlan = useMemo(() => {
    if (!planBase) return null
    if (!applied) return planBase
    const next = { ...planBase }
    if (applied.entries && applied.entries.length > 0) {
      next.entries = applied.entries.map((v) => ({ range: [v, v], weight: 50, type: "ENTRY" }))
    }
    if (applied.tp && applied.tp.length > 0) {
      next.tp = applied.tp.map((v, idx) => ({ name: `TP${idx + 1}`, range: [v, v], reduce_only_pct: idx === 0 ? 40 : 60 }))
    }
    if (applied.sl) {
      next.invalids = { ...(next.invalids || {}), hard_1h: applied.sl }
    }
    try {
      const posisi = pickModeSection(activeReport?.text, mode)?.posisi
      if (posisi) next.side = posisi
    } catch {}
    return next
  }, [planBase, applied, activeReport, mode])

  useEffect(() => {
    if (!activeReport) return
    setMessage(checkNoTrade(activeReport, mode))
  }, [activeReport, mode])

  const planDisplay = appliedPlan || planBase

  return (
    <div className="rounded-2xl ring-1 ring-zinc-200 dark:ring-white/10 bg-white dark:bg-zinc-900 shadow-sm p-4 md:p-6 space-y-4 text-zinc-900 dark:text-zinc-100">
      <header className="flex items-center justify-between">
        <div className="text-lg font-semibold flex items-center gap-2">
          <span>{symbol.toUpperCase()}</span>
          {plan?.tf_base && (
            <span className="px-1.5 py-0.5 rounded bg-zinc-200 dark:bg-zinc-800 text-xs">{plan.tf_base}</span>
          )}
          {planDisplay?.profile && (
            <span className="px-1.5 py-0.5 rounded bg-cyan-100 text-cyan-800 dark:bg-cyan-900/40 dark:text-cyan-200 text-xs">
              {planDisplay.profile.toUpperCase()}
            </span>
          )}
          {typeof planDisplay?.ttl_min === "number" && (
            <span className="px-1.5 py-0.5 rounded bg-emerald-100 text-emerald-700 dark:bg-emerald-900/40 dark:text-emerald-200 text-xs">
              TTL {planDisplay.ttl_min}m
            </span>
          )}
          {/* Badge sinkron dari hasil v2 (bias & alignment) */}
          {(() => {
            try {
              const bias = (v2Result?.btc_bias_used || '').toString()
              const align = (v2Result?.btc_alignment || '').toString()
              if (!bias && !align) return null
              const biasColor = bias.startsWith('bullish') ? 'bg-emerald-600' : bias.startsWith('bearish') ? 'bg-rose-600' : 'bg-zinc-500'
              const biasIcon = bias.startsWith('bullish') ? '⬆' : bias.startsWith('bearish') ? '⬇' : '◦'
              const alignColor = align === 'conflict' ? 'bg-rose-600' : align === 'aligned' ? 'bg-emerald-600' : 'bg-zinc-500'
              return (
                <span className="flex items-center gap-2">
                  {bias && <span className={`px-1.5 py-0.5 rounded text-white text-[11px] ${biasColor}`}>{biasIcon} {bias.replace('_', ' ')}</span>}
                  {align && <span className={`px-1.5 py-0.5 rounded text-white text-[11px] ${alignColor}`}>{align === 'conflict' ? 'Konflik' : 'Selaras'}</span>}
                </span>
              )
            } catch { return null }
          })()}
        </div>
        {activeReport?.created_at && (
          <div className="text-xs text-zinc-500">
            Cache {new Date(activeReport.created_at).toLocaleString("id-ID", { timeZone: "Asia/Jakarta" })} WIB
          </div>
        )}
      </header>

      <div className="flex items-center gap-2 text-sm" role="tablist" aria-label="TF">
        {(["5m", "15m", "1h", "4h"] as Tf[]).map((t) => (
          <button
            key={t}
            role="tab"
            aria-selected={tab === t}
            onClick={() => setTab(t)}
            className={`px-2.5 py-1 rounded-md transition ${tab === t ? "bg-indigo-600 text-white" : "bg-white text-zinc-900 hover:bg-zinc-100 dark:bg-zinc-800 dark:text-white/90"}`}
          >
            {t}
          </button>
        ))}
        {overlayTf && overlayTf !== tf && (
          <span className="text-xs text-amber-500">Overlay dihitung untuk TF {overlayTf}</span>
        )}
      </div>

      {planErr && <div className="p-2 rounded bg-rose-50 border border-rose-200 text-rose-700 text-sm">{planErr}</div>}
      {message && !planErr && <div className="p-2 rounded bg-amber-50 border border-amber-200 text-amber-700 text-sm">{message}</div>}

      <div className="rounded-none overflow-hidden ring-1 ring-zinc-200 dark:ring-white/10 bg-white dark:bg-zinc-950 relative">
        <div className="aspect-[16/9] md:aspect-[21/9]">
          <ChartOHLCV data={ohlcv} overlays={chartOverlays as any} className="h-full" />
        </div>
        {loadingOhlcv && (
          <div className="absolute inset-0 flex items-center justify-center bg-black/5 dark:bg-white/5">
            <div className="text-xs text-zinc-700 dark:text-zinc-200">Memuat {tf}…</div>
          </div>
        )}
      </div>

      <div className="flex items-center gap-3 flex-wrap">
        <div className="flex items-center rounded-md overflow-hidden ring-1 ring-zinc-200">
          {(["scalping", "swing"] as Mode[]).map((m) => (
            <button
              key={m}
              onClick={() => setMode(m)}
              className={`px-3 py-1 text-sm ${mode === m ? "bg-cyan-600 text-white" : "bg-white text-zinc-900 hover:bg-zinc-100"}`}
            >
              {m}
            </button>
          ))}
        </div>
        <button
          disabled={busy || !llmEnabled || (typeof llmRemaining === "number" && llmRemaining <= 0)}
          className="px-3 py-2 rounded-md bg-cyan-600 text-white hover:bg-cyan-500 disabled:opacity-50"
          onClick={handleAnalyze}
        >
          {busy ? "Meminta…" : `Tanya GPT (${mode})`}
        </button>
        <button
          className="px-3 py-2 rounded-md bg-emerald-600 text-white hover:bg-emerald-500 disabled:opacity-50"
          onClick={handleApply}
          disabled={!overlayInfo || !overlayInfo.tp || overlayInfo.tp.length === 0}
        >
          Terapkan Saran
        </button>
        {/* Analyze v2 (beta) */}
        <label className="flex items-center gap-2 text-xs text-zinc-600 dark:text-zinc-300 ml-2">
          <input type="checkbox" checked={followBias} onChange={(e)=> setFollowBias(e.target.checked)} /> Ikuti Bias BTC
        </label>
        <button
          className="px-3 py-2 rounded-md bg-zinc-800 text-white hover:bg-zinc-700 disabled:opacity-50"
          onClick={handleAnalyzeV2}
          disabled={v2Busy}
          title="Analyze v2 tanpa screenshot (beta)"
        >
          {v2Busy ? 'Analyze v2…' : 'Analyze v2 (beta)'}
        </button>
        <button
          className="px-3 py-2 rounded-md bg-violet-700 text-white hover:bg-violet-600 disabled:opacity-50"
          onClick={handleApplyV2}
          disabled={!v2Result}
          title="Terapkan entries/TP/SL dari hasil v2 ke overlay aktif"
        >
          Terapkan v2
        </button>
        <button
          className="px-3 py-2 rounded-md bg-zinc-700 text-white hover:bg-zinc-600 disabled:opacity-50"
          onClick={() => {
            try {
              localStorage.removeItem(buildKey(symbol, 'scalping'))
              localStorage.removeItem(buildKey(symbol, 'swing'))
              setReports({})
              setApplied(null)
              setMessage('')
              alert('Cache report dibersihkan')
            } catch {}
          }}
        >
          Clear cache report
        </button>
      </div>

      <GptReportBox symbol={symbol} mode={mode} report={activeReport} loading={reportLoading} />

      {v2Result && <V2ReportBox result={v2Result} />}

      <FuturesMetrics plan={planDisplay} overlay={overlayInfo} />
    </div>
  )
}

function V2ReportBox({ result }: { result: any }){
  const bias = String(result?.plan?.bias || '').toLowerCase()
  const biasColor = bias.startsWith('bull') ? 'text-emerald-500' : bias.startsWith('bear') ? 'text-rose-500' : 'text-zinc-400'
  const entries = Array.isArray(result?.plan?.entries) ? result.plan.entries : []
  const tps = Array.isArray(result?.plan?.take_profits) ? result.plan.take_profits : []
  const sl = result?.plan?.stop_loss
  const keyLv = Array.isArray(result?.key_levels) ? result.key_levels : []
  const align = String(result?.btc_alignment || '')
  const alignColor = align === 'conflict' ? 'bg-rose-600' : align === 'aligned' ? 'bg-emerald-600' : 'bg-zinc-500'
  const biasUsed = String(result?.btc_bias_used || '')
  const biasUsedColor = biasUsed.startsWith('bullish') ? 'bg-emerald-600' : biasUsed.startsWith('bearish') ? 'bg-rose-600' : 'bg-zinc-500'
  return (
    <div className="rounded-xl ring-1 ring-cyan-500/20 bg-cyan-500/5 p-3 space-y-2">
      <div className="flex items-center gap-2 text-sm">
        <span className="font-medium">V2 Report</span>
        {biasUsed && <span className={`px-1.5 py-0.5 rounded text-white text-[11px] ${biasUsedColor}`}>{biasUsed.replace('_',' ')}</span>}
        {align && <span className={`px-1.5 py-0.5 rounded text-white text-[11px] ${alignColor}`}>{align==='conflict'? 'Konflik':'Selaras'}</span>}
      </div>
      {align==='conflict' && (
        <div className="p-2 rounded bg-rose-500/10 border border-rose-500/30 text-rose-300 text-xs">⚠ Rencana bertentangan dengan Bias BTC — verifikasi manual disarankan.</div>
      )}
      <dl className="grid grid-cols-1 md:grid-cols-2 gap-3 text-sm">
        <div>
          <dt className="text-zinc-500">Bias</dt>
          <dd className={biasColor}>{result?.plan?.bias || '-'}</dd>
        </div>
        <div>
          <dt className="text-zinc-500">Struktur / Momentum</dt>
          <dd>{result?.structure || '-'} • {result?.momentum || '-'}</dd>
        </div>
        <div>
          <dt className="text-zinc-500">Entries</dt>
          <dd>{entries.length>0 ? entries.map((e:any)=> `${e.label||''} ${e.price}`).join(' · ') : '-'}</dd>
        </div>
        <div>
          <dt className="text-zinc-500">TP</dt>
          <dd className="text-emerald-400">{tps.length>0 ? tps.map((t:any)=> `${t.label||''} ${t.price}`).join(' → ') : '-'}</dd>
        </div>
        <div>
          <dt className="text-zinc-500">SL</dt>
          <dd className="text-rose-400">{sl?.price ?? '-'}</dd>
        </div>
        <div>
          <dt className="text-zinc-500">Key Levels</dt>
          <dd>{keyLv.length>0 ? keyLv.map((k:any)=> `${k.label||''} ${k.price}`).join(' · ') : '-'}</dd>
        </div>
        <div className="md:col-span-2">
          <dt className="text-zinc-500">Rationale</dt>
          <dd>{result?.plan?.rationale || '-'}</dd>
        </div>
      </dl>
    </div>
  )
}

function pickModeSection(text: any, mode: Mode) {
  if (!text) return null
  if (mode === "scalping") return text?.section_scalping || null
  return text?.section_swing || null
}

function checkNoTrade(report: GptReport | null, mode: Mode): string {
  try {
    const sec =
      pickModeSection(report?.text, mode) ||
      pickModeSection(report?.text, (report?.overlay?.mode as Mode) || mode) ||
      pickModeSection(report?.text, "scalping")
    if (!sec) return ""
    if ((sec.posisi || "").toUpperCase() === "NO-TRADE") {
      return "Tidak ada setup valid; tunggu retest/konfirmasi."
    }
  } catch {}
  return ""
}

function normalizeReport(data: any): GptReport {
  if (!data || typeof data !== "object") return {}
  const out: GptReport = { ...data }
  if (data?.meta?.cached_at && !data.created_at) out.created_at = data.meta.cached_at
  if (!out.ttl && data?.meta?.ttl_seconds) out.ttl = data.meta.ttl_seconds
  return out
}

function buildKey(symbol: string, mode: Mode) {
  return `${LOCAL_PREFIX}:${symbol.toUpperCase()}:${mode}`
}

function loadLocalReport(symbol: string, mode: Mode): GptReport | null {
   if (typeof window === "undefined") return null
   try {
     const raw = localStorage.getItem(buildKey(symbol, mode))
     if (!raw) return null
     const parsed = JSON.parse(raw)
     const createdIso = parsed?.created_at || parsed?.meta?.cached_at
     const createdMs = createdIso ? Date.parse(createdIso) : parsed?.saved_at
    const fallbackTtl =
      (mode === "swing" ? DEFAULT_SWING_TTL : DEFAULT_SCALPING_TTL) * 1000
    const ttl =
      (parsed?.ttl ?? parsed?.meta?.ttl_seconds) * 1000 || fallbackTtl
     if (!createdMs || Date.now() - createdMs > ttl) {
       localStorage.removeItem(buildKey(symbol, mode))
       return null
     }
     return parsed
  } catch {
    localStorage.removeItem(buildKey(symbol, mode))
    return null
  }
}

function saveLocalReport(symbol: string, mode: Mode, data: any) {
  if (typeof window === "undefined") return
  const payload = {
    ...data,
    saved_at: Date.now(),
  }
  try {
    localStorage.setItem(buildKey(symbol, mode), JSON.stringify(payload))
  } catch {}
}

function logEngine(meta: any) {
  try {
    if (!meta) return
    const engine = meta.engine || meta.model
    const version = meta.version || meta.rev
    if (engine) console.info("[GPT Futures] engine", engine, version ? `(${version})` : "")
  } catch {}
}

function extractOverlay(overlay: any, tickSize: number, decimals: number): OverlaySummary | null {
  if (!overlay || typeof overlay !== "object") return null
  const info: OverlaySummary = {}
  try {
    if (Array.isArray(overlay.lines)) {
      const tp: number[] = []
      overlay.lines.forEach((line: any) => {
        const label = String(line?.label || line?.type || "").toUpperCase()
        const price = typeof line?.price === "number" ? roundTo(line.price, tickSize, decimals) : undefined
        if (!price) return
        if (label.includes("TP")) tp.push(price)
        if (label.includes("SL")) info.sl = price
      })
      if (tp.length > 0) info.tp = tp
    }
    if (Array.isArray(overlay.zones)) {
      const entries: number[] = []
      const bybk: { range: [number, number]; note?: string }[] = []
      overlay.zones.forEach((zone: any) => {
        if (!Array.isArray(zone?.range)) return
        const lo = typeof zone.range[0] === "number" ? roundTo(zone.range[0], tickSize, decimals) : undefined
        const hi = typeof zone.range[1] === "number" ? roundTo(zone.range[1], tickSize, decimals) : lo
        if (zone?.type?.toUpperCase() === "ENTRY" && typeof lo === "number") {
          entries.push(lo)
        }
        if (zone?.type?.toUpperCase() === "BYBK" && typeof lo === "number" && typeof hi === "number") {
          bybk.push({ range: [lo, hi], note: zone?.note })
        }
      })
      if (entries.length > 0) info.entries = entries
      if (bybk.length > 0) info.bybk = bybk
    }
    if (Array.isArray(overlay.markers)) {
      const markers: { price?: number; note?: string; direction?: "above" | "below" }[] = []
      overlay.markers.forEach((mk: any) => {
        const price = typeof mk?.price === "number" ? roundTo(mk.price, tickSize, decimals) : undefined
        const label = String(mk?.label || mk?.note || "")
        const type = String(mk?.type || "").toUpperCase()
        if (type === "BO" && price) {
          const dir = label.toLowerCase().includes("below") ? "below" : "above"
          markers.push({ price, note: label, direction: dir })
        }
      })
      if (markers.length > 0) info.bo = markers
    }
  } catch {}
  return info
}

function roundTo(value: number, tick: number, decimals: number) {
  if (!isFinite(value)) return value
  if (!tick || tick <= 0) return parseFloat(value.toFixed(decimals))
  const snapped = Math.round(value / tick) * tick
  return parseFloat(snapped.toFixed(decimals))
}

function computePivots(rows: any[], left = 15, right = 15) {
  const highs: number[] = []
  const lows: number[] = []
  for (let i = left; i < rows.length - right; i++) {
    let isHigh = true
    let isLow = true
    for (let j = i - left; j <= i + right; j++) {
      if (rows[j].h > rows[i].h) isHigh = false
      if (rows[j].l < rows[i].l) isLow = false
      if (!isHigh && !isLow) break
    }
    if (isHigh) highs.push(rows[i].h)
    if (isLow) lows.push(rows[i].l)
  }
  const round = (x: number) => +x.toFixed(6)
  const uniq = (arr: number[]) => {
    const out: number[] = []
    arr.sort((a, b) => a - b)
    for (const v of arr) {
      if (out.length === 0 || Math.abs(v - out[out.length - 1]) > 1e-6) out.push(v)
    }
    return out
  }
  return { highs: uniq(highs.map(round)).slice(-6), lows: uniq(lows.map(round)).slice(-6) }
}

function useSRExtra(tab: Tf, rows: any[]) {
  return useMemo(() => {
    if (!rows || rows.length === 0) return [] as number[]
    if (tab === "5m" || tab === "15m" || tab === "1h" || tab === "4h") {
      const piv = computePivots(rows, 15, 15)
      return [...piv.highs, ...piv.lows]
    }
    return [] as number[]
  }, [tab, JSON.stringify(rows?.slice(-220))])
}

function FuturesMetrics({ plan, overlay }: { plan: FuturesPlan | null; overlay: OverlaySummary | null }) {
  if (!plan) return <div className="text-sm text-zinc-500">Data futures belum tersedia.</div>
  const rr = plan?.risk || {}
  const sig = plan?.futures_signals || {}
  const tpOverlay = overlay?.tp || []
  const slOverlay = overlay?.sl
  const fmt = (n: number | undefined) => (typeof n === "number" ? n.toFixed(plan?.price_decimals ?? 4) : "-")
  const fundingColor = typeof sig?.funding?.now === "number" ? (sig.funding.now > 0 ? "text-rose-500" : "text-emerald-500") : "text-zinc-600"
  const basisBp = typeof sig?.basis?.bp === "number" ? sig.basis.bp : null
  const basisColor = basisBp !== null ? (basisBp > 0 ? "text-emerald-500" : "text-amber-600") : "text-zinc-600"
  const oiH1 = Number(sig?.oi?.h1 ?? sig?.oi?.d1 ?? 0)
  const oiH4 = Number(sig?.oi?.h4 ?? 0)
  const oiH1Color = isFinite(oiH1) ? (oiH1 > 0 ? "text-emerald-500" : oiH1 < 0 ? "text-rose-500" : "text-zinc-600") : "text-zinc-600"
  const oiH4Color = isFinite(oiH4) ? (oiH4 > 0 ? "text-emerald-500" : oiH4 < 0 ? "text-rose-500" : "text-zinc-600") : "text-zinc-600"
  const profileLabel = plan?.profile_config?.label || (plan?.profile ? String(plan.profile).toUpperCase() : "-")
  const ttlText = typeof plan?.ttl_min === "number" ? `${plan.ttl_min} menit` : "-"
  const tpPctText = Array.isArray(plan?.tp_pct) ? plan.tp_pct.join(" / ") : null
  return (
    <section className="rounded-xl ring-1 ring-indigo-200/60 dark:ring-indigo-500/20 bg-indigo-50/60 dark:bg-indigo-950/40 p-4 text-sm space-y-3">
      <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
        <div>
          <div className="text-zinc-500">Side • Leverage</div>
          <div>{plan?.side || "-"} • isolated x={plan?.leverage_suggested?.x ?? "-"}</div>
        </div>
        <div>
          <div className="text-zinc-500">Risk</div>
          <div>
            risk/trade: {rr?.risk_per_trade_pct ?? "-"}% • rr_min: {rr?.rr_min ?? "-"}
          </div>
          <div>liq est: {typeof rr?.liq_price_est === "number" ? rr.liq_price_est : "-"}</div>
        </div>
        <div>
          <div className="text-zinc-500">Profil</div>
          <div>{profileLabel}</div>
          <div className="text-xs text-zinc-500/80">TTL: {ttlText}{tpPctText ? ` • TP ${tpPctText}%` : ""}</div>
        </div>
        <div>
          <div className="text-zinc-500">Entries</div>
          <div>{overlay?.entries?.map((v) => fmt(v)).join(" · ") || "-"}</div>
        </div>
        <div>
          <div className="text-zinc-500">SL</div>
          <div className="text-rose-500">{slOverlay ? fmt(slOverlay) : "-"}</div>
        </div>
        <div className="md:col-span-2">
          <div className="text-zinc-500">TP Ladder</div>
          <div className="text-emerald-600">{tpOverlay.length > 0 ? tpOverlay.map((v) => fmt(v)).join(" → ") : "-"}</div>
        </div>
      </div>
      <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
        <div>
          <div className="text-zinc-500">Funding</div>
          <div className={fundingColor}>now: {sig?.funding?.now ?? "-"} • next: {sig?.funding?.next ?? "-"}</div>
          <div>time: {sig?.funding?.time ?? "-"}</div>
        </div>
        <div>
          <div className="text-zinc-500">Open Interest</div>
          <div>now: {sig?.oi?.now ?? "-"}</div>
          <div>
            Δ1h: <span className={oiH1Color}>{isFinite(oiH1) ? oiH1.toFixed(0) : "-"}</span> • Δ4h: <span className={oiH4Color}>{isFinite(oiH4) ? oiH4.toFixed(0) : "-"}</span>
          </div>
        </div>
        <div>
          <div className="text-zinc-500">Basis</div>
          <div>
            now: {sig?.basis?.now ?? "-"} {basisBp !== null && <span className={basisColor}>({basisBp.toFixed(1)} bp)</span>}
          </div>
        </div>
        <div>
          <div className="text-zinc-500">LSR</div>
          <div>
            acc: {sig?.lsr?.accounts ?? "-"} • pos: {sig?.lsr?.positions ?? "-"}
          </div>
        </div>
        <div>
          <div className="text-zinc-500">Taker Δ</div>
          <div>
            m5: {sig?.taker_delta?.m5 ?? "-"} • m15: {sig?.taker_delta?.m15 ?? "-"} • h1: {sig?.taker_delta?.h1 ?? "-"}
          </div>
        </div>
        {overlay?.bybk && overlay.bybk.length > 0 && (
          <div className="md:col-span-2">
            <div className="text-zinc-500">Buy-back Zone</div>
            <div>{overlay.bybk.map((z) => `[${z.range.map((v) => v.toFixed(plan?.price_decimals ?? 4)).join("-")}] ${z.note ?? ""}`).join("; ")}</div>
          </div>
        )}
        {overlay?.bo && overlay.bo.length > 0 && (
          <div className="md:col-span-2">
            <div className="text-zinc-500">Break Out</div>
            <div>{overlay.bo.map((b) => `${b.direction === "below" ? "Di bawah" : "Di atas"} ${b.price?.toFixed(plan?.price_decimals ?? 4)} ${b.note ?? ""}`).join("; ")}</div>
          </div>
        )}
      </div>
    </section>
  )
}
