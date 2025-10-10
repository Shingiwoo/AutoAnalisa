"use client"
function fmt(n:any){ const v=Number(n); if(Number.isNaN(v)) return '-'; const d=v>=1000?2:v>=100?3:v>=1?4:6; return v.toFixed(d) }

function Card({ title, items }: { title: string, items: any[] }){
  return (
    <div className="rounded-lg ring-1 ring-white/10 bg-zinc-900/60 p-3 text-xs text-zinc-200">
      <div className="text-zinc-100 font-semibold mb-2">{title}</div>
      <div className="space-y-1">
        {items.map((it,idx)=> (
          <div key={idx} className="flex items-center justify-between"><span className="opacity-80">{it.k}:</span> <span>{it.v}</span></div>
        ))}
      </div>
    </div>
  )
}

export default function StrategyCards({ data }: { data: any }){
  const st = data?.strategi || {}
  const sc = st?.scalping || {}
  const sw = st?.swing || {}
  const itemsSc = [
    { k:'Timeframe', v: sc?.timeframe || '-' },
    { k:'Entries', v: (sc?.entry_zone||[]).slice(0,2).map((x:number)=>fmt(x)).join(', ') || '-' },
    { k:'TP', v: (sc?.take_profit||[]).slice(0,2).map((x:number)=>fmt(x)).join(', ') || '-' },
    { k:'SL', v: fmt(sc?.stop_loss) },
    { k:'Leverage', v: sc?.leverage_saran || '-' },
    { k:'Risk/Trade', v: sc?.alokasi_risiko_per_trade || '-' },
  ]
  const itemsSw = [
    { k:'Timeframe', v: sw?.timeframe || '-' },
    { k:'Entry Utama', v: (sw?.entry_zone_utama||[]).slice(0,2).map((x:number)=>fmt(x)).join(', ') || '-' },
    { k:'TP', v: ['TP1','TP2','TP3'].map(k=> sw?.take_profit?.[k]).filter(Boolean).map((x:number)=>fmt(x)).join(', ') || '-' },
    { k:'SL', v: fmt(sw?.stop_loss) },
    { k:'Leverage', v: sw?.leverage_saran || '-' },
    { k:'Risk/Trade', v: sw?.alokasi_risiko_per_trade || '-' },
  ]
  return (
    <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
      <Card title="Scalping" items={itemsSc} />
      <Card title="Swing" items={itemsSw} />
    </div>
  )
}

