"use client"
export default function Spot2View({ spot2, decimals, fmt:fmtProp }:{ spot2:any, decimals?:number, fmt?:(n:number)=>string|number }){
  if(!spot2) return null
  const entries = Array.isArray(spot2.entries) ? spot2.entries : []
  const tp = Array.isArray(spot2.tp) ? spot2.tp : []
  const sr = spot2.sr || {}
  const m = spot2.metrics || {}
  const macro = spot2.macro_gate || {}
  const buyback = Array.isArray(spot2.buyback) ? spot2.buyback : []
  const notes = Array.isArray(spot2.notes) ? spot2.notes : []
  const warnings = Array.isArray(spot2.warnings) ? spot2.warnings : []
  const dec = typeof decimals==='number' ? decimals : (typeof m.price_decimals==='number'? m.price_decimals : 5)
  const fmt = (n:number)=> typeof fmtProp==='function' ? fmtProp(n) : (typeof n==='number'? n.toFixed(dec): n as any)
  const joinFmt = (arr:any[])=> (arr||[]).map((x:any)=> typeof x==='number'? fmt(x): x).join(' – ')
  return (
    <section className="rounded-xl ring-1 ring-zinc-200 dark:ring-white/10 bg-white/5 p-3 text-sm">
      <div className="flex flex-wrap items-center gap-2 text-xs text-zinc-500 mb-1">
        <span className="px-2 py-0.5 rounded bg-cyan-600/10 text-cyan-700 dark:text-cyan-300">{spot2.trade_type?.toUpperCase?.() || 'SPOT'}</span>
        {spot2.regime?.regime && <span>Regime: {spot2.regime.regime} ({typeof spot2.regime.confidence==='number'? (spot2.regime.confidence*100).toFixed(0):'-'}%)</span>}
        {spot2.mode && <span>Mode: {spot2.mode}</span>}
        {typeof m.macro_score==='number' && <span>Macro Score: {m.macro_score?.toFixed?.(1)} / {m.macro_score_threshold ?? '-'}</span>}
      </div>
      {spot2.ringkas_teknis && (
        <div className="mb-2">
          <div className="text-zinc-500">Ringkas Teknis</div>
          <div>{spot2.ringkas_teknis}</div>
        </div>
      )}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
        <div>
          <div className="text-zinc-500">Entries ({spot2.mode||'-'})</div>
          <ul className="list-disc pl-5">
            {entries.map((e:any,i:number)=> (
              <li key={i} className="space-y-0.5">
                <div>Harga: {typeof e.price==='number'? fmt(e.price): joinFmt(e.range||[])} • w={e.weight ?? '-'} • {e.type||spot2.mode||'PB'}</div>
                {e.note && <div className="text-xs text-zinc-500">{e.note}</div>}
              </li>
            ))}
            {entries.length===0 && <li>Tidak ada entry.</li>}
          </ul>
        </div>
        <div>
          <div className="text-zinc-500">Invalid</div>
          <div className="text-rose-500 font-medium">{typeof spot2.invalid==='number'? fmt(spot2.invalid): spot2.invalid ?? '-'}</div>
        </div>
        <div className="md:col-span-2">
          <div className="text-zinc-500">TP</div>
          <ul className="list-disc pl-5 text-emerald-600">
            {tp.map((t:any,i:number)=> (
              <li key={i}>
                {t.name||`TP${i+1}`}: {typeof t.price==='number'? fmt(t.price): joinFmt(t.range||[])} • {t.qty_pct ?? '-'}% — {t.logic||'-'}
              </li>
            ))}
          </ul>
        </div>
        <div>
          <div className="text-zinc-500">Support</div>
          <div>{(sr.support||[]).map((x:number)=> fmt(x)).join(' · ')||'-'}</div>
        </div>
        <div>
          <div className="text-zinc-500">Resistance</div>
          <div>{(sr.resistance||[]).map((x:number)=> fmt(x)).join(' · ')||'-'}</div>
        </div>
        <div>
          <div className="text-zinc-500">RR Min</div>
          <div className="text-cyan-600">{typeof m.rr_min==='number'? m.rr_min.toFixed(2):'-'}</div>
        </div>
        {spot2.trailing && (
          <div>
            <div className="text-zinc-500">Trailing</div>
            <div>{spot2.trailing.enabled? `Aktif (${spot2.trailing.anchor||'-'}, offset ${spot2.trailing.offset_atr ?? '-' }×ATR)` : 'Nonaktif'}</div>
          </div>
        )}
        {spot2.time_exit && (
          <div>
            <div className="text-zinc-500">Time Exit</div>
            <div>{spot2.time_exit.enabled? `${spot2.time_exit.ttl_min||'-'} menit • ${spot2.time_exit.reason||'-'}`:'Nonaktif'}</div>
          </div>
        )}
      </div>
      {buyback.length>0 && (
        <div className="mt-3">
          <div className="text-zinc-500">Buyback</div>
          <ul className="list-disc pl-5">
            {buyback.map((bb:any,i:number)=> (
              <li key={i}>{bb.name||`BB${i+1}`}: {joinFmt(bb.range||[])} — {bb.note||'-'}</li>
            ))}
          </ul>
        </div>
      )}
      {macro && (
        <div className="mt-3 grid grid-cols-1 md:grid-cols-2 gap-3">
          <div>
            <div className="text-zinc-500">Window Hijau (WIB)</div>
            <div>{(macro.prefer_wib||[]).join(', ')||'-'}</div>
          </div>
          <div>
            <div className="text-zinc-500">Hindari (WIB)</div>
            <div>{(macro.avoid_wib||[]).join(', ')||'-'}</div>
          </div>
          <div className="md:col-span-2">
            <div className="text-zinc-500">Catatan Sesi</div>
            <div>{macro.session_refs || '-'}</div>
          </div>
        </div>
      )}
      {notes.length>0 && (
        <div className="mt-3">
          <div className="text-zinc-500">Catatan Eksekusi</div>
          <ul className="list-disc pl-5">{notes.map((n:string,i:number)=> <li key={i}>{n}</li>)}</ul>
        </div>
      )}
      {warnings.length>0 && (
        <div className="mt-3">
          <div className="text-rose-500">Peringatan</div>
          <ul className="list-disc pl-5 text-rose-500/80">{warnings.map((w:string,i:number)=> <li key={i}>{w}</li>)}</ul>
        </div>
      )}
    </section>
  )
}
