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
    <main className="relative isolate min-h-screen flex items-center justify-center px-4 bg-slate-950 text-white">
      {/* background accents */}
      <div className="absolute inset-x-0 top-0 -z-10 h-px bg-gradient-to-r from-white/10 via-white/20 to-white/10" />
      <div className="absolute inset-0 -z-20 bg-[linear-gradient(to_right,transparent_0,transparent_calc(50%-0.5px),rgba(255,255,255,.06)_50%,transparent_calc(50%+0.5px),transparent_100%)] bg-[length:40px_40px] [mask-image:radial-gradient(400px_300px_at_50%_50%,black,transparent_85%)]" />

      <div className="w-full max-w-md rounded-2xl ring-1 ring-white/10 bg-white/5 backdrop-blur p-6 shadow-2xl">
        <div className="mb-5">
          <h1 className="text-2xl font-bold tracking-tight">Buat Akun</h1>
          <p className="text-sm text-zinc-300 mt-1">Daftar untuk mulai menggunakan Auto Analisa.</p>
        </div>
        {enabled===false && (
          <div className="mb-4 rounded-lg p-2 text-sm text-amber-300 ring-1 ring-inset ring-amber-500/20 bg-amber-500/10">Registrasi dinonaktifkan oleh admin.</div>
        )}
        {msg && (
          <div className="mb-4 rounded-lg p-2 text-sm text-cyan-300 ring-1 ring-inset ring-cyan-500/20 bg-cyan-500/10">{msg}</div>
        )}
        <form onSubmit={submit} className="space-y-4">
          <div>
            <label className="block text-sm mb-1 text-zinc-300">Email</label>
            <input
              autoFocus
              value={email}
              onChange={e=>setEmail(e.target.value)}
              className="block w-full rounded-md bg-transparent px-3 py-2 text-white placeholder:text-zinc-400 ring-1 ring-inset ring-white/10 focus:outline-none focus:ring-2 focus:ring-cyan-500"
              placeholder="you@example.com"
            />
          </div>
          <div>
            <label className="block text-sm mb-1 text-zinc-300">Password</label>
            <input
              type="password"
              value={password}
              onChange={e=>setPassword(e.target.value)}
              className="block w-full rounded-md bg-transparent px-3 py-2 text-white placeholder:text-zinc-400 ring-1 ring-inset ring-white/10 focus:outline-none focus:ring-2 focus:ring-cyan-500"
              placeholder="••••••••"
            />
          </div>
          <button disabled={loading || enabled===false} className="w-full px-4 py-2 rounded-md bg-cyan-600 text-white font-medium hover:bg-cyan-500 focus:ring-2 focus:ring-cyan-500 disabled:opacity-50">{loading?'Mendaftar…':'Daftar'}</button>
        </form>
        <div className="mt-5 flex items-center justify-between text-sm">
          <button onClick={()=>history.back()} className="text-zinc-300 hover:text-white">Kembali</button>
          <Link href="/login" className="text-cyan-400 hover:text-cyan-300">Sudah punya akun?</Link>
        </div>
      </div>
    </main>
  )
}
