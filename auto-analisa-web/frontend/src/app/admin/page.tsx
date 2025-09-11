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
  const [saveErr,setSaveErr]=useState<string>('')
  const [macroErr,setMacroErr]=useState<string>('')
  const [busySave,setBusySave]=useState(false)
  const [busyMacro,setBusyMacro]=useState(false)

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

  async function save(next?: any){
    try{
      setBusySave(true); setSaveErr(''); setSaved('')
      const payload = next ?? s
      await api.post('admin/settings', payload)
      setSaved('Pengaturan disimpan')
      await load()
    }catch(e:any){
      setSaveErr(e?.response?.data?.detail || 'Gagal menyimpan pengaturan')
    }finally{ setBusySave(false) }
  }
  if(denied) return <div className="max-w-7xl mx-auto p-6">Admin only</div>
  if(!s) return <div className="max-w-7xl mx-auto p-6">Loading…</div>
  return (
    <div className="max-w-7xl mx-auto p-6 space-y-6 text-zinc-900 dark:text-zinc-100">
      <h1 className="text-2xl font-bold">Admin Dashboard</h1>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="rounded-2xl ring-1 ring-zinc-200 dark:ring-white/10 bg-white dark:bg-zinc-900 p-4 space-y-4">
          <div className="font-semibold">Pengaturan</div>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3 text-sm">
            <label className="flex items-center gap-2"><input type="checkbox" className="accent-cyan-600" checked={s.use_llm} onChange={async e=>{ const next={...s,use_llm:e.target.checked}; setS(next); await save(next) }}/> LLM aktif</label>
            <label className="flex items-center gap-2"><input type="checkbox" className="accent-cyan-600" checked={s.registration_enabled} onChange={async e=>{ const next={...s,registration_enabled:e.target.checked}; setS(next); await save(next) }}/> Izinkan pendaftaran baru</label>
            <label className="flex items-center gap-2"><input type="checkbox" className="accent-cyan-600" checked={s.auto_off_at_budget} onChange={async e=>{ const next={...s,auto_off_at_budget:e.target.checked}; setS(next); await save(next) }}/> Auto-off saat cap</label>
            <label>Budget USD/bln <input type="number" className="rounded px-2 py-1 w-full bg-white text-zinc-900 ring-1 ring-inset ring-zinc-200 focus:outline-none focus:ring-2 focus:ring-cyan-500 dark:bg-transparent dark:text-white dark:ring-white/10" value={s.budget_monthly_usd} onChange={e=>setS({...s,budget_monthly_usd:+e.target.value})}/></label>
            <label>Harga Input /1k <input type="number" className="rounded px-2 py-1 w-full bg-white text-zinc-900 ring-1 ring-inset ring-zinc-200 focus:outline-none focus:ring-2 focus:ring-cyan-500 dark:bg-transparent dark:text-white dark:ring-white/10" value={s.input_usd_per_1k} onChange={e=>setS({...s,input_usd_per_1k:+e.target.value})}/></label>
            <label>Harga Output /1k <input type="number" className="rounded px-2 py-1 w-full bg-white text-zinc-900 ring-1 ring-inset ring-zinc-200 focus:outline-none focus:ring-2 focus:ring-cyan-500 dark:bg-transparent dark:text-white dark:ring-white/10" value={s.output_usd_per_1k} onChange={e=>setS({...s,output_usd_per_1k:+e.target.value})}/></label>
          </div>
          <div className="flex items-center gap-3">
            <button disabled={busySave} onClick={()=>save()} className="px-3 py-2 rounded bg-cyan-600 text-white font-medium hover:bg-cyan-500 disabled:opacity-50">{busySave?'Menyimpan…':'Simpan'}</button>
            {saved && <div className="text-sm text-green-600">✔ {saved}</div>}
            {saveErr && <div className="text-sm text-rose-500">{saveErr}</div>}
          </div>
        </div>

        <div className="rounded-2xl ring-1 ring-zinc-200 dark:ring-white/10 bg-white dark:bg-zinc-900 p-4 space-y-2">
          <div className="font-semibold">Penggunaan</div>
          <div className="flex justify-between text-sm">
            <div>Bulan: {usage?.month_key}</div>
            <div>Total panggilan: {usage?.count}</div>
          </div>
          <div className="text-sm">Biaya bulan ini: <b>${usage?.total_usd?.toFixed?.(4) ?? usage?.total_usd}</b></div>
          <div className="text-sm">Limit: <b>${s?.budget_monthly_usd}</b></div>
          <Progress current={s?.budget_used_usd || 0} max={s?.budget_monthly_usd || 1} />
          <p className="text-xs text-gray-500">* Estimasi biaya dari token usage dan harga /1k token.</p>
        </div>

        <div className="rounded-2xl ring-1 ring-zinc-200 dark:ring-white/10 bg-white dark:bg-zinc-900 p-4 space-y-3">
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

        <div className="rounded-2xl ring-1 ring-zinc-200 dark:ring-white/10 bg-white dark:bg-zinc-900 p-4 space-y-2">
          <div className="font-semibold">Makro Harian</div>
          {macroMsg && <div className="p-2 rounded text-sm text-cyan-300 ring-1 ring-cyan-500/20 bg-cyan-500/10">{macroMsg}</div>}
          {macroErr && <div className="p-2 rounded text-sm text-rose-400 ring-1 ring-rose-500/20 bg-rose-500/10">{macroErr}</div>}
          <button disabled={busyMacro} className="px-3 py-2 rounded bg-cyan-600 text-white font-medium hover:bg-cyan-500 disabled:opacity-50" onClick={async()=>{
            try{ setMacroErr(''); setMacroMsg(''); setBusyMacro(true); await api.post('admin/macro/generate'); setMacroMsg('Makro harian diperbarui.'); }
            catch(e:any){ setMacroErr(e?.response?.data?.detail || 'Gagal generate makro (500). Cek backend log).') }
            finally{ setBusyMacro(false) }
          }}>{busyMacro?'Memproses…':'Generate Hari Ini'}</button>
        </div>
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
