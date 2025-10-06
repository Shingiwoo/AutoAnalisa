import axios from "axios";

const baseRaw = process.env.NEXT_PUBLIC_API_BASE || "";
const base = baseRaw.replace(/\/+$/, ""); // trim trailing slashes

export const api = axios.create({
  baseURL: base,
  withCredentials: true,
});

// Normalize URL to include /api if base doesn't include it and path doesn't start with it
api.interceptors.request.use((cfg) => {
  const path = cfg.url || "";
  const baseHasApi = /\/api$/.test(base);
  const pathHasApi = /^\/api\//.test(path);
  if (!baseHasApi && !pathHasApi) {
    cfg.url = "/api" + (path.startsWith("/") ? path : "/" + path);
  }
  // If using Authorization header approach
  const t = typeof window !== "undefined" ? (localStorage.getItem("access_token") || localStorage.getItem("token")) : null;
  if (t) {
    const h: any = cfg.headers ?? {};
    if (typeof h.set === "function") h.set("Authorization", `Bearer ${t}`);
    else h.Authorization = `Bearer ${t}`;
    cfg.headers = h;
  }
  return cfg;
});

// Redirect to /login on 401
api.interceptors.response.use(
  (r) => r,
  (err) => {
    const status = err?.response?.status;
    if (status === 401 && typeof window !== "undefined") {
      try {
        // Avoid redirect loops: don't redirect from login/register calls
        const reqUrl: string = err?.config?.url || "";
        const isAuthEndpoint = /\/auth\/(login|register)/.test(reqUrl);
        const isAlreadyOnLogin = window.location.pathname.startsWith("/login");
        const isAlreadyOnRegister = window.location.pathname.startsWith("/register");
        const isPublicEndpoint = /\/api\/public\//.test(reqUrl);
        if (!isAuthEndpoint && !isPublicEndpoint && !isAlreadyOnLogin && !isAlreadyOnRegister) {
          // debounce redirect
          const w = window as any;
          if (!w.__authRedirecting) {
            w.__authRedirecting = true;
            window.location.href = "/login";
          }
        }
      } catch {}
    }
    return Promise.reject(err);
  }
);

export default api;
