"use client"
import { useEffect, useState } from "react"
import { api } from "../../app/api"

type N = { id: number, kind: string, title: string, body: string, status: string, created_at: string, read_at?: string|null }

export default function NotificationsPanel(){
  const [rows,setRows]=useState<N[]>([])
  const [busy,setBusy]=useState(false)
  const [err,setErr]=useState('')
  const [filter,setFilter]=useState<'all'|'unread'>('unread')

  async function load(){
    try{
      setErr('')
      const params:any = {}
      if (filter==='unread') params.status='unread'
      const {data} = await api.get('admin/notifications', { params })
      setRows(data)
    }catch(e:any){ setErr(e?.response?.data?.detail || 'Gagal memuat notifikasi') }
  }
  useEffect(()=>{ load() },[filter])

  async function markRead(id:number){ try{ setBusy(true); await api.post(`admin/notifications/${id}/read`); await load() } finally{ setBusy(false) } }
  async function clearAll(){ if(!confirm('Tandai semua notifikasi sebagai terbaca?')) return; try{ setBusy(true); await api.post('admin/notifications/clear_all'); await load() } finally{ setBusy(false) } }

  return (
    <div className="rounded-2xl ring-1 ring-zinc-200 dark:ring-white/10 bg-white dark:bg-zinc-900 p-4 text-sm space-y-3">
      <div className="flex items-center justify-between">
        <div className="font-semibold">Notifikasi</div>
        <div className="flex items-center gap-2">
          <select value={filter} onChange={e=>setFilter(e.target.value as any)} className="aa-select">
            <option value="unread">Unread</option>
            <option value="all">All</option>
          </select>
          <button onClick={clearAll} disabled={busy} className="px-3 py-1.5 rounded bg-zinc-800 text-white hover:bg-zinc-700 disabled:opacity-50">Clear All</button>
        </div>
      </div>
      {err && <div className="rounded p-2 bg-rose-500/10 text-rose-300 ring-1 ring-rose-500/20">{err}</div>}
      <div className="space-y-2 max-h-[60vh] overflow-auto">
        {rows.map(n=> (
          <div key={n.id} className="rounded p-2 ring-1 ring-zinc-200 dark:ring-white/10 flex items-start justify-between gap-3">
            <div>
              <div className="font-medium">{n.title}</div>
              <div className="text-zinc-500 text-xs">{n.kind} • {new Date(n.created_at).toLocaleString()}</div>
              {!!n.body && <div className="text-sm mt-1">{n.body}</div>}
            </div>
            {n.status!=='read' ? (
              <button onClick={()=>markRead(n.id)} disabled={busy} className="px-2 py-1 rounded bg-cyan-600 text-white hover:bg-cyan-500">Mark read</button>
            ) : (
              <span className="text-xs opacity-60">read</span>
            )}
          </div>
        ))}
        {rows.length===0 && <div className="text-sm text-zinc-500">Tidak ada notifikasi.</div>}
      </div>
    </div>
  )}

