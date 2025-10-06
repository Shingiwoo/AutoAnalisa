"use client"
import { useState } from "react"
import Link from "next/link"
import { usePathname } from 'next/navigation'
import { api } from '../api'
import { Menu, KeyRound, LogOut, Shield, Home } from 'lucide-react'

export default function SiteHeader({ loggedIn, isAdmin }:{ loggedIn:boolean, isAdmin:boolean }){
  const [open,setOpen]=useState(false)
  const [pwdOpen,setPwdOpen]=useState(false)
  const [pwd,setPwd]=useState('')
  const [pwdMsg,setPwdMsg]=useState('')
  const pathname = usePathname()

  function logout(){
    if (typeof window !== 'undefined'){
      localStorage.removeItem('token')
      localStorage.removeItem('access_token')
      localStorage.removeItem('role')
      location.reload()
    }
  }

  return (
    <header className="sticky top-0 z-20">
      <div className="relative isolate">
        <div className="absolute inset-0 -z-10 bg-slate-950" />
        <div className="absolute inset-x-0 top-0 -z-10 h-px bg-gradient-to-r from-white/10 via-white/20 to-white/10" />
        <nav className="mx-auto max-w-7xl px-4 md:px-6 py-3 flex items-center justify-between text-sm">
          <div className="flex items-center gap-3">
            <Link href="/" className="text-white font-semibold tracking-tight">Auto Analisa</Link>
            <div className="hidden md:flex items-center gap-4 text-zinc-300">
              <Link href="/futures" className="hover:text-white">Futures</Link>
              {isAdmin && <Link href="/admin" className="hover:text-white">Admin</Link>}
            </div>
          </div>
          <div className="hidden md:flex items-center gap-3">
            {isAdmin && pathname?.startsWith('/admin') && (
              <Link href="/" className="inline-flex items-center gap-1 text-zinc-300 hover:text-white"><Home size={16}/> Dashboard</Link>
            )}
            {loggedIn && (
              <Link href="/journal" className="text-zinc-300 hover:text-white">Journal</Link>
            )}
            {!loggedIn && (
              <>
                <Link href="/login" className="text-zinc-300 hover:text-white">Login</Link>
                <Link href="/register" className="rounded px-3 py-1.5 bg-white text-slate-900 font-medium hover:bg-zinc-200">Daftar</Link>
              </>
            )}
            {loggedIn && (
              <div className="flex items-center gap-2">
                <button onClick={()=>setPwdOpen(v=>!v)} className="inline-flex items-center gap-1 rounded px-3 py-1.5 bg-zinc-800 text-white hover:bg-zinc-700"><KeyRound size={16}/> Ganti Password</button>
                <button onClick={logout} className="inline-flex items-center gap-1 rounded px-3 py-1.5 bg-zinc-800 text-white hover:bg-zinc-700"><LogOut size={16}/> Logout</button>
              </div>
            )}
          </div>
          <button aria-label="Menu" onClick={()=>setOpen(v=>!v)} className="md:hidden rounded px-2 py-1 text-zinc-300 hover:text-white"><Menu size={18} /></button>
        </nav>
        {open && (
          <div className="md:hidden border-t border-white/10 bg-slate-950/98 backdrop-blur">
            <div className="mx-auto max-w-7xl px-4 md:px-6 py-3 space-y-2 text-sm">
              <Link href="/futures" className="block text-zinc-300 hover:text-white">Futures</Link>
              {isAdmin && <Link href="/admin" className="block text-zinc-300 hover:text-white inline-flex items-center gap-1"><Shield size={16}/> Admin</Link>}
              {isAdmin && pathname?.startsWith('/admin') && (
                <Link href="/" className="block text-zinc-300 hover:text-white inline-flex items-center gap-1"><Home size={16}/> Dashboard</Link>
              )}
              {loggedIn && <Link href="/journal" className="block text-zinc-300 hover:text-white">Journal</Link>}
              {!loggedIn ? (
                <div className="pt-2 flex gap-3">
                  <Link href="/login" className="text-zinc-300 hover:text-white">Login</Link>
                  <Link href="/register" className="rounded px-3 py-1.5 bg-white text-slate-900 font-medium">Daftar</Link>
                </div>
              ) : (
                <div className="flex items-center gap-2 pt-2">
                  <button onClick={()=>setPwdOpen(v=>!v)} className="inline-flex items-center gap-1 rounded px-3 py-1.5 bg-zinc-800 text-white"><KeyRound size={16}/> Ganti Password</button>
                  <button onClick={logout} className="inline-flex items-center gap-1 rounded px-3 py-1.5 bg-zinc-800 text-white"><LogOut size={16}/> Logout</button>
                </div>
              )}
            </div>
          </div>
        )}
        <div className="h-px bg-white/10" />
        {pwdOpen && (
          <div className="border-t border-white/10 bg-slate-950">
            <div className="mx-auto max-w-7xl px-4 md:px-6 py-3 text-sm text-white flex flex-col md:flex-row gap-2 md:items-center">
              <div className="opacity-80">Ganti Password (butuh persetujuan admin)</div>
              <input type="password" value={pwd} onChange={e=>setPwd(e.target.value)} placeholder="Password baru" className="min-w-[220px] rounded bg-transparent px-3 py-1.5 ring-1 ring-inset ring-white/10 focus:outline-none focus:ring-2 focus:ring-cyan-500"/>
              <button className="rounded px-3 py-1.5 bg-cyan-600 text-white hover:bg-cyan-500" onClick={async()=>{
                try{ await api.post('user/password_request', null, { params:{ new_password: pwd } }); setPwdMsg('Permintaan terkirim. Menunggu persetujuan admin.'); setPwd('') }
                catch{ setPwdMsg('Gagal mengirim permintaan.') }
              }}>Kirim</button>
              {pwdMsg && <div className="text-cyan-300">{pwdMsg}</div>}
            </div>
          </div>
        )}
      </div>
    </header>
  )
}
