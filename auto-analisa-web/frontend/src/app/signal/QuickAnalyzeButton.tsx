"use client"
import { useState } from "react"
import { api } from "../api"

export default function QuickAnalyzeButton({ symbol, mode, tfMap, useContext=true, onDone, className }: { symbol: string, mode: 'fast'|'medium'|'swing', tfMap: {trend:string;pattern:string;trigger:string}, useContext?: boolean, onDone?: (result: any)=>void, className?: string }){
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState('')

  async function run(){
    setBusy(true); setErr('')
    try{
      // Call new Quick Analyze endpoint with explicit tf_map
      const { data } = await api.post('/quick-analyze', { symbol, mode, tf_map: tfMap, use_context: useContext })
      onDone && onDone(data)
    }catch(e:any){ setErr('gagal') }
    finally{ setBusy(false) }
  }

  return (
    <>
      <button onClick={run} disabled={busy} className={"rounded px-2 py-1 bg-zinc-800 text-white text-xs hover:bg-zinc-700 disabled:opacity-50 "+(className||'')}>{busy? 'Analyzing…':'Quick Analyze'}</button>
      {err && <span className="ml-2 text-xs text-rose-300">{err}</span>}
    </>
  )
}
