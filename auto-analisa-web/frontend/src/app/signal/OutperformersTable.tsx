"use client"
import { useEffect, useState } from "react"
import { api } from "../api"

type Row = { symbol: string; score: number; rsh?: number; alpha_z?: number }

export default function OutperformersTable({ mode, market='binanceusdm', limit=10, onSymbols }: { mode: 'fast'|'medium'|'swing', market?: string, limit?: number, onSymbols?: (syms: string[])=>void }){
  const [rows, setRows] = useState<Row[]>([])
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState('')

  async function load(){
    setBusy(true); setErr('')
    try{
      const { data } = await api.get('/outperformers', { params: { mode, market, limit } })
      const arr = Array.isArray(data) ? data : (Array.isArray(data?.results) ? data.results : [])
      setRows(arr)
      onSymbols && onSymbols(arr.map((r:any)=>r.symbol))
    }catch(e:any){ setErr('gagal memuat') }
    finally{ setBusy(false) }
  }

  useEffect(()=>{ load() }, [mode])

  return (
    <div className="mt-8">
      <div className="flex items-center justify-between mb-2">
        <h3 className="text-sm font-semibold text-zinc-100">Outperformers (Market scan)</h3>
        <button onClick={load} disabled={busy} className="rounded px-2 py-1 bg-zinc-800 text-white text-xs hover:bg-zinc-700 disabled:opacity-50">{busy?'Memuat…':'Refresh'}</button>
      </div>
      {err && <div className="text-xs text-rose-300">{err}</div>}
      <div className="overflow-x-auto">
        <table className="min-w-full text-xs">
          <thead>
            <tr className="text-left text-zinc-400 border-b border-white/10">
              <th className="px-2 py-2">Symbol</th>
              <th className="px-2 py-2">Score</th>
              <th className="px-2 py-2">RSh</th>
              <th className="px-2 py-2">Alpha-z</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r)=> (
              <tr key={r.symbol} className="border-b border-white/5">
                <td className="px-2 py-2 font-medium">{r.symbol}</td>
                <td className="px-2 py-2">{typeof r.score==='number'? r.score.toFixed(3): '-'}</td>
                <td className="px-2 py-2">{typeof r.rsh==='number'? r.rsh.toFixed(3): '-'}</td>
                <td className="px-2 py-2">{typeof r.alpha_z==='number'? r.alpha_z.toFixed(2): '-'}</td>
              </tr>
            ))}
            {rows.length===0 && (
              <tr><td colSpan={4} className="px-2 py-4 text-zinc-400">Tidak ada data.</td></tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  )
}
