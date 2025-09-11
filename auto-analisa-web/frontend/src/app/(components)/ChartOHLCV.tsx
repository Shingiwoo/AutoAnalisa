'use client'
import { useEffect, useRef } from 'react'
import { createChart, ColorType, CandlestickData } from 'lightweight-charts'

type Row = { t:number,o:number,h:number,l:number,c:number,v:number }

export default function ChartOHLCV({ data, overlays }:{ data: Row[], overlays?: { sr?: number[], tp?: number[], invalid?: number, entries?: number[] } }){
  const ref = useRef<HTMLDivElement>(null)
  useEffect(()=>{
    if(!ref.current) return
    const chart = createChart(ref.current, { width: ref.current.clientWidth, height: 260, layout:{ background:{ type: ColorType.Solid, color:'#fff' }}})
    const series = chart.addCandlestickSeries()
    const mapped: CandlestickData[] = data.map(d=>({ time: d.t/1000 as any, open:d.o, high:d.h, low:d.l, close:d.c }))
    series.setData(mapped)

    if (overlays?.invalid){
      series.createPriceLine({ price: overlays.invalid, color: '#ef4444', lineWidth: 2, lineStyle: 2, title: 'Invalid' })
    }
    if (overlays?.tp){
      for (const t of overlays.tp){ series.createPriceLine({ price: t, color: '#16a34a', lineWidth: 1, lineStyle: 0, title: 'TP' }) }
    }
    if (overlays?.sr){
      for (const s of overlays.sr){ series.createPriceLine({ price: s, color: '#64748b', lineWidth: 1, lineStyle: 1, title: 'S/R' }) }
    }
    if (overlays?.entries){
      for (const e of overlays.entries){ series.createPriceLine({ price: e, color: '#0ea5e9', lineWidth: 1, lineStyle: 0, title: 'Entry' }) }
    }

    const ro = new ResizeObserver(()=> chart.applyOptions({ width: ref.current!.clientWidth }))
    ro.observe(ref.current)
    return ()=>{ ro.disconnect(); chart.remove() }
  },[JSON.stringify(data), JSON.stringify(overlays)])
  return <div ref={ref} className="w-full" />
}

