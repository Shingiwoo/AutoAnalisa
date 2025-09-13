'use client'
import { useEffect, useState } from 'react'
import { api } from '../api'

export default function MacroBanner(){
  const [txt,setTxt]=useState<string>('')
  const [date,setDate]=useState<string>('')
  const [dateWib,setDateWib]=useState<string>('')
  useEffect(()=>{ (async()=>{
    try{ const {data}=await api.get('macro/today'); setTxt(data?.narrative||''); setDate(data?.date||''); setDateWib(data?.date_wib||'') }catch{}
  })() },[])
  if(!txt) return null
  return (
    <div className="p-2 bg-blue-50 border border-blue-200 rounded text-blue-800 text-sm">
      <div className="font-semibold flex items-center gap-2"><span aria-hidden>ℹ</span> <span>Makro Harian {dateWib?`(${dateWib} WIB)`: (date?`(${date})`:'')}</span></div>
      <div className="mt-0.5">{txt}</div>
    </div>
  )
}
