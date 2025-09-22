import { useEffect, useState } from "react"
import { api } from "../../app/api"

type Kind = "spot" | "futures"

type CacheEntry = {
  ts: number
  symbols: string[]
}

const cache: Record<Kind, CacheEntry | undefined> = {
  spot: undefined,
  futures: undefined,
}

export function normalizeSymbolInput(symbol: string): string {
  if (!symbol) return ""
  const upper = symbol.toUpperCase().trim()
  const [base] = upper.split(":")
  return base.replace(/\//g, "")
}

export function useSymbols(kind: Kind) {
  const [symbols, setSymbols] = useState<string[]>([])
  const [loading, setLoading] = useState<boolean>(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false

    async function load() {
      setLoading(true)
      setError(null)
      try {
        const cached = cache[kind]
        const now = Date.now() / 1000
        if (cached && now - cached.ts < 1800) {
          if (!cancelled) setSymbols(cached.symbols)
          return
        }
        const { data } = await api.get(`/symbols/${kind}`)
        const list: string[] = data?.symbols || []
        cache[kind] = { ts: now, symbols: list }
        if (!cancelled) setSymbols(list)
      } catch (e: any) {
        if (!cancelled) {
          setError(e?.response?.data?.detail || "Gagal memuat simbol")
          setSymbols([])
        }
      } finally {
        if (!cancelled) setLoading(false)
      }
    }

    load()
    return () => {
      cancelled = true
    }
  }, [kind])

  return { symbols, loading, error }
}
