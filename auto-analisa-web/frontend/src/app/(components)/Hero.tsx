"use client"
import Link from "next/link"

export default function Hero({ loggedIn, isAdmin }:{ loggedIn:boolean, isAdmin:boolean }){
  return (
    <section className="relative isolate overflow-hidden rounded-2xl bg-slate-950 text-white ring-1 ring-white/10 mx-4 md:mx-6 mt-4">
      <div className="absolute inset-x-0 -top-40 -z-10 blur-3xl" aria-hidden>
        <div className="h-72 bg-[radial-gradient(60%_60%_at_50%_0%,rgba(56,189,248,0.35)_0%,rgba(56,189,248,0)_60%)]" />
      </div>
      <div className="px-6 py-12 md:px-12 md:py-16 max-w-5xl">
        <h1 className="text-3xl md:text-5xl font-bold tracking-tight">Analisis Crypto Otomatis, Cepat & Jelas</h1>
        <p className="mt-3 text-zinc-300 max-w-2xl">Dapatkan rencana intraday lengkap: bias dominan, level kunci, entri, TP, dan invalidasi — dihasilkan otomatis berdasarkan data pasar terbaru.</p>
        <div className="mt-6 flex flex-wrap gap-3">
          <a href="#analisa" className="rounded px-4 py-2 bg-white text-slate-900 font-medium hover:bg-zinc-200">Mulai Analisa</a>
          <Link href="/futures" className="rounded px-4 py-2 bg-indigo-600 text-white hover:bg-indigo-500">Futures</Link>
          {isAdmin && <Link href="/admin" className="rounded px-4 py-2 bg-zinc-800 text-white hover:bg-zinc-700">Ke Admin</Link>}
          {!loggedIn && <Link href="/register" className="rounded px-4 py-2 bg-cyan-600 text-white hover:bg-cyan-500">Buat Akun</Link>}
        </div>
      </div>
      <div className="absolute inset-0 -z-20 bg-[linear-gradient(to_right,transparent_0,transparent_calc(50%-0.5px),rgba(255,255,255,.06)_50%,transparent_calc(50%+0.5px),transparent_100%)] bg-[length:40px_40px] [mask-image:radial-gradient(closest-side_at_50%_50%,black,transparent_85%)]" />
    </section>
  )
}
