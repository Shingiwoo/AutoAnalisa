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
    <div className="p-4 rounded-2xl shadow bg-white space-y-3">
      <div className="text-lg font-semibold flex items-center gap-2">
        <span>{plan.symbol} • v{plan.version}</span>
        <ScoreBadge score={p.score} />
      </div>
      <div className="text-sm opacity-70">{new Date(plan.created_at).toLocaleString('id-ID')}</div>

      <div className="flex items-center gap-2 text-sm">
        <button onClick={()=>setTf('5m')} className={`px-2 py-1 rounded ${tf==='5m'?'bg-black text-white':'bg-zinc-100'}`}>5m</button>
        <button onClick={()=>setTf('15m')} className={`px-2 py-1 rounded ${tf==='15m'?'bg-black text-white':'bg-zinc-100'}`}>15m</button>
        <button onClick={()=>setTf('1h')} className={`px-2 py-1 rounded ${tf==='1h'?'bg-black text-white':'bg-zinc-100'}`}>1h</button>
      </div>
      <ChartOHLCV data={ohlcv} overlays={{ sr:[...(p.support||[]),...(p.resistance||[])], tp:p.tp||[], invalid:p.invalid, entries:p.entries||[] }} />

      <div className="whitespace-pre-wrap text-sm">
        <b>Bias Dominan:</b> {p.bias}
        {'\n'}<b>Level Kunci</b>{'\n'}Support: {(p.support||[]).join(' · ')}{'\n'}Resistance: {(p.resistance||[]).join(' · ')}
        {'\n'}<b>Rencana Eksekusi (spot)</b>{'\n'}PB/BO: {(p.entries||[]).join(' / ')}{p.weights?` (w=${p.weights.join('/')})`:''} • Invalid: {p.invalid}
        {'\n'}TP: {(p.tp||[]).join(' → ')}
        {'\n'}<b>Bacaan Sinyal:</b> {p.narrative}
      </div>
      <Glossary />
      <div className="flex gap-2">
        <button onClick={onUpdate} className="px-3 py-2 rounded bg-zinc-900 text-white">Update</button>
        {onArchive && <button onClick={onArchive} className="px-3 py-2 rounded bg-zinc-200">Save</button>}
      </div>
    </div>
  )
}

function label(score:number){
  if(score>=70) return {text:'Kuat', color:'bg-green-600'}
  if(score>=50) return {text:'Menengah', color:'bg-yellow-500'}
  if(score>=30) return {text:'Lemah', color:'bg-orange-500'}
  return {text:'Hindari', color:'bg-red-600'}
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
