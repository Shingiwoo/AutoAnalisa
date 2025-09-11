'use client'
import { useState, useEffect } from 'react'
import { api } from '../app/api'

export default function AuthBar({ onAuth }: { onAuth?: () => void }) {
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [token, setToken] = useState<string | null>(null)

  useEffect(() => {
    if (typeof window !== 'undefined') {
      const t = localStorage.getItem('token') || localStorage.getItem('access_token')
      setToken(t)
    }
  }, [])

  async function login() {
    const r = await api.post('/auth/login', { email: email.trim(), password })
    const tok = r.data?.access_token || r.data?.token
    localStorage.setItem('access_token', tok)
    localStorage.setItem('token', tok)
    localStorage.setItem('role', r.data.role)
    api.defaults.headers.common.Authorization = `Bearer ${tok}` as any
    setToken(tok)
    onAuth?.()
  }
  function logout() {
    localStorage.removeItem('token')
    localStorage.removeItem('access_token')
    localStorage.removeItem('role')
    try { delete (api.defaults.headers as any).common?.Authorization } catch {}
    setToken(null)
    onAuth?.()
  }

  return (
    <div className="flex gap-2 items-center">
      {token ? (
        <button onClick={logout} className="px-3 py-1 rounded bg-gray-200">Logout</button>
      ) : (
        <>
          <input value={email} onChange={e => setEmail(e.target.value)} placeholder="email" className="border rounded px-2 py-1 text-sm"/>
          <input type="password" value={password} onChange={e => setPassword(e.target.value)} placeholder="password" className="border rounded px-2 py-1 text-sm"/>
          <button onClick={login} className="px-3 py-1 rounded bg-black text-white">Login</button>
        </>
      )}
    </div>
  )
}
