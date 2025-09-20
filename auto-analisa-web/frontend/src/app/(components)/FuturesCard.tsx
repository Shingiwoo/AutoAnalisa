"use client"
import { useEffect, useMemo, useState } from 'react'
import { api } from '../../app/api'
import ChartOHLCV from './ChartOHLCV'
import LLMReport from './LLMReport'

export default function FuturesCard({plan, onUpdate, llmEnabled, llmRemaining, onAfterVerify}:{plan:any,onUpdate:()=>void, llmEnabled?:boolean, llmRemaining?:number, onAfterVerify?:()=>void}){
  const p = plan.payload || {}
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
  const [fut,setFut]=useState<any|null>(null)
  const [futErr,setFutErr]=useState<string>('')
  // SERI L (GPT Analyze) state
  const [gptMode,setGptMode]=useState<'scalping'|'swing'>('scalping')
  const [gptBusy,setGptBusy]=useState(false)
  const [gptOut,setGptOut]=useState<any|null>(null)

  const createdWIB = useMemo(()=>{
    try{ return new Date(plan.created_at).toLocaleString('id-ID', { timeZone: 'Asia/Jakarta' }) + ' WIB' }catch{ return new Date(plan.created_at).toLocaleString('id-ID') }
  },[plan.created_at])

  useEffect(()=>{ const t = (tab==='tren'? '15m' : tab) as '5m'|'15m'|'1h'|'4h'; setTf(t) },[tab])
  useEffect(()=>{ (async()=>{
    try{ setLoading(true); const {data}=await api.get('ohlcv', { params:{ symbol:plan.symbol, tf, limit:200, market: 'futures' } }); setOhlcv(data) }catch{} finally{ setLoading(false) }
  })() },[tf, plan.symbol])
  useEffect(()=>{ (async()=>{
    try{ setFutErr(''); const {data}=await api.get(`analyses/${plan.symbol}/futures`); setFut(data) }
    catch(e:any){ setFut(null); setFutErr(e?.response?.data?.detail||'Futures tidak tersedia') }
  })() },[plan.symbol])

  const lastClose = (ohlcv && ohlcv.length>0) ? ohlcv[ohlcv.length-1].c : undefined
  const invalids = useMemo(()=>{
    const inv = fut?.invalids || {}
    return {
      m5: typeof inv.tactical_5m==='number'? inv.tactical_5m : undefined,
      m15: typeof inv.soft_15m==='number'? inv.soft_15m : undefined,
      h1: typeof inv.hard_1h==='number'? inv.hard_1h : undefined,
      h4: typeof inv.struct_4h==='number'? inv.struct_4h : undefined,
    }
  },[JSON.stringify(fut?.invalids)])
  const breach = useMemo(()=>{
    if(typeof lastClose !== 'number') return null
    const invH1 = invalids.h1
    const invM15 = invalids.m15
    if(typeof invH1 === 'number' && lastClose <= invH1){ return { type:'hard', text:'Invalidated — cek ulang setup (1H)' } }
    if(typeof invM15 === 'number' && lastClose <= invM15){ return { type:'soft', text:'Rawan — cek ulang 15m' } }
    return null
  },[lastClose, invalids])
  const srExtra = useSRExtra(tab, ohlcv)
  const computeSRCombined = () => ([...(p.support||[]), ...(p.resistance||[]), ...srExtra])
  // Map GPT overlay to ghost format (price-only)
  const gptGhost = useMemo(()=>{
    const out = gptOut || null
    if(!out || !out.overlay) return null
    const ov = out.overlay || {}
    const entries:number[] = []
    const tp:number[] = []
    let invalid:number|undefined
    try{
      if(Array.isArray(ov.lines)){
        for(const l of ov.lines){
          const label = (l?.label||l?.type||'').toString().toUpperCase()
          const price = typeof l?.price==='number'? l.price : undefined
          if(typeof price!=='number') continue
          if(label.includes('TP')) tp.push(price)
          if(label.includes('SL') || label.includes('INVALID')) invalid = price
        }
      }
      if(Array.isArray(ov.zones)){
        for(const z of ov.zones){
          if((z?.type||'').toUpperCase()==='ENTRY' && Array.isArray(z?.range)){
            const [a,b] = z.range
            if(typeof a==='number' && typeof b==='number') entries.push((a+b)/2)
          }
        }
      }
    }catch{}
    return { entries, tp, invalid }
  },[JSON.stringify(gptOut)])

  return (
    <div className="rounded-2xl ring-1 ring-zinc-200 dark:ring-white/10 bg-white dark:bg-zinc-900 shadow-sm p-4 md:p-6 space-y-4 text-zinc-900 dark:text-zinc-100">
      <div className="flex items-center justify-between">
        <div className="text-lg font-semibold flex items-center gap-2">
          <span>{plan.symbol} • v{plan.version}</span>
          <span className="px-1.5 py-0.5 rounded bg-zinc-200 dark:bg-zinc-800 text-xs" title="tf_base">{fut?.tf_base||'15m'}</span>
        </div>
        <div className="text-xs text-zinc-500" title={new Date(plan.created_at).toISOString()}>{createdWIB}</div>
      </div>

      <div className="rounded-xl ring-1 ring-zinc-200 dark:ring-white/10 bg-white/5 p-3 text-sm">
        {fut ? (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            <div>
              <div className="text-zinc-500">Side • Leverage</div>
              <div>{fut?.side||'-'} • isolated x={fut?.leverage_suggested?.x ?? '-'}</div>
            </div>
            <div>
              <div className="text-zinc-500">Risk</div>
              <div>risk/trade: {fut?.risk?.risk_per_trade_pct ?? '-'}% • rr_min: {fut?.risk?.rr_min||'-'}</div>
            </div>
          </div>
        ) : (
          <div className="text-zinc-500">{futErr||'Memuat Futures…'}</div>
        )}
      </div>

      <div className="flex items-center gap-2 text-sm" role="tablist" aria-label="Analisa Tabs">
        {(['tren','5m','15m','1h','4h'] as const).map(t=> (
          <button key={t} role="tab" aria-selected={tab===t} onClick={()=>setTab(t)}
            className={`px-2.5 py-1 rounded-md transition ${tab===t? 'bg-indigo-600 text-white':'bg-white text-zinc-900 hover:bg-zinc-100 dark:bg-zinc-800 dark:text-white/90'} `}>
            {t==='tren'? 'Tren Utama' : t}
          </button>
        ))}
      </div>

      {breach && (
        <div className={`p-2 rounded text-sm ${breach.type==='hard'?'bg-rose-50 border border-rose-200 text-rose-700':'bg-amber-50 border border-amber-200 text-amber-800'}`}>{breach.text}</div>
      )}

      <div className="rounded-none overflow-hidden ring-1 ring-zinc-200 dark:ring-white/10 bg-white dark:bg-zinc-950 relative">
        <div className="aspect-[16/9] md:aspect-[21/9]">
          <ChartOHLCV
            key={`${plan.symbol}-futures-${tf}-${expanded?'x':''}`}
            className="h-full"
            data={ohlcv}
            overlays={{
              sr: computeSRCombined(),
              tp: (fut?.tp||[]).map((t:any)=> Array.isArray(t.range)? t.range[0] : undefined).filter((x:any)=> typeof x==='number'),
              invalid: invalids as any,
              entries: (fut?.entries||[]).map((e:any)=> Array.isArray(e.range)? e.range[0]: undefined).filter((x:any)=> typeof x==='number'),
              ghost: (ghost || gptGhost || undefined) as any,
              liq: typeof fut?.risk?.liq_price_est==='number' ? fut.risk.liq_price_est : undefined,
              funding: fut?.futures_signals?.funding?.time ? [{ timeMs: Date.parse(fut.futures_signals.funding.time), windowMin: (fut?.risk?.funding_window_min||10) }] : undefined,
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

      {/* Funding soon banner */}
      {(()=>{
        try{
          const thr = Number(fut?.risk?.funding_threshold_bp)||3
          const rate = Math.abs(Number(fut?.futures_signals?.funding?.now)||0)*10000
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
                key={`${plan.symbol}-futures-modal-${tf}`}
                className="w-full h-full"
                data={ohlcv}
                overlays={{
                  sr: computeSRCombined(),
                  tp: (fut?.tp||[]).map((t:any)=> Array.isArray(t.range)? t.range[0] : undefined).filter((x:any)=> typeof x==='number'),
                  invalid: invalids as any,
                  entries: (fut?.entries||[]).map((e:any)=> Array.isArray(e.range)? e.range[0]: undefined).filter((x:any)=> typeof x==='number'),
                  ghost: (ghost || gptGhost || undefined) as any,
                  liq: typeof fut?.risk?.liq_price_est==='number' ? fut.risk.liq_price_est : undefined,
                  funding: fut?.futures_signals?.funding?.time ? [{ timeMs: Date.parse(fut.futures_signals.funding.time), windowMin: (fut?.risk?.funding_window_min||10) }] : undefined,
                }}
              />
            </div>
          </div>
        </div>
      )}

      <FuturesSummary fut={fut} />
      <LLMReport analysisId={plan.id} verification={verification} onApplied={()=> onUpdate()} onPreview={setGhost} kind='futures' />

      <div className="flex items-center gap-2 flex-wrap">
        <button onClick={onUpdate} className="px-3 py-2 rounded-md bg-zinc-900 text-white hover:bg-zinc-800">Update</button>
        <button className="px-3 py-2 rounded-md bg-zinc-800 text-white hover:bg-zinc-700" onClick={async()=>{
          try{ await api.post(`analyses/${plan.id}/save`); alert('Versi disimpan ke arsip') }
          catch(e:any){ alert(e?.response?.data?.detail||'Gagal menyimpan versi') }
        }}>Simpan Versi</button>
        <button disabled={verifying || !llmEnabled || (typeof llmRemaining==='number' && llmRemaining<=0)} title={!llmEnabled? 'LLM nonaktif (limit/budget)':'Tanya GPT (Futures)'}
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
        {/* SERI L: Tanya GPT Analyze (Mode Scalping/Swing) */}
        <div className="flex items-center gap-2">
          <div className="flex items-center rounded-md overflow-hidden ring-1 ring-zinc-200">
            {(['scalping','swing'] as const).map(m=> (
              <button key={m} onClick={()=> setGptMode(m)} className={`px-2 py-1 text-sm ${gptMode===m? 'bg-cyan-600 text-white':'bg-white text-zinc-900 hover:bg-zinc-100'}`}>{m}</button>
            ))}
          </div>
          <button disabled={gptBusy || !llmEnabled || (typeof llmRemaining==='number' && llmRemaining<=0)} title={!llmEnabled? 'LLM nonaktif (limit/budget)':'Tanya GPT (Mode)'}
            onClick={async()=>{
              try{
                setGptBusy(true)
                const payload:any = { symbol: plan.symbol, tf, ohlcv15m: (tf==='15m'? ohlcv: undefined), futures: fut }
                if(gptMode==='scalping'){
                  try{ const {data} = await api.get('ohlcv', { params:{ symbol: plan.symbol, tf: '5m', limit: 200, market: 'futures' } }); payload.ohlcv5m = data }catch{}
                }
                if(tf!=='15m'){
                  try{ const {data} = await api.get('ohlcv', { params:{ symbol: plan.symbol, tf: '15m', limit: 200, market: 'futures' } }); payload.ohlcv15m = data }catch{}
                }
                const { data } = await api.post('gpt/futures/analyze', { symbol: plan.symbol, mode: gptMode, payload, opts: { timezone: 'Asia/Jakarta' } })
                setGptOut(data)
              }catch(e:any){
                const msg = e?.response?.data?.detail?.message || e?.response?.data?.detail || e?.message || 'Gagal memanggil GPT analyze'
                alert(msg)
              }finally{ setGptBusy(false) }
            }} className="px-3 py-2 rounded-md bg-cyan-600 text-white hover:bg-cyan-500 disabled:opacity-50">{gptBusy? 'Meminta…' : 'Tanya GPT (Mode)'}</button>
        </div>
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
      <div className="flex items-center gap-2">
        <button className="px-2.5 py-1.5 rounded bg-zinc-800 text-white text-xs" onClick={async()=>{
          const next = !prevOpen
          setPrevOpen(next)
          if(next && !prevPlan){
            try{
              const { data } = await api.get('analyses', { params:{ status:'archived', trade_type: 'futures' } })
              const same = (data||[]).filter((x:any)=> x.symbol===plan.symbol)
              setPrevList(same)
              const prev = same.find((x:any)=> new Date(x.created_at) < new Date(plan.created_at)) || same[0]
              setPrevPlan(prev||null)
            }catch{}
          }
        }}>{prevOpen? 'Sembunyikan versi sebelumnya':'Tampilkan versi sebelumnya'}</button>
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
          <div title="Basis absolut & dalam basis points">now: {sig?.basis?.now ?? '-'} {typeof sig?.basis?.bp==='number' && <span className={basisColor}>({sig?.basis?.bp.toFixed(1)} bp)</span>}</div>
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

function tryFormatGptText(out:any){
  try{
    const t = out?.text || {}
    const s = t.section_scalping || t.section_swing || {}
    const pos = s.posisi || 'NO-TRADE'
    const tp = Array.isArray(s.tp)? s.tp : []
    const sl = s.sl
    const bybk = Array.isArray(s.bybk)? s.bybk : []
    const bo = Array.isArray(s.bo)? s.bo : []
    const strat = Array.isArray(s.strategi_singkat)? s.strategi_singkat : []
    const fund = Array.isArray(s.fundamental)? s.fundamental : []
    const lines = [
      `Posisi : ${pos}`,
      `TP : ${tp.map((x:any,i:number)=> `${i+1}) ${x}`).join('  ')}`,
      `SL : ${typeof sl==='number'? sl : '-'}`,
      bybk.length? `Buy-back (BYBK): ${bybk.map((b:any)=> `[${b?.zone?.[0]}–${b?.zone?.[1]}] ${b?.note||''}`).join('; ')}` : '',
      bo.length? `Break Out (BO): ${bo.map((b:any)=> `${typeof b?.above==='number'? 'di atas '+b.above: (typeof b?.below==='number'? 'di bawah '+b.below:'')} ${b?.note||''}`).join('; ')}` : '',
      'Strategi Simple untuk Entry:',
      ...strat.map((x:string)=> `- ${x}`),
      fund.length? 'Fundamental:' : '',
      ...fund.map((x:string)=> `- ${x}`),
    ].filter(Boolean)
    return lines.join('\n')
  }catch{
    try{ return JSON.stringify(out, null, 2) }catch{ return String(out) }
  }
