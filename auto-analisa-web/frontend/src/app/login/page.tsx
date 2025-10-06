'use client'
import { useEffect, useState } from 'react'
import Link from 'next/link'
import { useRouter } from 'next/navigation'
import { api } from '../api'

export default function LoginPage(){
  const [email,setEmail]=useState('')
  const [password,setPassword]=useState('')
  const [loading,setLoading]=useState(false)
  const [showPw,setShowPw]=useState(false)
  const [err,setErr]=useState('')
  const router = useRouter()
  // Jika sudah login dan user menekan Back ke /login, redirect kembali ke dashboard
  useEffect(()=>{
    const check = () => {
      try{
        const tok = typeof window !== 'undefined' ? (localStorage.getItem('access_token') || localStorage.getItem('token')) : null
        if(tok){ router.replace('/') }
      }catch{}
    }
    check()
    const onShow = (e: any) => { check() }
    window.addEventListener('pageshow', onShow)
    return () => window.removeEventListener('pageshow', onShow)
  },[router])
  async function submit(e:React.FormEvent){
    e.preventDefault()
    setErr('')
    setLoading(true)
    try{
      const r = await api.post('/auth/login', { email: email.trim(), password })
      const tok = r.data?.access_token || r.data?.token
      if (!tok) throw new Error('No token')
      localStorage.setItem('access_token', tok)
      localStorage.setItem('token', tok) // backward-compat
      localStorage.setItem('role', r.data.role)
      api.defaults.headers.common.Authorization = `Bearer ${tok}` as any
      router.replace('/')
    }catch(e:any){
      const d = e?.response?.data?.detail
      if (e?.response?.status===403 && typeof d==='string'){
        if (d.toLowerCase().includes('menunggu persetujuan')){
          try{ sessionStorage.setItem('pending_email', email.trim()) }catch{}
          router.replace('/pending-approval')
          return
        }
        setErr(d)
      } else setErr('Login gagal. Periksa email/password Anda.')
    }finally{ setLoading(false) }
  }
  return (
    <main className="relative isolate min-h-screen flex items-center justify-center px-4 bg-slate-950 text-white">
      {/* background accents */}
      <div className="absolute inset-x-0 top-0 -z-10 h-px bg-gradient-to-r from-white/10 via-white/20 to-white/10" />
      <div className="absolute inset-0 -z-20 bg-[linear-gradient(to_right,transparent_0,transparent_calc(50%-0.5px),rgba(255,255,255,.06)_50%,transparent_calc(50%+0.5px),transparent_100%)] bg-[length:40px_40px] [mask-image:radial-gradient(closest-side_at_50%_50%,black,transparent_85%)]" />

      <div className="w-full max-w-md rounded-2xl ring-1 ring-white/10 bg-white/5 backdrop-blur p-6 shadow-2xl">
        <div className="mb-5">
          <h1 className="text-2xl font-bold tracking-tight">Masuk</h1>
          <p className="text-sm text-zinc-300 mt-1">Gunakan akun Anda untuk melanjutkan.</p>
        </div>
        {err && (
          <div className="mb-4 rounded-lg p-2 text-sm text-rose-400 ring-1 ring-inset ring-rose-500/20 bg-rose-500/10">{err}</div>
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
            <div className="relative">
              <input
                type={showPw? 'text':'password'}
                value={password}
                onChange={e=>setPassword(e.target.value)}
                className="block w-full rounded-md bg-transparent px-3 py-2 pr-10 text-white placeholder:text-zinc-400 ring-1 ring-inset ring-white/10 focus:outline-none focus:ring-2 focus:ring-cyan-500"
                placeholder="••••••••"
              />
              <button type="button" onClick={()=>setShowPw(v=>!v)} className="absolute inset-y-0 right-2 my-auto h-7 px-1 rounded text-zinc-300 hover:text-white focus:outline-none focus:ring-1 focus:ring-cyan-500">
                {showPw? '🙈':'👁️'}
              </button>
            </div>
          </div>
          <button disabled={loading} className="w-full px-4 py-2 rounded-md bg-cyan-600 text-white font-medium hover:bg-cyan-500 focus:ring-2 focus:ring-cyan-500 disabled:opacity-50">{loading?'Masuk…':'Masuk'}</button>
        </form>
        <div className="mt-5 flex items-center justify-between text-sm">
          <button onClick={()=>history.back()} className="text-zinc-300 hover:text-white">Kembali</button>
          <Link href="/register" className="text-cyan-400 hover:text-cyan-300">Buat akun</Link>
        </div>
      </div>
    </main>
  )
}
