'use client'
export default function PlanCard({plan, onUpdate}:{plan:any,onUpdate:()=>void}){
  const p=plan.payload
  return (
    <div className="p-4 rounded-2xl shadow bg-white space-y-2">
      <div className="text-lg font-semibold">{plan.symbol} • v{plan.version} • Skor {p.score}</div>
      <div className="text-sm opacity-70">{new Date(plan.created_at).toLocaleString('id-ID')}</div>
      <div className="whitespace-pre-wrap text-sm">
        <b>Bias Dominan:</b> {p.bias}
        {'\n'}<b>Level Kunci</b>{'\n'}Support: {p.support.join(' · ')}{'\n'}Resistance: {p.resistance.join(' · ')}
        {'\n'}<b>Rencana Eksekusi (spot)</b>{'\n'}PB: {p.entries.join(' / ')} (w={p.weights.join('/')}) • Invalid: {p.invalid}
        {'\n'}TP: {p.tp.join(' → ')}
        {'\n'}<b>Bacaan Sinyal:</b> {p.narrative}
      </div>
      <button onClick={onUpdate} className="px-3 py-2 rounded bg-zinc-900 text-white">Update</button>
    </div>
  )
}

