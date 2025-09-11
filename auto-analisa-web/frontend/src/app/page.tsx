'use client'
import {useEffect, useState} from 'react'
import PlanCard from './(components)/PlanCard'
import {api} from './api'
import Link from 'next/link'
import Watchlist from './(components)/Watchlist'
import WatchlistRow from './(components)/WatchlistRow'
import MacroBanner from './(components)/MacroBanner'
import PasswordRequest from './(components)/PasswordRequest'
import Hero from './(components)/Hero'

function scoreLabel(score:number){
  if(score>=70) return {text:'Kuat', color:'bg-green-600'}
  if(score>=50) return {text:'Menengah', color:'bg-yellow-500'}
  if(score>=30) return {text:'Lemah', color:'bg-orange-500'}
  return {text:'Hindari', color:'bg-red-600'}
}

export default function Page(){
  const [cards,setCards]=useState<any[]>([])
  const [notice,setNotice]=useState<string|undefined>(undefined)
  const [isAdmin,setIsAdmin]=useState(false)
  const [loggedIn,setLoggedIn]=useState(false)

  useEffect(()=>{
    if(typeof window!=='undefined'){
      setIsAdmin(localStorage.getItem('role')==='admin')
      const isLogged = !!(localStorage.getItem('token') || localStorage.getItem('access_token'))
      setLoggedIn(isLogged)
      if (isLogged) load(); else setCards([])
    }
  },[])

  async function load(){
    try{
      const r = await api.get('analyses', { params:{ status: 'active' } })
      setCards(r.data)
      // Try admin settings; ignore if forbidden
      try {
        const s = await api.get('admin/settings')
        if (s?.data?.use_llm === false) setNotice('LLM sedang OFF oleh admin / cap budget.')
      } catch {}
    }catch{}
  }

  async function analyze(symbol:string){
    if(cards.length>=4){ alert('Maksimal 4 analisa aktif. Arsipkan salah satu dulu.'); return }
    try{
      const {data}=await api.post('analyze',{symbol})
      setNotice(data?.payload?.notice)
      setCards(prev=>{
        const next=[data, ...prev]
        // dedup by symbol keep first
        const seen = new Set<string>()
        const uniq: any[] = []
        for (const it of next){ if(!seen.has(it.symbol)){ uniq.push(it); seen.add(it.symbol) } }
        return uniq.slice(0,4)
      })
    }catch(e:any){
      if(e?.response?.status===409) alert(e.response.data?.detail||'Maksimum 4 analisa aktif per user.')
      else alert('Gagal menganalisa')
    }
  }

  async function updateOne(idx:number){
    const c=cards[idx]
    const {data}=await api.post('analyze',{symbol:c.symbol})
    setNotice(data?.payload?.notice)
    const cp=[...cards]; cp[idx]=data; setCards(cp)
  }

  return (
    <main className="space-y-4">
      <Hero loggedIn={loggedIn} isAdmin={isAdmin} />
      <div className="max-w-7xl mx-auto px-4 md:px-6">
        <MacroBanner />
        {notice && (
          <div className="mt-3 p-2 bg-amber-50 border border-amber-200 rounded text-amber-800 flex items-start gap-2 text-sm">
            <span aria-hidden>⚠</span>
            <span>{notice}</span>
          </div>
        )}
      </div>
      <div id="analisa" className="max-w-7xl mx-auto px-4 md:px-6 space-y-4">
        {loggedIn ? (
          <WatchlistRow onPick={analyze} />
        ) : (
          <div className="rounded-2xl ring-1 ring-zinc-200 dark:ring-white/10 bg-white dark:bg-zinc-900 p-4 text-sm text-gray-600">Login untuk mengelola watchlist dan menganalisa.</div>
        )}
        <div>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {cards.map((c,idx)=> (
              <PlanCard key={c.id} plan={c} onUpdate={()=>updateOne(idx)} />
            ))}
          </div>
        </div>
        <div className="mt-6 text-xs opacity-60">Aturan: Edukasi, bukan saran finansial. Rate-limit aktif. Hasil per user terpisah.</div>
      </div>
    </main>
  )
}
