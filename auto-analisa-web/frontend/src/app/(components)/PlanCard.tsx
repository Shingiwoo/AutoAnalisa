"use client"
import { useEffect, useMemo, useState } from 'react'
import { api } from '../../app/api'
import ChartOHLCV from './ChartOHLCV'

export default function PlanCard({plan, onUpdate, llmEnabled, llmRemaining, onAfterVerify}:{plan:any,onUpdate:()=>void, llmEnabled?:boolean, llmRemaining?:number, onAfterVerify?:()=>void}){
  const p=plan.payload
  const [tf,setTf]=useState<'5m'|'15m'|'1h'>(()=> '15m')
  const [ohlcv,setOhlcv]=useState<any[]>([])
  const [loading,setLoading]=useState(false)
  const [verifying,setVerifying]=useState(false)
  const [verification,setVerification]=useState<any|null>(null)
  const [expanded,setExpanded]=useState(false)
  const createdWIB = useMemo(()=>{
    try{ return new Date(plan.created_at).toLocaleString('id-ID', { timeZone: 'Asia/Jakarta' }) + ' WIB' }catch{ return new Date(plan.created_at).toLocaleString('id-ID') }
  },[plan.created_at])
  const precision = useMemo(()=>{
    const base = (p?.entries && p.entries[0]) || (p?.tp && p.tp[0]) || (typeof p?.invalid==='number' ? p.invalid : 1)
    const last = typeof base === 'number' ? base : 1
    return last >= 1000 ? 2 : last >= 100 ? 2 : last >= 10 ? 3 : last >= 1 ? 4 : last >= 0.1 ? 5 : 6
  },[p])
  const fmt = (n:number) => typeof n==='number' ? n.toFixed(precision) : n
  useEffect(()=>{ (async()=>{
    try{ setLoading(true); const {data}=await api.get('ohlcv', { params:{ symbol:plan.symbol, tf, limit:200 } }); setOhlcv(data) }catch{} finally{ setLoading(false) }
  })() },[tf, plan.symbol])
  return (
    <div className="rounded-2xl ring-1 ring-zinc-200 dark:ring-white/10 bg-white dark:bg-zinc-900 shadow-sm p-4 md:p-6 space-y-4 text-zinc-900 dark:text-zinc-100">
      <div className="flex items-center justify-between">
        <div className="text-lg font-semibold flex items-center gap-2">
          <span>{plan.symbol} • v{plan.version}</span>
          <ScoreBadge score={p.score} />
        </div>
        <div className="text-xs text-zinc-500" title={new Date(plan.created_at).toISOString()}>{createdWIB}</div>
      </div>

      <div className="flex items-center gap-2 text-sm" role="tablist" aria-label="Timeframes">
        <button role="tab" aria-selected={tf==='5m'} onClick={()=>setTf('5m')} className={`px-2.5 py-1 rounded-md transition ${tf==='5m'?'bg-cyan-600 text-white':'bg-zinc-100 text-zinc-800 hover:bg-zinc-200'}`}>5m</button>
        <button role="tab" aria-selected={tf==='15m'} onClick={()=>setTf('15m')} className={`px-2.5 py-1 rounded-md transition ${tf==='15m'?'bg-cyan-600 text-white':'bg-zinc-100 text-zinc-800 hover:bg-zinc-200'}`}>15m</button>
        <button role="tab" aria-selected={tf==='1h'} onClick={()=>setTf('1h')} className={`px-2.5 py-1 rounded-md transition ${tf==='1h'?'bg-cyan-600 text-white':'bg-zinc-100 text-zinc-800 hover:bg-zinc-200'}`}>1h</button>
      </div>

      <div className="rounded-none overflow-hidden ring-1 ring-zinc-200 dark:ring-white/10 bg-white dark:bg-zinc-950 relative">
        <div className="aspect-[16/9] md:aspect-[21/9]">
          <ChartOHLCV key={`${plan.symbol}-${tf}-${expanded?'x':''}`} className="h-full" data={ohlcv} overlays={{ sr:[...(p.support||[]),...(p.resistance||[])], tp:p.tp||[], invalid:p.invalid, entries:p.entries||[] }} />
        </div>
        {loading && (
          <div className="absolute inset-0 flex items-center justify-center bg-black/5 dark:bg-white/5">
            <div className="text-xs text-zinc-700 dark:text-zinc-200">Memuat {tf}…</div>
          </div>
        )}
        <button onClick={()=>setExpanded(true)} className="absolute top-2 right-2 text-xs px-2 py-1 rounded bg-zinc-900/80 text-white hover:bg-zinc-900">Perbesar</button>
      </div>

      {expanded && (
        <div className="fixed inset-0 z-50 bg-black/70 flex items-center justify-center p-4" onClick={()=>setExpanded(false)}>
          <div className="w-full max-w-7xl h-[80vh] bg-zinc-950 ring-1 ring-white/10 rounded-none relative" onClick={e=>e.stopPropagation()}>
            <button onClick={()=>setExpanded(false)} className="absolute top-3 right-3 px-2 py-1 rounded bg-zinc-800 text-white text-sm">Tutup</button>
            <div className="absolute inset-0">
              <ChartOHLCV key={`${plan.symbol}-modal-${tf}`} className="w-full h-full" data={ohlcv} overlays={{ sr:[...(p.support||[]),...(p.resistance||[])], tp:p.tp||[], invalid:p.invalid, entries:p.entries||[] }} />
            </div>
          </div>
        </div>
      )}

      <div className="text-sm">
        <dl className="grid grid-cols-1 sm:grid-cols-2 gap-x-6 gap-y-3">
          <div>
            <dt className="text-zinc-500">Bias Dominan</dt>
            <dd className="text-zinc-900 dark:text-zinc-100">{p.bias}</dd>
          </div>
          <div>
            <dt className="text-zinc-500">Invalid</dt>
            <dd className="text-red-600 font-semibold">{fmt(p.invalid)}</dd>
          </div>
          <div>
            <dt className="text-zinc-500">Support</dt>
            <dd className="text-zinc-900 dark:text-zinc-100">{(p.support||[]).map(fmt).join(' · ')||'-'}</dd>
          </div>
          <div>
            <dt className="text-zinc-500">Resistance</dt>
            <dd className="text-zinc-900 dark:text-zinc-100">{(p.resistance||[]).map(fmt).join(' · ')||'-'}</dd>
          </div>
          <div className="sm:col-span-2">
            <dt className="text-zinc-500">Entry (PB/BO)</dt>
            <dd className="text-sky-600">{(p.entries||[]).map(fmt).join(' / ')||'-'}{p.weights? <span className="text-zinc-500"> {` (w=${p.weights.join('/')})`}</span> : null}</dd>
          </div>
          <div className="sm:col-span-2">
            <dt className="text-zinc-500">TP</dt>
            <dd className="text-green-700">{(p.tp||[]).map(fmt).join(' → ')||'-'}</dd>
          </div>
          <div className="sm:col-span-2">
            <dt className="text-zinc-500">Bacaan Sinyal</dt>
            <dd className="italic text-zinc-700 dark:text-zinc-300">{p.narrative}</dd>
        </div>
        </dl>
      </div>

      {/* LLM Verification block */}
      <LLMVerifyBlock plan={p} verification={verification || p?.llm_verification} fmt={fmt} />

      <Glossary />
      <div className="flex gap-2">
        <button onClick={onUpdate} className="px-3 py-2 rounded-md bg-zinc-900 text-white hover:bg-zinc-800">Update</button>
        <button disabled={verifying || !llmEnabled || (typeof llmRemaining==='number' && llmRemaining<=0)} title={!llmEnabled? 'LLM nonaktif (limit/budget)':'Tanya GPT'} onClick={async()=>{
          try{
            setVerifying(true)
            const {data} = await api.post(`analyses/${plan.id}/verify`)
            setVerification(data.verification)
          }catch(e:any){
            alert(e?.response?.data?.detail || 'Verifikasi gagal')
          }finally{ setVerifying(false); onAfterVerify?.() }
        }} className="px-3 py-2 rounded-md bg-cyan-600 text-white hover:bg-cyan-500 disabled:opacity-50">{verifying?'Memverifikasi…':'Tanya GPT'}</button>
      </div>
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
        {kept.length>0 && <span className="text-zinc-300">{kept.map(fmt as any).join(' · ')}</span>}
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
      {verification.summary && <div className="text-sm italic text-zinc-300">{verification.summary}</div>}
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
