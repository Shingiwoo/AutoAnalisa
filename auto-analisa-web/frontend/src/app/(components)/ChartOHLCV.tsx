'use client'
import { useEffect, useRef } from 'react'
import { createChart, ColorType, CandlestickData } from 'lightweight-charts'

type Row = { t:number,o:number,h:number,l:number,c:number,v:number }

type FVG = { type:'bull'|'bear', gap_low:number, gap_high:number, mitigated?:boolean }
type Zone = { type:'supply'|'demand', low:number, high:number }

export default function ChartOHLCV({ data, overlays, className }:{ data: Row[], overlays?: { sr?: number[], tp?: number[], invalid?: number, entries?: number[], fvg?: FVG[], zones?: Zone[] }, className?: string }){
  const ref = useRef<HTMLDivElement>(null)
  useEffect(()=>{
    if(!ref.current) return
    const w = ref.current.clientWidth
    const h = ref.current.clientHeight || 260
    // Derive reasonable precision from last close to better reflect notional/price scale
    const last = data && data.length ? data[data.length-1].c : 1
    const prec = last >= 1000 ? 2 : last >= 100 ? 2 : last >= 10 ? 3 : last >= 1 ? 4 : last >= 0.1 ? 5 : 6
    const minMove = parseFloat((1/Math.pow(10, prec)).toFixed(prec))
    const chart = createChart(ref.current, {
      width: w,
      height: h,
      layout:{ background:{ type: ColorType.Solid, color:'#fff' }},
      rightPriceScale: { borderVisible: false },
      timeScale: { borderVisible: false },
    })
    const series = chart.addCandlestickSeries({ priceFormat: { type: 'price', precision: prec, minMove } })
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
    // FVG overlay: render band boundaries as lines (box-lite)
    if (overlays?.fvg){
      for (const b of overlays.fvg){
        const color = b.type==='bull' ? '#10b981' : '#ef4444'
        const style = b.mitigated ? 1 : 0
        series.createPriceLine({ price: b.gap_low, color, lineWidth: 1, lineStyle: style, title: 'FVG' })
        series.createPriceLine({ price: b.gap_high, color, lineWidth: 1, lineStyle: style, title: 'FVG' })
      }
    }
    // Supply/Demand zones: render low/high boundaries
    if (overlays?.zones){
      for (const z of overlays.zones){
        const color = z.type==='supply' ? '#f59e0b' : '#8b5cf6'
        series.createPriceLine({ price: z.low, color, lineWidth: 1, lineStyle: 2, title: z.type==='supply'?'Supply':'Demand' })
        series.createPriceLine({ price: z.high, color, lineWidth: 1, lineStyle: 2, title: z.type==='supply'?'Supply':'Demand' })
      }
    }

    // Overlay rectangles for FVG & Zones (approximate TradingView boxes)
    const overlay = document.createElement('div')
    overlay.style.position = 'absolute'
    overlay.style.inset = '0'
    overlay.style.pointerEvents = 'none'
    ref.current.appendChild(overlay)

    function drawBoxes(){
      overlay.innerHTML=''
      const priceToY = (price:number): number => {
        const v = series.priceToCoordinate(price)
        return typeof v === 'number' ? v : 0
      }
      const timeToX = (ms:number): number => {
        const v = chart.timeScale().timeToCoordinate((ms/1000) as any)
        return typeof v === 'number' ? v : 0
      }
      const wpx: number = (ref.current?.clientWidth ?? 0) as number

      // FVG boxes (extend to right)
      (overlays?.fvg||[]).forEach(b=>{
        if(typeof b.gap_low!=='number' || typeof b.gap_high!=='number') return
        const y1: number = priceToY(b.gap_high)
        const y2: number = priceToY(b.gap_low)
        if(typeof y1 !== 'number' || typeof y2 !== 'number') return
        const left = typeof (b as any).ts_start==='number' ? timeToX((b as any).ts_start) : 0
        const right = wpx
        const div = document.createElement('div')
        div.style.position='absolute'
        div.style.left = `${Math.max(0,left)}px`
        div.style.right = `0px`
        div.style.top = `${Math.min(y1,y2)}px`
        div.style.height = `${Math.abs(y2-y1)}px`
        div.style.background = (b.type==='bull' ? 'rgba(16,185,129,0.12)' : 'rgba(239,68,68,0.12)')
        div.style.borderTop = `1px dashed ${b.type==='bull' ? '#10b981' : '#ef4444'}`
        div.style.borderBottom = `1px dashed ${b.type==='bull' ? '#10b981' : '#ef4444'}`
        overlay.appendChild(div)
      })

      // Supply/Demand zones (extend to right)
      (overlays?.zones||[]).forEach(z=>{
        if(typeof z.low!=='number' || typeof z.high!=='number') return
        const y1: number = priceToY(z.high)
        const y2: number = priceToY(z.low)
        if(typeof y1 !== 'number' || typeof y2 !== 'number') return
        const left = typeof (z as any).ts_start==='number' ? timeToX((z as any).ts_start) : 0
        const div = document.createElement('div')
        div.style.position='absolute'
        div.style.left = `${Math.max(0,left)}px`
        div.style.right = `0px`
        div.style.top = `${Math.min(y1,y2)}px`
        div.style.height = `${Math.abs(y2-y1)}px`
        div.style.background = (z.type==='supply' ? 'rgba(245,158,11,0.10)' : 'rgba(139,92,246,0.10)')
        div.style.borderTop = `1px dotted ${z.type==='supply' ? '#f59e0b' : '#8b5cf6'}`
        div.style.borderBottom = `1px dotted ${z.type==='supply' ? '#f59e0b' : '#8b5cf6'}`
        overlay.appendChild(div)
      })
    }

    drawBoxes()

    chart.timeScale().subscribeVisibleTimeRangeChange(()=> drawBoxes())
    const ro = new ResizeObserver(()=> { chart.applyOptions({ width: ref.current!.clientWidth, height: ref.current!.clientHeight || h }); drawBoxes() })
    ro.observe(ref.current)
    return ()=>{ ro.disconnect(); chart.remove(); try{ overlay.remove() }catch{} }
  },[JSON.stringify(data), JSON.stringify(overlays)])
  return <div ref={ref} className={`w-full ${className||''}`} />
}
