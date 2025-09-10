'use client'
import {useState} from 'react'
import AnalyzeForm from './(components)/AnalyzeForm'
import PlanCard from './(components)/PlanCard'
import {api} from './api'

export default function Page(){
  const [plan,setPlan]=useState<any|null>(null)
  async function update(){ if(!plan) return; const {data}=await api.post('/api/analyze',{symbol:plan.symbol}); setPlan(data) }
  return (
    <main className="max-w-3xl mx-auto p-6 space-y-4">
      <h1 className="text-2xl font-bold">Webpage Analisa Otomatis (Local)</h1>
      <AnalyzeForm onDone={setPlan} />
      {plan && <PlanCard plan={plan} onUpdate={update} />}
      <div className="text-xs opacity-60">Aturan: Edukasi, bukan saran finansial. Rate-limit aktif. Hasil per user terpisah.</div>
    </main>
  )
}

