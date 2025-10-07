"use client"
import { useEffect, useMemo, useState } from "react"
import { api } from "../api"

type TJ = {
  id: number
  entry_at: string
  exit_at?: string
  pair: string
  arah: string
  status: string
  saldo_awal?: number
  equity_balance?: number
  pnl_pct: number
  notes: string
  entry_price?: number
  exit_price?: number
  tp1_status?: string
  tp2_status?: string
  tp3_status?: string
  sl_status?: string
  be_status?: string
  winloss?: string
}

export default function JournalTradeTable(){
  const [rows,setRows] = useState<TJ[]>([])
  const [loading,setLoading] = useState(true)
  const [err,setErr] = useState("")
  const [pair,setPair] = useState("")
  const [status,setStatus] = useState("")
  const [start,setStart] = useState("")
  const [end,setEnd] = useState("")

  const [editId,setEditId]=useState<number|null>(null)
  const [editExitAt,setEditExitAt]=useState("")
  const [editExitPrice,setEditExitPrice]=useState("")
  const [editNotes,setEditNotes]=useState("")
  const [etp1,setEtp1]=useState("PENDING")
  const [etp2,setEtp2]=useState("PENDING")
  const [etp3,setEtp3]=useState("PENDING")
  const [esl,setEsl]=useState("PENDING")
  const [ebe,setEbe]=useState("PENDING")
  const [estat,setEstat]=useState("OPEN")
  const [autoBE,setAutoBE]=useState(true)
  const [autoTP1,setAutoTP1]=useState(false)

  async function load(){
    setLoading(true); setErr("")
    try{
      const r = await api.get('/trade-journal', { params: { pair: pair||undefined, status: status||undefined, start: start||undefined, end: end||undefined, limit: 100 } })
      setRows(r.data||[])
    }catch(e:any){ setErr('Gagal memuat data') }
    finally{ setLoading(false) }
  }

  useEffect(()=>{ load() },[])

  function startEdit(it: TJ){
    setEditId(it.id)
    setEditExitAt(it.exit_at?.slice(0,16) || "")
    setEditExitPrice((it.exit_price ?? "").toString())
    setEditNotes(it.notes||"")
    setEtp1(it.tp1_status||"PENDING")
    setEtp2(it.tp2_status||"PENDING")
    setEtp3(it.tp3_status||"PENDING")
    setEsl(it.sl_status||"PENDING")
    setEbe(it.be_status||"PENDING")
    setEstat(it.status||"OPEN")
  }

  function cancelEdit(){
    setEditId(null); setEditExitAt(""); setEditExitPrice(""); setEditNotes("")
  }

  async function saveEdit(){
    if(editId==null) return
    try{
      const body:any = { notes: editNotes, tp1_status: etp1, tp2_status: etp2, tp3_status: etp3, sl_status: esl, be_status: ebe, status: estat, auto_move_sl_to_be: autoBE, auto_lock_tp1: autoTP1 }
      if(editExitAt) body.exit_at = editExitAt
      if(editExitPrice) body.exit_price = Number(editExitPrice)
      const r = await api.put(`/trade-journal/${editId}`, body)
      setRows(prev=> prev.map(x=> x.id===editId ? r.data : x))
      cancelEdit()
    }catch{ alert('Gagal menyimpan') }
  }

  async function closeTrade(it: TJ){
    const now = new Date();
    const isoLocal = new Date(now.getTime() - now.getTimezoneOffset()*60000).toISOString().slice(0,16)
    try{
      const r = await api.put(`/trade-journal/${it.id}`, { status: 'CLOSED', exit_at: isoLocal })
      setRows(prev=> prev.map(x=> x.id===it.id ? r.data : x))
    }catch{ alert('Gagal close') }
  }

  async function del(id:number){
    if(!confirm('Hapus trade ini?')) return
    try{
      await api.delete(`/trade-journal/${id}`)
      setRows(prev=> prev.filter(x=> x.id!==id))
    }catch{ alert('Gagal hapus') }
  }

  const exportHref = useMemo(()=>{
    const p = new URLSearchParams()
    if(pair) p.set('pair', pair)
    if(status) p.set('status', status)
    if(start) p.set('start', start)
    if(end) p.set('end', end)
    return `/api/trade-journal/export${p.toString()?('?' + p.toString()):''}`
  },[pair,status,start,end])

  return (
    <section className="rounded-2xl ring-1 ring-white/10 bg-white/50 dark:bg-white/5 backdrop-blur p-4">
      <div className="flex flex-col md:flex-row md:items-end gap-2 md:gap-3 mb-3">
        <div>
          <div className="text-xs text-zinc-500 mb-1">Pair</div>
          <input value={pair} onChange={e=>setPair(e.target.value.toUpperCase())} placeholder="BTCUSDT" className="rounded px-3 py-1.5 ring-1 ring-inset ring-zinc-200 focus:outline-none focus:ring-2 focus:ring-cyan-500 bg-white text-zinc-900" />
        </div>
        <div>
          <div className="text-xs text-zinc-500 mb-1">Status</div>
          <select value={status} onChange={e=>setStatus(e.target.value)} className="rounded px-3 py-1.5 ring-1 ring-inset ring-zinc-200 bg-white text-zinc-900">
            <option value="">Semua</option>
            <option value="OPEN">OPEN</option>
            <option value="CLOSED">CLOSED</option>
          </select>
        </div>
        <div>
          <div className="text-xs text-zinc-500 mb-1">Dari</div>
          <input type="datetime-local" value={start} onChange={e=>setStart(e.target.value)} className="rounded px-3 py-1.5 ring-1 ring-inset ring-zinc-200 bg-white text-zinc-900" />
        </div>
        <div>
          <div className="text-xs text-zinc-500 mb-1">Sampai</div>
          <input type="datetime-local" value={end} onChange={e=>setEnd(e.target.value)} className="rounded px-3 py-1.5 ring-1 ring-inset ring-zinc-200 bg-white text-zinc-900" />
        </div>
        <div className="flex gap-2">
          <button className="rounded px-3 py-1.5 bg-zinc-800 text-white hover:bg-zinc-700" onClick={load}>Terapkan</button>
          <a href={exportHref} target="_blank" className="rounded px-3 py-1.5 bg-cyan-600 text-white hover:bg-cyan-500">Export CSV</a>
        </div>
      </div>

      {loading ? (
        <div className="text-sm text-zinc-500">Memuat…</div>
      ) : err ? (
        <div className="text-sm text-rose-500">{err}</div>
      ) : (
        <div className="overflow-x-auto">
          <table className="min-w-full text-sm">
            <thead>
              <tr className="text-left text-zinc-500 border-b border-white/10">
                <th className="px-3 py-2">No</th>
                <th className="px-3 py-2">Tanggal Entry</th>
                <th className="px-3 py-2">Pair</th>
                <th className="px-3 py-2">Posisi</th>
                <th className="px-3 py-2">Status</th>
                <th className="px-3 py-2">Win/Loss</th>
                <th className="px-3 py-2">Saldo Awal</th>
                <th className="px-3 py-2">Equity</th>
                <th className="px-3 py-2">Profit(%)</th>
                <th className="px-3 py-2">Catatan</th>
                <th className="px-3 py-2">Aksi</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((it, idx)=> (
                <tr key={it.id} className="border-b border-white/10 align-top">
                  <td className="px-3 py-2">{idx+1}</td>
                  <td className="px-3 py-2 whitespace-nowrap">{new Date(it.entry_at).toLocaleString()}</td>
                  <td className="px-3 py-2">{it.pair}</td>
                  <td className="px-3 py-2">{it.arah}</td>
                  <td className="px-3 py-2">{it.status}</td>
                  <td className="px-3 py-2">{it.winloss||'WAITING'}</td>
                  <td className="px-3 py-2">{it.saldo_awal ?? '-'}</td>
                  <td className="px-3 py-2">{it.equity_balance ?? '-'}</td>
                  <td className="px-3 py-2">{(it.pnl_pct||0).toFixed(2)}%</td>
                  <td className="px-3 py-2 max-w-[22rem] whitespace-pre-wrap break-words">{it.notes||'-'}</td>
                  <td className="px-3 py-2">
                    {editId===it.id ? (
                      <div className="space-y-2 w-[260px]">
                        <div className="grid gap-2">
                          <input type="datetime-local" value={editExitAt} onChange={e=>setEditExitAt(e.target.value)} className="w-full rounded px-2 py-1 ring-1 ring-inset ring-zinc-200 bg-white text-zinc-900" />
                          <input value={editExitPrice} onChange={e=>setEditExitPrice(e.target.value)} placeholder="Exit price" className="w-full rounded px-2 py-1 ring-1 ring-inset ring-zinc-200 bg-white text-zinc-900" />
                        </div>
                        <div className="grid grid-cols-2 gap-2">
                          <select value={etp1} onChange={e=>setEtp1(e.target.value)} className="rounded px-2 py-1 ring-1 ring-inset ring-zinc-200"><option>PENDING</option><option>HIT</option><option>FAIL</option></select>
                          <select value={etp2} onChange={e=>setEtp2(e.target.value)} className="rounded px-2 py-1 ring-1 ring-inset ring-zinc-200"><option>PENDING</option><option>HIT</option><option>FAIL</option></select>
                          <select value={etp3} onChange={e=>setEtp3(e.target.value)} className="rounded px-2 py-1 ring-1 ring-inset ring-zinc-200"><option>PENDING</option><option>HIT</option><option>FAIL</option></select>
                          <select value={esl} onChange={e=>setEsl(e.target.value)} className="rounded px-2 py-1 ring-1 ring-inset ring-zinc-200"><option>PENDING</option><option>HIT</option><option>PASS</option></select>
                          <select value={ebe} onChange={e=>setEbe(e.target.value)} className="rounded px-2 py-1 ring-1 ring-inset ring-zinc-200"><option>PENDING</option><option>HIT</option><option>PASS</option></select>
                          <select value={estat} onChange={e=>setEstat(e.target.value)} className="rounded px-2 py-1 ring-1 ring-inset ring-zinc-200"><option>OPEN</option><option>CLOSED</option></select>
                        </div>
                        <label className="flex items-center gap-2 text-xs"><input type="checkbox" checked={autoBE} onChange={e=>setAutoBE(e.target.checked)} /> Auto-SL ke BE saat TP1 HIT</label>
                        <label className="flex items-center gap-2 text-xs"><input type="checkbox" checked={autoTP1} onChange={e=>setAutoTP1(e.target.checked)} /> Kunci SL = TP1 saat TP2 HIT</label>
                        <textarea value={editNotes} onChange={e=>setEditNotes(e.target.value)} rows={2} className="w-full rounded px-2 py-1 ring-1 ring-inset ring-zinc-200 bg-white text-zinc-900" />
                        <div className="flex gap-2">
                          <button className="rounded px-3 py-1 bg-cyan-600 text-white" onClick={saveEdit}>Simpan</button>
                          <button className="rounded px-3 py-1 bg-zinc-800 text-white" onClick={cancelEdit}>Batal</button>
                        </div>
                      </div>
                    ) : (
                      <div className="flex flex-wrap gap-2">
                        <button className="rounded px-3 py-1 bg-zinc-800 text-white hover:bg-zinc-700" onClick={()=>startEdit(it)}>Edit</button>
                        {it.status==='OPEN' && <button className="rounded px-3 py-1 bg-emerald-600 text-white hover:bg-emerald-500" onClick={()=>closeTrade(it)}>Close</button>}
                        <button className="rounded px-3 py-1 bg-rose-600 text-white hover:bg-rose-500" onClick={()=>del(it.id)}>Hapus</button>
                      </div>
                    )}
                  </td>
                </tr>
              ))}
              {rows.length===0 && (
                <tr><td colSpan={11} className="px-3 py-6 text-sm text-zinc-500">Data kosong.</td></tr>
              )}
            </tbody>
          </table>
        </div>
      )}
    </section>
  )
}
