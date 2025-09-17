"use client"
import { useMemo, useState } from 'react'
import { api } from '../api'

export default function LLMReport({ analysisId, verification, onApplied, onPreview, kind }:{ analysisId:number, verification:any|null, onApplied:()=>void, onPreview:(ghost:{entries?:number[],tp?:number[],invalid?:number}|null)=>void, kind?: 'spot'|'futures' }){
  const [busy,setBusy]=useState(false)
  const verdict = (verification?.verdict||'').toLowerCase()
  const tsWib = useMemo(()=> verification?.created_at ? new Date(verification.created_at).toLocaleString('id-ID', { timeZone: 'Asia/Jakarta' }) : '',[verification?.created_at])
  const data = verification?.spot2_json || verification?.futures_json
  const sug = (data?.rencana_jual_beli) ? data.rencana_jual_beli : (data?.entries ? { entries: data.entries, invalid: data?.invalids?.hard_1h } : {})
  const tp = data?.tp || []
  const ghost = useMemo(()=>{
    if(!data) return null
    const g:any={}
    try{
      const ents = (sug.entries||[]).map((e:any)=> (Array.isArray(e.range)? e.range[0] : undefined)).filter((x:any)=> typeof x==='number')
      const inv = typeof (sug.invalid ?? data?.invalids?.hard_1h)==='number' ? (sug.invalid ?? data?.invalids?.hard_1h) : undefined
      const tps = (tp||[]).map((t:any)=> (Array.isArray(t.range)? t.range[0]:undefined)).filter((x:any)=> typeof x==='number')
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
        <span className={`px-2 py-0.5 rounded text-white text-xs ${badgeColor}`}>{verdict||'verify'}</span>
        <span className="font-medium">LLM Report</span>
        <span className="text-xs opacity-70">{tsWib} WIB</span>
      </summary>
      <div className="mt-3 text-sm space-y-2">
        {verification.summary && <div className="italic text-zinc-600 dark:text-zinc-300">{verification.summary}</div>}
        <dl className="grid grid-cols-1 md:grid-cols-2 gap-3">
          <div>
            <dt className="text-zinc-500">Entries</dt>
            <dd>{(sug.entries||[]).map((e:any,i:number)=> `${(e.range||[]).join('–')} (w=${e.weight})`).join(' · ')||'-'}</dd>
          </div>
          <div>
            <dt className="text-zinc-500">Invalid</dt>
            <dd className="text-rose-400">{sug.invalid}</dd>
          </div>
          <div className="md:col-span-2">
            <dt className="text-zinc-500">TP</dt>
            <dd className="text-emerald-400">{(tp||[]).map((t:any)=> (t?.range||[]).join('–')).join(' → ')||'-'}</dd>
          </div>
          {Array.isArray(verification?.fundamentals?.bullets) && verification.fundamentals.bullets.length>0 && (
            <div className="md:col-span-2">
              <dt className="text-zinc-500">Fundamentals</dt>
              <dd>
                <ul className="list-disc pl-5">
                  {verification.fundamentals.bullets.map((b:string,i:number)=> <li key={i}>{b}</li>)}
                </ul>
              </dd>
            </div>
          )}
        </dl>
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
