"use client"
import { useEffect, useMemo, useRef, useState } from "react"
import { useSymbols, normalizeSymbolInput } from "../../lib/hooks/useSymbols"

type Props = {
  kind?: "spot" | "futures"
  placeholder?: string
  onPick: (symbol: string) => void
  buttonLabel?: string
}

export default function SymbolSearch({ kind = "spot", placeholder = "Cari simbol…", onPick, buttonLabel = "Analisa" }: Props) {
  const { symbols, loading } = useSymbols(kind)
  const [query, setQuery] = useState("")
  const inputRef = useRef<HTMLInputElement | null>(null)

  const listId = useMemo(() => `symbols-${kind}-list`, [kind])
  const matches = useMemo(() => {
    const q = normalizeSymbolInput(query)
    if (!q) return symbols.slice(0, 50)
    return symbols.filter(s => s.includes(q)).slice(0, 50)
  }, [symbols, query])

  function submit() {
    const sym = normalizeSymbolInput(query)
    if (!sym) return
    onPick(sym)
  }

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Enter") submit()
    }
    const el = inputRef.current
    el?.addEventListener("keydown", onKey)
    return () => el?.removeEventListener("keydown", onKey)
  }, [query])

  return (
    <div className="flex items-center gap-2">
      <input
        ref={inputRef}
        className="aa-input w-full md:w-72"
        list={listId}
        value={query}
        onChange={(e) => setQuery(e.target.value)}
        placeholder={loading ? "Memuat simbol…" : placeholder}
        autoComplete="off"
      />
      <datalist id={listId}>
        {matches.map((s) => (
          <option key={s} value={s} />
        ))}
      </datalist>
      <button onClick={submit} className="px-3 py-2 rounded-md bg-cyan-600 hover:bg-cyan-500 text-white disabled:opacity-50" disabled={!query}>
        {buttonLabel}
      </button>
    </div>
  )
}

