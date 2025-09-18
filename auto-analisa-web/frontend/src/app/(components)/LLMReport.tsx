"use client"
import { useMemo, useState } from 'react'
import { api } from '../api'

export default function LLMReport({ analysisId, verification, onApplied, onPreview, kind }:{ analysisId:number, verification:any|null, onApplied:()=>void, onPreview:(ghost:{entries?:number[],tp?:number[],invalid?:number}|null)=>void, kind?: 'spot'|'futures' }){
  const [busy,setBusy]=useState(false)
  const [view,setView]=useState<'summary'|'json'>('summary')
  const verdict = (verification?.verdict||'').toLowerCase()
  const verdictLabel = useMemo(()=>{
    switch(verdict){
      case 'valid': return '✅ Valid'
      case 'tweak': return '🛠️ Perlu Penyesuaian'
      case 'reject': return '⛔ Tolak'
      case 'warning': return '⚠️ Warning'
      default: return verdict||'verify'
    }
  },[verdict])
  const tsWib = useMemo(()=> verification?.created_at ? new Date(verification.created_at).toLocaleString('id-ID', { timeZone: 'Asia/Jakarta' }) : '',[verification?.created_at])
  const data = (kind==='futures') ? verification?.futures_json : verification?.spot2_json
  const sug = (data?.rencana_jual_beli) ? data.rencana_jual_beli : (data?.entries ? { entries: data.entries, invalid: data?.invalids?.hard_1h } : {})
  const tp = data?.tp || []
  // Formatting helpers: prefer provided decimals; fallback infer from numbers
  const decimals = useMemo(()=>{
    const d = (data?.metrics?.price_decimals ?? data?.price_decimals)
    if (typeof d === 'number' && d>=0 && d<=8) return d
    // infer from representative price
    try{
      const sample = (()=>{
        const arr:number[] = []
        ;(sug?.entries||[]).forEach((e:any)=> Array.isArray(e?.range) && e.range.forEach((x:number)=> typeof x==='number' && arr.push(x)))
        ;(tp||[]).forEach((t:any)=> Array.isArray(t?.range) && t.range.forEach((x:number)=> typeof x==='number' && arr.push(x)))
        if (typeof (sug?.invalid)==='number') arr.push(sug.invalid)
        const v = arr.find((x)=> typeof x==='number' && isFinite(x))
        return (typeof v==='number' && isFinite(v)) ? v : 1
      })()
      return sample >= 1000 ? 2 : sample >= 100 ? 2 : sample >= 10 ? 3 : sample >= 1 ? 4 : sample >= 0.1 ? 5 : 6
    }catch{ return 5 }
  },[JSON.stringify(data)])
  const fmtNum = (n:any)=> typeof n==='number' ? n.toFixed(decimals) : n
  const fmtRange = (r:any)=>{
    const arr = Array.isArray(r)? r:[]
    const lo = arr[0]
    const hi = (arr.length>1? arr[1] : lo)
    if (typeof lo==='number' && typeof hi==='number'){
      const eps = 0.5 * Math.pow(10, -decimals)
      if (Math.abs(hi-lo) <= eps) return `${fmtNum(lo)}`
    }
    return arr.map((x:any)=> fmtNum(x)).join('–')
  }
  const roundN = (x:number)=> {
    const f = Math.pow(10, decimals)
    return Math.round(x * f) / f
  }
  const uniqueWithTolerance = (arr:number[], eps:number)=>{
    const out:number[] = []
    const s = [...arr].sort((a,b)=> a-b)
    for(const v of s){
      if(out.length===0 || Math.abs(v - out[out.length-1]) > eps){ out.push(v) }
    }
    return out
  }
  const eps = 0.5 * Math.pow(10, -decimals)
  // Prepare normalized/deduped data for display and preview
  const entriesDisplay = useMemo(()=>{
    try{
      const list = (sug?.entries||[]).map((e:any)=> (Array.isArray(e?.range) ? e.range[0] : undefined)).filter((x:any)=> typeof x==='number') as number[]
      const rounded = list.map(roundN)
      return uniqueWithTolerance(rounded, eps)
    }catch{ return [] }
  },[JSON.stringify(sug?.entries), decimals])
  const tpDisplay = useMemo(()=>{
    try{
      const list = (tp||[]).map((t:any)=> (Array.isArray(t?.range) ? t.range[0] : undefined)).filter((x:any)=> typeof x==='number') as number[]
      const rounded = list.map(roundN)
      return uniqueWithTolerance(rounded, eps)
    }catch{ return [] }
  },[JSON.stringify(tp), decimals])
  const ghost = useMemo(()=>{
    if(!data) return null
    const g:any={}
    try{
      const ents = entriesDisplay
      const inv = typeof (sug.invalid ?? data?.invalids?.hard_1h)==='number' ? (sug.invalid ?? data?.invalids?.hard_1h) : undefined
      const tps = tpDisplay
      g.entries = ents
      g.invalid = inv
      g.tp = tps
    }catch{}
    return g
  },[verification])

  if(!verification) return null
  const badgeColor = verdict==='confirm'? 'bg-green-600' : verdict==='tweak'? 'bg-amber-600' : verdict==='warning'? 'bg-orange-600':'bg-rose-600'
  return (
    <details className="rounded-xl ring-1 ring-zinc-200 dark:ring-white/10 bg-white/5 p-3">
      <summary className="flex items-center gap-2 cursor-pointer text-sm">
        <span className={`px-2 py-0.5 rounded text-white text-xs ${badgeColor}`}>{verdictLabel}</span>
        <span className="font-medium">LLM Report</span>
        <span className="text-xs opacity-70">{tsWib} WIB</span>
      </summary>
      <div className="mt-3 text-sm space-y-2">
        <div className="flex items-center gap-2 text-xs">
          <button className={`px-2 py-0.5 rounded ${view==='summary'?'bg-zinc-800 text-white':'bg-zinc-200 dark:bg-zinc-800 dark:text-white/80'}`} onClick={()=>setView('summary')}>Ringkas</button>
          <button className={`px-2 py-0.5 rounded ${view==='json'?'bg-zinc-800 text-white':'bg-zinc-200 dark:bg-zinc-800 dark:text-white/80'}`} onClick={()=>setView('json')}>JSON</button>
        </div>
        {view==='json' ? (
          <div className="rounded bg-zinc-900 text-zinc-100 p-2 text-xs overflow-auto">
            <pre className="whitespace-pre-wrap">{data ? JSON.stringify(data, null, 2) : '-'}</pre>
            <div className="mt-2">
              <button className="px-2 py-1 rounded bg-zinc-800 text-white hover:bg-zinc-700" onClick={()=> navigator.clipboard?.writeText(JSON.stringify(data||{}, null, 2))}>Copy JSON</button>
            </div>
          </div>
        ) : (
          <>
            {verification.summary && <div className="italic text-zinc-600 dark:text-zinc-300">{verification.summary}</div>}
            {kind==='futures' ? (
              <>
                <dl className="grid grid-cols-1 md:grid-cols-2 gap-3">
                  <div>
                    <dt className="text-zinc-500">Leverage</dt>
                    <dd>
                      {typeof data?.leverage?.lev_default==='number' ? (
                        <>
                          default x={data.leverage.lev_default}
                          {data.leverage.violates_lev_policy && <span className="ml-2 px-1.5 py-0.5 rounded bg-amber-600 text-white text-xs">⚠️ policy</span>}
                        </>
                      ) : (
                        <>{data?.side || '-'} • isolated x={(data?.leverage_suggested?.x ?? '-')}</>
                      )}
                    </dd>
                  </div>
                  <div>
                    <dt className="text-zinc-500">Risk</dt>
                    <dd>risk/trade: {data?.risk?.risk_per_trade_pct ?? '-'}% • rr_min: {data?.risk?.rr_min ?? '-'}</dd>
                  </div>
                  <div>
                    <dt className="text-zinc-500">Entries</dt>
                    <dd>{entriesDisplay.length>0 ? entriesDisplay.map((x:number)=> fmtNum(x)).join(' · ') : '-'}</dd>
                  </div>
                  <div>
                    <dt className="text-zinc-500">Invalid (tiers)</dt>
                    <dd className="text-rose-400">{['tactical_5m','soft_15m','hard_1h','struct_4h'].map((k)=> data?.invalids?.[k]).filter((x:any)=> typeof x==='number').map((x:number)=> fmtNum(x)).join(' · ')||'-'}</dd>
                  </div>
                  <div className="md:col-span-2">
                    <dt className="text-zinc-500">TP Ladder</dt>
                    <dd className="text-emerald-400">
                      {Array.isArray(data?.tp_ladder_pct) && data.tp_ladder_pct.length>0 ? (
                        <>{data.tp_ladder_pct.join('/')}{' '}% • {tpDisplay.length>0 ? tpDisplay.map((x:number)=> fmtNum(x)).join(' → ') : '-'}</>
                      ) : (
                        <>{tpDisplay.length>0 ? tpDisplay.map((x:number)=> fmtNum(x)).join(' → ') : '-'}</>
                      )}
                    </dd>
                  </div>
                </dl>
                {(Array.isArray(data?.macro_notes) && data.macro_notes.length>0) && (
                  <div>
                    <div className="text-zinc-500 flex items-center gap-2">
                      <span>Makro WIB</span>
                      {(()=>{
                        const w = (verification?.macro_snapshot?.wib_window||'').toUpperCase()
                        const icon = w==='HIJAU'? '🟢' : w==='MERAH'? '🔴' : w? '🟡' : ''
                        return icon ? <span title={w}>{icon}</span> : null
                      })()}
                    </div>
                    <ul className="list-disc pl-5">
                      {data.macro_notes.slice(0,3).map((m:string,i:number)=> <li key={i}>{m}</li>)}
                    </ul>
                  </div>
                )}
                {(data?.ui_flags && (data.ui_flags.need_rounding || data.ui_flags.dup_values_cleaned)) && (
                  <div className="flex items-center gap-2 text-xs">
                    {data.ui_flags.need_rounding && <span className="px-1.5 py-0.5 rounded bg-zinc-200 dark:bg-zinc-800">Rounded</span>}
                    {data.ui_flags.dup_values_cleaned && <span className="px-1.5 py-0.5 rounded bg-zinc-200 dark:bg-zinc-800">Dedupe</span>}
                  </div>
                )}
              </>
            ) : (
              <dl className="grid grid-cols-1 md:grid-cols-2 gap-3">
                <div>
                  <dt className="text-zinc-500">Entries</dt>
                  <dd>{entriesDisplay.length>0 ? entriesDisplay.map((x:number)=> fmtNum(x)).join(' · ') : '-'}</dd>
                </div>
                <div>
                  <dt className="text-zinc-500">Invalid</dt>
                  <dd className="text-rose-400">{typeof sug.invalid==='number'? fmtNum(sug.invalid) : (sug.invalid||'-')}</dd>
                </div>
                <div className="md:col-span-2">
                  <dt className="text-zinc-500">TP</dt>
                  <dd className="text-emerald-400">{tpDisplay.length>0 ? tpDisplay.map((x:number)=> fmtNum(x)).join(' → ') : '-'}</dd>
                </div>
              </dl>
            )}
            {Array.isArray(verification?.fundamentals?.bullets) && verification.fundamentals.bullets.length>0 && (
              <div className="mt-2">
                <div className="text-zinc-500">Fundamentals</div>
                <ul className="list-disc pl-5">
                  {verification.fundamentals.bullets.map((b:string,i:number)=> <li key={i}>{b}</li>)}
                </ul>
              </div>
            )}
          </>
        )}
        <div className="flex items-center gap-2">
          <button disabled={busy} className="px-3 py-1.5 rounded bg-cyan-600 text-white text-sm hover:bg-cyan-500 disabled:opacity-50" onClick={async()=>{
            try{ setBusy(true); const url = kind==='futures' ? `analyses/${analysisId}/futures/apply-llm` : `analyses/${analysisId}/apply-llm`; await api.post(url); onApplied(); }
            catch(e:any){ alert(e?.response?.data?.detail||'Gagal menerapkan saran') }
            finally{ setBusy(false) }
          }}>Terapkan Saran</button>
          <button className="px-3 py-1.5 rounded bg-zinc-800 text-white text-sm hover:bg-zinc-700" onClick={()=> onPreview(ghost)}>Pratinjau (ghost)</button>
          <button className="px-3 py-1.5 rounded bg-zinc-800 text-white text-sm hover:bg-zinc-700" onClick={()=> onPreview(null)}>Sembunyikan Pratinjau</button>
        </div>
      </div>
    </details>
  )
}
