'use client'
import { useEffect, useState } from 'react'
import Link from 'next/link'
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
  const router = useRouter()

  useEffect(()=>{
    // guard: redirect if not logged in
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

  async function saveEdit(it: Entry, next: Partial<Entry>){
    try{
      const r = await api.put(`/journal/${it.id}`, next)
      setList(prev=> prev.map(x=> x.id===it.id? r.data : x))
    }catch{ alert('Gagal menyimpan') }
  }

  return (
    <main className="mx-auto max-w-5xl px-4 md:px-6 py-6">
      <div className="mb-6">
        <h1 className="text-2xl font-bold tracking-tight">Journal</h1>
        <p className="text-sm text-zinc-500">Catatan pribadi Anda. Hanya Anda yang dapat mengakses.</p>
      </div>

      <section className="mb-8 rounded-2xl ring-1 ring-white/10 bg-white/50 dark:bg-white/5 backdrop-blur p-4">
        <h2 className="font-semibold mb-3">Catatan baru</h2>
        {err && <div className="mb-3 rounded bg-rose-500/10 text-rose-400 ring-1 ring-inset ring-rose-500/20 px-3 py-2 text-sm">{err}</div>}
        <form onSubmit={createEntry} className="space-y-3">
          <input value={title} onChange={e=>setTitle(e.target.value)} placeholder="Judul" className="w-full rounded px-3 py-2 ring-1 ring-inset ring-zinc-200 focus:outline-none focus:ring-2 focus:ring-cyan-500 bg-white text-zinc-900 dark:bg-white dark:text-zinc-900"/>
          <textarea value={content} onChange={e=>setContent(e.target.value)} placeholder="Isi catatan…" rows={5} className="w-full rounded px-3 py-2 ring-1 ring-inset ring-zinc-200 focus:outline-none focus:ring-2 focus:ring-cyan-500 bg-white text-zinc-900 dark:bg-white dark:text-zinc-900"/>
          <button disabled={saving} className="rounded px-4 py-2 bg-cyan-600 text-white hover:bg-cyan-500 disabled:opacity-50">{saving? 'Menyimpan…':'Simpan'}</button>
        </form>
      </section>

      <section>
        <h2 className="font-semibold mb-3">Daftar catatan</h2>
        {loading ? (
          <div className="text-sm text-zinc-500">Memuat…</div>
        ) : (
          <div className="space-y-3">
            {list.length===0 && <div className="text-sm text-zinc-500">Belum ada catatan.</div>}
            {list.map(it=> <EntryCard key={it.id} it={it} onDelete={()=>del(it.id)} onSave={(next)=>saveEdit(it, next)} />)}
          </div>
        )}
      </section>
    </main>
  )
}

function EntryCard({ it, onDelete, onSave }:{ it: Entry, onDelete: ()=>void, onSave: (next: Partial<Entry>)=>void }){
  const [edit,setEdit]=useState(false)
  const [title,setTitle]=useState(it.title)
  const [content,setContent]=useState(it.content)
  return (
    <div className="rounded-2xl ring-1 ring-white/10 bg-white/50 dark:bg-white/5 backdrop-blur p-4">
      {edit ? (
        <div className="space-y-2">
          <input value={title} onChange={e=>setTitle(e.target.value)} className="w-full rounded px-3 py-2 ring-1 ring-inset ring-zinc-200 focus:outline-none focus:ring-2 focus:ring-cyan-500 bg-white text-zinc-900 dark:bg-white dark:text-zinc-900"/>
          <textarea value={content} onChange={e=>setContent(e.target.value)} rows={5} className="w-full rounded px-3 py-2 ring-1 ring-inset ring-zinc-200 focus:outline-none focus:ring-2 focus:ring-cyan-500 bg-white text-zinc-900 dark:bg-white dark:text-zinc-900"/>
          <div className="flex gap-2">
            <button className="rounded px-3 py-1.5 bg-cyan-600 text-white hover:bg-cyan-500" onClick={()=>{ onSave({ title: title.trim(), content }); setEdit(false) }}>Simpan</button>
            <button className="rounded px-3 py-1.5 bg-zinc-800 text-white hover:bg-zinc-700" onClick={()=>{ setTitle(it.title); setContent(it.content); setEdit(false) }}>Batal</button>
          </div>
        </div>
      ) : (
        <div>
          <div className="flex items-start justify-between gap-3">
            <h3 className="font-medium">{it.title || '(Tanpa judul)'}</h3>
            <div className="flex gap-2 shrink-0">
              <button className="rounded px-3 py-1.5 bg-zinc-800 text-white hover:bg-zinc-700" onClick={()=>setEdit(true)}>Edit</button>
              <button className="rounded px-3 py-1.5 bg-rose-600 text-white hover:bg-rose-500" onClick={onDelete}>Hapus</button>
            </div>
          </div>
          {it.content && <p className="mt-2 whitespace-pre-wrap text-sm opacity-90">{it.content}</p>}
          <div className="mt-2 text-xs text-zinc-500">Dibuat: {new Date(it.created_at).toLocaleString()} • Diperbarui: {new Date(it.updated_at).toLocaleString()}</div>
        </div>
      )}
    </div>
  )
}

