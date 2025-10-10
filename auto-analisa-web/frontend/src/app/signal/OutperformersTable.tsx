"use client"
import { useEffect, useState } from "react"
import { api } from "../api"

type Row = { symbol: string; score: number; alpha_z?: number; ratio_break?: boolean; [k:string]: any }

export default function OutperformersTable({ symbols, mode, market='futures', top=20 }: { symbols: string, mode: 'fast'|'medium'|'swing', market?: string, top?: number }){
  const [rows, setRows] = useState<Row[]>([])
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState('')

  async function load(){
    setBusy(true); setErr('')
    try{
      const { data } = await api.get('/screener/outperformers', { params: { symbols, mode, market, top } })
      setRows(Array.isArray(data?.results) ? data.results : [])
    }catch(e:any){ setErr('gagal memuat') }
    finally{ setBusy(false) }
  }

  useEffect(()=>{ load() }, [symbols, mode])

  return (
    <div className="mt-8">
      <div className="flex items-center justify-between mb-2">
        <h3 className="text-sm font-semibold text-zinc-100">Outperformers</h3>
        <button onClick={load} disabled={busy} className="rounded px-2 py-1 bg-zinc-800 text-white text-xs hover:bg-zinc-700 disabled:opacity-50">{busy?'Memuat…':'Refresh'}</button>
      </div>
      {err && <div className="text-xs text-rose-300">{err}</div>}
      <div className="overflow-x-auto">
        <table className="min-w-full text-xs">
          <thead>
            <tr className="text-left text-zinc-400 border-b border-white/10">
              <th className="px-2 py-2">Symbol</th>
              <th className="px-2 py-2">Score</th>
              <th className="px-2 py-2">RS(1h)</th>
              <th className="px-2 py-2">RS(4h)</th>
              <th className="px-2 py-2">RS(1D)</th>
              <th className="px-2 py-2">Alpha-z</th>
              <th className="px-2 py-2">Ratio Break</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r)=> (
              <tr key={r.symbol} className="border-b border-white/5">
                <td className="px-2 py-2 font-medium">{r.symbol}</td>
                <td className="px-2 py-2">{typeof r.score==='number'? r.score.toFixed(3): '-'}</td>
                <td className="px-2 py-2">{typeof r.rs_short==='number'? r.rs_short.toFixed(3): (typeof r.rs_h1==='number'? r.rs_h1.toFixed(3) : '-')}</td>
                <td className="px-2 py-2">{typeof r.rs_mid==='number'? r.rs_mid.toFixed(3): (typeof r.rs_4h==='number'? r.rs_4h.toFixed(3) : '-')}</td>
                <td className="px-2 py-2">{typeof r.rs_long==='number'? r.rs_long.toFixed(3): (typeof r.rs_1d==='number'? r.rs_1d.toFixed(3) : '-')}</td>
                <td className="px-2 py-2">{typeof r.alpha_z==='number'? r.alpha_z.toFixed(2): '-'}</td>
                <td className="px-2 py-2">{r.ratio_break? <span className="px-1.5 py-0.5 rounded bg-emerald-700 text-white">BREAK</span> : <span className="px-1.5 py-0.5 rounded bg-zinc-700 text-white">-</span>}</td>
              </tr>
            ))}
            {rows.length===0 && (
              <tr><td colSpan={7} className="px-2 py-4 text-zinc-400">Tidak ada data.</td></tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  )
}

