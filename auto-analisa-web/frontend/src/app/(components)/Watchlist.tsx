'use client'
import {useEffect, useState} from 'react'
import {api} from '../api'

export default function Watchlist({onPick}:{onPick:(s:string)=>void}){
  const [items,setItems]=useState<string[]>([])
  const [sym,setSym]=useState('')
  async function load(){ try{ const r=await api.get('watchlist'); setItems(r.data) }catch{} }
  async function add(){ if(!sym) return; try{ await api.post('watchlist/add', null, { params:{ symbol: sym } }); setSym(''); load() }catch(e:any){ alert(e?.response?.data?.detail || 'Gagal menambah') } }
  async function del(s:string){ try{ await api.delete(`watchlist/${s}`); load() }catch{} }
  useEffect(()=>{ load() },[])
  return (
    <div className="space-y-2">
      <div className="flex gap-2">
        <input value={sym} onChange={e=>setSym(e.target.value.toUpperCase())} placeholder="OPUSDT" className="border px-2 py-1 rounded w-full"/>
        <button onClick={add} className="px-3 py-1 rounded bg-blue-600 text-white">Add</button>
      </div>
      <ul className="space-y-1">
        {items.map(s=> (
          <li key={s} className="flex justify-between items-center">
            <button onClick={()=>onPick(s)} className="underline">{s}</button>
            <button onClick={()=>del(s)} className="text-red-600">×</button>
          </li>
        ))}
      </ul>
    </div>
  )
}

