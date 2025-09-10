'use client'
import { useEffect, useState } from 'react'
import { api } from '../api'

export default function AdminPage(){
  const [s,setS]=useState<any|null>(null)
  const [usage,setUsage]=useState<any|null>(null)
  const [denied,setDenied]=useState(false)

  async function load(){
    try{
      const [a,b] = await Promise.all([
        api.get('/api/admin/settings'),
        api.get('/api/admin/usage')
      ])
      setS(a.data); setUsage(b.data)
    }catch(e:any){
      setDenied(true)
    }
  }
  useEffect(()=>{
    const role = typeof window!=='undefined' ? localStorage.getItem('role') : null
    if(role!=='admin'){ setDenied(true); return }
    load()
  },[])

  async function save(){
    await api.post('/api/admin/settings', s)
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
    </div>
  )
}
