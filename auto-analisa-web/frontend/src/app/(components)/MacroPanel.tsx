"use client"
import { useEffect, useState } from 'react'
import { api } from '../api'

export default function MacroPanel(){
  const [data,setData]=useState<any|null>(null)
  const [open,setOpen]=useState(true)
  const [err,setErr]=useState('')
  useEffect(()=>{ (async()=>{
    try{ const {data}=await api.get('macro/today'); setData(data) }catch(e:any){ setErr(e?.response?.data?.detail||'') }
  })() },[])
  if(!data && !err) return null
  const dateLabel = data?.date_wib ? `${data.date_wib} WIB` : (data?.date||'')
  const slot = data?.slot
  const status = (data?.last_run_status||'').toLowerCase()
  const statusColor = status==='ok'? 'bg-emerald-600' : status==='skip'? 'bg-amber-600' : status==='error'? 'bg-rose-600':'bg-zinc-500'
  return (
    <section className="rounded-2xl ring-1 ring-zinc-200 dark:ring-white/10 bg-white dark:bg-zinc-900 p-3">
      <div className="flex items-center justify-between">
        <div className="font-semibold flex items-center gap-2">
          Makro Harian {dateLabel? `(${dateLabel})`:''}
          {slot && <span className="px-2 py-0.5 rounded bg-zinc-800 text-white text-xs">{slot}</span>}
          {status && <span className={`px-2 py-0.5 rounded text-white text-xs ${statusColor}`} title={data?.last_run_wib? `Last run: ${new Date(data.last_run_wib).toLocaleString('id-ID',{ timeZone:'Asia/Jakarta' })} WIB`:''}>{status}</span>}
        </div>
        <button className="text-sm underline" onClick={()=>setOpen(o=>!o)}>{open?'Tutup':'Buka'}</button>
      </div>
      {open && (
        <div className="mt-2 text-sm space-y-2">
          {data?.narrative && <div className="italic text-zinc-700 dark:text-zinc-300">{data.narrative}</div>}
          {(Array.isArray(data?.sections) && data.sections.length>0) ? (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
              {data.sections.map((s:any,idx:number)=> (
                <div key={idx} className="rounded border border-zinc-200 dark:border-white/10 p-2">
                  <div className="font-medium">{s?.title||'-'}</div>
                  <ul className="list-disc pl-5 mt-1">
                    {(s?.bullets||[]).map((b:string,i:number)=> <li key={i}>{b}</li>)}
                  </ul>
                </div>
              ))}
            </div>
          ) : (
            <div className="text-xs text-zinc-500">Belum ada makro signifikan untuk slot ini.</div>
          )}
        </div>
      )}
    </section>
  )
}
