'use client'
import {useEffect, useState} from 'react'
import PlanCard from './(components)/PlanCard'
import {api} from './api'
import { normalizeSymbolInput } from '../lib/hooks/useSymbols'
import Link from 'next/link'
import WatchlistRow from './(components)/WatchlistRow'
import SymbolQuickForm from './(components)/SymbolQuickForm'
import SymbolSearch from './(components)/SymbolSearch'
import MacroPanel from './(components)/MacroPanel'
import SessionsHint from './(components)/SessionsHint'
import PasswordRequest from './(components)/PasswordRequest'
import Hero from './(components)/Hero'
import UserGuide from './(components)/UserGuide'

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
  const [quota,setQuota]=useState<{limit:number, remaining:number, calls?:number, llm_enabled:boolean}|null>(null)

  useEffect(()=>{
    if(typeof window!=='undefined'){
      setIsAdmin(localStorage.getItem('role')==='admin')
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
      const r = await api.get('analyses', { params:{ status: 'active', trade_type: 'spot' } })
      setCards(r.data)
      // Try admin settings; ignore if forbidden
      try {
        const s = await api.get('admin/settings')
        if (s?.data?.use_llm === false) setNotice('LLM sedang OFF oleh admin / cap budget.')
      } catch {}
    }catch{}
  }

  async function analyze(symbol:string, trade_type:'spot'|'futures'='spot'){
    if(cards.length>=4){ alert('Maksimal 4 analisa aktif. Arsipkan salah satu dulu.'); return }
    const symUpper = normalizeSymbolInput(symbol)
    if(!symUpper){ alert('Simbol tidak valid.'); return }
    if(trade_type==='spot' && symUpper.includes('.P')){
      alert('Simbol perpetual (.P) tidak valid untuk analisa Spot.')
      return
    }
    try{
      const {data}=await api.post('analyze',{symbol: symUpper, trade_type})
      setNotice(data?.payload?.notice)
      setCards(prev=>{
        const next=[data, ...prev]
        // dedup by symbol+trade_type keep first
        const seen = new Set<string>()
        const uniq: any[] = []
        for (const it of next){
          const key = `${it.symbol}:${it.trade_type||'spot'}`
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
        setNotice(updated?.payload?.notice)
        const cp=[...cards]; cp[idx]=updated; setCards(cp)
      }
    }catch(e:any){
      if(e?.response?.status===429) alert('Terlalu sering, coba lagi sebentar.')
      else alert('Gagal update analisa')
    }
  }

  return (
    <main className="space-y-4">
      <Hero loggedIn={loggedIn} isAdmin={isAdmin} />
      <div className="max-w-7xl mx-auto px-4 md:px-6">
        <MacroPanel />
        {/* Sembunyikan hint jika admin mematikannya; fallback tetap tampil bila tidak bisa baca settings */}
        <SessionsHint />
        {notice && (
          <div className="mt-3 p-2 bg-amber-50 border border-amber-200 rounded text-amber-800 flex items-start gap-2 text-sm">
            <span aria-hidden>⚠</span>
            <span>{notice}</span>
          </div>
        )}
      </div>
      <div id="analisa" className="max-w-7xl mx-auto px-4 md:px-6 space-y-4">
        {loggedIn ? (
          <>
            {/* Pencarian simbol cepat dengan datalist (ketik untuk filter) */}
            <div className="mb-2">
              <SymbolSearch onPick={(s)=>analyze(s,'spot')} />
            </div>
            <SymbolQuickForm onAnalyze={(sym, type)=>analyze(sym, type)} disabled={cards.length>=4} />
            <WatchlistRow tradeType='spot' quota={quota} onPick={(s)=>analyze(s,'spot')} onDelete={(s)=>{ setCards(prev=> prev.filter(c=> c.symbol !== s)) }} />
            <div className="mt-2 text-xs text-zinc-600">Butuh Futures? Gunakan halaman khusus: <Link href="/futures" className="underline">/futures</Link></div>
          </>
        ) : (
          <div className="rounded-2xl ring-1 ring-zinc-200 dark:ring-white/10 bg-white dark:bg-zinc-900 p-4 text-sm text-gray-600">Login untuk mengelola watchlist dan menganalisa.</div>
        )}
        {loggedIn && (
          <div className="mt-3">
            <UserGuide />
          </div>
        )}
        {quota && !quota.llm_enabled && (
          <div className="mt-3 p-2 bg-amber-50 border border-amber-200 rounded text-amber-800 flex items-start gap-2 text-sm">
            <span aria-hidden>⚠</span>
            <span>LLM dinonaktifkan: {quota.remaining===0? 'limit harian tercapai' : 'budget bulanan tercapai / dimatikan admin'}</span>
          </div>
        )}
        <div>
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {cards.map((c,idx)=> (
              <PlanCard key={c.id} plan={c} onUpdate={()=>updateOne(idx)} llmEnabled={!!quota?.llm_enabled} llmRemaining={quota?.remaining ?? 0} onAfterVerify={loadQuota} />
            ))}
          </div>
        </div>
        <div className="mt-6 text-xs opacity-60">Aturan: Edukasi, bukan saran finansial. Rate-limit aktif. Hasil per user terpisah.</div>
      </div>
    </main>
  )
}
