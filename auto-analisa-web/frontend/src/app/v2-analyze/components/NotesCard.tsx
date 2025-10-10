"use client"
export default function NotesCard({ data }: { data: any }){
  const rangkuman = data?.rangkuman || {}
  const pos = data?.penjelasan_posisi || {}
  const risk = data?.risk_management || {}
  const disc = data?.disclaimer || ''
  return (
    <div className="rounded-xl ring-1 ring-white/10 bg-black/20 p-4 text-sm text-zinc-200 space-y-3">
      <div>
        <div className="font-semibold mb-1">Rangkuman</div>
        <div className="text-xs opacity-90">{rangkumaan(rangkuman)}</div>
      </div>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
        <div>
          <div className="text-xs font-medium mb-1">Kenapa LONG</div>
          <ul className="list-disc ml-5 text-xs opacity-90">{(pos?.kenapa_LONG||[]).map((t:string,i:number)=>(<li key={i}>{t}</li>))}</ul>
        </div>
        <div>
          <div className="text-xs font-medium mb-1">Kapan SHORT</div>
          <ul className="list-disc ml-5 text-xs opacity-90">{(pos?.kapan_SHORT||[]).map((t:string,i:number)=>(<li key={i}>{t}</li>))}</ul>
        </div>
      </div>
      <div>
        <div className="text-xs font-medium mb-1">Risk Management</div>
        <pre className="text-xs whitespace-pre-wrap opacity-90">{JSON.stringify(risk, null, 2)}</pre>
      </div>
      {disc && <div className="text-[11px] opacity-80">{disc}</div>}
    </div>
  )
}

function rangkumaan(r: any): string{
  const parts: string[] = []
  if (r?.narasi) parts.push(String(r.narasi))
  if (r?.invalidasi_utama) parts.push(`Invalidasi: ${r.invalidasi_utama}`)
  return parts.join('\n')
}

