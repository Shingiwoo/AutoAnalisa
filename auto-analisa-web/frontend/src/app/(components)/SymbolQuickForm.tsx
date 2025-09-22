"use client"

import { useEffect, useMemo, useState } from "react"
import { useSymbols, normalizeSymbolInput } from "../../lib/hooks/useSymbols"

interface Props {
  onAnalyze: (symbol: string, tradeType: "spot" | "futures") => void
  disabled?: boolean
}

export default function SymbolQuickForm({ onAnalyze, disabled }: Props) {
  const [marketType, setMarketType] = useState<"spot" | "futures">("spot")
  const { symbols, loading, error } = useSymbols(marketType)
  const [selected, setSelected] = useState<string>("")
  const [warn, setWarn] = useState<string | null>(null)

  const options = useMemo(() => {
    const map = new Map<string, string>()
    symbols.forEach((raw) => {
      const value = normalizeSymbolInput(raw)
      if (!value) return
      if (!map.has(value)) {
        map.set(value, raw.toUpperCase())
      }
    })
    return Array.from(map.entries()).map(([value, label]) => ({ value, label }))
  }, [symbols])

  useEffect(() => {
    if (options.length === 0) {
      setSelected("")
      return
    }
    setSelected((prev) => {
      if (prev && options.some((opt) => opt.value === prev)) {
        return prev
      }
      return options[0]?.value ?? ""
    })
  }, [options])

  function submit() {
    if (!selected) return
    if (marketType === "spot" && selected.includes(".P")) {
      setWarn("Simbol perpetual (.P) tidak boleh untuk Spot")
      return
    }
    setWarn(null)
    onAnalyze(selected, marketType)
  }

  return (
    <div className="rounded-2xl ring-1 ring-zinc-200 dark:ring-white/10 bg-white dark:bg-zinc-900 p-4 flex flex-col md:flex-row md:items-end gap-3">
      <div className="flex flex-col min-w-[160px]">
        <label className="text-xs font-medium">Market Type</label>
        <select
          value={marketType}
          onChange={(e) => setMarketType(e.target.value === "futures" ? "futures" : "spot")}
          className="rounded px-3 py-2 bg-white text-zinc-900 ring-1 ring-zinc-200 focus:outline-none focus:ring-2 focus:ring-cyan-500 dark:bg-transparent dark:text-white dark:ring-white/10"
          disabled={disabled}
        >
          <option value="spot">Spot</option>
          <option value="futures">Futures</option>
        </select>
      </div>
      <div className="flex flex-col flex-1 min-w-[200px]">
        <label className="text-xs font-medium">Symbol</label>
        <select
          value={selected}
          onChange={(e) => setSelected(e.target.value)}
          className="rounded px-3 py-2 bg-white text-zinc-900 ring-1 ring-zinc-200 focus:outline-none focus:ring-2 focus:ring-cyan-500 dark:bg-transparent dark:text-white dark:ring-white/10"
          disabled={disabled || loading || options.length === 0}
        >
          {options.length === 0 ? (
            <option value="">{loading ? "Memuat simbol…" : "Tidak ada simbol"}</option>
          ) : (
            options.map((opt) => (
              <option key={opt.value} value={opt.value}>
                {opt.label}
              </option>
            ))
          )}
        </select>
        {(loading || error) && (
          <span className="text-xs text-zinc-500 mt-1">
            {loading ? "Memuat simbol…" : error}
          </span>
        )}
        {warn && <span className="text-xs text-rose-500 mt-1">{warn}</span>}
      </div>
      <button
        onClick={submit}
        disabled={disabled || !selected || loading}
        className="inline-flex items-center gap-2 px-4 py-2 rounded bg-indigo-600 text-white font-medium hover:bg-indigo-500 disabled:opacity-50"
      >
        Analisa
      </button>
    </div>
  )
}
