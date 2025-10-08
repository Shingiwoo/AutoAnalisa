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
  margin?: number
  leverage?: number
  equity_balance?: number
  pnl_pct: number
  notes: string
  entry_price?: number
  exit_price?: number
  tp1_price?: number
  tp2_price?: number
  tp3_price?: number
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
  const [editMargin,setEditMargin]=useState("")
  const [editLeverage,setEditLeverage]=useState("")
  const [customTP,setCustomTP]=useState(false)
  const [ct1,setCt1]=useState("")
  const [ct2,setCt2]=useState("")
  const [ct3,setCt3]=useState("")
  const [etp1,setEtp1]=useState("PENDING")
  const [etp2,setEtp2]=useState("PENDING")
  const [etp3,setEtp3]=useState("PENDING")
  const [esl,setEsl]=useState("PENDING")
  const [ebe,setEbe]=useState("PENDING")
  const [estat,setEstat]=useState("OPEN")
  const [autoBE,setAutoBE]=useState(true)
  const [autoTP1,setAutoTP1]=useState(false)
  const [modalOpen,setModalOpen]=useState(false)
  const [modalKind,setModalKind]=useState<'edit'|'notes'|null>(null)
  const [notesRow,setNotesRow]=useState<TJ|null>(null)

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
    setEditMargin((it.margin ?? "").toString())
    setEditLeverage((it.leverage ?? "").toString())
    setEtp1(it.tp1_status||"PENDING")
    setEtp2(it.tp2_status||"PENDING")
    setEtp3(it.tp3_status||"PENDING")
    setEsl(it.sl_status||"PENDING")
    setEbe(it.be_status||"PENDING")
    setEstat(it.status||"OPEN")
    setCustomTP(false)
    setCt1((it.tp1_price ?? "").toString())
    setCt2((it.tp2_price ?? "").toString())
    setCt3((it.tp3_price ?? "").toString())
    setModalKind('edit')
    setModalOpen(true)
  }

  function cancelEdit(){
    setEditId(null); setEditExitAt(""); setEditExitPrice(""); setEditNotes("")
  }

  async function saveEdit(){
    if(editId==null) return
    try{
      const body:any = { notes: editNotes, tp1_status: etp1, tp2_status: etp2, tp3_status: etp3, sl_status: esl, be_status: ebe, status: estat, auto_move_sl_to_be: autoBE, auto_lock_tp1: autoTP1 }
      if(editMargin) body.margin = Number(editMargin)
      if(editLeverage) body.leverage = Number(editLeverage)
      if(customTP){
        body.custom_tp = true
        if(ct1) body.tp1_price = Number(ct1)
        if(ct2) body.tp2_price = Number(ct2)
        if(ct3) body.tp3_price = Number(ct3)
      }
      if(editExitAt) body.exit_at = editExitAt
      if(editExitPrice) body.exit_price = Number(editExitPrice)
      const r = await api.put(`/trade-journal/${editId}`, body)
      setRows(prev=> prev.map(x=> x.id===editId ? r.data : x))
      cancelEdit()
      setModalOpen(false)
      setModalKind(null)
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

  function pnlUsdt(it: TJ): number | null{
    const e = it.entry_price
    const x = it.exit_price
    const m = it.margin
    const lev = it.leverage
    if(!e || !x || !m || !lev) return null
    const qty = (m * lev) / e
    const pnl = it.arah==='SHORT' ? qty * (e - x) : qty * (x - e)
    return pnl
  }

  function badge(color: 'green'|'red'|'yellow', text: string){
    const cls = color==='green'? 'bg-emerald-600' : color==='red'? 'bg-rose-600' : 'bg-amber-500'
    return <span className={`inline-flex items-center px-2 py-0.5 rounded text-white text-xs ${cls}`}>{text}</span>
  }

  function fmt(n?: number | null, d=2){
    if(n==null || Number.isNaN(Number(n))) return '-'
    try{ return Number(n).toLocaleString(undefined, { maximumFractionDigits: d }) }catch{ return String(n) }
  }

  function snippet(s?: string, n=120){
    if(!s) return ''
    if(s.length<=n) return s
    return s.slice(0,n).trim() + '…'
  }

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
                <th className="px-3 py-2">Profit (PnL(USDT)/ROI(%))</th>
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
                  <td className="px-3 py-2">{it.status==='OPEN'? badge('green','OPEN') : badge('red','CLOSED')}</td>
                  <td className="px-3 py-2">{(it.winloss||'WAITING')==='WIN'? badge('green','WIN') : (it.winloss||'WAITING')==='LOSS'? badge('red','LOSS') : badge('yellow','WAITING')}</td>
                  <td className="px-3 py-2">{it.saldo_awal ?? '-'}</td>
                  <td className="px-3 py-2">{it.equity_balance ?? '-'}</td>
                  <td className="px-3 py-2">
                    {(() => {
                      const p = pnlUsdt(it)
                      const roi = (it.pnl_pct||0).toFixed(2)
                      return p==null ? '-' : `${p.toFixed(2)} / ${roi}%`
                    })()}
                  </td>
                  <td className="px-3 py-2 max-w-[22rem] whitespace-pre-wrap break-words">
                    {it.notes? (
                      <>
                        <button className="mt-1 text-xs text-cyan-400 hover:text-cyan-300" onClick={()=>{ setNotesRow(it); setModalKind('notes'); setModalOpen(true) }}>Detail</button>
                      </>
                    ) : '-'}
                  </td>
                  <td className="px-3 py-2">
                    {
                      <div className="flex flex-wrap gap-2">
                        <button className="rounded px-3 py-1 bg-zinc-800 text-white hover:bg-zinc-700" onClick={()=>startEdit(it)}>Edit</button>
                        {it.status==='OPEN' && <button className="rounded px-3 py-1 bg-emerald-600 text-white hover:bg-emerald-500" onClick={()=>closeTrade(it)}>Close</button>}
                        <button className="rounded px-3 py-1 bg-rose-600 text-white hover:bg-rose-500" onClick={()=>del(it.id)}>Hapus</button>
                      </div>
                    }
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
      {modalOpen && (
        <div className="fixed inset-0 z-50">
          <div className="absolute inset-0 bg-black/70 backdrop-blur-sm" onClick={()=>{ setModalOpen(false); setModalKind(null) }} />
          <div className="absolute inset-0 flex items-center justify-center p-4">
            <div className="w-full max-w-3xl rounded-2xl bg-slate-950 text-white shadow-2xl ring-1 ring-white/10 overflow-hidden">
              <div className="px-4 py-3 border-b border-white/10 flex items-center justify-between">
                <h3 className="font-semibold">{modalKind==='edit' ? 'Edit Trade' : 'Detail Catatan'}</h3>
                <button onClick={()=>{ setModalOpen(false); setModalKind(null) }} className="text-zinc-300 hover:text-white">✕</button>
              </div>
              <div className="p-4 max-h-[75vh] overflow-auto">
                {modalKind==='notes' && (
                  <div className="space-y-4">
                    <div className="grid gap-4 md:grid-cols-2 text-sm">
                      <div>
                        <div className="text-zinc-400">Closing PNL (USDT)</div>
                        <div className={((pnlUsdt(notesRow!)||0) >= 0 ? 'text-emerald-400' : 'text-rose-400') + ' text-lg font-semibold'}>{fmt(pnlUsdt(notesRow!))}</div>
                      </div>
                      <div>
                        <div className="text-zinc-400">ROI</div>
                        <div className={(Number(notesRow?.pnl_pct)||0)>=0? 'text-emerald-400 text-lg font-semibold' : 'text-rose-400 text-lg font-semibold'}>{fmt(notesRow?.pnl_pct,2)}%</div>
                      </div>
                      <div>
                        <div className="text-zinc-400">Entry Price</div>
                        <div className="text-white text-lg font-semibold">{fmt(notesRow?.entry_price)}</div>
                      </div>
                      <div>
                        <div className="text-zinc-400">Avg. Close Price</div>
                        <div className="text-white text-lg font-semibold">{fmt(notesRow?.exit_price)}</div>
                      </div>
                      <div>
                        <div className="text-zinc-400">Opened</div>
                        <div className="text-white">{notesRow?.entry_at ? new Date(notesRow.entry_at).toLocaleString() : '-'}</div>
                      </div>
                      <div>
                        <div className="text-zinc-400">Closed</div>
                        <div className="text-white">{notesRow?.exit_at ? new Date(notesRow.exit_at).toLocaleString() : '-'}</div>
                      </div>
                      <div>
                        <div className="text-zinc-400">Pair</div>
                        <div className="text-white">{notesRow?.pair} • {notesRow?.arah}</div>
                      </div>
                      <div>
                        <div className="text-zinc-400">Status</div>
                        <div className="text-white">{notesRow?.status}</div>
                      </div>
                      <div>
                        <div className="text-zinc-400">Margin</div>
                        <div className="text-white">{fmt(notesRow?.margin)}</div>
                      </div>
                      <div>
                        <div className="text-zinc-400">Leverage</div>
                        <div className="text-white">{fmt(notesRow?.leverage)}</div>
                      </div>
                      <div>
                        <div className="text-zinc-400">Equity</div>
                        <div className="text-white">{fmt(notesRow?.equity_balance)}</div>
                      </div>
                    </div>
                    <div className="border-t border-white/10 pt-3">
                      <div className="text-zinc-400 text-sm mb-1">Catatan</div>
                      <div className="whitespace-pre-wrap text-sm text-zinc-100">{notesRow?.notes || '-'}</div>
                    </div>
                  </div>
                )}
                {modalKind==='edit' && (
                  <div className="space-y-3">
                    <div className="grid gap-2 md:grid-cols-2">
                      <div>
                        <div className="text-xs text-zinc-400 mb-1">Tanggal & jam close (exit)</div>
                        <input type="datetime-local" value={editExitAt} onChange={e=>setEditExitAt(e.target.value)} className="w-full rounded px-3 py-2 bg-zinc-900 text-white ring-1 ring-inset ring-white/10 focus:outline-none focus:ring-2 focus:ring-cyan-500" />
                      </div>
                      <div>
                        <div className="text-xs text-zinc-400 mb-1">Harga Exit</div>
                        <input value={editExitPrice} onChange={e=>setEditExitPrice(e.target.value)} placeholder="mis. 63350.25" className="w-full rounded px-3 py-2 bg-zinc-900 text-white ring-1 ring-inset ring-white/10 focus:outline-none focus:ring-2 focus:ring-cyan-500" />
                      </div>
                    </div>
                    <div className="grid gap-2 md:grid-cols-2">
                      <div>
                        <div className="text-xs text-zinc-400 mb-1">Margin</div>
                        <input value={editMargin} onChange={e=>setEditMargin(e.target.value)} inputMode="decimal" className="w-full rounded px-3 py-2 bg-zinc-900 text-white ring-1 ring-inset ring-white/10 focus:outline-none focus:ring-2 focus:ring-cyan-500" />
                      </div>
                      <div>
                        <div className="text-xs text-zinc-400 mb-1">Leverage</div>
                        <input value={editLeverage} onChange={e=>setEditLeverage(e.target.value)} inputMode="decimal" className="w-full rounded px-3 py-2 bg-zinc-900 text-white ring-1 ring-inset ring-white/10 focus:outline-none focus:ring-2 focus:ring-cyan-500" />
                      </div>
                    </div>
                    <div className="grid gap-2 md:grid-cols-2">
                      <div>
                        <div className="text-xs text-zinc-400 mb-1">TP1 status</div>
                        <select value={etp1} onChange={e=>setEtp1(e.target.value)} className="w-full rounded px-3 py-2 bg-zinc-900 text-white ring-1 ring-inset ring-white/10"><option>PENDING</option><option>HIT</option><option>FAIL</option></select>
                      </div>
                      <div>
                        <div className="text-xs text-zinc-400 mb-1">TP2 status</div>
                        <select value={etp2} onChange={e=>setEtp2(e.target.value)} className="w-full rounded px-3 py-2 bg-zinc-900 text-white ring-1 ring-inset ring-white/10"><option>PENDING</option><option>HIT</option><option>FAIL</option></select>
                      </div>
                      <div>
                        <div className="text-xs text-zinc-400 mb-1">TP3 status</div>
                        <select value={etp3} onChange={e=>setEtp3(e.target.value)} className="w-full rounded px-3 py-2 bg-zinc-900 text-white ring-1 ring-inset ring-white/10"><option>PENDING</option><option>HIT</option><option>FAIL</option></select>
                      </div>
                      <div>
                        <div className="text-xs text-zinc-400 mb-1">SL status</div>
                        <select value={esl} onChange={e=>setEsl(e.target.value)} className="w-full rounded px-3 py-2 bg-zinc-900 text-white ring-1 ring-inset ring-white/10"><option>PENDING</option><option>HIT</option><option>PASS</option></select>
                      </div>
                      <div>
                        <div className="text-xs text-zinc-400 mb-1">BE status</div>
                        <select value={ebe} onChange={e=>setEbe(e.target.value)} className="w-full rounded px-3 py-2 bg-zinc-900 text-white ring-1 ring-inset ring-white/10"><option>PENDING</option><option>HIT</option><option>PASS</option></select>
                      </div>
                      <div>
                        <div className="text-xs text-zinc-400 mb-1">Status trade</div>
                        <select value={estat} onChange={e=>setEstat(e.target.value)} className="w-full rounded px-3 py-2 bg-zinc-900 text-white ring-1 ring-inset ring-white/10"><option>OPEN</option><option>CLOSED</option></select>
                      </div>
                    </div>
                    <label className="inline-flex items-center gap-2 text-sm"><input type="checkbox" checked={customTP} onChange={e=>setCustomTP(e.target.checked)} /> Gunakan TP custom</label>
                    {customTP && (
                      <div className="grid gap-2 md:grid-cols-3">
                        <div>
                          <div className="text-xs text-zinc-400 mb-1">TP1 (custom)</div>
                          <input value={ct1} onChange={e=>setCt1(e.target.value)} inputMode="decimal" className="w-full rounded px-3 py-2 bg-zinc-900 text-white ring-1 ring-inset ring-white/10" />
                        </div>
                        <div>
                          <div className="text-xs text-zinc-400 mb-1">TP2 (custom)</div>
                          <input value={ct2} onChange={e=>setCt2(e.target.value)} inputMode="decimal" className="w-full rounded px-3 py-2 bg-zinc-900 text-white ring-1 ring-inset ring-white/10" />
                        </div>
                        <div>
                          <div className="text-xs text-zinc-400 mb-1">TP3 (custom)</div>
                          <input value={ct3} onChange={e=>setCt3(e.target.value)} inputMode="decimal" className="w-full rounded px-3 py-2 bg-zinc-900 text-white ring-1 ring-inset ring-white/10" />
                        </div>
                      </div>
                    )}
                    <label className="flex items-center gap-2 text-xs"><input type="checkbox" checked={autoBE} onChange={e=>setAutoBE(e.target.checked)} /> Auto‑SL ke BE saat TP1 = HIT</label>
                    <label className="flex items-center gap-2 text-xs"><input type="checkbox" checked={autoTP1} onChange={e=>setAutoTP1(e.target.checked)} /> Kunci SL = TP1 saat TP2 = HIT</label>
                    <div>
                      <div className="text-xs text-zinc-400 mb-1">Catatan</div>
                      <textarea value={editNotes} onChange={e=>setEditNotes(e.target.value)} rows={3} className="w-full rounded px-3 py-2 bg-zinc-900 text-white ring-1 ring-inset ring-white/10" />
                    </div>
                  </div>
                )}
              </div>
              <div className="px-4 py-3 border-t border-white/10 flex items-center justify-end gap-2 bg-black/30">
                <button onClick={()=>{ setModalOpen(false); setModalKind(null); cancelEdit() }} className="rounded px-3 py-1.5 bg-zinc-800 text-white">Tutup</button>
                {modalKind==='edit' && (
                  <button onClick={saveEdit} className="rounded px-3 py-1.5 bg-cyan-600 text-white">Simpan</button>
                )}
              </div>
            </div>
          </div>
        </div>
      )}
    </section>
  )
}
