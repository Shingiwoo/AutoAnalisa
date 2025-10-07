'use client'
import { useEffect, useState } from 'react'
import { useRouter } from 'next/navigation'
import { api } from '../api'

type Entry = {
  id: number
  title: string
  content: string
  created_at: string
  updated_at: string
}

export default function JournalPage(){
  const [list,setList]=useState<Entry[]>([])
  const [loading,setLoading]=useState(true)
  const [err,setErr]=useState('')
  const [title,setTitle]=useState('')
  const [content,setContent]=useState('')
  const [saving,setSaving]=useState(false)

  const [editId,setEditId]=useState<number|null>(null)
  const [editTitle,setEditTitle]=useState('')
  const [editContent,setEditContent]=useState('')

  const router = useRouter()

  useEffect(()=>{
    try{
      const tok = typeof window !== 'undefined' ? (localStorage.getItem('access_token') || localStorage.getItem('token')) : null
      if(!tok){ router.replace('/login'); return }
    }catch{}
    ;(async()=>{
      setLoading(true)
      setErr('')
      try{
        const r = await api.get('/journal')
        setList(r.data || [])
      }catch(e:any){ setErr('Gagal memuat journal.') }
      finally{ setLoading(false) }
    })()
  },[router])

  async function createEntry(e: React.FormEvent){
    e.preventDefault()
    setSaving(true); setErr('')
    try{
      const r = await api.post('/journal', { title: title.trim(), content })
      setList(prev=> [r.data, ...prev])
      setTitle(''); setContent('')
    }catch(e:any){ setErr('Gagal membuat catatan.') }
    finally{ setSaving(false) }
  }

  async function del(id: number){
    if(!confirm('Hapus catatan ini?')) return
    try{
      await api.delete(`/journal/${id}`)
      setList(prev=> prev.filter(x=>x.id!==id))
    }catch{ alert('Gagal menghapus') }
  }

  function startEdit(it: Entry){
    setEditId(it.id)
    setEditTitle(it.title)
    setEditContent(it.content)
  }

  function cancelEdit(){
    setEditId(null)
    setEditTitle('')
    setEditContent('')
  }

  async function saveEditRow(){
    if(editId==null) return
    try{
      const r = await api.put(`/journal/${editId}`, { title: editTitle.trim(), content: editContent })
      setList(prev=> prev.map(x=> x.id===editId? r.data : x))
      cancelEdit()
    }catch{ alert('Gagal menyimpan') }
  }

  return (
    <main className="mx-auto max-w-6xl px-4 md:px-6 py-6">
      <div className="mb-6">
        <h1 className="text-2xl font-bold tracking-tight">Journal</h1>
        <p className="text-sm text-zinc-500">Catatan pribadi Anda dalam format tabel. Hanya Anda yang dapat mengakses.</p>
      </div>

      <section className="mb-8 rounded-2xl ring-1 ring-white/10 bg-white/50 dark:bg-white/5 backdrop-blur p-4">
        <h2 className="font-semibold mb-3">Catatan baru</h2>
        {err && <div className="mb-3 rounded bg-rose-500/10 text-rose-400 ring-1 ring-inset ring-rose-500/20 px-3 py-2 text-sm">{err}</div>}
        <form onSubmit={createEntry} className="grid gap-3 md:grid-cols-2">
          <input value={title} onChange={e=>setTitle(e.target.value)} placeholder="Judul" className="w-full rounded px-3 py-2 ring-1 ring-inset ring-zinc-200 focus:outline-none focus:ring-2 focus:ring-cyan-500 bg-white text-zinc-900 dark:bg-white dark:text-zinc-900"/>
          <div className="md:col-span-2">
            <textarea value={content} onChange={e=>setContent(e.target.value)} placeholder="Isi catatan…" rows={4} className="w-full rounded px-3 py-2 ring-1 ring-inset ring-zinc-200 focus:outline-none focus:ring-2 focus:ring-cyan-500 bg-white text-zinc-900 dark:bg-white dark:text-zinc-900"/>
          </div>
          <div className="md:col-span-2">
            <button disabled={saving} className="rounded px-4 py-2 bg-cyan-600 text-white hover:bg-cyan-500 disabled:opacity-50">{saving? 'Menyimpan…':'Simpan'}</button>
          </div>
        </form>
      </section>

      <section>
        <h2 className="font-semibold mb-3">Daftar catatan</h2>
        {loading ? (
          <div className="text-sm text-zinc-500">Memuat…</div>
        ) : (
          <div className="overflow-x-auto rounded-2xl ring-1 ring-white/10 bg-white/50 dark:bg-white/5">
            {list.length===0 ? (
              <div className="px-4 py-6 text-sm text-zinc-500">Belum ada catatan.</div>
            ) : (
              <table className="min-w-full text-sm">
                <thead>
                  <tr className="text-left text-zinc-500 border-b border-white/10">
                    <th className="px-4 py-3">Tanggal</th>
                    <th className="px-4 py-3">Judul</th>
                    <th className="px-4 py-3 hidden md:table-cell">Isi</th>
                    <th className="px-4 py-3 hidden md:table-cell">Diperbarui</th>
                    <th className="px-4 py-3">Aksi</th>
                  </tr>
                </thead>
                <tbody>
                  {list.map(it=> (
                    <tr key={it.id} className="border-b border-white/10 align-top">
                      <td className="px-4 py-3 whitespace-nowrap">{new Date(it.created_at).toLocaleString()}</td>
                      <td className="px-4 py-3">
                        {editId===it.id ? (
                          <input value={editTitle} onChange={e=>setEditTitle(e.target.value)} className="w-full rounded px-2 py-1 ring-1 ring-inset ring-zinc-200 focus:outline-none focus:ring-2 focus:ring-cyan-500 bg-white text-zinc-900 dark:bg-white dark:text-zinc-900"/>
                        ) : (
                          <div className="font-medium break-words max-w-[28rem] md:max-w-none">{it.title || '(Tanpa judul)'}</div>
                        )}
                        <div className="mt-2 md:hidden text-xs text-zinc-500">Diperbarui: {new Date(it.updated_at).toLocaleString()}</div>
                        <div className="mt-2 md:hidden text-xs text-zinc-700 dark:text-zinc-300 break-words opacity-90">{(editId===it.id? '' : it.content)}</div>
                      </td>
                      <td className="px-4 py-3 hidden md:table-cell">
                        {editId===it.id ? (
                          <textarea value={editContent} onChange={e=>setEditContent(e.target.value)} rows={3} className="w-full rounded px-2 py-1 ring-1 ring-inset ring-zinc-200 focus:outline-none focus:ring-2 focus:ring-cyan-500 bg-white text-zinc-900 dark:bg-white dark:text-zinc-900"/>
                        ) : (
                          <div className="max-w-[38rem] overflow-hidden text-ellipsis whitespace-nowrap md:whitespace-normal break-words">{it.content}</div>
                        )}
                      </td>
                      <td className="px-4 py-3 hidden md:table-cell whitespace-nowrap">{new Date(it.updated_at).toLocaleString()}</td>
                      <td className="px-4 py-3 whitespace-nowrap">
                        {editId===it.id ? (
                          <div className="flex gap-2">
                            <button className="rounded px-3 py-1.5 bg-cyan-600 text-white hover:bg-cyan-500" onClick={saveEditRow}>Simpan</button>
                            <button className="rounded px-3 py-1.5 bg-zinc-800 text-white hover:bg-zinc-700" onClick={cancelEdit}>Batal</button>
                          </div>
                        ) : (
                          <div className="flex gap-2">
                            <button className="rounded px-3 py-1.5 bg-zinc-800 text-white hover:bg-zinc-700" onClick={()=>startEdit(it)}>Edit</button>
                            <button className="rounded px-3 py-1.5 bg-rose-600 text-white hover:bg-rose-500" onClick={()=>del(it.id)}>Hapus</button>
                          </div>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        )}
      </section>
    </main>
  )
}
