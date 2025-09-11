'use client'
import { useEffect, useState } from 'react'
import { api } from '../api'

export default function AdminPage(){
  const [s,setS]=useState<any|null>(null)
  const [usage,setUsage]=useState<any|null>(null)
  const [denied,setDenied]=useState(false)
  const [pwreqs,setPwreqs]=useState<any[]|null>(null)
  const [saved,setSaved]=useState<string>('')
  const [macroMsg,setMacroMsg]=useState<string>('')

  async function load(){
    try{
      const [a,b] = await Promise.all([
        api.get('admin/settings'),
        api.get('admin/usage')
      ])
      setS(a.data); setUsage(b.data)
      try{ const r = await api.get('admin/password_requests'); setPwreqs(r.data) }catch{}
    }catch(e:any){
      setDenied(true)
    }
  }
  useEffect(()=>{ load() },[])

  async function save(){
    await api.post('admin/settings', s)
    setSaved('Pengaturan disimpan')
    await load()
  }
  if(denied) return <div className="max-w-3xl mx-auto p-4">Admin only</div>
  if(!s) return <div className="max-w-3xl mx-auto p-4">Loading…</div>
  return (
    <div className="max-w-5xl mx-auto p-4 space-y-6">
      <h1 className="text-2xl font-bold">Admin</h1>

      <div className="bg-white dark:bg-zinc-900 border border-zinc-200 dark:border-zinc-800 rounded-2xl shadow-sm p-4 space-y-4">
        <div className="font-semibold">Pengaturan</div>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3 text-sm">
          <label className="flex items-center gap-2"><input type="checkbox" checked={s.use_llm} onChange={e=>setS({...s,use_llm:e.target.checked})}/> LLM aktif</label>
          <label className="flex items-center gap-2"><input type="checkbox" checked={s.registration_enabled} onChange={e=>setS({...s,registration_enabled:e.target.checked})}/> Izinkan pendaftaran baru</label>
          <label className="flex items-center gap-2"><input type="checkbox" checked={s.auto_off_at_budget} onChange={e=>setS({...s,auto_off_at_budget:e.target.checked})}/> Auto-off saat cap</label>
          <label>Budget USD/bln <input type="number" className="border rounded px-2 py-1 w-full focus:outline-none focus:ring-2 focus:ring-blue-500" value={s.budget_monthly_usd} onChange={e=>setS({...s,budget_monthly_usd:+e.target.value})}/></label>
          <label>Harga Input /1k <input type="number" className="border rounded px-2 py-1 w-full focus:outline-none focus:ring-2 focus:ring-blue-500" value={s.input_usd_per_1k} onChange={e=>setS({...s,input_usd_per_1k:+e.target.value})}/></label>
          <label>Harga Output /1k <input type="number" className="border rounded px-2 py-1 w-full focus:outline-none focus:ring-2 focus:ring-blue-500" value={s.output_usd_per_1k} onChange={e=>setS({...s,output_usd_per_1k:+e.target.value})}/></label>
        </div>
        <div className="flex items-center gap-3">
          <button onClick={save} className="px-3 py-2 rounded bg-blue-600 text-white font-medium hover:bg-blue-700">Simpan</button>
          {saved && <div className="text-sm text-green-600">✔ {saved}</div>}
        </div>
      </div>

      <div className="bg-white dark:bg-zinc-900 border border-zinc-200 dark:border-zinc-800 rounded-2xl shadow-sm p-4 space-y-2">
        <div className="font-semibold">Penggunaan</div>
        <div className="flex justify-between text-sm">
          <div>Bulan: {usage?.month_key}</div>
          <div>Total panggilan: {usage?.count}</div>
        </div>
        <div className="text-sm">Biaya bulan ini: <b>${usage?.total_usd?.toFixed?.(4) ?? usage?.total_usd}</b></div>
        <div className="text-sm">Limit: <b>${s?.budget_monthly_usd}</b></div>
        <Progress current={s?.budget_used_usd || 0} max={s?.budget_monthly_usd || 1} />
      </div>
      <p className="text-sm text-gray-500">* Estimasi biaya dari token usage dan harga /1k token.</p>

      <div className="bg-white dark:bg-zinc-900 border border-zinc-200 dark:border-zinc-800 rounded-2xl shadow-sm p-4 space-y-3">
        <div className="font-semibold">Permintaan Ganti Password</div>
        {!pwreqs?.length && <div className="text-sm text-gray-500">Tidak ada permintaan.</div>}
        {pwreqs?.map(r=> (
          <div key={r.id} className="flex items-center justify-between text-sm">
            <div>ID: {r.id} • User: {r.user_id} • {new Date(r.requested_at).toLocaleString('id-ID')}</div>
            <div className="flex gap-2">
              <button className="px-2.5 py-1.5 rounded bg-green-600 text-white hover:bg-green-700" onClick={async()=>{ await api.post(`admin/password_requests/${r.id}/approve`); load() }}>✔ Approve</button>
              <button className="px-2.5 py-1.5 rounded bg-red-600 text-white hover:bg-red-700" onClick={async()=>{ if(confirm('Tolak permintaan ini?')){ await api.post(`admin/password_requests/${r.id}/reject`); load() } }}>✖ Reject</button>
            </div>
          </div>
        ))}
      </div>

      <div className="bg-white dark:bg-zinc-900 border border-zinc-200 dark:border-zinc-800 rounded-2xl shadow-sm p-4 space-y-2">
        <div className="font-semibold">Makro Harian</div>
        {macroMsg && <div className="p-2 bg-blue-50 border border-blue-200 text-blue-800 rounded text-sm">{macroMsg}</div>}
        <button className="px-3 py-2 rounded bg-blue-600 text-white font-medium hover:bg-blue-700" onClick={async()=>{ await api.post('admin/macro/generate'); setMacroMsg('Makro harian diperbarui.'); }}>Generate Hari Ini</button>
      </div>
    </div>
  )
}

function Progress({ current, max }:{ current:number, max:number }){
  const pct = Math.min(100, Math.round((current / (max || 1)) * 100))
  return (
    <div className="w-full bg-zinc-200 rounded h-2 overflow-hidden">
      <div className="h-2 bg-green-600" style={{ width: `${pct}%` }} />
    </div>
  )
}
