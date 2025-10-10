"use client"
import { useEffect, useState } from "react"
import { api } from "../api"

export default function QuickAnalyzeButton({ symbol, mode, onDone, className }: { symbol: string, mode: 'fast'|'medium'|'swing', onDone?: (result: any)=>void, className?: string }){
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState('')

  async function run(){
    setBusy(true); setErr('')
    try{
      let followBias = true
      try{ if(typeof window!=="undefined"){ const s = localStorage.getItem('follow_btc_bias'); followBias = s===null ? true : s==='1' } }catch{}
      const profile = (mode==='swing' ? 'swing' : 'scalp')
      // 1) snapshot batch (single symbol) to lock time and mode
      const sb = await api.post('v2/snapshot/batch', [symbol], { params: { mode } })
      const sid = sb?.data?.snapshot_id
      if(!sid) throw new Error('snapshot gagal')
      // 2) analyze snapshot (index 0) with profile + rich output
      const res = await api.post('v2/analyze_snapshot', null, { params: { snapshot_id: sid, index: 0, follow_btc_bias: followBias, profile, format: 'rich' } })
      onDone && onDone(res.data)
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
