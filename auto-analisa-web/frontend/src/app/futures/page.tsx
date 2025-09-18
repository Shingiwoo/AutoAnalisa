"use client"
import {useEffect, useState} from 'react'
import Link from 'next/link'
import { api } from '../api'
import WatchlistRow from '../(components)/WatchlistRow'
import FuturesCard from '../(components)/FuturesCard'

export default function FuturesPage(){
  const [cards,setCards]=useState<any[]>([])
  const [loggedIn,setLoggedIn]=useState(false)
  const [quota,setQuota]=useState<{limit:number, remaining:number, calls?:number, llm_enabled:boolean, futures_limit?:number, futures_remaining?:number}|null>(null)

  useEffect(()=>{
    if(typeof window!=='undefined'){
      const isLogged = !!(localStorage.getItem('token') || localStorage.getItem('access_token'))
      setLoggedIn(isLogged)
      if (isLogged) { load(); loadQuota() } else { setCards([]); setQuota(null) }
    }
  },[])

  async function loadQuota(){
    try{
      const r = await api.get('llm/quota')
      setQuota(r.data)
    }catch{ setQuota(null) }
  }
  async function load(){
    try{
      const r = await api.get('analyses', { params:{ status: 'active', trade_type: 'futures' } })
      setCards(r.data)
    }catch{}
  }
  async function analyze(symbol:string){
    if(cards.length>=4){ alert('Maksimal 4 analisa aktif. Arsipkan salah satu dulu.'); return }
    try{
      const {data}=await api.post('analyze',{symbol, trade_type: 'futures'})
      setCards(prev=>{
        const next=[data, ...prev]
        const seen = new Set<string>()
        const uniq: any[] = []
        for (const it of next){
          const key = `${it.symbol}:${it.trade_type||'futures'}`
          if(!seen.has(key)){ uniq.push(it); seen.add(key) }
        }
        return uniq.slice(0,4)
      })
    }catch(e:any){
      if(e?.response?.status===409) alert(e.response.data?.detail||'Maksimum 4 analisa aktif per user.')
      else alert('Gagal menganalisa')
    }
  }
  async function updateOne(idx:number){
    const c=cards[idx]
    try{
      const {data}=await api.post(`analyses/${c.id}/refresh`)
      const updated = data?.analysis
      if(updated){
        const cp=[...cards]; cp[idx]=updated; setCards(cp)
      }
    }catch(e:any){
      if(e?.response?.status===429) alert('Terlalu sering, coba lagi sebentar.')
      else alert('Gagal update analisa')
    }
  }

  const futRemaining = (quota?.futures_remaining ?? quota?.remaining ?? 0)
  const futLimit = (quota?.futures_limit ?? quota?.limit ?? 0)

  return (
    <main className="space-y-4">
      <div className="max-w-7xl mx-auto px-4 md:px-6 pt-6">
        <div className="flex items-center justify-between">
          <h1 className="text-xl font-semibold">Analisa Futures</h1>
          <Link href="/" className="text-sm underline">← Kembali ke Spot</Link>
        </div>
        <p className="mt-1 text-sm text-zinc-600">Halaman ini terpisah dari Spot. Setiap simbol dianalisa dalam konteks Futures.</p>
      </div>
      <div id="analisa" className="max-w-7xl mx-auto px-4 md:px-6 space-y-4">
        {loggedIn ? (
          <WatchlistRow quota={{ limit: futLimit, remaining: futRemaining, llm_enabled: !!quota?.llm_enabled }} onPick={(s)=>analyze(s)} titleLabel="Analisa Futures" onDelete={(s)=>{ setCards(prev=> prev.filter(c=> c.symbol !== s)) }} />
        ) : (
          <div className="rounded-2xl ring-1 ring-zinc-200 dark:ring-white/10 bg-white dark:bg-zinc-900 p-4 text-sm text-gray-600">Login untuk mengelola watchlist dan menganalisa.</div>
        )}
        {quota && (typeof futRemaining==='number') && (
          <div className="mt-1 text-xs opacity-60">LLM futures quota: {futRemaining}/{futLimit}</div>
        )}
        <div>
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {cards.map((c,idx)=> (
              <FuturesCard key={c.id} plan={c} onUpdate={()=>updateOne(idx)} llmEnabled={!!quota?.llm_enabled} llmRemaining={futRemaining} onAfterVerify={loadQuota} />
            ))}
          </div>
        </div>
        <div className="mt-6 text-xs opacity-60">Aturan: Edukasi, bukan saran finansial. Rate-limit aktif. Hasil per user terpisah.</div>
      </div>
    </main>
  )
}

