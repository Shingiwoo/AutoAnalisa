"use client"

import { useEffect, useState } from "react"
import { Plus, X } from "lucide-react"
import { api } from "../api"

type QuotaInfo = { limit: number; remaining: number; llm_enabled?: boolean }

type Props = {
  onSelect: (symbol: string) => void
  selectedSymbol?: string | null
  quota?: QuotaInfo | null
  onReady?: (items: string[]) => void
}

export default function FuturesWatchlist({ onSelect, selectedSymbol, quota, onReady }: Props) {
  const [items, setItems] = useState<string[]>([])
  const [input, setInput] = useState("")
  const [msg, setMsg] = useState<string>("")

  async function load() {
    try {
      const r = await api.get("watchlist", { params: { trade_type: "futures" } })
      const list: string[] = r.data || []
      setItems(list)
      onReady?.(list)
      setMsg("")
    } catch (e: any) {
      setMsg(e?.response?.data?.detail || "Gagal memuat watchlist")
    }
  }

  async function add() {
    if (!input) return
    if (items.length >= 4) {
      setMsg("Maksimal 4 simbol dalam watchlist.")
      return
    }
    try {
      const symbol = input.trim().toUpperCase()
      await api.post("watchlist/add", null, { params: { symbol, trade_type: "futures" } })
      setInput("")
      setMsg("")
      await load()
      onSelect(symbol)
    } catch (e: any) {
      setMsg(e?.response?.data?.detail || "Gagal menambah simbol")
    }
  }

  async function remove(symbol: string) {
    try {
      await api.delete(`watchlist/${encodeURIComponent(symbol)}`, { params: { trade_type: "futures" } })
      setItems((prev) => {
        const next = prev.filter((s) => s !== symbol)
        if (selectedSymbol && selectedSymbol.toUpperCase() === symbol.toUpperCase()) {
          const fallback = next[0] || ""
          onSelect(fallback)
        }
        onReady?.(next)
        return next
      })
    } catch (e: any) {
      setMsg(e?.response?.data?.detail || "Gagal menghapus simbol")
    }
  }

  useEffect(() => {
    load()
  }, [])

  return (
    <section className="rounded-2xl ring-1 ring-zinc-200 dark:ring-white/10 bg-white dark:bg-zinc-900 p-4 text-zinc-900 dark:text-zinc-100">
      <div className="flex flex-col md:flex-row md:items-start md:justify-between gap-4">
        <div className="flex-1 space-y-2">
          <h3 className="font-semibold text-base">Watchlist Futures</h3>
          <div className="flex items-center gap-2">
            <input
              value={input}
              onChange={(e) => setInput(e.target.value.toUpperCase())}
              placeholder="IMXUSDT"
              className="rounded px-3 py-2 w-full bg-white text-zinc-900 ring-1 ring-inset ring-zinc-200 focus:outline-none focus:ring-2 focus:ring-cyan-500 dark:bg-transparent dark:text-white placeholder:text-zinc-400 dark:ring-white/10"
            />
            <button
              onClick={add}
              className="inline-flex items-center gap-1 px-3 py-2 rounded bg-cyan-600 text-white hover:bg-cyan-500 disabled:opacity-50"
              disabled={items.length >= 4}
            >
              <Plus size={16} /> Tambah
            </button>
            {quota && (
              <span
                className={`px-2 py-1 rounded text-xs ${quota.remaining > 0 ? "bg-emerald-600" : "bg-rose-600"} text-white`}
                title={quota.llm_enabled ? "LLM aktif" : "LLM nonaktif"}
              >
                LLM {quota.remaining}/{quota.limit}
              </span>
            )}
          </div>
          {msg && <div className="text-xs text-rose-500">{msg}</div>}
        </div>
        <div className="flex-1">
          <h4 className="text-sm font-medium mb-1">Simbol</h4>
          <div className="flex flex-wrap gap-2">
            {items.map((s) => (
              <div
                key={s}
                className={`inline-flex items-center gap-2 px-3 py-1 rounded-full border ${
                  selectedSymbol && selectedSymbol.toUpperCase() === s
                    ? "bg-indigo-600 border-indigo-600 text-white"
                    : "bg-zinc-100 border-zinc-200 dark:bg-zinc-800 dark:border-zinc-700 text-zinc-800 dark:text-zinc-100"
                }`}
              >
                <button onClick={() => onSelect(s)} className="font-medium">
                  {s}
                </button>
                <button onClick={() => remove(s)} className="text-rose-600 hover:text-rose-700">
                  <X size={14} />
                </button>
              </div>
            ))}
            {items.length === 0 && <div className="text-xs text-zinc-500">Tambah simbol untuk mulai menganalisa.</div>}
          </div>
        </div>
      </div>
    </section>
  )
}
