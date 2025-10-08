"use client"
import type { ContextBlock } from "../../lib/types/context"

function Chip({children, color}:{children: any, color?: string}){
  const cls = color || 'bg-zinc-800 text-white'
  return <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs ${cls}`}>{children}</span>
}

export default function ContextBadges({ ctx }:{ ctx: ContextBlock | undefined }){
  if (!ctx) return null
  const f = ctx.funding
  const mx = ctx.alt_btc
  const d = ctx.btcd
  const po = ctx.price_oi
  const fColor = f?.score>0? 'bg-emerald-700 text-white' : f?.score<0? 'bg-rose-700 text-white' : 'bg-zinc-700 text-white'
  const dColor = d?.dir==='LONG'? 'bg-emerald-700 text-white' : d?.dir==='SHORT'? 'bg-rose-700 text-white' : 'bg-zinc-700 text-white'
  const mxColor = mx?.dir==='LONG'? 'bg-emerald-700 text-white' : mx?.dir==='SHORT'? 'bg-rose-700 text-white' : 'bg-zinc-700 text-white'
  const poColor = (po?.label||'').includes('NAIK')? 'bg-emerald-700 text-white' : (po?.label||'').includes('TURUN')? 'bg-rose-700 text-white' : 'bg-zinc-700 text-white'
  return (
    <div className="flex flex-wrap gap-2 text-xs">
      <Chip color={fColor}>Funding {f?.score>0?'+':' '}{(Number(f?.rate||0)*100).toFixed(3)}bp</Chip>
      <Chip color={mxColor}>ALT×BTC: {mx?.label}</Chip>
      {d && <Chip color={dColor}>BTC.D: {d?.dir==='LONG'? '▼ ALTS UP' : d?.dir==='SHORT'? '▲ ALTS DOWN' : 'NEUTRAL'}</Chip>}
      <Chip color={poColor}>Price×OI: {po?.label}</Chip>
    </div>
  )
}

