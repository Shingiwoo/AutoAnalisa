"use client"
import { useState } from "react"
import Link from "next/link"

export default function SiteHeader({ loggedIn, isAdmin }:{ loggedIn:boolean, isAdmin:boolean }){
  const [open,setOpen]=useState(false)

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
              <a href="#analisa" className="hover:text-white">Analisa</a>
              <a href="#watchlist" className="hover:text-white">Watchlist</a>
              {isAdmin && <Link href="/admin" className="hover:text-white">Admin</Link>}
            </div>
          </div>
          <div className="hidden md:flex items-center gap-3">
            {!loggedIn && (
              <>
                <Link href="/login" className="text-zinc-300 hover:text-white">Login</Link>
                <Link href="/register" className="rounded px-3 py-1.5 bg-white text-slate-900 font-medium hover:bg-zinc-200">Daftar</Link>
              </>
            )}
            {loggedIn && (
              <button onClick={logout} className="rounded px-3 py-1.5 bg-zinc-800 text-white hover:bg-zinc-700">Logout</button>
            )}
          </div>
          <button aria-label="Menu" onClick={()=>setOpen(v=>!v)} className="md:hidden rounded px-2 py-1 text-zinc-300 hover:text-white">☰</button>
        </nav>
        {open && (
          <div className="md:hidden border-t border-white/10 bg-slate-950/98 backdrop-blur">
            <div className="mx-auto max-w-7xl px-4 md:px-6 py-3 space-y-2 text-sm">
              <a href="#analisa" className="block text-zinc-300 hover:text-white">Analisa</a>
              <a href="#watchlist" className="block text-zinc-300 hover:text-white">Watchlist</a>
              {isAdmin && <Link href="/admin" className="block text-zinc-300 hover:text-white">Admin</Link>}
              {!loggedIn ? (
                <div className="pt-2 flex gap-3">
                  <Link href="/login" className="text-zinc-300 hover:text-white">Login</Link>
                  <Link href="/register" className="rounded px-3 py-1.5 bg-white text-slate-900 font-medium">Daftar</Link>
                </div>
              ) : (
                <button onClick={logout} className="rounded px-3 py-1.5 bg-zinc-800 text-white">Logout</button>
              )}
            </div>
          </div>
        )}
        <div className="h-px bg-white/10" />
      </div>
    </header>
  )
}

