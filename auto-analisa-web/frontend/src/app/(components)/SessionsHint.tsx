"use client"
import { useEffect, useState } from 'react'
import { api } from '../api'

type Bucket = { hour:number, n:number, mean:number, hit_rate:number, ci_low:number, ci_high:number, p_value:number, effect:number, tz:string }

export default function SessionsHint(){
  const [buckets,setBuckets]=useState<Bucket[]|null>(null)
  const [show,setShow]=useState<boolean>(true)
  useEffect(()=>{ (async()=>{
    try{ const s = await api.get('public/settings'); if(s?.data && s.data.show_sessions_hint===false){ setShow(false); return } }catch{}
    try{ const {data}=await api.get('sessions/btc/wib'); setBuckets(data||[]) }catch{ setBuckets([]) }
  })() },[])
  if(!show) return null
  if(!buckets || buckets.length===0) return null
  return (
    <div className="p-2 bg-emerald-50 border border-emerald-200 rounded text-emerald-800 text-sm">
      <div className="font-semibold">Jam hijau/merah signifikan (WIB)</div>
      <div className="mt-1 flex flex-wrap gap-2">
        {buckets.map(b=> (
          <span key={b.hour} className={`px-2 py-0.5 rounded ${b.mean>=0? 'bg-emerald-600 text-white':'bg-rose-600 text-white'}`} title={`n=${b.n}, mean=${b.mean.toFixed(4)}, hit=${(b.hit_rate*100).toFixed(1)}%, p=${b.p_value.toFixed(3)}`}>
            {String(b.hour).padStart(2,'0')}:00
          </span>
        ))}
      </div>
    </div>
  )
}
