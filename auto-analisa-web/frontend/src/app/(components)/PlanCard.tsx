"use client"
import { useEffect, useMemo, useState } from 'react'
import { api } from '../../app/api'
import ChartOHLCV from './ChartOHLCV'
import LLMReport from './LLMReport'
import Spot2View from './Spot2View'

export default function PlanCard({plan, onUpdate, llmEnabled, llmRemaining, onAfterVerify}:{plan:any,onUpdate:()=>void, llmEnabled?:boolean, llmRemaining?:number, onAfterVerify?:()=>void}){
  const p=plan.payload
  // Spot | Futures mode (persist per symbol)
  const [mode,setMode]=useState<'spot'|'futures'>(()=>{
    try{ return (localStorage.getItem(`aa_mode_${plan.symbol}`)||'spot') as any }catch{ return 'spot' }
  })
  // Jika plan disimpan sebagai trade_type=futures, paksa mode futures & sembunyikan toggle
  const forcedFutures = String((plan as any)?.trade_type||'spot').toLowerCase()==='futures'
  useEffect(()=>{ if(forcedFutures) setMode('futures') },[forcedFutures])
  useEffect(()=>{ try{ localStorage.setItem(`aa_mode_${plan.symbol}`, mode) }catch{} },[mode, plan.symbol])
  const [fut,setFut]=useState<any|null>(null)
  const [futErr,setFutErr]=useState<string>('')
  // Single tab controls both chart timeframe and analysis content
  const [tab,setTab]=useState<'tren'|'5m'|'15m'|'1h'|'4h'>(()=> 'tren')
  const [tf,setTf]=useState<'5m'|'15m'|'1h'|'4h'>(()=> '15m')
  const [ohlcv,setOhlcv]=useState<any[]>([])
  const [loading,setLoading]=useState(false)
  const [verifying,setVerifying]=useState(false)
  const [verification,setVerification]=useState<any|null>(null)
  const [expanded,setExpanded]=useState(false)
  const [ghost,setGhost]=useState<any|null>(null)
  const [err,setErr]=useState<{code?:string,message?:string,retry?:string}|null>(null)
  const [prevOpen,setPrevOpen]=useState(false)
  const [prevPlan,setPrevPlan]=useState<any|null>(null)
  const [prevList,setPrevList]=useState<any[]|null>(null)
  const futUpdatedRecently = useMemo(()=>{
    try{
      if(mode!=='futures') return false
      const ts = fut?.futures_signals?.created_at ? new Date(fut.futures_signals.created_at).getTime() : NaN
      if(!isFinite(ts)) return false
      const mins = (Date.now() - ts)/60000
      return mins < 20
    }catch{ return false }
  },[mode, fut?.futures_signals?.created_at])
  const createdWIB = useMemo(()=>{
    try{ return new Date(plan.created_at).toLocaleString('id-ID', { timeZone: 'Asia/Jakarta' }) + ' WIB' }catch{ return new Date(plan.created_at).toLocaleString('id-ID') }
  },[plan.created_at])
  // Decimals for Spot formatting (from spot2.metrics or fallback)
  const decimals = useMemo(()=>{
    try{
      const d = p?.spot2?.metrics?.price_decimals ?? p?.price_decimals
      return (typeof d === 'number') ? d : 5
    }catch{ return 5 }
  }, [p?.spot2?.metrics?.price_decimals, p?.price_decimals])
  const precision = useMemo(()=>{
    const base = (p?.entries && p.entries[0]) || (p?.tp && p.tp[0]) || (typeof p?.invalid==='number' ? p.invalid : 1)
    const last = typeof base === 'number' ? base : 1
    return last >= 1000 ? 2 : last >= 100 ? 2 : last >= 10 ? 3 : last >= 1 ? 4 : last >= 0.1 ? 5 : 6
  },[p])
  const fmt = (n:number) => typeof n==='number' ? n.toFixed(precision) : n
  const mtfData = useMemo(()=> (p?.mtf_summary || p?.spot2?.mtf_summary || {}), [p])
  // Sync chart timeframe with tab selection
  useEffect(()=>{
    const t = (tab==='tren'? '15m' : tab) as '5m'|'15m'|'1h'|'4h'
    setTf(t)
  },[tab])
  useEffect(()=>{ (async()=>{
    try{ setLoading(true); const {data}=await api.get('ohlcv', { params:{ symbol:plan.symbol, tf, limit:200, market: (mode==='futures'?'futures':'spot') } }); setOhlcv(data) }catch{} finally{ setLoading(false) }
  })() },[tf, plan.symbol, mode])
  // Load futures plan on demand
  useEffect(()=>{ (async()=>{
    if(mode!=='futures') return
    try{ setFutErr(''); const {data}=await api.get(`analyses/${plan.symbol}/futures`); setFut(data) }
    catch(e:any){ setFut(null); setFutErr(e?.response?.data?.detail||'Futures tidak tersedia') }
  })() },[mode, plan.symbol])
  const invalids = useMemo(()=>{
    const s2 = p?.spot2 || {}
    const invs = s2?.invalids || {}
    return {
      m5:  typeof invs.m5 === 'number'  ? invs.m5  : (typeof p?.invalid_tactical_5m==='number'? p.invalid_tactical_5m : undefined),
      m15: typeof invs.m15 === 'number' ? invs.m15 : (typeof p?.invalid_soft_15m==='number'? p.invalid_soft_15m : undefined),
      h1:  typeof invs.h1 === 'number'  ? invs.h1  : (typeof p?.invalid_hard_1h==='number'? p.invalid_hard_1h : (typeof p?.invalid==='number'? p.invalid : undefined)),
      h4:  typeof invs.h4 === 'number'  ? invs.h4  : (typeof p?.invalid_struct_4h==='number'? p.invalid_struct_4h : undefined),
    }
  },[p])
  const lastClose = (ohlcv && ohlcv.length>0) ? ohlcv[ohlcv.length-1].c : undefined
  const breach = useMemo(()=>{
    if(typeof lastClose !== 'number') return null
    const invH1 = mode==='futures' ? (typeof fut?.invalids?.hard_1h==='number'? fut.invalids.hard_1h : invalids.h1) : invalids.h1
    const invM15 = mode==='futures' ? (typeof fut?.invalids?.soft_15m==='number'? fut.invalids.soft_15m : invalids.m15) : invalids.m15
    if(typeof invH1 === 'number' && lastClose <= invH1){ return { type:'hard', text:'Invalidated — rencana baru dibuat (v+1)' } }
    if(typeof invM15 === 'number' && lastClose <= invM15){ return { type:'soft', text:'Rawan — cek ulang 15m' } }
    return null
  },[lastClose, invalids, fut, mode])
  const srExtra = useSRExtra(tab, ohlcv)
  const computeSRCombined = () => ([...(p.support||[]), ...(p.resistance||[]), ...srExtra])
  return (
    <div className="rounded-2xl ring-1 ring-zinc-200 dark:ring-white/10 bg-white dark:bg-zinc-900 shadow-sm p-4 md:p-6 space-y-4 text-zinc-900 dark:text-zinc-100">
      <div className="flex items-center justify-between">
        <div className="text-lg font-semibold flex items-center gap-2">
          <span>{plan.symbol} • v{plan.version}</span>
          <ScoreBadge score={p.score} />
          {p?.notice && <span className="px-2 py-0.5 rounded bg-amber-600 text-white text-xs" title={p.notice}>Updated</span>}
          {futUpdatedRecently && <span className="px-2 py-0.5 rounded bg-emerald-600 text-white text-xs" title="Sinyal Futures baru diperbarui">Updated</span>}
        </div>
      </div>
      {/* Spot | Futures toggle (disembunyikan jika analisa trade_type=futures) */}
      {!forcedFutures && (
        <div className="flex items-center gap-2 text-sm" role="tablist" aria-label="Mode Tabs">
          {(['spot','futures'] as const).map(m=> (
            <button key={m} role="tab" aria-selected={mode===m} onClick={()=> setMode(m)}
              className={`px-3 py-1.5 rounded-md transition ${mode===m? 'bg-cyan-600 text-white':'bg-zinc-800 text-white/80 hover:bg-zinc-700'} `}>
              {m==='spot'? 'Spot':'Futures'}
            </button>
          ))}
          {mode==='futures' && futErr && <span className="text-xs text-rose-400">{futErr}</span>}
        </div>
      )}

      {mode==='futures' && (
        <div className="rounded-xl ring-1 ring-zinc-200 dark:ring-white/10 bg-white/5 p-3 text-sm">
          {fut ? (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              <div>
                <div className="text-zinc-500">Leverage & Margin</div>
                <div>isolated x={fut?.leverage_suggested?.x ?? '-'}</div>
              </div>
              <div>
                <div className="text-zinc-500">Risk</div>
                <div>risk/trade: {fut?.risk?.risk_per_trade_pct ?? '-'}% • rr_min: {fut?.risk?.rr_min||'-'}</div>
              </div>
              <div className="md:col-span-2 text-xs text-zinc-500">Catatan: modul Futures (beta skeleton).</div>
            </div>
          ) : (
            <div className="text-zinc-500">{futErr||'Memuat Futures…'}</div>
          )}
        </div>
      )}

      {/* Unified Tabs: controls chart timeframe & content */}
      <div className="flex items-center gap-2 text-sm" role="tablist" aria-label="Analisa Tabs">
        {(['tren','5m','15m','1h','4h'] as const).map(t=> (
          <button key={t} role="tab" aria-selected={tab===t} onClick={()=>setTab(t)}
            className={`px-2.5 py-1 rounded-md transition ${tab===t? 'bg-cyan-600 text-white':'bg-white text-zinc-900 hover:bg-zinc-100 dark:bg-zinc-800 dark:text-white/90'} `}>
            {t==='tren'? 'Tren Utama' : t}
          </button>
        ))}
        <div className="text-xs text-zinc-500" title={new Date(plan.created_at).toISOString()}>{createdWIB}</div>
      </div>

      {/* Notice banner per coin when invalidated & refreshed */}
      {p?.notice && (
        <div className="p-2 bg-amber-50 border border-amber-200 rounded text-amber-800 text-sm">{p.notice}</div>
      )}
      {/* Runtime breach notification based on latest price */}
      {breach && (
        <div className={`p-2 rounded text-sm ${breach.type==='hard'?'bg-rose-50 border border-rose-200 text-rose-700':'bg-amber-50 border border-amber-200 text-amber-800'}`}>{breach.text}</div>
      )}

      <div className="rounded-none overflow-hidden ring-1 ring-zinc-200 dark:ring-white/10 bg-white dark:bg-zinc-950 relative">
        <div className="aspect-[16/9] md:aspect-[21/9]">
          <ChartOHLCV
            key={`${plan.symbol}-${tf}-${expanded?'x':''}`}
            className="h-full"
            data={ohlcv}
            overlays={{
              sr: computeSRCombined(),
              tp: p.tp||[],
              invalid: mode==='futures' ? ({
                m5: typeof fut?.invalids?.tactical_5m==='number'? fut.invalids.tactical_5m : invalids.m5,
                m15: typeof fut?.invalids?.soft_15m==='number'? fut.invalids.soft_15m : invalids.m15,
                h1: typeof fut?.invalids?.hard_1h==='number'? fut.invalids.hard_1h : invalids.h1,
                h4: typeof fut?.invalids?.struct_4h==='number'? fut.invalids.struct_4h : invalids.h4,
              } as any) : invalids,
              entries: mode==='futures' ? (fut?.entries||[]).map((e:any)=> Array.isArray(e.range)? e.range[0]: undefined).filter((x:any)=> typeof x==='number') : (p.entries||[]),
              fvg: p.fvg||[],
              zones: p.sd_zones||[],
              ghost: ghost||undefined,
              liq: mode==='futures' && typeof fut?.risk?.liq_price_est==='number' ? fut.risk.liq_price_est : undefined,
              funding: mode==='futures' && fut?.futures_signals?.funding?.time ? [{ timeMs: Date.parse(fut.futures_signals.funding.time), windowMin: (fut?.risk?.funding_window_min||10) }] : undefined,
            }}
          />
        </div>
        {loading && (
          <div className="absolute inset-0 flex items-center justify-center bg-black/5 dark:bg-white/5">
            <div className="text-xs text-zinc-700 dark:text-zinc-200">Memuat {tf}…</div>
          </div>
        )}
        <button onClick={()=>setExpanded(true)} className="absolute top-2 right-2 text-xs px-2 py-1 rounded bg-zinc-900/80 text-white hover:bg-zinc-900">Perbesar</button>
      </div>

      {/* Funding soon banner (Futures) */}
      {mode==='futures' && (()=>{
        try{
          const thr = Number(fut?.risk?.funding_threshold_bp)||3
          const rate = Math.abs(Number(fut?.futures_signals?.funding?.now)||0)*10000 // convert to bp if %
          const t = fut?.futures_signals?.funding?.time ? Date.parse(fut.futures_signals.funding.time) : null
          const mins = t ? Math.abs((t - Date.now())/60000) : null
          const enabled = (fut?.risk?.funding_alert_enabled!==false)
          const win = Number(fut?.risk?.funding_alert_window_min ?? fut?.risk?.funding_window_min ?? 30)
          if(enabled && t && mins!==null && mins < win && rate > thr){
            return <div className="p-2 rounded text-sm bg-blue-50 border border-blue-200 text-blue-800">Funding soon — pertimbangkan hindari entry ±{Math.round(Number(fut?.risk?.funding_window_min)||10)} menit</div>
          }
        }catch{}
        return null
      })()}

      {expanded && (
        <div className="fixed inset-0 z-50 bg-black/70 flex items-center justify-center p-4" onClick={()=>setExpanded(false)}>
          <div className="w-full max-w-7xl h-[80vh] bg-zinc-950 ring-1 ring-white/10 rounded-none relative" onClick={e=>e.stopPropagation()}>
            <button onClick={()=>setExpanded(false)} className="absolute top-3 right-3 px-2 py-1 rounded bg-zinc-800 text-white text-sm">Tutup</button>
            <div className="absolute inset-0">
              <ChartOHLCV
                key={`${plan.symbol}-modal-${tf}`}
                className="w-full h-full"
                data={ohlcv}
                overlays={{
                  sr: computeSRCombined(),
                  tp:p.tp||[],
                  invalid: mode==='futures' ? ({
                    m5: typeof fut?.invalids?.tactical_5m==='number'? fut.invalids.tactical_5m : invalids.m5,
                    m15: typeof fut?.invalids?.soft_15m==='number'? fut.invalids.soft_15m : invalids.m15,
                    h1: typeof fut?.invalids?.hard_1h==='number'? fut.invalids.hard_1h : invalids.h1,
                    h4: typeof fut?.invalids?.struct_4h==='number'? fut.invalids.struct_4h : invalids.h4,
                  } as any) : invalids,
                  entries: mode==='futures' ? (fut?.entries||[]).map((e:any)=> Array.isArray(e.range)? e.range[0]: undefined).filter((x:any)=> typeof x==='number') : (p.entries||[]),
                  fvg: p.fvg||[],
                  zones: p.sd_zones||[],
                  ghost: ghost||undefined,
                  liq: mode==='futures' && typeof fut?.risk?.liq_price_est==='number' ? fut.risk.liq_price_est : undefined,
                  funding: mode==='futures' && fut?.futures_signals?.funding?.time ? [{ timeMs: Date.parse(fut.futures_signals.funding.time), windowMin: (fut?.risk?.funding_window_min||10) }] : undefined,
                }}
              />
            </div>
          </div>
        </div>
      )}

      {mode==='futures' ? (
        <>
          <FuturesSummary fut={fut} />
          {/* LLM Report khusus Futures */}
          <LLMReport analysisId={plan.id} verification={verification} onApplied={()=> onUpdate()} onPreview={setGhost} kind='futures' />
        </>
      ) : (
        (tab==='tren' ? (
          <div className="space-y-2">
            <div className="flex flex-wrap gap-2 text-xs">
              {typeof invalids.m5==='number' && <span className="px-2 py-0.5 rounded bg-amber-600 text-white" title="Invalid tactical 5m">5m: {fmt(invalids.m5)}</span>}
              {typeof invalids.m15==='number' && <span className="px-2 py-0.5 rounded bg-yellow-600 text-white" title="Invalid soft 15m">15m: {fmt(invalids.m15)}</span>}
              {typeof invalids.h1==='number' && <span className="px-2 py-0.5 rounded bg-rose-600 text-white" title="Invalid hard 1h">1h: {fmt(invalids.h1)}</span>}
              {typeof invalids.h4==='number' && <span className="px-2 py-0.5 rounded bg-violet-600 text-white" title="Invalid struct 4h">4h: {fmt(invalids.h4)}</span>}
            </div>
            <Spot2View spot2={p.spot2} decimals={decimals} fmt={fmt} />
          </div>
        ) : (
          <MTFDesc mtf={mtfData || {}} tf={tab} />
        ))
      )}

      {/* Previous version toggle */}
      <div className="flex items-center gap-2">
        <button className="px-2.5 py-1.5 rounded bg-zinc-800 text-white text-xs hover:bg-zinc-700" onClick={async()=>{
          const next = !prevOpen
          setPrevOpen(next)
          if(next && !prevPlan){
            try{
              const { data } = await api.get('analyses', { params:{ status:'archived', trade_type: forcedFutures? 'futures':'spot' } })
              const same = (data||[]).filter((x:any)=> x.symbol===plan.symbol)
              setPrevList(same)
              const prev = same.find((x:any)=> new Date(x.created_at) < new Date(plan.created_at)) || same[0]
              setPrevPlan(prev||null)
            }catch{}
          }
        }}>{prevOpen? 'Sembunyikan versi sebelumnya':'Tampilkan versi sebelumnya'}</button>
      </div>
      {prevOpen && prevList && prevList.length>0 && (
        <div className="rounded-xl ring-1 ring-amber-500/20 bg-amber-500/5 p-3 space-y-2">
          <div className="text-xs text-amber-400">Pilih versi:</div>
          <div className="flex flex-wrap gap-2 text-xs">
            {prevList.map((it:any)=> (
              <button key={it.id} className={`px-2 py-1 rounded ${prevPlan?.id===it.id? 'bg-amber-600 text-white':'bg-zinc-800 text-white/90'}`} onClick={()=> setPrevPlan(it)}>
                v{it.version} • {new Date(it.created_at).toLocaleString('id-ID',{ timeZone:'Asia/Jakarta'})}
              </button>
            ))}
          </div>
        </div>
      )}
      {prevOpen && prevPlan?.payload && mode!=='futures' && (
        <div className="rounded-xl ring-1 ring-amber-500/20 bg-amber-500/5 p-3">
          <div className="text-xs text-amber-400 mb-1">Versi sebelumnya • {prevPlan?.created_at ? new Date(prevPlan.created_at).toLocaleString('id-ID', { timeZone: 'Asia/Jakarta' }) : ''} WIB</div>
          <Spot2View spot2={prevPlan.payload.spot2 || prevPlan.payload} decimals={prevPlan?.payload?.spot2?.metrics?.price_decimals || decimals} fmt={fmt} />
        </div>
      )}
      {prevOpen && mode==='futures' && p?.futures && (
        <div className="rounded-xl ring-1 ring-amber-500/20 bg-amber-500/5 p-3">
          <div className="text-xs text-amber-400 mb-1">Versi Futures (diterapkan)</div>
          <FuturesSummary fut={p.futures} />
        </div>
      )}

      {/* LLM Verification (legacy diff) */}
      {mode==='spot' && <LLMVerifyBlock plan={p} verification={verification || p?.llm_verification} fmt={fmt} />}
      {/* LLM SPOT II report */}
      {mode==='spot' && <LLMReport analysisId={plan.id} verification={verification} onApplied={()=> onUpdate()} onPreview={setGhost} kind='spot' />}

      <Glossary />
      <div className="flex gap-2">
        <button onClick={onUpdate} className="px-3 py-2 rounded-md bg-zinc-900 text-white hover:bg-zinc-800">Update</button>
        {/* Spot verify */}
        <button disabled={mode!=='spot' || verifying || !llmEnabled || (typeof llmRemaining==='number' && llmRemaining<=0)} title={mode!=='spot' ? 'Verifikasi hanya untuk Spot' : (!llmEnabled? 'LLM nonaktif (limit/budget)':'Tanya GPT')}
          onClick={async()=>{
          try{
            setVerifying(true)
            const {data} = await api.post(`analyses/${plan.id}/verify`)
            setVerification(data.verification)
          }catch(e:any){
            const resp = e?.response
            const data = resp?.data
            const det = data?.detail
            if(det && typeof det==='object'){
              setErr({ code: det.error_code, message: det.message, retry: det.retry_hint })
            }else if(typeof det === 'string'){
              setErr({ message: det })
            }else if(typeof data?.message === 'string'){
              setErr({ message: data.message })
            }else if(typeof e?.message === 'string'){
              setErr({ message: e.message })
            }else{
              setErr({ message: 'Verifikasi gagal' })
            }
          }finally{ setVerifying(false); onAfterVerify?.() }
        }} className="px-3 py-2 rounded-md bg-cyan-600 text-white hover:bg-cyan-500 disabled:opacity-50">{verifying?'Memverifikasi…':'Tanya GPT'}</button>
        {/* Futures verify */}
        <button disabled={mode!=='futures' || verifying || !llmEnabled || (typeof llmRemaining==='number' && llmRemaining<=0)} title={mode!=='futures' ? 'Verifikasi Futures nonaktif' : (!llmEnabled? 'LLM nonaktif (limit/budget)':'Tanya GPT (Futures)')}
          onClick={async()=>{
          try{
            setVerifying(true)
            const {data} = await api.post(`analyses/${plan.id}/futures/verify`)
            setVerification(data.verification)
          }catch(e:any){
            const resp = e?.response
            const data = resp?.data
            const det = data?.detail
            if(det && typeof det==='object'){
              setErr({ code: det.error_code, message: det.message, retry: det.retry_hint })
            }else if(typeof det === 'string'){
              setErr({ message: det })
            }else if(typeof data?.message === 'string'){
              setErr({ message: data.message })
            }else if(typeof e?.message === 'string'){
              setErr({ message: e.message })
            }else{
              setErr({ message: 'Verifikasi Futures gagal' })
            }
          }finally{ setVerifying(false); onAfterVerify?.() }
        }} className="px-3 py-2 rounded-md bg-indigo-600 text-white hover:bg-indigo-500 disabled:opacity-50">{verifying?'Memverifikasi…':'Tanya GPT (Futures)'}</button>
      </div>

      {err && (
        <div className="fixed inset-0 z-50 bg-black/60 flex items-center justify-center p-4" onClick={()=>setErr(null)}>
          <div className="max-w-md w-full rounded-xl bg-zinc-900 text-white ring-1 ring-white/10 p-4 space-y-2" onClick={(e)=>e.stopPropagation()}>
            <div className="text-sm font-semibold">Verifikasi Gagal</div>
            {err.code && <div className="text-xs opacity-70">Kode: {err.code}</div>}
            <div className="text-sm">{err.message||'Gagal memverifikasi rencana.'}</div>
            {err.retry && <div className="text-xs opacity-70">Saran: {err.retry}</div>}
            <div className="flex items-center gap-2 pt-1">
              <button className="px-3 py-1.5 rounded bg-zinc-800 hover:bg-zinc-700 text-sm" onClick={()=>{
                const text = JSON.stringify(err)
                navigator.clipboard?.writeText(text)
              }}>Salin Log</button>
              <button className="px-3 py-1.5 rounded bg-cyan-600 hover:bg-cyan-500 text-sm" onClick={()=> setErr(null)}>Tutup</button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

function label(score:number){
  if(score>35) return {text:'High', color:'bg-green-600'}
  if(score>=25) return {text:'Medium', color:'bg-yellow-500'}
  return {text:'Low', color:'bg-red-600'}
}

function ScoreBadge({score}:{score:number}){
  const s=label(score)
  return <span className={`px-2 py-0.5 rounded text-white text-xs ${s.color}`}>{s.text} • {score}</span>
}

function DiffList({ label, oldVals, newVals, colorUp, colorDown, fmt }:{ label:string, oldVals:any[], newVals:any[]|undefined, colorUp:string, colorDown:string, fmt:(n:number)=>string|number }){
  if(!newVals || newVals.length===0) return null
  const oldSet = new Set(oldVals||[])
  const added = (newVals||[]).filter(x=> !oldSet.has(x))
  const kept = (newVals||[]).filter(x=> oldSet.has(x))
  return (
    <div>
      <dt className="text-zinc-500">{label} (LLM)</dt>
      <dd className="text-sm">
        {kept.length>0 && <span className="text-zinc-600 dark:text-zinc-300">{kept.map(fmt as any).join(' · ')}</span>}
        {added.length>0 && <span className={`ml-2 ${colorUp}`}>{added.map(fmt as any).join(' · ')}</span>}
      </dd>
    </div>
  )
}

function LLMVerifyBlock({ plan, verification, fmt }:{ plan:any, verification:any, fmt:(n:number)=>string|number }){
  if(!verification) return null
  const sug = verification.suggestions || {}
  const verdict = (verification.verdict||'').toLowerCase()
  const badgeColor = verdict==='confirm' ? 'bg-green-600' : verdict==='tweak' ? 'bg-amber-600' : verdict==='warning' ? 'bg-orange-600' : 'bg-red-600'
  return (
    <div className="rounded-xl ring-1 ring-cyan-500/20 bg-cyan-500/5 p-3 space-y-2">
      <div className="flex items-center gap-2 text-sm">
        <span className={`px-2 py-0.5 rounded text-white text-xs ${badgeColor}`}>{verdict || 'verify'}</span>
        <span className="font-medium">LLM Verifikasi</span>
        <span className="text-xs opacity-70">{verification?.created_at ? new Date(verification.created_at).toLocaleString('id-ID', { timeZone: 'Asia/Jakarta' }) : ''}</span>
      </div>
      {verification.summary && <div className="text-sm italic text-zinc-600 dark:text-zinc-300">{verification.summary}</div>}
      <dl className="grid grid-cols-1 sm:grid-cols-2 gap-3">
        <DiffList label="Entry" oldVals={plan.entries||[]} newVals={sug.entries} colorUp="text-emerald-400" colorDown="text-rose-400" fmt={fmt} />
        <DiffList label="TP" oldVals={plan.tp||[]} newVals={sug.tp} colorUp="text-emerald-400" colorDown="text-rose-400" fmt={fmt} />
        {typeof sug.invalid!== 'undefined' && (
          <div>
            <dt className="text-zinc-500">Invalid (LLM)</dt>
            <dd className={`text-sm ${sug.invalid>plan.invalid?'text-rose-400':'text-emerald-400'}`}>{fmt(sug.invalid)}</dd>
          </div>
        )}
      </dl>
    </div>
  )
}

function Glossary(){
  return (
    <details className="mt-2 text-sm text-zinc-900 dark:text-zinc-100">
      <summary className="cursor-pointer underline">Glosarium</summary>
      <ul className="list-disc pl-5 mt-1 space-y-1">
        <li><b>TP</b>: Take Profit (harga target jual sebagian/seluruhnya)</li>
        <li><b>PB</b>: Pullback Buy (beli saat harga kembali ke area support setelah naik)</li>
        <li><b>BO</b>: Breakout Buy (beli saat menembus resistance dengan volume)</li>
        <li><b>w=1 / w=0.6/0.4</b>: bobot antrian beli bertahap (persentase alokasi di tiap level)</li>
        <li><b>Invalid</b>: level gagalnya skenario intraday (tutup 1H di bawah level ini → cut/tingkatkan kehati-hatian)</li>
        <li><b>LLM Verifikasi</b>: konfirmasi/penyesuaian rencana oleh model (opsional)</li>
      </ul>
    </details>
  )
}

function MTFDesc({ mtf, tf }:{ mtf:any, tf:'5m'|'15m'|'1h'|'4h' }){
  const d = mtf?.[tf] || {}
  return (
    <section className="rounded-xl ring-1 ring-zinc-200 dark:ring-white/10 bg-white/5 p-3 text-sm">
      <dl className="grid grid-cols-1 md:grid-cols-2 gap-3">
        <div>
          <dt className="text-zinc-500">Tren & Momentum</dt>
          <dd>{d.tren_momentum || '-'}</dd>
        </div>
        <div>
          <dt className="text-zinc-500">Level & Zona</dt>
          <dd>{d.level_zona || '-'}</dd>
        </div>
        <div className="md:col-span-2">
          <dt className="text-zinc-500">Skenario cepat</dt>
          <dd>{d.skenario || '-'}</dd>
        </div>
        <div className="md:col-span-2">
          <dt className="text-zinc-500">Catatan</dt>
          <dd>{d.catatan || '-'}</dd>
        </div>
      </dl>
    </section>
  )
}

// Lightweight S/R overlay inspired by TV pivots
function computePivots(rows:any[], left=15, right=15){
  const highs:number[]=[]; const lows:number[]=[]
  for(let i=left;i<rows.length-right;i++){
    let isHigh=true, isLow=true
    for(let j=i-left;j<=i+right;j++){
      if(rows[j].h>rows[i].h) isHigh=false
      if(rows[j].l<rows[i].l) isLow=false
      if(!isHigh && !isLow) break
    }
    if(isHigh) highs.push(rows[i].h)
    if(isLow) lows.push(rows[i].l)
  }
  // Dedup (near-equal levels) and limit count
  const round=(x:number)=> +x.toFixed(6)
  const uniq=(arr:number[])=>{
    const out:number[]=[]
    arr.sort((a,b)=>a-b)
    for(const v of arr){ if(out.length===0 || Math.abs(v-out[out.length-1])>1e-6) out.push(v) }
    return out
  }
  return { highs: uniq(highs.map(round)).slice(-6), lows: uniq(lows.map(round)).slice(-6) }
}

function useSRExtra(tab:'tren'|'5m'|'15m'|'1h'|'4h', rows:any[]){
  return useMemo(()=>{
    if(tab==='tren' || !rows || rows.length===0) return [] as number[]
    const { highs, lows } = computePivots(rows, 15, 15)
    return [...highs, ...lows]
  },[tab, JSON.stringify(rows?.slice(-220))])
}

function FuturesSummary({ fut }:{ fut:any }){
  if(!fut) return <div className="text-sm text-zinc-500">Futures tidak tersedia.</div>
  const s = fut || {}
  const rr = s?.risk||{}
  const sig = s?.futures_signals||{}
  const tp = s?.tp||[]
  const ents = s?.entries||[]
  const dec = typeof s?.price_decimals==='number' ? s.price_decimals : 5
  const fmt = (n:number)=> typeof n==='number' ? n.toFixed(dec) : n
  const fundingColor = typeof sig?.funding?.now==='number' ? (sig.funding.now>0 ? 'text-rose-500' : 'text-emerald-500') : 'text-zinc-600'
  const oiH1 = Number(sig?.oi?.h1)
  const oiH4 = Number(sig?.oi?.h4)
  const oiH1Color = isFinite(oiH1) ? (oiH1>0?'text-emerald-500':oiH1<0?'text-rose-500':'text-zinc-600') : 'text-zinc-600'
  const oiH4Color = isFinite(oiH4) ? (oiH4>0?'text-emerald-500':oiH4<0?'text-rose-500':'text-zinc-600') : 'text-zinc-600'
  const basisBp = typeof sig?.basis?.bp==='number' ? sig.basis.bp : null
  const basisColor = basisBp!==null ? (basisBp>0?'text-emerald-500':'text-amber-600') : 'text-zinc-600'
  return (
    <section className="rounded-xl ring-1 ring-zinc-200 dark:ring-white/10 bg-white/5 p-3 text-sm space-y-2">
      <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
        <div>
          <div className="text-zinc-500">Side • Leverage</div>
          <div>{s?.side||'-'} • isolated x={s?.leverage_suggested?.x ?? '-'}</div>
        </div>
        <div>
          <div className="text-zinc-500">Risk</div>
          <div>risk/trade: {rr?.risk_per_trade_pct ?? '-'}% • rr_min: {rr?.rr_min||'-'}</div>
          <div>liq est: {typeof rr?.liq_price_est==='number' ? rr.liq_price_est : '-'}</div>
        </div>
        <div>
          <div className="text-zinc-500">Entries</div>
          <div>{ents.map((e:any)=> (Array.isArray(e.range)? fmt(e.range[0]): '-')).join(' · ')||'-'}</div>
        </div>
        <div>
          <div className="text-zinc-500">Invalid (tiers)</div>
          <div>{['tactical_5m','soft_15m','hard_1h','struct_4h'].map((k)=> s?.invalids?.[k]).filter((x:any)=> typeof x==='number').map((x:number)=> fmt(x)).join(' · ')||'-'}</div>
        </div>
        <div className="md:col-span-2">
          <div className="text-zinc-500">TP (reduce-only)</div>
          <div className="text-emerald-600">{tp.map((t:any)=> `${(t?.range||[]).map((x:number)=>fmt(x)).join('–')} (${typeof t?.reduce_only_pct==='number'? t.reduce_only_pct: '-' }%)`).join(' → ')||'-'}</div>
        </div>
      </div>
      <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
        <div>
          <div className="text-zinc-500">Funding <span title="Warna hijau: rate negatif (cenderung baik untuk long). Merah: positif.">ⓘ</span></div>
          <div className={fundingColor} title="Nilai funding saat ini (perpetual)">now: {sig?.funding?.now ?? '-'} • next: {sig?.funding?.next ?? '-'}</div>
          <div title="Perkiraan waktu funding berikutnya (UTC)">time: {sig?.funding?.time ?? '-'}</div>
        </div>
        <div>
          <div className="text-zinc-500">Open Interest <span title="Panah hijau ▲: kenaikan OI; merah ▼: penurunan OI.">ⓘ</span></div>
          <div title="Open Interest saat ini">now: {sig?.oi?.now ?? '-'}</div>
          <div title="Perubahan OI dalam 1 jam dan 4 jam terakhir">Δ1h: <span className={oiH1Color}>{isFinite(oiH1)? (oiH1>0?'▲':'▼') : ''} {isFinite(oiH1)? oiH1.toFixed(0): '-'}</span> • Δ4h: <span className={oiH4Color}>{isFinite(oiH4)? (oiH4>0?'▲':'▼') : ''} {isFinite(oiH4)? oiH4.toFixed(0): '-'}</span></div>
        </div>
        <div>
          <div className="text-zinc-500">Basis <span title="Basis = Mark−Index; bp positif umumnya bullish">ⓘ</span></div>
          <div title="Basis absolut & dalam basis points">now: {sig?.basis?.now ?? '-'} {basisBp!==null && <span className={basisColor}>({basisBp.toFixed(1)} bp)</span>}</div>
        </div>
        <div>
          <div className="text-zinc-500">LSR</div>
          <div>acc: {sig?.lsr?.accounts ?? '-'} • pos: {sig?.lsr?.positions ?? '-'}</div>
        </div>
        <div className="md:col-span-2">
          <div className="text-zinc-500">Taker Δ</div>
          <div>m5: {sig?.taker_delta?.m5 ?? '-'} • m15: {sig?.taker_delta?.m15 ?? '-'} • h1: {sig?.taker_delta?.h1 ?? '-'}</div>
        </div>
        {sig?.orderbook && (
          <div className="md:col-span-2">
            <div className="text-zinc-500">Orderbook</div>
            <div>spread: {typeof sig?.orderbook?.spread_bp==='number' ? `${sig?.orderbook?.spread_bp.toFixed(2)} bp` : '-'}, depth10bp: bid {sig?.orderbook?.depth10bp_bid ?? '-'} • ask {sig?.orderbook?.depth10bp_ask ?? '-'}, imbalance: {typeof sig?.orderbook?.imbalance==='number' ? sig?.orderbook?.imbalance.toFixed(2) : '-'}</div>
          </div>
        )}
      </div>
      {Array.isArray(s?.jam_pantau_wib) && s.jam_pantau_wib.length>0 && (
        <div>
          <div className="text-zinc-500">Jam pantau WIB (signifikan)</div>
          <div className="flex flex-wrap gap-1 text-xs">{s.jam_pantau_wib.map((h:number)=> <span key={h} className="px-2 py-0.5 rounded bg-emerald-600 text-white">{String(h).padStart(2,'0')}:00</span>)}</div>
        </div>
      )}
    </section>
  )
}
