'use client'
import { useEffect, useState } from 'react'
import { api } from '../api'

export default function AdminPage(){
  const [s,setS]=useState<any|null>(null)
  const [usage,setUsage]=useState<any|null>(null)
  const [denied,setDenied]=useState(false)
  const [pwreqs,setPwreqs]=useState<any[]|null>(null)

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
    await load()
  }
  if(denied) return <div className="max-w-3xl mx-auto p-4">Unauthorized</div>
  if(!s) return <div className="max-w-3xl mx-auto p-4">Loading…</div>
  return (
    <div className="max-w-3xl mx-auto p-4 space-y-4">
      <h1 className="text-2xl font-bold">Admin Settings</h1>
      <div className="grid grid-cols-2 gap-3">
        <label className="flex items-center gap-2"><input type="checkbox" checked={s.use_llm} onChange={e=>setS({...s,use_llm:e.target.checked})}/> LLM aktif</label>
        <label className="flex items-center gap-2"><input type="checkbox" checked={s.registration_enabled} onChange={e=>setS({...s,registration_enabled:e.target.checked})}/> Izinkan pendaftaran baru</label>
        <label className="flex items-center gap-2"><input type="checkbox" checked={s.auto_off_at_budget} onChange={e=>setS({...s,auto_off_at_budget:e.target.checked})}/> Auto-off saat cap</label>
        <label>Budget USD/bln <input type="number" className="border rounded px-2 py-1 w-full" value={s.budget_monthly_usd} onChange={e=>setS({...s,budget_monthly_usd:+e.target.value})}/></label>
        <label>Harga Input /1k <input type="number" className="border rounded px-2 py-1 w-full" value={s.input_usd_per_1k} onChange={e=>setS({...s,input_usd_per_1k:+e.target.value})}/></label>
        <label>Harga Output /1k <input type="number" className="border rounded px-2 py-1 w-full" value={s.output_usd_per_1k} onChange={e=>setS({...s,output_usd_per_1k:+e.target.value})}/></label>
      </div>
      <button onClick={save} className="px-3 py-1 rounded bg-black text-white">Simpan</button>

      <div className="mt-4 p-3 border rounded bg-white">
        <div>Bulan: {usage?.month_key}</div>
        <div>Total panggilan: {usage?.count}</div>
        <div>Biaya bulan ini: <b>${usage?.total_usd?.toFixed?.(4) ?? usage?.total_usd}</b></div>
      </div>
      <p className="text-sm text-gray-500">* Biaya diestimasikan dari token usage OpenAI sesuai harga /1k token.</p>

      <div className="mt-6 p-3 border rounded bg-white space-y-2">
        <div className="font-semibold">Password Change Requests</div>
        {!pwreqs?.length && <div className="text-sm text-gray-500">Tidak ada permintaan.</div>}
        {pwreqs?.map(r=> (
          <div key={r.id} className="flex items-center justify-between text-sm">
            <div>ID: {r.id} • User: {r.user_id} • {new Date(r.requested_at).toLocaleString('id-ID')}</div>
            <div className="flex gap-2">
              <button className="px-2 py-1 rounded bg-green-600 text-white" onClick={async()=>{ await api.post(`admin/password_requests/${r.id}/approve`); load() }}>Approve</button>
              <button className="px-2 py-1 rounded bg-red-600 text-white" onClick={async()=>{ await api.post(`admin/password_requests/${r.id}/reject`); load() }}>Reject</button>
            </div>
          </div>
        ))}
      </div>

      <div className="mt-6 p-3 border rounded bg-white space-y-2">
        <div className="font-semibold">Makro Harian</div>
        <button className="px-3 py-1 rounded bg-blue-600 text-white" onClick={async()=>{ await api.post('admin/macro/generate'); alert('Makro harian diperbarui'); }}>Generate Hari Ini</button>
      </div>
    </div>
  )
}
