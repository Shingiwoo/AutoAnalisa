'use client'
import { useEffect, useRef } from 'react'
import { createChart, ColorType, CandlestickData } from 'lightweight-charts'

type Row = { t:number,o:number,h:number,l:number,c:number,v:number }

type FVG = { type:'bull'|'bear', gap_low:number, gap_high:number, mitigated?:boolean }
type Zone = { type:'supply'|'demand', low:number, high:number }

type GhostOverlay = { entries?: number[], tp?: number[], invalid?: number }

type FundingWin = { timeMs: number, windowMin: number }

type InvalidMulti = number | { m5?: number, m15?: number, h1?: number, h4?: number }

type LLMLine = { type?: string, label?: string, price?: number }
type LLMZone = { type?: string, range?: [number, number], note?: string }
type LLMMarker = { type?: string, price?: number, label?: string, note?: string }

export default function ChartOHLCV({ data, overlays, className }:{ data: Row[], overlays?: { sr?: number[], tp?: number[], invalid?: InvalidMulti, entries?: number[], fvg?: FVG[], zones?: Zone[], ghost?: GhostOverlay, liq?: number, funding?: FundingWin[], llm?: { lines?: LLMLine[], zones?: LLMZone[], markers?: LLMMarker[] } | null }, className?: string }){
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
    const llmOverlay = overlays?.llm || null

    // Invalid overlays (single or bertingkat)
    if (typeof overlays?.invalid === 'number'){
      series.createPriceLine({ price: overlays.invalid, color: '#ef4444', lineWidth: 2, lineStyle: 2, title: 'Invalid' })
    } else if (overlays?.invalid && typeof overlays.invalid === 'object'){
      const inv = overlays.invalid as any
      if (typeof inv.m5 === 'number') series.createPriceLine({ price: inv.m5, color: '#f59e0b', lineWidth: 1, lineStyle: 2, title: 'Inv 5m' })
      if (typeof inv.m15 === 'number') series.createPriceLine({ price: inv.m15, color: '#eab308', lineWidth: 1, lineStyle: 2, title: 'Inv 15m' })
      if (typeof inv.h1 === 'number') series.createPriceLine({ price: inv.h1, color: '#ef4444', lineWidth: 2, lineStyle: 0, title: 'Invalid 1h' })
      if (typeof inv.h4 === 'number') series.createPriceLine({ price: inv.h4, color: '#8b5cf6', lineWidth: 1, lineStyle: 1, title: 'Inv 4h' })
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
    // Ghost overlay (LLM preview) dashed
    if (overlays?.ghost){
      const g = overlays.ghost
      if (typeof g.invalid === 'number') series.createPriceLine({ price: g.invalid, color: '#0ea5e9', lineWidth: 2, lineStyle: 2, title: 'LLM Invalid' })
      if (Array.isArray(g.tp)) for (const t of g.tp){ series.createPriceLine({ price: t, color: '#22c55e', lineWidth: 1, lineStyle: 2, title: 'LLM TP' }) }
      if (Array.isArray(g.entries)) for (const e of g.entries){ series.createPriceLine({ price: e, color: '#06b6d4', lineWidth: 1, lineStyle: 2, title: 'LLM Entry' }) }
    }
    if (llmOverlay && Array.isArray(llmOverlay.lines)){
      for (const ln of llmOverlay.lines){
        if (typeof ln?.price !== 'number') continue
        const label = (ln?.label || ln?.type || '').toString().toUpperCase()
        let color = '#2563eb'
        let width: 1 | 2 | 3 | 4 = 1
        let style = 0
        if (label.includes('SL')){ color = '#ff4d4f'; width = 2 as const; style = 0 }
        else if (label.includes('TP')){ color = '#16a34a'; width = 2 as const; style = 0 }
        series.createPriceLine({ price: ln.price, color, lineWidth: width, lineStyle: style, title: ln?.label || label || 'LLM' })
      }
    }
    if (llmOverlay && Array.isArray(llmOverlay.markers)){
      for (const mk of llmOverlay.markers){
        if (typeof mk?.price !== 'number') continue
        const title = mk?.label || mk?.note || 'BO'
        series.createPriceLine({ price: mk.price, color: '#2563eb', lineWidth: 1, lineStyle: 2, title })
      }
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
      const fvgList: FVG[] = (overlays && overlays.fvg) ? overlays.fvg : []
      fvgList.forEach((b: FVG)=>{
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
      const zoneList: Zone[] = (overlays && overlays.zones) ? overlays.zones : []
      zoneList.forEach((z: Zone)=>{
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
      const llmZones: LLMZone[] = llmOverlay && Array.isArray(llmOverlay.zones) ? llmOverlay.zones : []
      llmZones.forEach((z: LLMZone)=>{
        if(!Array.isArray(z?.range)) return
        const lo = typeof z.range[0]==='number'? z.range[0] : null
        const hi = typeof z.range[1]==='number'? z.range[1] : lo
        if(typeof lo!=='number' || typeof hi!=='number') return
        const y1:number = priceToY(Math.max(lo, hi))
        const y2:number = priceToY(Math.min(lo, hi))
        if(typeof y1!=='number' || typeof y2!=='number') return
        const left = 0
        const div = document.createElement('div')
        div.style.position='absolute'
        div.style.left = `${left}px`
        div.style.right = `0px`
        div.style.top = `${Math.min(y1,y2)}px`
        div.style.height = `${Math.abs(y2-y1)}px`
        const type = (z?.type || '').toString().toUpperCase()
        if(type==='BYBK'){
          div.style.background = 'rgba(249,115,22,0.18)'
          div.style.borderTop = '1px dashed rgba(249,115,22,0.45)'
          div.style.borderBottom = '1px dashed rgba(249,115,22,0.45)'
        }else{
          div.style.background = 'rgba(14,165,233,0.15)'
          div.style.borderTop = '1px dashed rgba(14,165,233,0.45)'
          div.style.borderBottom = '1px dashed rgba(14,165,233,0.45)'
        }
        overlay.appendChild(div)
      })
    }

    drawBoxes()

    // Liqudation price line (grey dotted)
    if (typeof overlays?.liq === 'number'){
      series.createPriceLine({ price: overlays.liq, color: '#9ca3af', lineWidth: 1, lineStyle: 1, title: 'Liq' })
    }
    // Funding window vertical highlights (± minutes around time)
    const vOverlay = document.createElement('div')
    vOverlay.style.position = 'absolute'
    vOverlay.style.inset = '0'
    vOverlay.style.pointerEvents = 'none'
    ref.current.appendChild(vOverlay)
    function drawFunding(){
      vOverlay.innerHTML=''
      const funding = overlays?.funding || []
      if(!funding || funding.length===0) return
      const timeToX = (ms:number): number => {
        const v = chart.timeScale().timeToCoordinate((ms/1000) as any)
        return typeof v === 'number' ? v : 0
      }
      const h = ref.current?.clientHeight || 0
      const msPerMin = 60_000
      for(const win of funding){
        const x = timeToX(win.timeMs)
        const pad = Math.max(1, (win.windowMin||10) * 0.35) // approx pixels per minute
        const left = Math.max(0, x - pad)
        const right = Math.max(0, (ref.current?.clientWidth||0) - (x + pad))
        const div = document.createElement('div')
        div.style.position='absolute'
        div.style.left = `${left}px`
        div.style.right = `${right}px`
        div.style.top = `0px`
        div.style.height = `${h}px`
        div.style.background = 'rgba(59,130,246,0.08)'
        div.style.borderLeft = '1px solid rgba(59,130,246,0.35)'
        div.style.borderRight = '1px solid rgba(59,130,246,0.35)'
        vOverlay.appendChild(div)
      }
    }
    drawFunding()

    chart.timeScale().subscribeVisibleTimeRangeChange(()=> drawBoxes())
    const ro = new ResizeObserver(()=> {
      if(!ref.current) return
      const w2 = ref.current.clientWidth
      const h2 = ref.current.clientHeight || h
      chart.applyOptions({ width: w2, height: h2 });
      drawBoxes()
    })
    if(ref.current) ro.observe(ref.current)
    return ()=>{ ro.disconnect(); chart.remove(); try{ overlay.remove() }catch{} try{ vOverlay.remove() }catch{} }
  },[JSON.stringify(data), JSON.stringify(overlays)])
  return <div ref={ref} className={`w-full ${className||''}`} />
}
