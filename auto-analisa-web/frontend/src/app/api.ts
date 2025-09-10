import axios from 'axios'

function resolveBaseURL(){
  const envBase = process.env.NEXT_PUBLIC_API_BASE
  if (envBase && envBase.trim().length>0) return envBase
  if (typeof window !== 'undefined') return '/api' // production: relative path
  return 'http://localhost:8940' // dev SSR fallback to backend port
}

export const api = axios.create({
  baseURL: resolveBaseURL(),
  withCredentials: false,
})

api.interceptors.request.use((config) => {
  if (typeof window !== 'undefined') {
    const t = localStorage.getItem('token')
    if (t) config.headers.Authorization = `Bearer ${t}`
  }
  return config
})
