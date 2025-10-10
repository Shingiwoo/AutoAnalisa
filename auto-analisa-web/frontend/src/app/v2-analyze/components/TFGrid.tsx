"use client"
function Block({ title, blk }: { title: string, blk: any }){
  return (
    <div className="rounded-lg ring-1 ring-white/10 bg-zinc-900/60 p-3 text-xs text-zinc-200">
      <div className="text-zinc-100 font-semibold mb-1">{title}</div>
      <div>Bias: {blk?.bias || '-'}</div>
      <div>Kondisi: {blk?.kondisi || '-'}</div>
      <div className="mt-1">Support: {(blk?.support||[]).slice(0,3).map((v:number,i:number)=>(<span key={i} className="mr-2">{typeof v==='number'? v.toFixed(6): v}</span>))}</div>
      <div>Resistance: {(blk?.resistance||[]).slice(0,3).map((v:number,i:number)=>(<span key={i} className="mr-2">{typeof v==='number'? v.toFixed(6): v}</span>))}</div>
      <div className="mt-1 opacity-80">EMA: {blk?.indikator?.EMA || '-'}</div>
      <div className="opacity-80">MACD: {blk?.indikator?.MACD || '-'}</div>
      <div className="opacity-80">RSI: {blk?.indikator?.RSI ?? '-'}</div>
    </div>
  )
}

export default function TFGrid({ data }: { data: any }){
  const mtf = data?.multi_timeframe || {}
  return (
    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-3">
      <Block title="M15" blk={mtf?.M15} />
      <Block title="H1" blk={mtf?.H1} />
      <Block title="H4" blk={mtf?.H4} />
      <Block title="D1" blk={mtf?.D1} />
    </div>
  )
}

