'use client'
import { useEffect, useMemo, useState } from 'react'
import { api } from '../api'
import { useSymbols, normalizeSymbolInput } from '../../lib/hooks/useSymbols'

type Props = {
  onPick: (symbol: string) => void
  onDelete?: (symbol: string) => void
  tradeType?: 'spot' | 'futures'
}

export default function Watchlist({ onPick, onDelete, tradeType = 'spot' }: Props) {
  const [items, setItems] = useState<string[]>([])
  const [selected, setSelected] = useState('')
  const [msg, setMsg] = useState<string>('')
  const { symbols, loading, error } = useSymbols(tradeType)

  const options = useMemo(() => {
    const map = new Map<string, string>()
    symbols.forEach((raw) => {
      const value = normalizeSymbolInput(raw)
      if (!value) return
      if (!map.has(value)) map.set(value, raw.toUpperCase())
    })
    return Array.from(map.entries()).map(([value, label]) => ({ value, label }))
  }, [symbols])

  useEffect(() => {
    if (options.length === 0) {
      setSelected('')
      return
    }
    setSelected((prev) => {
      if (prev && options.some((opt) => opt.value === prev)) {
        return prev
      }
      return options[0]?.value ?? ''
    })
  }, [options])

  async function load() {
    try {
      const r = await api.get('watchlist', { params: { trade_type: tradeType } })
      const list: string[] = r.data || []
      setItems(list)
    } catch (e: any) {
      setMsg(e?.response?.data?.detail || 'Gagal memuat watchlist')
    }
  }

  useEffect(() => {
    load()
  }, [tradeType])

  async function add() {
    if (!selected) {
      setMsg('Pilih simbol terlebih dahulu.')
      return
    }
    if (items.length >= 4) {
      setMsg('Maksimal 4 koin dalam watchlist.')
      return
    }
    const normalized = normalizeSymbolInput(selected)
    if (!normalized) {
      setMsg('Simbol tidak valid.')
      return
    }
    if (tradeType === 'spot' && normalized.includes('.P')) {
      setMsg('Simbol perpetual (.P) tidak valid untuk Spot.')
      return
    }
    try {
      await api.post('watchlist/add', null, { params: { symbol: normalized, trade_type: tradeType } })
      setMsg('')
      await load()
    } catch (e: any) {
      setMsg(e?.response?.data?.detail || 'Gagal menambah simbol')
    }
  }

  async function del(symbol: string) {
    try {
      await api.delete(`watchlist/${encodeURIComponent(symbol)}`, { params: { trade_type: tradeType } })
      onDelete?.(symbol)
      await load()
    } catch (e: any) {
      setMsg(e?.response?.data?.detail || 'Gagal menghapus simbol')
    }
  }

  return (
    <div className="space-y-2">
      <div className="flex gap-2">
        <select
          value={selected}
          onChange={(e) => setSelected(e.target.value)}
          className="border rounded px-3 py-2 w-full focus:outline-none focus:ring-2 focus:ring-blue-500 bg-white text-zinc-900 dark:bg-zinc-900 dark:text-zinc-100"
          disabled={loading || options.length === 0}
        >
          {options.length === 0 ? (
            <option value="">{loading ? 'Memuat simbol…' : 'Tidak ada simbol'}</option>
          ) : (
            options.map((opt) => (
              <option key={opt.value} value={opt.value}>
                {opt.label}
              </option>
            ))
          )}
        </select>
        <button
          onClick={add}
          disabled={items.length >= 4 || !selected || loading}
          className="px-3 py-2 rounded bg-blue-600 text-white font-medium hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed"
        >
          Tambah
        </button>
      </div>
      {(loading || error) && (
        <div className="text-xs text-zinc-500">{loading ? 'Memuat simbol…' : error}</div>
      )}
      {msg && (
        <div className="p-2 bg-amber-50 border border-amber-200 text-amber-800 rounded text-xs flex items-start gap-2">
          <span aria-hidden>⚠</span>
          <span>{msg}</span>
        </div>
      )}
      <div className="flex flex-wrap gap-2">
        {items.map((s) => (
          <div key={s} className="inline-flex items-center px-3 py-1 rounded-full bg-gray-100 text-sm font-medium text-gray-800">
            <button onClick={() => onPick(s)} className="mr-2 hover:underline">
              {s}
            </button>
            <button onClick={() => confirm(`Hapus ${s}?`) && del(s)} className="text-red-600 hover:text-red-800" title="Remove">
              ×
            </button>
          </div>
        ))}
      </div>
    </div>
  )
}
