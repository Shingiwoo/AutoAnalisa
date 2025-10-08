"use client"
import { useEffect, useMemo, useState } from "react"
import { api } from "../api"

type Mode = 'fast'|'medium'|'swing'
type Kind = 'close'|'st_line'

type SparkRow = { ts: string, close: number, st_line: number }

export default function Spark({ symbol, tf, mode, kind='close', limit=200 }: { symbol: string, tf: string, mode: Mode, kind?: Kind, limit?: number }){
  const [rows, setRows] = useState<SparkRow[]>([])
  const [err, setErr] = useState<string>('')

  useEffect(() => {
    let alive = true
    async function run(){
      try{
        const r = await api.get('/spark', { params: { symbol, tf, mode, kind, limit } })
        const data = Array.isArray(r?.data?.data) ? r.data.data : []
        if (!alive) return
        const mapped = data.map((d:any)=>({ ts: String(d.ts||''), close: Number(d.close||0), st_line: Number(d.st_line||0) }))
        setRows(mapped)
      }catch(e:any){ if(alive) setErr('load fail') }
    }
    run()
    return ()=>{ alive=false }
  }, [symbol, tf, mode, kind, limit])

  const points = useMemo(() => {
    const d = Array.isArray(rows) ? rows : []
    const n = d.length
    if (!n) return { pts: '', up: false }
    const series = kind === 'st_line' ? d.map(x=>x.st_line) : d.map(x=>x.close)
    const min = Math.min(...series), max = Math.max(...series)
    const flat = !(isFinite(min) && isFinite(max)) || Math.abs(max - min) < 1e-12
    const yvals = flat ? d.map(x=>x.close) : series
    const w = 176, h = 48, pad = 4
    const range = Math.max(1e-12, Math.max(...yvals) - Math.min(...yvals))
    const step = (w - pad*2) / Math.max(1, n - 1)
    const minY = Math.min(...yvals)
    const pts = yvals.map((y,i)=>{
      const xpx = pad + i*step
      const ypx = pad + (h - pad*2) * (1 - (y - minY)/range)
      return `${xpx.toFixed(2)},${ypx.toFixed(2)}`
    }).join(' ')
    const up = yvals[n-1] >= yvals[0]
    return { pts, up }
  }, [JSON.stringify(rows), kind])

  const stroke = points.up ? '#22c55e' : '#ef4444'
  if (err) return <div className="text-xs text-red-400">{err}</div>
  if (!points.pts) return <div className="text-xs opacity-70">insufficient data</div>
  return (
    <svg viewBox="0 0 176 48" width={176} height={48} className="overflow-visible">
      <polyline fill="none" stroke={stroke} strokeWidth={2} strokeLinejoin="round" strokeLinecap="round" points={points.pts} />
    </svg>
  )
}
