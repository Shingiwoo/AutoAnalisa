"use client"
import { useEffect, useMemo, useState } from "react"
import Link from "next/link"
import { api } from "../api"
import FuturesWatchlist from "../(components)/FuturesWatchlist"
import FuturesCard from "../(components)/FuturesCard"

type Quota = {
  limit: number
  remaining: number
  calls?: number
  llm_enabled?: boolean
  futures_limit?: number
  futures_remaining?: number
}

const LOCAL_SELECTED_KEY = "futures:selected-symbol"

export default function FuturesPage() {
  const [selectedSymbol, setSelectedSymbol] = useState<string | null>(() => {
    if (typeof window === "undefined") return null
    return localStorage.getItem(LOCAL_SELECTED_KEY)
  })
  const [loggedIn, setLoggedIn] = useState(false)
  const [quota, setQuota] = useState<Quota | null>(null)

  useEffect(() => {
    if (typeof window === "undefined") return
    const token = localStorage.getItem("token") || localStorage.getItem("access_token")
    const isLogged = !!token
    setLoggedIn(isLogged)
    if (isLogged) {
      loadQuota()
    } else {
      setQuota(null)
    }
  }, [])

  useEffect(() => {
    if (typeof window === "undefined") return
    if (selectedSymbol) localStorage.setItem(LOCAL_SELECTED_KEY, selectedSymbol)
    else localStorage.removeItem(LOCAL_SELECTED_KEY)
  }, [selectedSymbol])

  async function loadQuota() {
    try {
      const r = await api.get("llm/quota")
      setQuota(r.data)
    } catch {
      setQuota(null)
    }
  }

  const futRemaining = useMemo(() => quota?.futures_remaining ?? quota?.remaining ?? 0, [quota])
  const futLimit = useMemo(() => quota?.futures_limit ?? quota?.limit ?? 0, [quota])

  return (
    <main className="space-y-4">
      <div className="max-w-7xl mx-auto px-4 md:px-6 pt-6">
        <div className="flex items-center justify-between">
          <h1 className="text-xl font-semibold">Analisa Futures</h1>
          <Link href="/" className="text-sm underline">
            ← Kembali ke Spot
          </Link>
        </div>
        <p className="mt-1 text-sm text-zinc-600">
          Klik simbol atau gunakan Tanya GPT untuk memunculkan analisa lengkap dengan overlay.
        </p>
      </div>
      <div id="analisa" className="max-w-7xl mx-auto px-4 md:px-6 space-y-4">
        {loggedIn ? (
          <>
            <FuturesWatchlist
              quota={{ limit: futLimit, remaining: futRemaining, llm_enabled: !!quota?.llm_enabled }}
              selectedSymbol={selectedSymbol}
              onSelect={(s) => setSelectedSymbol(s || null)}
              onReady={(items) => {
                if (!selectedSymbol && items && items.length > 0) {
                  setSelectedSymbol(items[0])
                }
              }}
            />
            {quota && (
              <div className="mt-1 text-xs opacity-60">
                Kuota LLM Futures: {futRemaining}/{futLimit}
              </div>
            )}
            {selectedSymbol ? (
              <FuturesCard
                key={selectedSymbol}
                symbol={selectedSymbol}
                llmEnabled={!!quota?.llm_enabled}
                llmRemaining={typeof futRemaining === "number" ? futRemaining : undefined}
                onRefreshQuota={loadQuota}
              />
            ) : (
              <div className="rounded-2xl ring-1 ring-zinc-200 dark:ring-white/10 bg-white dark:bg-zinc-900 p-6 text-sm text-zinc-500">
                Pilih simbol dari watchlist untuk memuat analisa Futures.
              </div>
            )}
          </>
        ) : (
          <div className="rounded-2xl ring-1 ring-zinc-200 dark:ring-white/10 bg-white dark:bg-zinc-900 p-4 text-sm text-gray-600">
            Login untuk mengelola watchlist dan menganalisa.
          </div>
        )}
        <div className="mt-6 text-xs opacity-60">
          Aturan: Edukasi, bukan saran finansial. Rate-limit aktif. Hasil per user terpisah.
        </div>
      </div>
    </main>
  )
}
