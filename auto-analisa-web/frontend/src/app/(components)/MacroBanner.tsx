'use client'
import { useEffect, useState } from 'react'
import { api } from '../api'

export default function MacroBanner(){
  const [txt,setTxt]=useState<string>('')
  const [date,setDate]=useState<string>('')
  useEffect(()=>{ (async()=>{
    try{ const {data}=await api.get('macro/today'); setTxt(data?.narrative||''); setDate(data?.date||'') }catch{}
  })() },[])
  if(!txt) return null
  return (
    <div className="p-2 bg-blue-50 border border-blue-200 rounded text-blue-800 text-sm">
      <div className="font-semibold">Makro Harian {date?`(${date})`:''}</div>
      <div>{txt}</div>
    </div>
  )
}

