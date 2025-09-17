'use client'
import { useEffect, useMemo, useState } from 'react'
import { api } from '../api'

export default function MacroBanner(){
  const [data,setData]=useState<any|null>(null)
  const dateWib = data?.date_wib || ''
  const slot = (data?.slot||'')
  const header = useMemo(()=>{
    if(!dateWib && !data?.date) return 'Macro Harian'
    const d = dateWib ? `${dateWib} WIB` : (data?.date||'')
    const sl = slot ? ` • Slot: ${slot.charAt(0).toUpperCase()+slot.slice(1)}` : ''
    return `Macro Harian (${d}${sl})`
  },[dateWib, data?.date, slot])
  useEffect(()=>{ (async()=>{
    try{
      const {data}=await api.get('macro/today');
      setData(data||null)
    }catch{ setData(null) }
  })() },[])
  const txt = data?.narrative||''
  const sections = data?.sections||[]
  if(!txt && !(sections && sections.length)) return null
  return (
    <details className="p-2 bg-blue-50 border border-blue-200 rounded text-blue-800 text-sm" open>
      <summary className="font-semibold flex items-center gap-2 cursor-pointer select-none"><span aria-hidden>ℹ</span> <span>{header}</span></summary>
      {sections && sections.length ? (
        <div className="mt-1 grid grid-cols-1 md:grid-cols-2 gap-2">
          {sections.map((s:any,idx:number)=> (
            <div key={idx} className="bg-white/60 rounded p-2 text-blue-900">
              <div className="font-medium">{s?.title||'-'}</div>
              <ul className="list-disc pl-5 mt-1">
                {(s?.bullets||[]).map((b:string,i:number)=> <li key={i}>{b}</li>)}
              </ul>
            </div>
          ))}
        </div>
      ) : (
        <div className="mt-1">{txt}</div>
      )}
    </details>
  )
}
