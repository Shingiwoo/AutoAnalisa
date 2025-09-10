'use client'
import { useEffect, useState } from 'react'
import { useRouter } from 'next/navigation'
import { api } from '../api'

export default function RegisterPage(){
  const [email,setEmail]=useState('')
  const [password,setPassword]=useState('')
  const [loading,setLoading]=useState(false)
  const [enabled,setEnabled]=useState<boolean|null>(null)
  const router = useRouter()

  useEffect(()=>{ (async()=>{
    try{ const {data}=await api.get('auth/register_enabled'); setEnabled(!!data.enabled) }
    catch{ setEnabled(null) }
  })() },[])

  async function submit(e:React.FormEvent){
    e.preventDefault()
    setLoading(true)
    try{
      await api.post('auth/register', { email: email.trim(), password })
      alert('Registrasi berhasil. Silakan login.')
      router.push('/login')
    }catch(e:any){
      if(e?.response?.status===403) alert('Registrasi sedang dinonaktifkan oleh admin')
      else if(e?.response?.status===409) alert('Email sudah terdaftar')
      else alert('Registrasi gagal')
    }finally{ setLoading(false) }
  }

  return (
    <main className="max-w-md mx-auto p-6 space-y-4">
      <h1 className="text-2xl font-bold">Register</h1>
      {enabled===false && <div className="p-2 bg-amber-100 border border-amber-300 rounded text-amber-800">Registrasi dinonaktifkan oleh admin.</div>}
      <form onSubmit={submit} className="space-y-3">
        <div>
          <label className="block text-sm mb-1">Email</label>
          <input value={email} onChange={e=>setEmail(e.target.value)} className="border rounded px-3 py-2 w-full"/>
        </div>
        <div>
          <label className="block text-sm mb-1">Password</label>
          <input type="password" value={password} onChange={e=>setPassword(e.target.value)} className="border rounded px-3 py-2 w-full"/>
        </div>
        <button disabled={loading || enabled===false} className="px-4 py-2 rounded bg-black text-white disabled:opacity-50">{loading?'Mendaftar…':'Daftar'}</button>
      </form>
    </main>
  )
}
