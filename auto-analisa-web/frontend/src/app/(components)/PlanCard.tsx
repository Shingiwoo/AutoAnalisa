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
    <div className="rounded-2xl border shadow-sm p-4 md:p-6 bg-white dark:bg-zinc-900 space-y-3">
      <div className="text-lg font-semibold flex items-center gap-2">
        <span>{plan.symbol} • v{plan.version}</span>
        <ScoreBadge score={p.score} />
      </div>
      <div className="text-sm opacity-70">{new Date(plan.created_at).toLocaleString('id-ID')}</div>

      <div className="flex items-center gap-2 text-sm" role="tablist" aria-label="Timeframes">
        <button role="tab" aria-selected={tf==='5m'} onClick={()=>setTf('5m')} className={`px-2.5 py-1 rounded transition ${tf==='5m'?'bg-blue-600 text-white':'bg-gray-100 text-gray-800 hover:bg-gray-200'}`}>5m</button>
        <button role="tab" aria-selected={tf==='15m'} onClick={()=>setTf('15m')} className={`px-2.5 py-1 rounded transition ${tf==='15m'?'bg-blue-600 text-white':'bg-gray-100 text-gray-800 hover:bg-gray-200'}`}>15m</button>
        <button role="tab" aria-selected={tf==='1h'} onClick={()=>setTf('1h')} className={`px-2.5 py-1 rounded transition ${tf==='1h'?'bg-blue-600 text-white':'bg-gray-100 text-gray-800 hover:bg-gray-200'}`}>1h</button>
      </div>
      <div className="aspect-[16/9] md:aspect-[21/9] overflow-hidden rounded-xl">
        <ChartOHLCV className="h-full" data={ohlcv} overlays={{ sr:[...(p.support||[]),...(p.resistance||[])], tp:p.tp||[], invalid:p.invalid, entries:p.entries||[] }} />
      </div>

      <div className="text-sm space-y-2">
        <div><b>Bias Dominan:</b> <span className="text-gray-800">{p.bias}</span></div>
        <div>
          <p className="font-medium">Level Kunci</p>
          <ul className="list-disc list-inside text-sm">
            <li><span className="text-gray-700">Support:</span> {(p.support||[]).join(' · ')}</li>
            <li><span className="text-gray-700">Resistance:</span> {(p.resistance||[]).join(' · ')}</li>
          </ul>
        </div>
        <div>
          <p className="font-medium">Rencana Eksekusi (spot)</p>
          <div><span className="text-gray-700">Entry (PB/BO):</span> <span className="text-sky-600">{(p.entries||[]).join(' / ')}</span>{p.weights? <span className="text-gray-600"> {` (w=${p.weights.join('/')})`}</span> : null}</div>
          <div><span className="text-gray-700">Invalid:</span> <span className="text-red-600 font-semibold">{p.invalid}</span></div>
        </div>
        <div><span className="font-medium text-green-700">TP:</span> <span className="text-green-700">{(p.tp||[]).join(' → ')}</span></div>
        <p className="mt-1 italic text-gray-800">
          {p.narrative}
        </p>
      </div>
      <Glossary />
      <div className="flex gap-2">
        <button onClick={onUpdate} className="px-3 py-2 rounded bg-zinc-900 text-white">Update</button>
        {onArchive && <button onClick={onArchive} className="px-3 py-2 rounded bg-zinc-200">Simpan</button>}
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
