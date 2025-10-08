'use client'
import {useState} from 'react'
import {api} from '../api'
import { normalizeSymbolInput } from '../../lib/hooks/useSymbols'

export default function AnalyzeForm({onDone}:{onDone:(plan:any)=>void}){
  const [symbol,setSymbol]=useState('XRPUSDT')
  const [loading,setLoading]=useState(false)
  const [followBias,setFollowBias]=useState<boolean>(()=>{
    if (typeof window==='undefined') return true
    const s = localStorage.getItem('follow_btc_bias')
    return s===null ? true : s==='1'
  })
  async function submit(){
    setLoading(true)
    try{
      const normalized = normalizeSymbolInput(symbol)
      if(!normalized){ alert('Simbol tidak valid.'); setLoading(false); return }
      if(normalized.includes('.P')){ alert('Simbol perpetual (.P) tidak valid untuk Spot.'); setLoading(false); return }
      try{ if (typeof window!=='undefined') localStorage.setItem('follow_btc_bias', followBias? '1':'0') }catch{}
      // Build snapshot server-side then analyze via v2
      const { data: snap } = await api.get('v2/snapshot', { params:{ symbol: normalized, timeframe: '1h' } })
      const { data } = await api.post('v2/analyze', snap, { params:{ follow_btc_bias: followBias } })
      onDone(data)
    }catch(e:any){
      if(e?.response?.status===409){ alert(e.response?.data?.detail || 'Maksimal 4 analisa aktif. Arsipkan salah satu dulu.') }
      else if(e?.response?.status===401){ alert('Harap login terlebih dulu') }
      else{ alert('Gagal menganalisa') }
    } finally{ setLoading(false) }
  }
  return (
    <div className="p-4 rounded-2xl shadow bg-white flex gap-3 items-end flex-wrap">
      <div className="flex flex-col">
        <label className="text-sm">Symbol</label>
        <input className="border rounded px-3 py-2" value={symbol} onChange={e=>setSymbol(e.target.value.toUpperCase())}/>
      </div>
      <label className="flex items-center gap-2 text-sm px-2 py-2 rounded bg-zinc-50">
        <input type="checkbox" checked={followBias} onChange={e=> setFollowBias(e.target.checked)} />
        Ikuti Bias BTC
      </label>
      <button onClick={submit} disabled={loading} className="px-4 py-2 rounded bg-black text-white">{loading?'Analisa v2…':'Analisa v2'}</button>
    </div>
  )
}
