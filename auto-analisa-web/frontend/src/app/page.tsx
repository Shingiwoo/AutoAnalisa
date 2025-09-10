'use client'
import {useEffect, useMemo, useState} from 'react'
import AnalyzeForm from './(components)/AnalyzeForm'
import PlanCard from './(components)/PlanCard'
import {api} from './api'
import AuthBar from '../components/AuthBar'
import Link from 'next/link'

function scoreLabel(score:number){
  if(score>=70) return {text:'Kuat', color:'bg-green-600'}
  if(score>=50) return {text:'Menengah', color:'bg-yellow-500'}
  if(score>=30) return {text:'Lemah', color:'bg-orange-500'}
  return {text:'Hindari', color:'bg-red-600'}
}

export default function Page(){
  const [cards,setCards]=useState<any[]>([])
  const [notice,setNotice]=useState<string|undefined>(undefined)
  const isAdmin = useMemo(()=>typeof window!=='undefined' && localStorage.getItem('role')==='admin',[])

  async function onNew(symbol:string){
    if(cards.length>=4){ alert('Maksimal 4 analisa aktif. Arsipkan salah satu dulu.'); return }
    try{
      const {data}=await api.post('/api/analyze',{symbol})
      setNotice(data?.payload?.notice)
      setCards(prev=>[data, ...prev].slice(0,4))
    }catch(e:any){
      if(e?.response?.status===409) alert(e.response.data?.detail||'Maksimum 4 analisa aktif per user.')
      else alert('Gagal menganalisa')
    }
  }

  async function updateOne(idx:number){
    const c=cards[idx]
    const {data}=await api.post('/api/analyze',{symbol:c.symbol})
    setNotice(data?.payload?.notice)
    const cp=[...cards]; cp[idx]=data; setCards(cp)
  }

  return (
    <main className="max-w-5xl mx-auto p-6 space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl md:text-3xl font-bold">Auto Analisa</h1>
        <div className="flex items-center gap-3">
          {isAdmin && <Link href="/admin" className="underline text-sm">Admin</Link>}
          <AuthBar onAuth={()=>location.reload()} />
        </div>
      </div>
      <AnalyzeForm onDone={(plan:any)=>setCards(prev=>[plan,...prev].slice(0,4))} />
      {notice && <div className="p-2 bg-amber-100 border border-amber-300 rounded text-amber-800">{notice}</div>}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {cards.map((c,idx)=> <PlanCard key={c.id} plan={c} onUpdate={()=>updateOne(idx)} onArchive={async()=>{
          try{ await api.post(`/api/archive/${c.id}`); setCards(cards.filter(x=>x.id!==c.id)) }catch{ alert('Gagal mengarsipkan') }
        }} />)}
      </div>
      <div className="text-xs opacity-60">Aturan: Edukasi, bukan saran finansial. Rate-limit aktif. Hasil per user terpisah.</div>
    </main>
  )
}
