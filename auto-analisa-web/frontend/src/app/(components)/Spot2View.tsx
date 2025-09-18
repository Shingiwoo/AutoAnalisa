"use client"
export default function Spot2View({ spot2, decimals, fmt:fmtProp }:{ spot2:any, decimals?:number, fmt?:(n:number)=>string|number }){
  if(!spot2) return null
  const rjb = spot2.rencana_jual_beli || {}
  const tp = spot2.tp || []
  const sr = spot2.sr || {}
  const m = spot2.metrics || {}
  const dec = typeof decimals==='number' ? decimals : (typeof m.price_decimals==='number'? m.price_decimals : 5)
  const fmt = (n:number)=> typeof fmtProp==='function' ? fmtProp(n) : (typeof n==='number'? n.toFixed(dec): n as any)
  const joinFmt = (arr:any[])=> (arr||[]).map((x:any)=> typeof x==='number'? fmt(x): x).join(' – ')
  return (
    <section className="rounded-xl ring-1 ring-zinc-200 dark:ring-white/10 bg-white/5 p-3 text-sm">
      {spot2.ringkas_teknis && (
        <div className="mb-2">
          <div className="text-zinc-500">Ringkas Teknis</div>
          <div>{spot2.ringkas_teknis}</div>
        </div>
      )}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
        <div>
          <div className="text-zinc-500">Rencana Jual–Beli ({rjb.profile||'-'})</div>
          <ul className="list-disc pl-5">
            {(rjb.entries||[]).map((e:any,i:number)=> (
              <li key={i}>Range: {joinFmt(e.range||[])} • w={e.weight} • {e.type||'PB'}</li>
            ))}
          </ul>
        </div>
        <div>
          <div className="text-zinc-500">Invalid</div>
          <div className="text-rose-500 font-medium">{typeof rjb.invalid==='number'? fmt(rjb.invalid): rjb.invalid}</div>
        </div>
        <div className="md:col-span-2">
          <div className="text-zinc-500">TP</div>
          <div className="text-emerald-600">{tp.map((t:any)=> `${t.name||''}: ${joinFmt(t.range||[])}`).join(' • ')}</div>
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
      </div>
      {spot2.fail_safe && spot2.fail_safe.length>0 && (
        <div className="mt-2">
          <div className="text-zinc-500">Fail-safe</div>
          <ul className="list-disc pl-5">{spot2.fail_safe.map((f:string,i:number)=> <li key={i}>{f}</li>)}</ul>
        </div>
      )}
    </section>
  )
}
