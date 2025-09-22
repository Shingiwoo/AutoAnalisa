"use client"
import { useMemo, useState } from 'react'
import { api } from '../api'

type ReportMode = 'scalping' | 'swing'

export function GptReportBox({ symbol, mode, report, loading }:{ symbol:string, mode:ReportMode, report:any|null, loading?:boolean }){
  const created = useMemo(()=>{
    try{
      const iso = report?.created_at || report?.meta?.cached_at
      return iso ? new Date(iso).toLocaleString('id-ID', { timeZone: 'Asia/Jakarta' }) : ''
    }catch{return ''}
  },[report?.created_at, report?.meta?.cached_at])
  const section = useMemo(()=> pickGptSection(report?.text, mode), [report?.text, mode])
  const decimals = useMemo(()=> inferDecimals(section), [JSON.stringify(section)])
  const fmtNum = (n:any)=> typeof n==='number' ? n.toFixed(decimals) : n
  const tpList = Array.isArray(section?.tp) ? section!.tp : []
  const sl = section?.sl
  const strategi = Array.isArray(section?.strategi_singkat)? section!.strategi_singkat : []
  const fundamental = Array.isArray(section?.fundamental)? section!.fundamental : []
  const bybk = Array.isArray(section?.bybk)? section!.bybk : []
  const bo = Array.isArray(section?.bo)? section!.bo : []
  const rekom = report?.text?.recommendation || {}
  const probability = report?.meta?.probability ?? report?.text?.probability

  const bodyLines = useMemo(()=>{
    if(!section) return [`Belum ada laporan GPT untuk mode ${mode}.`]
    const lines:string[] = []
    lines.push(`Analisa Coin ${symbol.toUpperCase()} :`)
    lines.push(`Posisi : ${section.posisi || '-'}`)
    if (tpList && tpList.length>0){
      const arr = tpList.slice(0,3).map((v:any,i:number)=> `${i+1}) ${fmtNum(v)}`)
      lines.push(`TP : ${arr.join('  ')}`)
    }else{
      lines.push('TP : -')
    }
    lines.push(`SL : ${typeof sl==='number'? fmtNum(sl): (sl || '-')}`)
    if (bybk && bybk.length>0){
      const arr = bybk.map((z:any)=>{
        const rng = Array.isArray(z?.zone)? z.zone : z?.range
        const lo = typeof rng?.[0]==='number'? fmtNum(rng[0]) : '-'
        const hi = typeof rng?.[1]==='number'? fmtNum(rng[1]) : lo
        return `[${lo}–${hi}] ${z?.note||''}`.trim()
      })
      lines.push(`Buy-back (BYBK): ${arr.join('; ')}`)
    }else{
      lines.push('Buy-back (BYBK): -')
    }
    if (bo && bo.length>0){
      const arr = bo.map((b:any)=>{
        const above = typeof b?.above==='number'? fmtNum(b.above) : null
        const below = typeof b?.below==='number'? fmtNum(b.below) : null
        const dir = above? `Above ${above}` : below? `Below ${below}` : ''
        return `${dir}${dir?' : ':''}${b?.note||''}`.trim()
      })
      lines.push(`Break Out (BO): ${arr.join('; ')}`)
    }else{
      lines.push('Break Out (BO): -')
    }
    lines.push(`Strategi ${mode==='scalping'?'Simple':'Detail'} untuk Entry:`)
    if (strategi.length>0){ strategi.forEach((s:string)=> lines.push(`- ${s}`)) }
    else lines.push('- -')
    if (fundamental.length>0){
      lines.push('Fundamental jika ada:')
      fundamental.forEach((f:string)=> lines.push(`- ${f}`))
    }
    if (rekom && (rekom.leverage_suggest || rekom.risk_per_trade || rekom.catatan)){
      lines.push('Saran Risiko & Leverage:')
      if (rekom.leverage_suggest) lines.push(`- Leverage: ${rekom.leverage_suggest}`)
      if (rekom.risk_per_trade) lines.push(`- Risk/Trade: ${rekom.risk_per_trade}`)
      if (rekom.catatan) lines.push(`- Catatan: ${rekom.catatan}`)
    }
    if (probability){
      lines.push(`Probabilitas: ${probability}%`)
    }
    return lines
  },[section, tpList, sl, strategi, fundamental, bybk, bo, fmtNum, rekom, probability, mode, symbol])

  if (loading){
    return <div className="rounded-xl ring-1 ring-sky-200/60 bg-sky-50/60 dark:bg-sky-950/40 dark:ring-sky-500/20 p-4 text-sm text-zinc-500">Memuat laporan GPT…</div>
  }
  if (!report){
    return <div className="rounded-xl ring-1 ring-sky-200/60 bg-sky-50/60 dark:bg-sky-950/40 dark:ring-sky-500/20 p-4 text-sm text-zinc-500">Belum ada laporan GPT untuk mode {mode}. Klik <b>Tanya GPT</b> untuk memulai.</div>
  }
  return (
    <details className="rounded-xl ring-1 ring-sky-200/60 bg-sky-50/60 dark:bg-sky-950/40 dark:ring-sky-500/20 p-4" open>
      <summary className="flex items-center gap-2 text-sm font-semibold text-sky-700 dark:text-sky-200 cursor-pointer">
        <span>LLM Report ({mode})</span>
        {created && <span className="text-xs font-normal text-sky-500/80">{created} WIB</span>}
      </summary>
      <div className="mt-3 text-sm">
        <pre className="whitespace-pre-wrap font-mono text-[13px] leading-6 text-sky-900 dark:text-sky-100">
          {bodyLines.join('\n')}
        </pre>
      </div>
    </details>
  )
}

function pickGptSection(text:any, mode:ReportMode){
  if(!text) return null
  if(mode==='scalping') return text?.section_scalping || null
  return text?.section_swing || text?.section_scalping || null
}

function inferDecimals(section:any){
  try{
    const nums:number[] = []
    if (Array.isArray(section?.tp)) section.tp.forEach((v:any)=> { if (typeof v==='number') nums.push(v) })
    if (typeof section?.sl==='number') nums.push(section.sl)
    if (Array.isArray(section?.bybk)) section.bybk.forEach((z:any)=>{ const rng = Array.isArray(z?.zone)? z.zone : z?.range; if (Array.isArray(rng)) rng.forEach((n:any)=> typeof n==='number' && nums.push(n)) })
    const sample = nums.find((v)=> typeof v==='number' && isFinite(v)) || 1
    if (sample >= 1000) return 2
    if (sample >= 100) return 2
    if (sample >= 10) return 3
    if (sample >= 1) return 4
    if (sample >= 0.1) return 5
    return 6
  }catch{}
  return 4
}

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
  const entriesRaw = Array.isArray(data?.entries) ? data.entries : (Array.isArray(data?.rencana_jual_beli?.entries) ? data.rencana_jual_beli.entries : [])
  const sug = { entries: entriesRaw, invalid: typeof data?.invalid==='number'? data.invalid : data?.invalids?.hard_1h }
  const tp = Array.isArray(data?.tp) ? data.tp : []
  // Formatting helpers: prefer provided decimals; fallback infer from numbers
  const decimals = useMemo(()=>{
    const d = (data?.metrics?.price_decimals ?? data?.price_decimals)
    if (typeof d === 'number' && d>=0 && d<=8) return d
    // infer from representative price
    try{
      const sample = (()=>{
        const arr:number[] = []
        ;(sug?.entries||[]).forEach((e:any)=> {
          if (typeof e?.price==='number') arr.push(e.price)
          else if(Array.isArray(e?.range)) e.range.forEach((x:number)=> typeof x==='number' && arr.push(x))
        })
        ;(tp||[]).forEach((t:any)=> {
          if (typeof t?.price==='number') arr.push(t.price)
          else if(Array.isArray(t?.range)) t.range.forEach((x:number)=> typeof x==='number' && arr.push(x))
        })
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
      const list = (sug?.entries||[]).map((e:any)=> {
        if(typeof e?.price==='number') return e.price
        if(Array.isArray(e?.range)) return e.range[0]
        return undefined
      }).filter((x:any)=> typeof x==='number') as number[]
      const rounded = list.map(roundN)
      return uniqueWithTolerance(rounded, eps)
    }catch{ return [] }
  },[JSON.stringify(sug?.entries), decimals])
  const tpDisplay = useMemo(()=>{
    try{
      const list = (tp||[]).map((t:any)=> {
        if(typeof t?.price==='number') return t.price
        if(Array.isArray(t?.range)) return t.range[0]
        return undefined
      }).filter((x:any)=> typeof x==='number') as number[]
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
