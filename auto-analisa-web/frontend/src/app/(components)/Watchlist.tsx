'use client'
import {useEffect, useState} from 'react'
import {api} from '../api'

export default function Watchlist({onPick}:{onPick:(s:string)=>void}){
  const [items,setItems]=useState<string[]>([])
  const [sym,setSym]=useState('')
  const [msg,setMsg]=useState<string>('')
  async function load(){ try{ const r=await api.get('watchlist'); setItems(r.data) }catch{} }
  async function add(){
    if(!sym) return
    if(items.length >= 4){ setMsg('Maksimal 4 koin dalam watchlist.'); return }
    try{
      await api.post('watchlist/add', null, { params:{ symbol: sym } })
      setSym(''); setMsg(''); load()
    }catch(e:any){ setMsg(e?.response?.data?.detail || 'Gagal menambah') }
  }
  async function del(s:string){ try{ await api.delete(`watchlist/${s}`); load() }catch{} }
  useEffect(()=>{ load() },[])
  return (
    <div className="space-y-2">
      <div className="flex gap-2">
        <input value={sym} onChange={e=>setSym(e.target.value.toUpperCase())} placeholder="OPUSDT" className="border rounded px-3 py-2 w-full focus:outline-none focus:ring-2 focus:ring-blue-500"/>
        <button onClick={add} disabled={items.length>=4} className="px-3 py-2 rounded bg-blue-600 text-white font-medium hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed">Tambah</button>
      </div>
      {msg && <div className="p-2 bg-amber-50 border border-amber-200 text-amber-800 rounded text-xs flex items-start gap-2"><span aria-hidden>⚠</span><span>{msg}</span></div>}
      <div className="flex flex-wrap gap-2">
        {items.map(s=> (
          <div key={s} className="inline-flex items-center px-3 py-1 rounded-full bg-gray-100 text-sm font-medium text-gray-800">
            <button onClick={()=>onPick(s)} className="mr-2 hover:underline">{s}</button>
            <button onClick={()=> (confirm(`Hapus ${s}?`) && del(s))} className="text-red-600 hover:text-red-800" title="Remove">×</button>
          </div>
        ))}
      </div>
    </div>
  )
}
