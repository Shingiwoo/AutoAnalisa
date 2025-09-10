'use client'
import {useState} from 'react'
import {api} from '../api'

export default function AnalyzeForm({onDone}:{onDone:(plan:any)=>void}){
  const [symbol,setSymbol]=useState('XRPUSDT')
  const [loading,setLoading]=useState(false)
  async function submit(){
    setLoading(true)
    try{
      const {data}=await api.post('/api/analyze',{symbol})
      onDone(data)
    }catch(e:any){
      if(e?.response?.status===409){ alert(e.response?.data?.detail || 'Maksimal 4 analisa aktif. Arsipkan salah satu dulu.') }
      else if(e?.response?.status===401){ alert('Harap login terlebih dulu') }
      else{ alert('Gagal menganalisa') }
    } finally{ setLoading(false) }
  }
  return (
    <div className="p-4 rounded-2xl shadow bg-white flex gap-2 items-end">
      <div className="flex flex-col">
        <label className="text-sm">Symbol</label>
        <input className="border rounded px-3 py-2" value={symbol} onChange={e=>setSymbol(e.target.value.toUpperCase())}/>
      </div>
      <button onClick={submit} disabled={loading} className="px-4 py-2 rounded bg-black text-white">{loading?'Analisa…':'Analisa'}</button>
    </div>
  )
}
