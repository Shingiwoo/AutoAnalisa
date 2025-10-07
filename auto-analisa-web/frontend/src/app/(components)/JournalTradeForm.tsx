"use client"
import { useMemo, useState } from "react"
import { api } from "../api"

export default function JournalTradeForm({ onSaved }:{ onSaved: ()=>void }){
  const [entryAt, setEntryAt] = useState("")
  const [exitAt, setExitAt] = useState("")
  const [pair, setPair] = useState("")
  const [arah, setArah] = useState("LONG")
  const [entryPrice, setEntryPrice] = useState<string>("")
  const [exitPrice, setExitPrice] = useState<string>("")
  const [slPrice, setSlPrice] = useState<string>("")
  const [bePrice, setBePrice] = useState<string>("")
  const [tp1, setTp1] = useState<string>("")
  const [tp2, setTp2] = useState<string>("")
  const [tp3, setTp3] = useState<string>("")
  const [saldoAwal, setSaldoAwal] = useState<string>("")
  const [margin, setMargin] = useState<string>("")
  const [leverage, setLeverage] = useState<string>("")
  const [equity, setEquity] = useState<string>("")
  const [strategy, setStrategy] = useState("")
  const [market, setMarket] = useState("")
  const [notes, setNotes] = useState("")
  const [saving, setSaving] = useState(false)
  const [err, setErr] = useState("")

  const sisaSaldo = useMemo(()=>{
    const a = parseFloat(saldoAwal||"NaN"); const m = parseFloat(margin||"NaN");
    if (!Number.isFinite(a) || !Number.isFinite(m)) return ""
    return (a - m).toString()
  },[saldoAwal, margin])

  const rr = useMemo(()=>{
    const e = parseFloat(entryPrice||"NaN"); const s = parseFloat(slPrice||"NaN");
    const t1 = parseFloat(tp1||"NaN"); const t2 = parseFloat(tp2||"NaN"); const t3 = parseFloat(tp3||"NaN");
    if (!Number.isFinite(e) || !Number.isFinite(s)) return ""
    const tps = [t1, t2, t3].filter(Number.isFinite) as number[]
    if (!tps.length) return ""
    const risk = Math.abs(e - s); if (risk<=0) return ""
    return tps.map(tp=>`1:${(Math.abs(tp - e)/risk).toFixed(1)}`).join(" | ")
  },[entryPrice, slPrice, tp1, tp2, tp3])

  async function submit(e: React.FormEvent){
    e.preventDefault(); setErr(""); setSaving(true)
    try{
      const body:any = {
        entry_at: entryAt,
        exit_at: exitAt || undefined,
        pair: pair.toUpperCase(),
        arah,
        entry_price: entryPrice? Number(entryPrice): undefined,
        exit_price: exitPrice? Number(exitPrice): undefined,
        sl_price: slPrice? Number(slPrice): undefined,
        be_price: bePrice? Number(bePrice): undefined,
        tp1_price: tp1? Number(tp1): undefined,
        tp2_price: tp2? Number(tp2): undefined,
        tp3_price: tp3? Number(tp3): undefined,
        saldo_awal: saldoAwal? Number(saldoAwal): undefined,
        margin: margin? Number(margin): undefined,
        leverage: leverage? Number(leverage): undefined,
        sisa_saldo: sisaSaldo? Number(sisaSaldo): undefined,
        equity_balance: equity? Number(equity): undefined,
        strategy, market_condition: market, notes,
      }
      await api.post('/trade-journal', body)
      // reset minimal
      setNotes("")
      onSaved()
    }catch(e:any){
      setErr(e?.response?.data?.detail || 'Gagal menyimpan. Pastikan field wajib terisi.')
    }finally{ setSaving(false) }
  }

  return (
    <section className="rounded-2xl ring-1 ring-white/10 bg-white/50 dark:bg-white/5 backdrop-blur p-4">
      <h2 className="font-semibold mb-3">Tambah Trade</h2>
      {err && <div className="mb-3 rounded bg-rose-500/10 text-rose-400 ring-1 ring-inset ring-rose-500/20 px-3 py-2 text-sm">{err}</div>}
      <form onSubmit={submit} className="grid gap-3 md:grid-cols-4">
        <div className="md:col-span-2">
          <label className="block text-xs text-zinc-500 mb-1">Datetime Entry</label>
          <input type="datetime-local" value={entryAt} onChange={e=>setEntryAt(e.target.value)} required className="w-full rounded px-3 py-2 ring-1 ring-inset ring-zinc-200 focus:outline-none focus:ring-2 focus:ring-cyan-500 bg-white text-zinc-900"/>
        </div>
        <div className="md:col-span-2">
          <label className="block text-xs text-zinc-500 mb-1">Datetime Exit</label>
          <input type="datetime-local" value={exitAt} onChange={e=>setExitAt(e.target.value)} className="w-full rounded px-3 py-2 ring-1 ring-inset ring-zinc-200 focus:outline-none focus:ring-2 focus:ring-cyan-500 bg-white text-zinc-900"/>
        </div>
        <div>
          <label className="block text-xs text-zinc-500 mb-1">Pair</label>
          <input value={pair} onChange={e=>setPair(e.target.value)} placeholder="BTCUSDT" required className="w-full rounded px-3 py-2 ring-1 ring-inset ring-zinc-200 focus:outline-none focus:ring-2 focus:ring-cyan-500 bg-white text-zinc-900"/>
        </div>
        <div>
          <label className="block text-xs text-zinc-500 mb-1">Arah</label>
          <div className="flex gap-3">
            <label className="inline-flex items-center gap-1"><input type="radio" name="arah" checked={arah==='LONG'} onChange={()=>setArah('LONG')} /> LONG</label>
            <label className="inline-flex items-center gap-1"><input type="radio" name="arah" checked={arah==='SHORT'} onChange={()=>setArah('SHORT')} /> SHORT</label>
          </div>
        </div>
        <div>
          <label className="block text-xs text-zinc-500 mb-1">Entry Price</label>
          <input value={entryPrice} onChange={e=>setEntryPrice(e.target.value)} inputMode="decimal" className="w-full rounded px-3 py-2 ring-1 ring-inset ring-zinc-200 focus:outline-none focus:ring-2 focus:ring-cyan-500 bg-white text-zinc-900"/>
        </div>
        <div>
          <label className="block text-xs text-zinc-500 mb-1">Exit Price</label>
          <input value={exitPrice} onChange={e=>setExitPrice(e.target.value)} inputMode="decimal" className="w-full rounded px-3 py-2 ring-1 ring-inset ring-zinc-200 focus:outline-none focus:ring-2 focus:ring-cyan-500 bg-white text-zinc-900"/>
        </div>
        <div>
          <label className="block text-xs text-zinc-500 mb-1">SL</label>
          <input value={slPrice} onChange={e=>setSlPrice(e.target.value)} inputMode="decimal" className="w-full rounded px-3 py-2 ring-1 ring-inset ring-zinc-200 focus:outline-none focus:ring-2 focus:ring-cyan-500 bg-white text-zinc-900"/>
        </div>
        <div>
          <label className="block text-xs text-zinc-500 mb-1">BE</label>
          <input value={bePrice} onChange={e=>setBePrice(e.target.value)} inputMode="decimal" className="w-full rounded px-3 py-2 ring-1 ring-inset ring-zinc-200 focus:outline-none focus:ring-2 focus:ring-cyan-500 bg-white text-zinc-900"/>
        </div>
        <div>
          <label className="block text-xs text-zinc-500 mb-1">TP1</label>
          <input value={tp1} onChange={e=>setTp1(e.target.value)} inputMode="decimal" className="w-full rounded px-3 py-2 ring-1 ring-inset ring-zinc-200 focus:outline-none focus:ring-2 focus:ring-cyan-500 bg-white text-zinc-900"/>
        </div>
        <div>
          <label className="block text-xs text-zinc-500 mb-1">TP2</label>
          <input value={tp2} onChange={e=>setTp2(e.target.value)} inputMode="decimal" className="w-full rounded px-3 py-2 ring-1 ring-inset ring-zinc-200 focus:outline-none focus:ring-2 focus:ring-cyan-500 bg-white text-zinc-900"/>
        </div>
        <div>
          <label className="block text-xs text-zinc-500 mb-1">TP3</label>
          <input value={tp3} onChange={e=>setTp3(e.target.value)} inputMode="decimal" className="w-full rounded px-3 py-2 ring-1 ring-inset ring-zinc-200 focus:outline-none focus:ring-2 focus:ring-cyan-500 bg-white text-zinc-900"/>
        </div>
        <div>
          <label className="block text-xs text-zinc-500 mb-1">Saldo Awal</label>
          <input value={saldoAwal} onChange={e=>setSaldoAwal(e.target.value)} inputMode="decimal" className="w-full rounded px-3 py-2 ring-1 ring-inset ring-zinc-200 focus:outline-none focus:ring-2 focus:ring-cyan-500 bg-white text-zinc-900"/>
        </div>
        <div>
          <label className="block text-xs text-zinc-500 mb-1">Margin</label>
          <input value={margin} onChange={e=>setMargin(e.target.value)} inputMode="decimal" className="w-full rounded px-3 py-2 ring-1 ring-inset ring-zinc-200 focus:outline-none focus:ring-2 focus:ring-cyan-500 bg-white text-zinc-900"/>
        </div>
        <div>
          <label className="block text-xs text-zinc-500 mb-1">Leverage</label>
          <input value={leverage} onChange={e=>setLeverage(e.target.value)} inputMode="decimal" className="w-full rounded px-3 py-2 ring-1 ring-inset ring-zinc-200 focus:outline-none focus:ring-2 focus:ring-cyan-500 bg-white text-zinc-900"/>
        </div>
        <div>
          <label className="block text-xs text-zinc-500 mb-1">Equity Balance</label>
          <input value={equity} onChange={e=>setEquity(e.target.value)} inputMode="decimal" className="w-full rounded px-3 py-2 ring-1 ring-inset ring-zinc-200 focus:outline-none focus:ring-2 focus:ring-cyan-500 bg-white text-zinc-900"/>
        </div>
        <div className="md:col-span-2 text-sm text-zinc-600">Sisa Saldo (auto): <span className="font-medium text-zinc-900">{sisaSaldo || '-'}</span></div>
        <div className="md:col-span-2 text-sm text-zinc-600">Risk:Reward (preview): <span className="font-medium text-zinc-900">{rr || '-'}</span></div>
        <div className="md:col-span-4">
          <label className="block text-xs text-zinc-500 mb-1">Strategi & Kondisi Pasar</label>
          <div className="grid gap-2 md:grid-cols-2">
            <input value={strategy} onChange={e=>setStrategy(e.target.value)} placeholder="Strategi" className="rounded px-3 py-2 ring-1 ring-inset ring-zinc-200 focus:outline-none focus:ring-2 focus:ring-cyan-500 bg-white text-zinc-900"/>
            <input value={market} onChange={e=>setMarket(e.target.value)} placeholder="Kondisi pasar" className="rounded px-3 py-2 ring-1 ring-inset ring-zinc-200 focus:outline-none focus:ring-2 focus:ring-cyan-500 bg-white text-zinc-900"/>
          </div>
        </div>
        <div className="md:col-span-4">
          <label className="block text-xs text-zinc-500 mb-1">Catatan</label>
          <textarea value={notes} onChange={e=>setNotes(e.target.value)} rows={3} className="w-full rounded px-3 py-2 ring-1 ring-inset ring-zinc-200 focus:outline-none focus:ring-2 focus:ring-cyan-500 bg-white text-zinc-900"/>
        </div>
        <div className="md:col-span-4">
          <button disabled={saving} className="rounded px-4 py-2 bg-cyan-600 text-white hover:bg-cyan-500 disabled:opacity-50">{saving? 'Menyimpan…':'Simpan'}</button>
        </div>
      </form>
    </section>
  )
}

