'use client'
import { useEffect, useState } from 'react'
import { api } from '../api'

export default function PendingApprovalPage(){
  const [email,setEmail]=useState('')
  const [msg,setMsg]=useState('')
  const [busy,setBusy]=useState(false)
  useEffect(()=>{
    try{ const e = sessionStorage.getItem('pending_email') || localStorage.getItem('pending_email') || '' ; setEmail(e) }catch{}
  },[])
  async function notify(){
    try{
      setBusy(true); setMsg('')
      await api.post('/public/notify_admin', { kind:'registration', title:'Pengingat approval akun', body: email||'User pending approval', meta:{ email } })
      setMsg('Notifikasi terkirim ke admin. Mohon tunggu persetujuan.')
    }catch{ setMsg('Gagal mengirim notifikasi ke admin') }
    finally{ setBusy(false) }
  }
  return (
    <main className="relative isolate min-h-screen flex items-center justify-center px-4 bg-slate-950 text-white">
      <div className="absolute inset-x-0 top-0 -z-10 h-px bg-gradient-to-r from-white/10 via-white/20 to-white/10" />
      <div className="absolute inset-0 -z-20 bg-[linear-gradient(to_right,transparent_0,transparent_calc(50%-0.5px),rgba(255,255,255,.06)_50%,transparent_calc(50%+0.5px),transparent_100%)] bg-[length:40px_40px] [mask-image:radial-gradient(closest-side_at_50%_50%,black,transparent_85%)]" />
      <div className="w-full max-w-md rounded-2xl ring-1 ring-white/10 bg-white/5 backdrop-blur p-6 shadow-2xl">
        <h1 className="text-2xl font-bold">Menunggu Persetujuan Admin</h1>
        <p className="text-sm text-zinc-300 mt-2">Akun Anda belum di-approve oleh admin. Setelah disetujui, Anda dapat login menggunakan email yang terdaftar.</p>
        {email && (<p className="text-sm text-zinc-400 mt-2">Email terdaftar: <span className="font-mono">{email}</span></p>)}
        <div className="mt-4 flex items-center gap-2">
          <button onClick={notify} disabled={busy} className="px-4 py-2 rounded-md bg-cyan-600 hover:bg-cyan-500 text-white disabled:opacity-50">{busy? 'Mengirim…':'Beritahu Admin'}</button>
          <a href="/login" className="px-4 py-2 rounded-md ring-1 ring-inset ring-white/10 text-white/90 hover:bg-white/10">Kembali ke Login</a>
        </div>
        {msg && <div className="mt-3 rounded p-2 text-cyan-300 bg-cyan-500/10 ring-1 ring-cyan-500/20 text-sm">{msg}</div>}
      </div>
    </main>
  )
}

