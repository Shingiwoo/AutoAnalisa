import axios from 'axios'

const base = (process.env.NEXT_PUBLIC_API_BASE || '')
  .replace(/\/+$/, '') // trim trailing slashes

export const api = axios.create({
  baseURL: base,
  withCredentials: false,
})

api.interceptors.request.use((cfg) => {
  // Normalize /api prefix based on base and path
  const path = cfg.url || ''
  const baseHasApi = /\/api$/.test(base)
  const pathHasApi = /^\/api\//.test(path)
  if (!baseHasApi && !pathHasApi) {
    cfg.url = '/api' + (path.startsWith('/') ? path : '/' + path)
  }
  // Attach bearer from localStorage if available
  if (typeof window !== 'undefined') {
    const t = localStorage.getItem('access_token') || localStorage.getItem('token')
    if (t) {
      const h: any = cfg.headers ?? {}
      if (typeof h.set === 'function') h.set('Authorization', `Bearer ${t}`)
      else h.Authorization = `Bearer ${t}`
      cfg.headers = h
    }
  }
  return cfg
})
