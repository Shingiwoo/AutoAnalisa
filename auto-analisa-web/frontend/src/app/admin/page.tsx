'use client'
import { useEffect, useState } from 'react'
import { api } from '../api'

export default function AdminPage(){
  const [s,setS]=useState<any|null>(null)
  const [usage,setUsage]=useState<any|null>(null)
  const [denied,setDenied]=useState(false)
  const [pwreqs,setPwreqs]=useState<any[]|null>(null)
  const [saved,setSaved]=useState<string>('')
  const [macroMsg,setMacroMsg]=useState<string>('')
  const [saveErr,setSaveErr]=useState<string>('')
  const [macroErr,setMacroErr]=useState<string>('')
  const [busySave,setBusySave]=useState(false)
  const [busyMacro,setBusyMacro]=useState(false)
  const [macroStatus,setMacroStatus]=useState<any|null>(null)
  // Simple tabs for grouping
  const [tab,setTab]=useState<'Settings'|'Indicator'|'Macro'|'Paritas'|'Docs'>('Settings')
  const [indTab,setIndTab]=useState<'FVG'|'SupplyDemand'>('FVG')
  // Parity test UI
  const [sym,setSym]=useState('BTCUSDT')
  const [tf,setTf]=useState<'15m'|'1h'>('15m')
  const [expected,setExpected]=useState<string>('')
  const [parity,setParity]=useState<any|null>(null)
  const [parityErr,setParityErr]=useState<string>('')

  async function load(){
    try{
      const [a,b] = await Promise.all([
        api.get('admin/settings'),
        api.get('admin/usage')
      ])
      setS(a.data); setUsage(b.data)
      try{ const r = await api.get('admin/password_requests'); setPwreqs(r.data) }catch{}
      try{ const ms = await api.get('admin/macro/status'); setMacroStatus(ms.data) }catch{}
    }catch(e:any){
      setDenied(true)
    }
  }
  useEffect(()=>{ load() },[])

  async function save(next?: any){
    try{
      setBusySave(true); setSaveErr(''); setSaved('')
      const payload = next ?? s
      await api.post('admin/settings', payload)
      setSaved('Pengaturan disimpan')
      await load()
    }catch(e:any){
      setSaveErr(e?.response?.data?.detail || 'Gagal menyimpan pengaturan')
    }finally{ setBusySave(false) }
  }
  if(denied) return <div className="max-w-7xl mx-auto p-6">Admin only</div>
  if(!s) return <div className="max-w-7xl mx-auto p-6">Loading…</div>
  return (
    <div className="max-w-7xl mx-auto p-6 space-y-6 text-zinc-900 dark:text-zinc-100">
      <h1 className="text-2xl font-bold text-zinc-900 dark:text-slate-100">Admin Dashboard</h1>
      {/* Tabs header */}
      <div className="flex items-center gap-2 text-sm">
        {(['Settings','Indicator','Macro','Paritas','Docs'] as const).map(t=> (
          <button key={t} onClick={()=> setTab(t)} className={`px-3 py-1.5 rounded ${tab===t? 'bg-cyan-600 text-white':'bg-zinc-800 text-white/80 hover:bg-zinc-700'}`}>{t}</button>
        ))}
      </div>

      {tab==='Settings' && (
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="rounded-2xl ring-1 ring-zinc-200 dark:ring-white/10 bg-white dark:bg-zinc-900 p-4 space-y-4">
          <div className="font-semibold">Pengaturan</div>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3 text-sm">
            <label className="flex items-center gap-2"><input type="checkbox" className="accent-cyan-600" checked={s.use_llm} onChange={async e=>{ const next={...s,use_llm:e.target.checked}; setS(next); await save(next) }}/> LLM aktif</label>
            <label className="flex items-center gap-2"><input type="checkbox" className="accent-cyan-600" checked={s.registration_enabled} onChange={async e=>{ const next={...s,registration_enabled:e.target.checked}; setS(next); await save(next) }}/> Izinkan pendaftaran baru</label>
            <label className="flex items-center gap-2"><input type="checkbox" className="accent-cyan-600" checked={s.auto_off_at_budget} onChange={async e=>{ const next={...s,auto_off_at_budget:e.target.checked}; setS(next); await save(next) }}/> Auto-off saat cap</label>
            <label>Maksimum user <input type="number" className="rounded px-2 py-1 w-full bg-white text-zinc-900 ring-1 ring-inset ring-zinc-200 focus:outline-none focus:ring-2 focus:ring-cyan-500 dark:bg-transparent dark:text-white dark:ring-white/10" value={s.max_users ?? 4} onChange={e=>setS({...s,max_users:+e.target.value})}/></label>
            <label className="flex items-center gap-2"><input type="checkbox" className="accent-cyan-600" checked={!!s.show_sessions_hint} onChange={async e=>{ const next={...s,show_sessions_hint:e.target.checked}; setS(next); await save(next) }}/> Tampilkan Sessions Hint (WIB)</label>
            <label>Default Weight Profile
              <select className="rounded px-2 py-1 w-full bg-white text-zinc-900 ring-1 ring-inset ring-zinc-200 focus:outline-none focus:ring-2 focus:ring-cyan-500 dark:bg-white dark:text-zinc-900 dark:ring-white/10" value={s.default_weight_profile||'DCA'} onChange={async e=>{ const next={...s,default_weight_profile:e.target.value}; setS(next); await save(next) }}>
                <option value="DCA">DCA (0.4/0.6)</option>
                <option value="Balanced">Balanced (0.5/0.5)</option>
                <option value="Near-Price">Near-Price (0.6/0.4)</option>
              </select>
            </label>
            <label>Budget USD/bln <input type="number" className="rounded px-2 py-1 w-full bg-white text-zinc-900 ring-1 ring-inset ring-zinc-200 focus:outline-none focus:ring-2 focus:ring-cyan-500 dark:bg-transparent dark:text-white dark:ring-white/10" value={s.budget_monthly_usd} onChange={e=>setS({...s,budget_monthly_usd:+e.target.value})}/></label>
            <label>Harga Input /1k <input type="number" className="rounded px-2 py-1 w-full bg-white text-zinc-900 ring-1 ring-inset ring-zinc-200 focus:outline-none focus:ring-2 focus:ring-cyan-500 dark:bg-transparent dark:text-white dark:ring-white/10" value={s.input_usd_per_1k} onChange={e=>setS({...s,input_usd_per_1k:+e.target.value})}/></label>
            <label>Harga Output /1k <input type="number" className="rounded px-2 py-1 w-full bg-white text-zinc-900 ring-1 ring-inset ring-zinc-200 focus:outline-none focus:ring-2 focus:ring-cyan-500 dark:bg-transparent dark:text-white dark:ring-white/10" value={s.output_usd_per_1k} onChange={e=>setS({...s,output_usd_per_1k:+e.target.value})}/></label>
          </div>
          <div className="flex items-center gap-3">
            <button disabled={busySave} onClick={()=>save()} className="px-3 py-2 rounded bg-cyan-600 text-white font-medium hover:bg-cyan-500 disabled:opacity-50">{busySave?'Menyimpan…':'Simpan'}</button>
            {saved && <div className="text-sm text-green-600">✔ {saved}</div>}
            {saveErr && <div className="text-sm text-rose-500">{saveErr}</div>}
          </div>
        </div>

        <div className="rounded-2xl ring-1 ring-zinc-200 dark:ring-white/10 bg-white dark:bg-zinc-900 p-4 space-y-2">
          <div className="font-semibold">Penggunaan</div>
          <div className="flex justify-between text-sm">
            <div>Bulan: {usage?.month_key}</div>
            <div>Total panggilan: {usage?.count}</div>
          </div>
          <div className="text-sm">Biaya bulan ini: <b>${usage?.total_usd?.toFixed?.(4) ?? usage?.total_usd}</b></div>
          <div className="text-sm">Limit: <b>${s?.budget_monthly_usd}</b></div>
          <Progress current={s?.budget_used_usd || 0} max={s?.budget_monthly_usd || 1} />
          <p className="text-xs text-gray-500">* Estimasi biaya dari token usage dan harga /1k token.</p>
        </div>

        <div className="rounded-2xl ring-1 ring-zinc-200 dark:ring-white/10 bg-white dark:bg-zinc-900 p-4 space-y-3">
          <div className="font-semibold">Permintaan Ganti Password</div>
          {!pwreqs?.length && <div className="text-sm text-gray-500">Tidak ada permintaan.</div>}
          {pwreqs?.map(r=> (
            <div key={r.id} className="flex items-center justify-between text-sm">
              <div>ID: {r.id} • User: {r.user_id} • {new Date(r.requested_at).toLocaleString('id-ID')}</div>
              <div className="flex gap-2">
                <button className="px-2.5 py-1.5 rounded bg-green-600 text-white hover:bg-green-700" onClick={async()=>{ await api.post(`admin/password_requests/${r.id}/approve`); load() }}>✔ Approve</button>
                <button className="px-2.5 py-1.5 rounded bg-red-600 text-white hover:bg-red-700" onClick={async()=>{ if(confirm('Tolak permintaan ini?')){ await api.post(`admin/password_requests/${r.id}/reject`); load() } }}>✖ Reject</button>
              </div>
            </div>
          ))}
        </div>

      </div>
      )}
      {/* Indicator tab content */}
      {tab==='Indicator' && (
        <div className="rounded-2xl ring-1 ring-zinc-200 dark:ring-white/10 bg-white dark:bg-zinc-900 p-4 space-y-4">
          <div className="flex items-center gap-2">
            {(['FVG','SupplyDemand'] as const).map(t=> (
              <button key={t} onClick={()=> setIndTab(t)} className={`px-3 py-1.5 rounded ${indTab===t? 'bg-cyan-600 text-white':'bg-zinc-800 text-white/80 hover:bg-zinc-700'}`}>{t==='FVG'?'FVG':'Supply/Demand'}</button>
            ))}
          </div>
          {indTab==='FVG' && (
            <div className="grid grid-cols-1 md:grid-cols-3 gap-3 text-sm">
              <label className="flex items-center gap-2"><input type="checkbox" className="accent-cyan-600" checked={!!s.enable_fvg} onChange={async e=>{ const next={...s,enable_fvg:e.target.checked}; setS(next); await save(next) }}/> Enable FVG</label>
              <label className="flex items-center gap-2"><input type="checkbox" className="accent-cyan-600" checked={!!s.fvg_use_bodies} onChange={async e=>{ const next={...s,fvg_use_bodies:e.target.checked}; setS(next); await save(next) }}/> Gunakan body candle</label>
              <label>Timeframe
                <select className="rounded px-2 py-1 w-full bg-white text-zinc-900 ring-1 ring-inset ring-zinc-200 focus:outline-none focus:ring-2 focus:ring-cyan-500 dark:bg-white dark:text-zinc-900 dark:ring-white/10" value={s.fvg_tf||'15m'} onChange={async e=>{ const next={...s,fvg_tf:e.target.value}; setS(next); await save(next) }}>
                  <option value="15m">15m</option>
                  <option value="1h">1h</option>
                </select>
              </label>
              <label>Fill Rule
                <select className="rounded px-2 py-1 w-full bg-white text-zinc-900 ring-1 ring-inset ring-zinc-200 focus:outline-none focus:ring-2 focus:ring-cyan-500 dark:bg-white dark:text-zinc-900 dark:ring-white/10" value={s.fvg_fill_rule||'any_touch'} onChange={async e=>{ const next={...s,fvg_fill_rule:e.target.value}; setS(next); await save(next) }}>
                  <option value="any_touch">any_touch</option>
                  <option value="50pct">50pct</option>
                  <option value="full">full</option>
                </select>
              </label>
              <label>Threshold (%) <input type="number" step="0.01" className="rounded px-2 py-1 w-full bg-white text-zinc-900 ring-1 ring-inset ring-zinc-200 focus:outline-none focus:ring-2 focus:ring-cyan-500 dark:bg-transparent dark:text-white dark:ring-white/10" value={s.fvg_threshold_pct ?? 0} onChange={async e=>{ const next={...s,fvg_threshold_pct:+e.target.value}; setS(next); await save(next) }}/></label>
              <label className="flex items-center gap-2"><input type="checkbox" className="accent-cyan-600" checked={!!s.fvg_threshold_auto} onChange={async e=>{ const next={...s,fvg_threshold_auto:e.target.checked}; setS(next); await save(next) }}/> Auto-Threshold</label>
            </div>
          )}
          {indTab==='SupplyDemand' && (
            <div className="grid grid-cols-1 md:grid-cols-3 gap-3 text-sm">
              <label className="flex items-center gap-2"><input type="checkbox" className="accent-cyan-600" checked={!!s.enable_supply_demand} onChange={async e=>{ const next={...s,enable_supply_demand:e.target.checked}; setS(next); await save(next) }}/> Enable Supply/Demand</label>
              <label>Mode
                <select className="rounded px-2 py-1 w-full bg-white text-zinc-900 ring-1 ring-inset ring-zinc-200 focus:outline-none focus:ring-2 focus:ring-cyan-500 dark:bg-white dark:text-zinc-900 dark:ring-white/10" value={s.sd_mode||'swing'} onChange={async e=>{ const next={...s,sd_mode:e.target.value}; setS(next); await save(next) }}>
                  <option value="swing">swing</option>
                  <option value="volume">volume</option>
                </select>
              </label>
              <label>Max Base <input type="number" className="rounded px-2 py-1 w-full bg-white text-zinc-900 ring-1 ring-inset ring-zinc-200 focus:outline-none focus:ring-2 focus:ring-cyan-500 dark:bg-transparent dark:text-white dark:ring-white/10" value={s.sd_max_base ?? 3} onChange={async e=>{ const next={...s,sd_max_base:+e.target.value}; setS(next); await save(next) }}/></label>
              <label>Body Ratio <input type="number" step="0.01" className="rounded px-2 py-1 w-full bg-white text-zinc-900 ring-1 ring-inset ring-zinc-200 focus:outline-none focus:ring-2 focus:ring-cyan-500 dark:bg-transparent dark:text-white dark:ring-white/10" value={s.sd_body_ratio ?? 0.33} onChange={async e=>{ const next={...s,sd_body_ratio:+e.target.value}; setS(next); await save(next) }}/></label>
              <label>Min Departure <input type="number" step="0.01" className="rounded px-2 py-1 w-full bg-white text-zinc-900 ring-1 ring-inset ring-zinc-200 focus:outline-none focus:ring-2 focus:ring-cyan-500 dark:bg-transparent dark:text-white dark:ring-white/10" value={s.sd_min_departure ?? 1.5} onChange={async e=>{ const next={...s,sd_min_departure:+e.target.value}; setS(next); await save(next) }}/></label>
              <label>Vol Div <input type="number" className="rounded px-2 py-1 w-full bg-white text-zinc-900 ring-1 ring-inset ring-zinc-200 focus:outline-none focus:ring-2 focus:ring-cyan-500 dark:bg-transparent dark:text-white dark:ring-white/10" value={s.sd_vol_div ?? 20} onChange={async e=>{ const next={...s,sd_vol_div:+e.target.value}; setS(next); await save(next) }}/></label>
              <label>Vol Threshold (%) <input type="number" step="0.01" className="rounded px-2 py-1 w-full bg-white text-zinc-900 ring-1 ring-inset ring-zinc-200 focus:outline-none focus:ring-2 focus:ring-cyan-500 dark:bg-transparent dark:text-white dark:ring-white/10" value={s.sd_vol_threshold_pct ?? 10} onChange={async e=>{ const next={...s,sd_vol_threshold_pct:+e.target.value}; setS(next); await save(next) }}/></label>
            </div>
          )}
        </div>
      )}

      {/* Docs tab */}
      {tab==='Docs' && (
        <div className="rounded-2xl ring-1 ring-zinc-200 dark:ring-white/10 bg-white dark:bg-zinc-900 p-4 text-sm space-y-4">
          <div>
            <div className="text-lg font-semibold">Panduan Admin</div>
            <ol className="list-decimal pl-5 space-y-1 mt-2">
              <li>Settings: atur LLM on/off, pendaftaran user, limit budget, dan profil bobot default (DCA/Balanced/Near-Price).</li>
              <li>Indicator: kelola FVG (TF, fill rule, threshold, auto-threshold) dan Supply/Demand (mode, base, ratio, departure, volume).</li>
              <li>Macro: generate Makro Harian slot pagi/malam. Gunakan Systemd timer untuk otomatis 07:00 dan 19:00 WIB.</li>
              <li>Paritas: uji presisi FVG/Zone terhadap referensi JSON untuk QA indikator.</li>
              <li>Password: tinjau dan setujui/tolak permintaan ganti password.</li>
              <li>Anggaran: pantau biaya bulanan dan harga token input/output per 1k token.</li>
            </ol>
          </div>
          <div>
            <div className="text-lg font-semibold">Panduan Pengguna</div>
            <ol className="list-decimal pl-5 space-y-1 mt-2">
              <li>Tambah simbol di Watchlist lalu klik Analisa untuk membuat kartu analisa (maks 4 aktif).</li>
              <li>PlanCard menampilkan rencana SPOT II (Rules). Klik Update untuk penyegaran. Jika harga tembus invalid, sistem membuat versi baru dan memberi tanda “Updated”.</li>
              <li>LLM Verifikasi opsional: klik Tanya GPT untuk verifikasi SPOT II; gunakan Pratinjau (ghost) untuk melihat overlay saran; Terapkan Saran untuk menyimpan.</li>
              <li>Chart: garis Entry, TP, Invalid, S/R akan tampil. Ghost overlay ditampilkan dengan garis putus-putus.</li>
              <li>Macro Harian dan Sessions Hint: ringkasan makro dan jam WIB signifikan tampil otomatis bila tersedia.</li>
              <li>Aturan: Edukasi, bukan saran finansial. Terdapat rate-limit dan batas harian LLM per pengguna.</li>
            </ol>
          </div>
        </div>
      )}
      {/* Macro tab */}
      {tab==='Macro' && (
      <div className="rounded-2xl ring-1 ring-zinc-200 dark:ring-white/10 bg-white dark:bg-zinc-900 p-4 space-y-2">
          <div className="font-semibold">Makro Harian</div>
          {macroStatus?.has_data && (
            <div className="text-xs text-zinc-400">
              Terakhir: {new Date(macroStatus.created_at).toLocaleString('id-ID', { timeZone: 'Asia/Jakarta' })} WIB
              {macroStatus?.slot && <> • Slot: <b>{macroStatus.slot}</b></>}
              {macroStatus?.last_run_status && <> • Status: <b>{macroStatus.last_run_status}</b></>}
            </div>
          )}
        {macroMsg && <div className="p-2 rounded text-sm text-cyan-300 ring-1 ring-cyan-500/20 bg-cyan-500/10">{macroMsg}</div>}
        {macroErr && <div className="p-2 rounded text-sm text-rose-400 ring-1 ring-rose-500/20 bg-rose-500/10">{macroErr}</div>}
        <button disabled={busyMacro} className="px-3 py-2 rounded bg-cyan-600 text-white font-medium hover:bg-cyan-500 disabled:opacity-50" onClick={async()=>{
          try{ setMacroErr(''); setMacroMsg(''); setBusyMacro(true); await api.post('admin/macro/generate'); setMacroMsg('Makro harian diperbarui.'); }
          catch(e:any){ setMacroErr(e?.response?.data?.detail || 'Gagal generate makro (500). Cek backend log).') }
          finally{ setBusyMacro(false) }
        }}>{busyMacro?'Memproses…':'Generate Hari Ini'}</button>
      </div>
      )}

      {/* Parity Test */}
      {tab==='Paritas' && (
      <div className="rounded-2xl ring-1 ring-zinc-200 dark:ring-white/10 bg-white dark:bg-zinc-900 p-4 space-y-2">
        <div className="font-semibold">Uji Paritas Indikator (FVG / Supply-Demand)</div>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-3 text-sm">
          <label>Symbol <input value={sym} onChange={e=>setSym(e.target.value)} className="rounded px-2 py-1 w-full bg-white text-zinc-900 ring-1 ring-inset ring-zinc-200 focus:outline-none focus:ring-2 focus:ring-cyan-500 dark:bg-transparent dark:text-white dark:ring-white/10"/></label>
          <label>Timeframe
            <select value={tf} onChange={e=>setTf(e.target.value as any)} className="rounded px-2 py-1 w-full bg-white text-zinc-900 ring-1 ring-inset ring-zinc-200 focus:outline-none focus:ring-2 focus:ring-cyan-500 dark:bg-transparent dark:text-white dark:ring-white/10">
              <option value="15m">15m</option>
              <option value="1h">1h</option>
            </select>
          </label>
          <div className="text-xs text-zinc-400 self-center">Tempel JSON referensi di bawah (keys: fvg, zones)</div>
        </div>
        <textarea value={expected} onChange={e=>setExpected(e.target.value)} rows={6} className="w-full rounded px-2 py-1 bg-white text-zinc-900 ring-1 ring-inset ring-zinc-200 focus:outline-none focus:ring-2 focus:ring-cyan-500 dark:bg-transparent dark:text-white dark:ring-white/10" placeholder='{"fvg": [...], "zones": [...] }' />
        <div className="flex items-center gap-3">
          <button className="px-3 py-2 rounded bg-cyan-600 text-white font-medium hover:bg-cyan-500" onClick={async()=>{
            try{
              setParityErr(''); setParity(null)
              const limit = tf==='15m' ? 500 : 600
              const { data:ohlcv } = await api.get('ohlcv', { params:{ symbol: sym, tf, limit } })
              let exp:any={}
              try{ exp = JSON.parse(expected) }catch{ throw new Error('JSON referensi tidak valid') }
              const { data } = await api.post('admin/parity/compute', { ohlcv, expected: exp })
              setParity(data)
            }catch(e:any){ setParityErr(e?.response?.data?.detail||e?.message||'Gagal menghitung paritas') }
          }}>Hitung Paritas</button>
          {parityErr && <div className="text-sm text-rose-500">{parityErr}</div>}
        </div>
          {parity && (
            <div className="space-y-2">
              <div className="text-xs grid grid-cols-1 md:grid-cols-2 gap-2">
                <div className="rounded p-2 ring-1 ring-zinc-200 dark:ring-white/10">
                  <div className="font-medium">FVG</div>
                  <div>Match: {(parity?.fvg?.match_pct*100)?.toFixed?.(1)}%</div>
                  <div>F1: {parity?.fvg?.f1?.toFixed?.(3)} (P: {parity?.fvg?.precision?.toFixed?.(3)}, R: {parity?.fvg?.recall?.toFixed?.(3)})</div>
                  <div>Avg offset: {parity?.fvg?.avg_offset?.toFixed?.(6)}</div>
                  <div>TP: {parity?.fvg?.tp} • FP: {parity?.fvg?.fp} • FN: {parity?.fvg?.fn}</div>
                </div>
                <div className="rounded p-2 ring-1 ring-zinc-200 dark:ring-white/10">
                  <div className="font-medium">Supply/Demand</div>
                  <div>Match: {(parity?.zones?.match_pct*100)?.toFixed?.(1)}%</div>
                  <div>F1: {parity?.zones?.f1?.toFixed?.(3)} (P: {parity?.zones?.precision?.toFixed?.(3)}, R: {parity?.zones?.recall?.toFixed?.(3)})</div>
                  <div>Avg IoU: {parity?.zones?.avg_iou?.toFixed?.(3)} • Avg offset: {parity?.zones?.avg_offset?.toFixed?.(6)}</div>
                  <div>TP: {parity?.zones?.tp} • FP: {parity?.zones?.fp} • FN: {parity?.zones?.fn}</div>
                </div>
              </div>
              <div className="flex items-center gap-2">
                <button className="px-3 py-1.5 rounded bg-zinc-800 text-white text-sm hover:bg-zinc-700" onClick={()=>{
                  navigator.clipboard?.writeText(JSON.stringify(parity, null, 2))
                }}>Salin JSON</button>
                <button className="px-3 py-1.5 rounded bg-zinc-800 text-white text-sm hover:bg-zinc-700" onClick={()=>{
                  const blob = new Blob([JSON.stringify(parity,null,2)], { type: 'application/json' })
                  const url = URL.createObjectURL(blob)
                  const a = document.createElement('a')
                  a.href = url
                  a.download = `parity_${sym}_${tf}.json`
                  a.click()
                  URL.revokeObjectURL(url)
                }}>Unduh JSON</button>
              </div>
            </div>
          )}
      </div>
      )}
    </div>
  )
}

function Progress({ current, max }:{ current:number, max:number }){
  const pct = Math.min(100, Math.round((current / (max || 1)) * 100))
  return (
    <div className="w-full bg-zinc-200 rounded h-2 overflow-hidden">
      <div className="h-2 bg-green-600" style={{ width: `${pct}%` }} />
    </div>
  )
}
