'use client'
import { useState } from 'react'
import Link from 'next/link'
import { useRouter } from 'next/navigation'
import { api } from '../api'

export default function LoginPage(){
  const [email,setEmail]=useState('')
  const [password,setPassword]=useState('')
  const [loading,setLoading]=useState(false)
  const [err,setErr]=useState('')
  const router = useRouter()
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
      router.push('/')
    }catch(e:any){
      setErr('Login gagal. Periksa email/password Anda.')
    }finally{ setLoading(false) }
  }
  return (
    <main className="min-h-screen flex items-center justify-center px-4">
      <div className="w-full max-w-md bg-white dark:bg-zinc-900 border border-zinc-200 dark:border-zinc-800 rounded-2xl shadow-sm p-6">
        <div className="mb-4">
          <h1 className="text-2xl font-bold">Masuk</h1>
          <p className="text-sm text-gray-600 mt-1">Gunakan akun Anda untuk melanjutkan.</p>
        </div>
        {err && (
          <div className="mb-3 p-2 bg-amber-50 border border-amber-200 text-amber-800 rounded text-sm flex items-start gap-2">
            <span aria-hidden>⚠</span><span>{err}</span>
          </div>
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
          <button disabled={loading} className="w-full px-4 py-2 rounded bg-blue-600 text-white font-medium hover:bg-blue-700 focus:ring-2 focus:ring-blue-500 disabled:opacity-50">{loading?'Masuk…':'Masuk'}</button>
        </form>
        <div className="mt-4 flex items-center justify-between">
          <button onClick={()=>history.back()} className="text-sm font-medium text-gray-600 hover:text-gray-900">Kembali</button>
          <Link href="/register" className="text-sm font-medium text-blue-600 hover:text-blue-700">Buat akun</Link>
        </div>
      </div>
    </main>
  )
}
