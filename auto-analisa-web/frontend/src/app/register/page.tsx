'use client'
import { useEffect, useState } from 'react'
import Link from 'next/link'
import { useRouter } from 'next/navigation'
import { api } from '../api'

export default function RegisterPage(){
  const [email,setEmail]=useState('')
  const [password,setPassword]=useState('')
  const [loading,setLoading]=useState(false)
  const [enabled,setEnabled]=useState<boolean|null>(null)
  const [msg,setMsg]=useState('')
  const router = useRouter()

  useEffect(()=>{ (async()=>{
    try{ const {data}=await api.get('auth/register_enabled'); setEnabled(!!data.enabled) }
    catch{ setEnabled(null) }
  })() },[])

  async function submit(e:React.FormEvent){
    e.preventDefault()
    setMsg('')
    setLoading(true)
    try{
      await api.post('auth/register', { email: email.trim(), password })
      setMsg('Registrasi berhasil. Silakan login.')
      setTimeout(()=> router.push('/login'), 600)
    }catch(e:any){
      if(e?.response?.status===403) setMsg('Registrasi dinonaktifkan oleh admin')
      else if(e?.response?.status===409) setMsg('Email sudah terdaftar')
      else setMsg('Registrasi gagal')
    }finally{ setLoading(false) }
  }

  return (
    <main className="min-h-screen flex items-center justify-center px-4">
      <div className="w-full max-w-md bg-white dark:bg-zinc-900 border border-zinc-200 dark:border-zinc-800 rounded-2xl shadow-sm p-6">
        <div className="mb-4">
          <h1 className="text-2xl font-bold">Buat Akun</h1>
          <p className="text-sm text-gray-600 mt-1">Daftar untuk mulai menggunakan Auto Analisa.</p>
        </div>
        {enabled===false && (
          <div className="mb-3 p-2 bg-amber-50 border border-amber-200 text-amber-800 rounded text-sm">Registrasi dinonaktifkan oleh admin.</div>
        )}
        {msg && (
          <div className="mb-3 p-2 bg-blue-50 border border-blue-200 text-blue-800 rounded text-sm">{msg}</div>
        )}
        <form onSubmit={submit} className="space-y-3">
          <div>
            <label className="block text-sm mb-1">Email</label>
            <input autoFocus value={email} onChange={e=>setEmail(e.target.value)} className="border rounded px-3 py-2 w-full focus:outline-none focus:ring-2 focus:ring-blue-500"/>
          </div>
          <div>
            <label className="block text-sm mb-1">Password</label>
            <input type="password" value={password} onChange={e=>setPassword(e.target.value)} className="border rounded px-3 py-2 w-full focus:outline-none focus:ring-2 focus:ring-blue-500"/>
          </div>
          <button disabled={loading || enabled===false} className="w-full px-4 py-2 rounded bg-blue-600 text-white font-medium hover:bg-blue-700 focus:ring-2 focus:ring-blue-500 disabled:opacity-50">{loading?'Mendaftar…':'Daftar'}</button>
        </form>
        <div className="mt-4 flex items-center justify-between">
          <button onClick={()=>history.back()} className="text-sm font-medium text-gray-600 hover:text-gray-900">Kembali</button>
          <Link href="/login" className="text-sm font-medium text-blue-600 hover:text-blue-700">Sudah punya akun?</Link>
        </div>
      </div>
    </main>
  )
}
