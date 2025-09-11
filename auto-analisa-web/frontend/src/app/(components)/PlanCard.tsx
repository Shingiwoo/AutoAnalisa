"use client"
import { useEffect, useState } from 'react'
import { api } from '../../app/api'
import ChartOHLCV from './ChartOHLCV'

export default function PlanCard({plan, onUpdate, onArchive}:{plan:any,onUpdate:()=>void,onArchive?:()=>void}){
  const p=plan.payload
  const [tf,setTf]=useState<'5m'|'15m'|'1h'>(()=> '15m')
  const [ohlcv,setOhlcv]=useState<any[]>([])
  useEffect(()=>{ (async()=>{
    try{ const {data}=await api.get('ohlcv', { params:{ symbol:plan.symbol, tf, limit:200 } }); setOhlcv(data) }catch{}
  })() },[tf, plan.symbol])
  return (
    <div className="rounded-2xl ring-1 ring-zinc-200 dark:ring-white/10 bg-white dark:bg-zinc-900 shadow-sm p-4 md:p-6 space-y-4">
      <div className="flex items-center justify-between">
        <div className="text-lg font-semibold flex items-center gap-2">
          <span>{plan.symbol} • v{plan.version}</span>
          <ScoreBadge score={p.score} />
        </div>
        <div className="text-xs text-zinc-500">{new Date(plan.created_at).toLocaleString('id-ID')}</div>
      </div>

      <div className="flex items-center gap-2 text-sm" role="tablist" aria-label="Timeframes">
        <button role="tab" aria-selected={tf==='5m'} onClick={()=>setTf('5m')} className={`px-2.5 py-1 rounded-md transition ${tf==='5m'?'bg-cyan-600 text-white':'bg-zinc-100 text-zinc-800 hover:bg-zinc-200'}`}>5m</button>
        <button role="tab" aria-selected={tf==='15m'} onClick={()=>setTf('15m')} className={`px-2.5 py-1 rounded-md transition ${tf==='15m'?'bg-cyan-600 text-white':'bg-zinc-100 text-zinc-800 hover:bg-zinc-200'}`}>15m</button>
        <button role="tab" aria-selected={tf==='1h'} onClick={()=>setTf('1h')} className={`px-2.5 py-1 rounded-md transition ${tf==='1h'?'bg-cyan-600 text-white':'bg-zinc-100 text-zinc-800 hover:bg-zinc-200'}`}>1h</button>
      </div>

      <div className="rounded-xl overflow-hidden ring-1 ring-zinc-200 dark:ring-white/10 bg-white dark:bg-zinc-950">
        <div className="aspect-[16/9] md:aspect-[21/9]">
          <ChartOHLCV className="h-full" data={ohlcv} overlays={{ sr:[...(p.support||[]),...(p.resistance||[])], tp:p.tp||[], invalid:p.invalid, entries:p.entries||[] }} />
        </div>
      </div>

      <div className="text-sm">
        <dl className="grid grid-cols-1 sm:grid-cols-2 gap-x-6 gap-y-3">
          <div>
            <dt className="text-zinc-500">Bias Dominan</dt>
            <dd className="text-zinc-900 dark:text-zinc-100">{p.bias}</dd>
          </div>
          <div>
            <dt className="text-zinc-500">Invalid</dt>
            <dd className="text-red-600 font-semibold">{p.invalid}</dd>
          </div>
          <div>
            <dt className="text-zinc-500">Support</dt>
            <dd className="text-zinc-900 dark:text-zinc-100">{(p.support||[]).join(' · ')||'-'}</dd>
          </div>
          <div>
            <dt className="text-zinc-500">Resistance</dt>
            <dd className="text-zinc-900 dark:text-zinc-100">{(p.resistance||[]).join(' · ')||'-'}</dd>
          </div>
          <div className="sm:col-span-2">
            <dt className="text-zinc-500">Entry (PB/BO)</dt>
            <dd className="text-sky-600">{(p.entries||[]).join(' / ')||'-'}{p.weights? <span className="text-zinc-500"> {` (w=${p.weights.join('/')})`}</span> : null}</dd>
          </div>
          <div className="sm:col-span-2">
            <dt className="text-zinc-500">TP</dt>
            <dd className="text-green-700">{(p.tp||[]).join(' → ')||'-'}</dd>
          </div>
          <div className="sm:col-span-2">
            <dt className="text-zinc-500">Bacaan Sinyal</dt>
            <dd className="italic text-zinc-800 dark:text-zinc-200">{p.narrative}</dd>
          </div>
        </dl>
      </div>

      <Glossary />
      <div className="flex gap-2">
        <button onClick={onUpdate} className="px-3 py-2 rounded-md bg-zinc-900 text-white hover:bg-zinc-800">Update</button>
        {onArchive && <button onClick={onArchive} className="px-3 py-2 rounded-md bg-zinc-200 hover:bg-zinc-300">Simpan</button>}
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

function Glossary(){
  return (
    <details className="mt-2 text-sm">
      <summary className="cursor-pointer underline">Glosarium</summary>
      <ul className="list-disc pl-5 mt-1">
        <li><b>TP</b>: Take Profit (harga target jual sebagian/seluruhnya)</li>
        <li><b>PB</b>: Pullback Buy (beli saat harga kembali ke area support setelah naik)</li>
        <li><b>BO</b>: Breakout Buy (beli saat menembus resistance dengan volume)</li>
        <li><b>w=1 / w=0.6/0.4</b>: bobot antrian beli bertahap (persentase alokasi di tiap level)</li>
        <li><b>Invalid</b>: level gagalnya skenario intraday (tutup 1H di bawah level ini → cut/tingkatkan kehati-hatian)</li>
      </ul>
    </details>
  )
}
