import axios from 'axios'

// VITE_API_URL is set to http://localhost:8000 at build time (see Dockerfile).
// Using an absolute URL means the app works from both http://localhost (nginx)
// and http://localhost:3000 (direct) without needing nginx for API routing.
// CORS for both origins is enabled in backend ALLOWED_ORIGINS.
const BASE_URL = (import.meta.env.VITE_API_URL as string | undefined) ?? ''

export const api = axios.create({
  baseURL: `${BASE_URL}/api/v1`,
})

// Attach JWT on every request
api.interceptors.request.use((config) => {
  const token = localStorage.getItem('access_token')
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})

// On 401, clear auth and redirect to login
api.interceptors.response.use(
  (res) => res,
  (err) => {
    if (err.response?.status === 401) {
      localStorage.removeItem('access_token')
      window.location.href = '/login'
    }
    return Promise.reject(err)
  }
)

// ── Auth ──────────────────────────────────────────────────────
export const authApi = {
  login: (email: string, password: string) => {
    const form = new URLSearchParams()
    form.append('username', email)
    form.append('password', password)
    return api.post<{ access_token: string }>('/auth/login', form, {
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    })
  },
  register: (email: string, password: string, full_name?: string) =>
    api.post('/auth/register', { email, password, full_name }),
  me: () => api.get('/auth/me'),
}

// ── Documents ─────────────────────────────────────────────────
export const docsApi = {
  upload: (file: File) => {
    const form = new FormData()
    form.append('file', file)
    // Do NOT set Content-Type — Axios must auto-set multipart/form-data with boundary
    return api.post('/documents/upload', form)
  },
  list: (skip = 0, limit = 20) =>
    api.get(`/documents/?skip=${skip}&limit=${limit}`),
  get: (id: string) => api.get(`/documents/${id}`),
  delete: (id: string) => api.delete(`/documents/${id}`),
}

// ── Q&A ───────────────────────────────────────────────────────
export type QuestionRequest = {
  question: string
  document_ids?: string[]
  top_k?: number
  use_reranker?: boolean
  stream?: boolean
}

export const qaApi = {
  ask: (req: QuestionRequest) => api.post('/qa/ask', req),
  askMcp: (req: QuestionRequest) => api.post('/qa/ask/mcp', req),
}
