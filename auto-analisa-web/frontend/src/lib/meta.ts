import { api } from './http'

type Meta = { symbol:string, market:'spot'|'futures', price_tick?:number|null, qty_step?:number|null, price_decimals?:number|null, quote_precision?:number|null }

const cache = new Map<string, Meta>()

export async function getSymbolMeta(symbol:string, market:'spot'|'futures'='spot'): Promise<Meta|null> {
  const key = `${symbol.toUpperCase()}:${market}`
  if (cache.has(key)) return cache.get(key) as Meta
  try{
    const { data } = await api.get('meta/symbol', { params:{ symbol, market } })
    cache.set(key, data)
    return data
  }catch{ return null }
}

