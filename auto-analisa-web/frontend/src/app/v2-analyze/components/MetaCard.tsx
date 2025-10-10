"use client"
export default function MetaCard({ data }: { data: any }){
  const meta = data?.metadata || {}
  const rangkuman = data?.rangkuman || {}
  const bias = (rangkuman?.bias_dominan || '').toString().toLowerCase()
  const biasCls = bias==='long'? 'bg-emerald-600' : bias==='short'? 'bg-rose-600' : 'bg-zinc-600'
  return (
    <div className="rounded-xl ring-1 ring-white/10 bg-black/20 p-4 text-sm text-zinc-200">
      <div className="flex items-center justify-between mb-2">
        <div className="font-semibold">{meta?.symbol || '-'}</div>
        <span className={`px-2 py-0.5 rounded text-white text-xs ${biasCls}`}>{bias? bias.toUpperCase():'-'}</span>
      </div>
      <div className="grid grid-cols-2 md:grid-cols-4 gap-2 text-xs opacity-90">
        <div>Market: {meta?.market || '-'}</div>
        <div>Now: {typeof meta?.harga_saat_ini==='number'? meta.harga_saat_ini.toFixed(6) : '-'}</div>
        <div>Generated: {meta?.generated_at || '-'}</div>
        <div>Source: {meta?.sumber || '-'}</div>
      </div>
    </div>
  )
}

