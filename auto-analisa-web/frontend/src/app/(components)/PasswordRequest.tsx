'use client'
import { useState } from 'react'
import { api } from '../api'

export default function PasswordRequest(){
  const [open,setOpen]=useState(false)
  const [pwd,setPwd]=useState('')
  const [ok,setOk]=useState<string>('')
  async function submit(){
    try{ await api.post('user/password_request', null, { params:{ new_password: pwd } }); setOk('Permintaan terkirim. Menunggu persetujuan admin.') }
    catch{ setOk('Gagal mengirim permintaan.') }
  }
  return (
    <div className="mt-4">
      <button onClick={()=>setOpen(!open)} className="underline text-sm">Ganti Password (via Admin)</button>
      {open && (
        <div className="mt-2 space-y-2">
          <input type="password" value={pwd} onChange={e=>setPwd(e.target.value)} placeholder="Password baru" className="border rounded px-2 py-1 w-full"/>
          <button onClick={submit} className="px-3 py-1 rounded bg-zinc-900 text-white">Kirim Permintaan</button>
          {ok && <div className="text-xs text-gray-600">{ok}</div>}
        </div>
      )}
    </div>
  )
}

