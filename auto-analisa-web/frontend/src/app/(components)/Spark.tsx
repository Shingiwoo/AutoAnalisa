"use client"
import { useMemo } from "react"

type Pt = { ts: number; close: number }

export default function Spark({ data, color }: { data: Pt[]|undefined, color?: string }){
  const path = useMemo(() => {
    const d = Array.isArray(data) ? data : []
    const n = d.length
    if (!n) return ''
    const w = 160, h = 48, pad = 4
    const xs = d.map((_, i) => i)
    const ys = d.map(p => p.close)
    const minY = Math.min(...ys), maxY = Math.max(...ys)
    const rangeY = maxY - minY || 1
    const stepX = (w - pad*2) / Math.max(1, n - 1)
    const pts = d.map((p, i) => {
      const x = pad + i * stepX
      const y = pad + (h - pad*2) * (1 - (p.close - minY) / rangeY)
      return `${x.toFixed(2)},${y.toFixed(2)}`
    })
    return pts.join(' ')
  }, [JSON.stringify(data)])

  const up = (Array.isArray(data) && data.length >= 2) ? data[data.length-1].close >= data[0].close : false
  const stroke = color || (up ? '#22c55e' : '#ef4444')

  return (
    <svg viewBox="0 0 160 48" width={160} height={48} className="overflow-visible">
      <polyline fill="none" stroke={stroke} strokeWidth={2} strokeLinejoin="round" strokeLinecap="round" points={path} />
    </svg>
  )
}

