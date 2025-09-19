"use client"
import { useEffect, useState } from 'react'
import { api } from '../api'
import { Plus, X } from 'lucide-react'

export default function WatchlistRow({ quota, onPick, onPickFutures, onDelete, titleLabel, tradeType='spot' }:{ quota?:{limit:number,remaining:number,llm_enabled:boolean}|null, onPick:(s:string)=>void, onPickFutures?:(s:string)=>void, onDelete?: (s:string)=>void, titleLabel?: string, tradeType?: 'spot'|'futures' }){
  const [items,setItems]=useState<string[]>([])
  const [sym,setSym]=useState('')
  const [msg,setMsg]=useState<string>('')
  async function load(){ try{ const r=await api.get('watchlist', { params:{ trade_type: tradeType } }); setItems(r.data||[]) }catch(e:any){ setMsg(e?.response?.data?.detail||'Gagal memuat watchlist') } }
  async function add(){
    if(!sym) return
    if(items.length >= 4){ setMsg('Maksimal 4 koin dalam watchlist.'); return }
    try{
      await api.post('watchlist/add', null, { params:{ symbol: sym.toUpperCase().trim(), trade_type: tradeType } })
      setSym(''); setMsg(''); load()
    }catch(e:any){ setMsg(e?.response?.data?.detail || 'Gagal menambah simbol') }
  }
  async function del(s:string){
    try{
      await api.delete(`watchlist/${encodeURIComponent(s)}`, { params:{ trade_type: tradeType } })
      onDelete?.(s)
      load()
    }catch(e:any){ setMsg(e?.response?.data?.detail || 'Gagal menghapus simbol') }
  }
  useEffect(()=>{ load() },[])
  return (
    <section id="watchlist" className="rounded-2xl ring-1 ring-zinc-200 dark:ring-white/10 bg-white dark:bg-zinc-900 p-4 text-zinc-900 dark:text-zinc-100">
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4 items-start">
        <div>
          <h3 className="font-semibold mb-2">Watchlist</h3>
          <div className="flex gap-2 items-center">
            <input
              value={sym}
              onChange={e=>setSym(e.target.value.toUpperCase())}
              placeholder="OPUSDT"
              className="rounded px-3 py-2 w-full bg-white text-zinc-900 ring-1 ring-inset ring-zinc-200 focus:outline-none focus:ring-2 focus:ring-cyan-500 dark:bg-transparent dark:text-white placeholder:text-zinc-400 dark:ring-white/10"
            />
            <button onClick={add} disabled={items.length>=4} className="inline-flex items-center gap-1 px-3 py-2 rounded bg-cyan-600 text-white font-medium hover:bg-cyan-500 disabled:opacity-50"><Plus size={16}/> Tambah</button>
            {quota && (
              <span className={`px-2 py-1 rounded text-xs ${quota.remaining>0? 'bg-emerald-600':'bg-rose-600'} text-white`} title={quota.llm_enabled? 'LLM aktif':'LLM nonaktif'}>
                LLM {quota.remaining}/{quota.limit}
              </span>
            )}
          </div>
          {msg && <div className="mt-2 text-xs text-rose-500">{msg}</div>}
        </div>
        <div>
          <h3 className="sr-only">Daftar Koin</h3>
          <div className="flex flex-wrap gap-2">
            {items.map(s=> (
              <div key={s} className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-zinc-100 dark:bg-zinc-800 text-sm font-medium text-zinc-800 dark:text-zinc-100">
                <button onClick={()=>onPick(s)} className="hover:underline" title={titleLabel || 'Analisa Spot'}>{s}</button>
                {onPickFutures && <button onClick={()=>onPickFutures!(s)} className="px-2 py-0.5 rounded bg-indigo-600 text-white text-xs hover:bg-indigo-500" title="Analisa Futures">Fut</button>}
                <button onClick={()=> (confirm(`Hapus ${s}?`) && del(s))} className="text-rose-600 hover:text-rose-700" title="Remove"><X size={16}/></button>
              </div>
            ))}
          </div>
        </div>
      </div>
    </section>
  )
}
