"use client"
import { useEffect, useState } from "react"
import { api } from "../../app/api"

type Row = { id: string, email: string, role: string, approved: boolean, blocked: boolean, created_at: string }

export default function UsersPanel(){
  const [rows,setRows]=useState<Row[]>([])
  const [busy,setBusy]=useState(false)
  const [err,setErr]=useState('')

  async function load(){
    try{ setErr(''); const {data}=await api.get('admin/users'); setRows(data) }catch(e:any){ setErr(e?.response?.data?.detail || 'Gagal memuat users') }
  }
  useEffect(()=>{ load() },[])

  async function act(path: string){ try{ setBusy(true); await api.post(path); await load() } finally{ setBusy(false) } }
  async function del(uid: string){ if(!confirm('Hapus user ini?')) return; try{ setBusy(true); await api.delete(`admin/users/${uid}`); await load() } finally{ setBusy(false) } }

  return (
    <div className="rounded-2xl ring-1 ring-zinc-200 dark:ring-white/10 bg-white dark:bg-zinc-900 p-4 text-sm">
      <div className="flex items-center justify-between mb-3">
        <div className="font-semibold">Users</div>
        <button onClick={load} className="px-3 py-1.5 rounded bg-zinc-800 text-white hover:bg-zinc-700 disabled:opacity-50" disabled={busy}>Reload</button>
      </div>
      {err && <div className="mb-3 rounded p-2 bg-rose-500/10 text-rose-300 ring-1 ring-rose-500/20">{err}</div>}
      <div className="overflow-auto">
        <table className="min-w-full text-left align-middle">
          <thead className="text-xs uppercase text-zinc-500">
            <tr>
              <th className="py-2 pr-3">Email</th>
              <th className="py-2 pr-3">Role</th>
              <th className="py-2 pr-3">Approved</th>
              <th className="py-2 pr-3">Blocked</th>
              <th className="py-2 pr-3">Actions</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-zinc-200 dark:divide-white/10">
            {rows.map(r=> (
              <tr key={r.id}>
                <td className="py-2 pr-3">{r.email}</td>
                <td className="py-2 pr-3">{r.role}</td>
                <td className="py-2 pr-3">{r.approved? 'Yes':'No'}</td>
                <td className="py-2 pr-3">{r.blocked? 'Yes':'No'}</td>
                <td className="py-2 pr-3 flex items-center gap-2">
                  {!r.approved && <button disabled={busy} onClick={()=>act(`admin/users/${r.id}/approve`)} className="px-2 py-1 rounded bg-cyan-600 text-white hover:bg-cyan-500">Approve</button>}
                  {!r.blocked && <button disabled={busy} onClick={()=>act(`admin/users/${r.id}/block`)} className="px-2 py-1 rounded bg-amber-600 text-white hover:bg-amber-500">Block</button>}
                  {r.blocked && <button disabled={busy} onClick={()=>act(`admin/users/${r.id}/unblock`)} className="px-2 py-1 rounded bg-green-600 text-white hover:bg-green-500">Unblock</button>}
                  <button disabled={busy} onClick={()=>del(r.id)} className="px-2 py-1 rounded bg-rose-600 text-white hover:bg-rose-500">Delete</button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}

