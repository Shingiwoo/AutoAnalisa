'use client'
import { useEffect } from 'react'
import { useRouter } from 'next/navigation'
import JournalTradeForm from '../(components)/JournalTradeForm'
import JournalTradeTable from '../(components)/JournalTradeTable'

export default function JournalTradePage(){
  const router = useRouter()
  useEffect(()=>{
    try{
      const tok = typeof window !== 'undefined' ? (localStorage.getItem('access_token') || localStorage.getItem('token')) : null
      if(!tok){ router.replace('/login') }
    }catch{}
  },[router])
  return (
    <main className="mx-auto max-w-6xl px-4 md:px-6 py-6 space-y-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Journal Trade</h1>
        <p className="text-sm text-zinc-500">Catat trade Anda (manual) lengkap dengan perhitungan dasar dan export CSV.</p>
      </div>
      <JournalTradeForm onSaved={()=>{ /* hint: could refresh table via event, simple page reload for now */ location.reload() }} />
      <JournalTradeTable />
    </main>
  )
}

