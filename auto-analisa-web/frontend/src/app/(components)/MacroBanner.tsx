'use client'
import { useEffect, useState } from 'react'
import { api } from '../api'

export default function MacroBanner(){
  const [txt,setTxt]=useState<string>('')
  const [date,setDate]=useState<string>('')
  const [dateWib,setDateWib]=useState<string>('')
  const [sections,setSections]=useState<any[]|null>(null)
  useEffect(()=>{ (async()=>{
    try{
      const {data}=await api.get('macro/today');
      setTxt(data?.narrative||''); setDate(data?.date||''); setDateWib(data?.date_wib||''); setSections(data?.sections||null)
    }catch{}
  })() },[])
  if(!txt && !(sections && sections.length)) return null
  return (
    <div className="p-2 bg-blue-50 border border-blue-200 rounded text-blue-800 text-sm">
      <div className="font-semibold flex items-center gap-2"><span aria-hidden>ℹ</span> <span>Makro Harian {dateWib?`(${dateWib} WIB)`: (date?`(${date})`:'')}</span></div>
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
        <div className="mt-0.5">{txt}</div>
      )}
    </div>
  )
}
