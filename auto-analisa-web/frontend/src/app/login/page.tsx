'use client'
import { useState } from 'react'
import { useRouter } from 'next/navigation'
import { api } from '../api'

export default function LoginPage(){
  const [email,setEmail]=useState('')
  const [password,setPassword]=useState('')
  const [loading,setLoading]=useState(false)
  const router = useRouter()
  async function submit(e:React.FormEvent){
    e.preventDefault()
    setLoading(true)
    try{
      const r = await api.post('auth/login', null, { params:{ email: email.trim(), password }})
      localStorage.setItem('token', r.data.token)
      localStorage.setItem('role', r.data.role)
      router.push('/')
    }catch(e:any){
      alert('Login gagal')
    }finally{ setLoading(false) }
  }
  return (
    <main className="max-w-md mx-auto p-6 space-y-4">
      <h1 className="text-2xl font-bold">Login</h1>
      <form onSubmit={submit} className="space-y-3">
        <div>
          <label className="block text-sm mb-1">Email</label>
          <input value={email} onChange={e=>setEmail(e.target.value)} className="border rounded px-3 py-2 w-full"/>
        </div>
        <div>
          <label className="block text-sm mb-1">Password</label>
          <input type="password" value={password} onChange={e=>setPassword(e.target.value)} className="border rounded px-3 py-2 w-full"/>
        </div>
        <button disabled={loading} className="px-4 py-2 rounded bg-black text-white">{loading?'Masuk…':'Masuk'}</button>
      </form>
    </main>
  )
}
