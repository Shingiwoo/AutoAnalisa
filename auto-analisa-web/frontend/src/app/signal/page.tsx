"use client"
import { useEffect, useMemo, useState } from "react"
import { api } from "../api"
import { useRouter } from "next/navigation"
import Spark from "../(components)/Spark"
import ContextBadges from "./ContextBadges"
import OutperformersTable from "./OutperformersTable"
import QuickAnalyzeButton from "./QuickAnalyzeButton"
import type { SignalRow } from "../../lib/types/signal"

type Mode = "fast" | "medium" | "swing"

// using shared type for clarity

export default function SignalBetaPage(){
  const router = useRouter()
  const [mode, setMode] = useState<Mode>("medium")
  const [symbols, setSymbols] = useState<string>("BTCUSDT,ETHUSDT,BNBUSDT")
  const [loading, setLoading] = useState(false)
  const [rows, setRows] = useState<SignalRow[]>([])
  const [autoRefresh, setAutoRefresh] = useState<boolean>(true)
  const [error, setError] = useState<string>("")
  const [useWatchlist, setUseWatchlist] = useState<boolean>(false)
  const [watchlist, setWatchlist] = useState<string[]>([])
  const [wlNew, setWlNew] = useState<string>("")
  const [modalOpen, setModalOpen] = useState(false)
  const [modalRow, setModalRow] = useState<SignalRow | null>(null)
  const [useContext, setUseContext] = useState<boolean>(true)
  const [contextCap, setContextCap] = useState<number>(0.20)
  const [qaResult, setQaResult] = useState<any|null>(null)
  const [qaSource, setQaSource] = useState<'watchlist'|'outperformers'>('watchlist')
  const [batchBusy, setBatchBusy] = useState(false)
  const [batchErr, setBatchErr] = useState('')
  const [batchOut, setBatchOut] = useState<any[]|null>(null)

  function fmt(n: any){
    const v = Number(n)
    if (Number.isNaN(v)) return '-'
    const d = v>=1000?2 : v>=100?3 : v>=1?4 : 6
    try{ return v.toFixed(d) }catch{ return String(v) }
  }

  async function fetchSignals(){
    setLoading(true)
    setError("")
    try {
      const params: any = { mode, symbols }
      if (!useContext) params.context = 'off'
      else params.boost_cap = contextCap
      const res = await api.get("/mtf-signals", { params })
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
  }, [mode, symbols, autoRefresh, useContext, contextCap])

  async function loadWatchlist(){
    try{
      const r = await api.get('/watchlist', { params: { trade_type: 'futures' } })
      const arr = Array.isArray(r?.data) ? r.data : []
      setWatchlist(arr)
      if (useWatchlist) setSymbols(arr.join(','))
    }catch{}
  }

  useEffect(()=>{ if(useWatchlist) loadWatchlist() }, [useWatchlist])

  return (<>
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
            <div className="flex items-center gap-3 text-xs text-zinc-300 mt-1">
              <label className="inline-flex items-center gap-2"><input type="checkbox" checked={useWatchlist} onChange={e=>{ setUseWatchlist(e.target.checked); if(!e.target.checked){/* keep manual symbols */} }} /> Gunakan Watchlist (Futures)</label>
              {useWatchlist && (
                <span className="opacity-75">{watchlist.length? `Watchlist: ${watchlist.join(', ')}` : 'memuat…'}</span>
              )}
            </div>
            {useWatchlist && (
              <div className="flex items-center gap-2 mt-1">
                <input value={wlNew} onChange={e=>setWlNew(e.target.value.toUpperCase())} placeholder="Tambah symbol" className="min-w-[160px] rounded bg-transparent px-2 py-1.5 ring-1 ring-inset ring-white/10" />
                <button className="rounded px-2.5 py-1.5 bg-zinc-800 text-white hover:bg-zinc-700" onClick={async()=>{
                  if(!wlNew) return
                  try{ await api.post('/watchlist/add', null, { params: { symbol: wlNew, trade_type: 'futures' } }); setWlNew(''); loadWatchlist() }catch{}
                }}>Tambah</button>
                {watchlist.map(sym=> (
                  <button key={sym} className="text-xs text-rose-300 hover:text-rose-200" onClick={async()=>{ try{ await api.delete(`/watchlist/${sym}`, { params:{ trade_type:'futures' } }); loadWatchlist() }catch{} }}>hapus {sym}</button>
                ))}
              </div>
            )}
            {/* Controls moved below watchlist for cleaner layout */}
            <div className="mt-3 flex flex-wrap items-center gap-3 text-sm text-zinc-300">
              <button onClick={fetchSignals} disabled={loading} className="rounded px-3 py-2 bg-cyan-600 hover:bg-cyan-500 disabled:opacity-50">{loading?"Memuat...":"Refresh"}</button>
              <label className="inline-flex items-center gap-2">
                <input type="checkbox" checked={autoRefresh} onChange={e=>setAutoRefresh(e.target.checked)} />
                Auto refresh
              </label>
              <div className="inline-flex items-center gap-2">
                <span>Sumber</span>
                <label className="inline-flex items-center gap-1"><input type="radio" name="qa_src" checked={qaSource==='watchlist'} onChange={()=>setQaSource('watchlist')} /> Watchlist</label>
                <label className="inline-flex items-center gap-1"><input type="radio" name="qa_src" checked={qaSource==='outperformers'} onChange={()=>setQaSource('outperformers')} /> Outperformers</label>
              </div>
              <label className="inline-flex items-center gap-2">
                <input type="checkbox" checked={useContext} onChange={e=>setUseContext(e.target.checked)} />
                Use context
              </label>
              {useContext && (
                <div className="text-xs text-zinc-300 flex items-center gap-2">
                  <span>Context cap</span>
                  <input type="range" min={0} max={0.2} step={0.01} value={contextCap} onChange={e=>setContextCap(parseFloat(e.target.value))} />
                  <span>{contextCap.toFixed(2)}</span>
                </div>
              )}
            </div>
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
                      <div className="flex items-center gap-2">
                        <button className="text-cyan-300 hover:text-cyan-200" onClick={()=>{ setModalRow(r); setQaResult(null); setModalOpen(true) }}>Lihat</button>
                        <QuickAnalyzeButton symbol={r.symbol} mode={mode} tfMap={r.tf_map} useContext={useContext} onDone={(res)=>{ setModalRow(r); setModalOpen(true); setQaResult(res) }} />
                      </div>
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
        {qaSource==='outperformers' && (
          <>
            <OutperformersTable mode={mode} onSymbols={(syms)=>{ /* keep last fetched symbols in state for batch analyze */ setSymbols(syms.join(',')) }} />
            <div className="mt-3 flex items-center gap-2 text-sm">
              <button className="rounded px-3 py-1.5 bg-zinc-800 text-white hover:bg-zinc-700 disabled:opacity-50" disabled={batchBusy} onClick={async()=>{
                try{
                  setBatchBusy(true); setBatchErr(''); setBatchOut(null)
                  // fetch current outperformers, then analyze top list
                  const { data } = await api.get('/outperformers', { params: { mode, market: 'binanceusdm', limit: 10 } })
                  const arr = Array.isArray(data) ? data : (Array.isArray(data?.results) ? data.results : [])
                  const symList = (arr || []).map((r:any)=>r.symbol).slice(0, 10)
                  if(symList.length===0) throw new Error('no symbols')
                  const { data: sb } = await api.post('v2/snapshot/batch', symList, { params:{ mode } })
                  const sid = sb?.snapshot_id
                  if(!sid) throw new Error('snapshot gagal')
                  const { data: ab } = await api.post('v2/analyze_batch', null, { params:{ snapshot_id: sid, count: Math.min(symList.length, 10), format: 'rich' } })
                  setBatchOut(ab?.results||[])
                }catch(e:any){ setBatchErr('Analyze All gagal') }
                finally{ setBatchBusy(false) }
              }}>{batchBusy? 'Analyzing…' : 'Analyze All (Top list)'}</button>
              {batchErr && <span className="text-rose-300 text-xs">{batchErr}</span>}
            </div>
            {Array.isArray(batchOut) && batchOut.length>0 && (
              <div className="mt-3 rounded bg-zinc-900 p-3 text-xs text-zinc-100 max-h-80 overflow-auto">
                <pre>{JSON.stringify(batchOut, null, 2)}</pre>
              </div>
            )}
          </>
        )}
        <div className="mt-6 space-y-2 text-sm leading-6 text-zinc-300">
            <h3 className="font-semibold text-zinc-100">Cara menggunakan Signal (Beta)</h3>
            <ul className="list-disc ml-5">
              <li><b>Mode Fast/Medium/Swing</b> memakai kombinasi TF: Fast (15m/5m/1m), Medium (1h/15m/5m), Swing (1D/4h/15m) untuk <i>Trend/Pattern/Trigger</i>.</li>
              <li><b>BTC Bias</b> bersifat <i>strict gate</i>: jika arah sinyal berlawanan dengan bias BTC, hasil menjadi <b>NO_TRADE</b>.</li>
              <li><b>Total</b> adalah skor gabungan (-1..+1). <b>Strength</b> dipetakan dari |Total|: WEAK [0.20–0.35), MEDIUM [0.35–0.55), STRONG [0.55–0.75), EXTREME ≥0.75.</li>
              <li><b>Detail Trend/Pattern/Trigger</b>: setiap panel menampilkan sparkline <i>Supertrend line</i> pada TF terkait. Jika data tidak cukup/flat, sistem fallback ke harga <i>close</i>.</li>
              <li>Baru open posisi bila <b>side ≠ NO_TRADE</b> dan strength ≥ <b>MEDIUM</b>. Untuk scalping cepat, perhatikan <i>Trigger</i> flip (signal=±1).</li>
              <li>Keputusan dibuat pada <b>bar close</b> untuk menghindari repaint. Auto-refresh menyesuaikan TF terpendek.</li>
              <li><b>Context</b> (Funding, ALT×BTC, BTC.D, Price×OI) menambah/kurangi skor total (maks ±0.20) sebagai penguat penilaian.</li>
            </ul>
            <p className="opacity-80">Catatan: nilai indikator lain (EMA/RSI/MACD) ditampilkan di bawah sparkline. Parameter dapat diatur pada preset.</p>
          </div>
        </div>
      </div>
    {modalOpen && modalRow && (
      <div className="fixed inset-0 z-50">
        <div className="absolute inset-0 bg-black/70 backdrop-blur-sm" onClick={()=>{ setModalOpen(false); setModalRow(null) }} />
        <div className="absolute inset-0 flex items-center justify-center p-4">
          <div className="w-full max-w-5xl rounded-2xl bg-slate-950 text-white shadow-2xl ring-1 ring-white/10 overflow-hidden">
            <div className="px-4 py-3 border-b border-white/10 flex items-center justify-between">
              <h3 className="font-semibold flex items-center gap-2">
                <span>{modalRow.symbol} • {modalRow.mode.toUpperCase()}</span>
                <span className="text-xs px-2 py-0.5 rounded bg-zinc-800 text-zinc-200">
                  {modalRow.mode.toUpperCase()} • {modalRow.tf_map.trend}/{modalRow.tf_map.pattern}/{modalRow.tf_map.trigger}
                </span>
              </h3>
              <button onClick={()=>{ setModalOpen(false); setModalRow(null) }} className="text-zinc-300 hover:text-white">✕</button>
            </div>
            <div className="p-4 max-h-[80vh] overflow-auto text-sm text-zinc-300">
              <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                <div>
                  <div className="font-semibold text-zinc-200 mb-1">Trend ({modalRow.tf_map.trend})</div>
                  <Spark symbol={modalRow.symbol} tf={modalRow.tf_map.trend} mode={modalRow.mode} kind="st_line" />
                  <div className="mt-2">trend: {modalRow?.st?.trend?.trend} • signal: {modalRow?.st?.trend?.signal}</div>
                  <div>ST: {modalRow?.indicators?.trend?.ST}, EMA50: {modalRow?.indicators?.trend?.EMA50}, RSI: {modalRow?.indicators?.trend?.RSI}, MACD: {modalRow?.indicators?.trend?.MACD}</div>
                </div>
                <div>
                  <div className="font-semibold text-zinc-200 mb-1">Pattern ({modalRow.tf_map.pattern})</div>
                  <Spark symbol={modalRow.symbol} tf={modalRow.tf_map.pattern} mode={modalRow.mode} kind="st_line" />
                  <div className="mt-2">trend: {modalRow?.st?.pattern?.trend} • signal: {modalRow?.st?.pattern?.signal}</div>
                  <div>ST: {modalRow?.indicators?.pattern?.ST}, RSI: {modalRow?.indicators?.pattern?.RSI}, MACD: {modalRow?.indicators?.pattern?.MACD}, EMA50: {modalRow?.indicators?.pattern?.EMA50}</div>
                </div>
                <div>
                  <div className="font-semibold text-zinc-200 mb-1">Trigger ({modalRow.tf_map.trigger})</div>
                  <Spark symbol={modalRow.symbol} tf={modalRow.tf_map.trigger} mode={modalRow.mode} kind="st_line" />
                  <div className="mt-2">trend: {modalRow?.st?.trigger?.trend} • signal: {modalRow?.st?.trigger?.signal}</div>
                  <div>ST: {modalRow?.indicators?.trigger?.ST}, EMA50: {modalRow?.indicators?.trigger?.EMA50}, RSI: {modalRow?.indicators?.trigger?.RSI}, MACD: {modalRow?.indicators?.trigger?.MACD}</div>
                </div>
              </div>
              {/* Context moved into modal */}
              <div className="mt-4">
                <div className="font-semibold text-zinc-200 mb-1">Context</div>
                {!useContext ? (
                  <div className="text-xs">
                    <span className="inline-flex items-center px-2 py-0.5 rounded bg-zinc-700 text-white">Context OFF</span>
                    <div className="mt-2 opacity-80">Context boost dinonaktifkan. Total sama dengan hasil MTF.</div>
                  </div>
                ) : (
                  <ContextBadges ctx={(modalRow as any).context} />
                )}
                <div className="mt-2 text-xs opacity-80">
                  {typeof (modalRow as any)?.total_score_context === 'number' && (
                    <div>Total {useContext ? '(with context)' : '(no context)'}: {(modalRow as any).total_score_context?.toFixed?.(2)}</div>
                  )}
                  {typeof (modalRow as any)?.risk_mult === 'number' && useContext && (
                    <div>Risk multiplier (suggestion): {(modalRow as any).risk_mult}</div>
                  )}
                </div>
              </div>
              {qaResult && (
                <div className="mt-6">
                  <div className="font-semibold text-zinc-200 mb-1 flex items-center justify-between">
                    <span>Quick Analyze</span>
                    <button className="rounded px-2 py-1 bg-zinc-800 text-white text-xs hover:bg-zinc-700" onClick={()=>{
                      const tf = (mode==='fast'?'15m': mode==='medium'?'1h':'1d')
                      const prof = (mode==='swing' ? 'swing' : 'scalp')
                      router.push(`/v2-analyze?symbol=${encodeURIComponent(modalRow?.symbol||'')}&timeframe=${tf}&profile=${prof}`)
                    }}>Open in Analyze v2</button>
                  </div>
                  {qaResult?.btc_alignment === 'conflict' && (
                    <div className="rounded border border-rose-500/30 bg-rose-500/10 text-rose-200 p-2 text-xs mb-2">Konflik dengan Bias BTC</div>
                  )}
                  {/* Summary */}
                  {(() => {
                    const isRich = qaResult && qaResult.strategi && qaResult.metadata
                    const biasStr = isRich ? (qaResult?.rangkuman?.bias_dominan?.toString()?.toLowerCase?.()||'') : (qaResult?.plan?.bias||'')
                    const bcls = biasStr==='long'? 'bg-emerald-600' : biasStr==='short'? 'bg-rose-600' : 'bg-zinc-600'
                    const entries = isRich ? (qaResult?.strategi?.scalping?.entry_zone||[]) : ((qaResult?.plan?.entries||[]).map((e:any)=>e?.price))
                    const tps = isRich ? (qaResult?.strategi?.scalping?.take_profit||[]) : ((qaResult?.plan?.take_profits||[]).map((t:any)=>t?.price))
                    const sl = isRich ? qaResult?.strategi?.scalping?.stop_loss : qaResult?.plan?.stop_loss?.price
                    const tfShow = isRich ? (modalRow?.tf_map?.trend||'') : (qaResult?.tf_map?.trend || modalRow?.tf_map?.trend || String(qaResult?.timeframe||''))
                    return (
                      <div className="rounded-xl ring-1 ring-white/10 bg-black/20 p-3 text-xs mb-2">
                        <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
                          <div>
                            <div><span className="opacity-70">Timeframe:</span> {tfShow}</div>
                            <div className="flex items-center gap-2"><span className="opacity-70">Bias:</span>
                              <span className={`px-1.5 py-0.5 rounded text-white ${bcls}`}>{biasStr? biasStr.toUpperCase():'-'}</span>
                            </div>
                            <div><span className="opacity-70">RR min:</span> {typeof qaResult?.metrics?.rr_min==='number'? qaResult.metrics.rr_min.toFixed(2): '-'}</div>
                            <div><span className="opacity-70">TTL (min):</span> {qaResult?.plan?.ttl_min ?? qaResult?.ttl_min ?? '-'}</div>
                          </div>
                          <div>
                            <div className="opacity-70">Entries:</div>
                            <div>
                              {(entries||[]).slice(0,2).map((p:any,idx:number)=> (
                                <span key={idx} className="mr-2">E{idx+1} @ {fmt(p)}</span>
                              ))}
                            </div>
                            <div className="opacity-70">TP:</div>
                            <div>
                              {(tps||[]).slice(0,2).map((p:any,idx:number)=> (
                                <span key={idx} className="mr-2">TP{idx+1} @ {fmt(p)}</span>
                              ))}
                            </div>
                            <div><span className="opacity-70">SL:</span> {fmt(sl)}</div>
                          </div>
                        </div>
                      </div>
                    )
                  })()}
                  <div className="rounded bg-zinc-900 text-zinc-100 p-3 text-xs overflow-auto max-h-64">
                    <pre>{JSON.stringify(qaResult, null, 2)}</pre>
                  </div>
                </div>
              )}
            </div>
            <div className="px-4 py-3 border-t border-white/10 flex items-center justify-end bg-black/30">
              <button onClick={()=>{ setModalOpen(false); setModalRow(null) }} className="rounded px-3 py-1.5 bg-zinc-800 text-white">Tutup</button>
            </div>
          </div>
        </div>
      </div>
    )}
  </>)
}
