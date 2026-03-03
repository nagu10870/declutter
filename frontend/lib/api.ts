import axios from 'axios'

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api/v1'

export const api = axios.create({
  baseURL: API_BASE,
  headers: { 'Content-Type': 'application/json' },
})

api.interceptors.request.use((config) => {
  if (typeof window !== 'undefined') {
    const token = localStorage.getItem('access_token')
    if (token) config.headers.Authorization = `Bearer ${token}`
    // Admin secret (for admin panel)
    const adminSecret = localStorage.getItem('admin_secret')
    if (adminSecret) config.headers['X-Admin-Secret'] = adminSecret
  }
  return config
})

api.interceptors.response.use(
  (res) => res,
  async (error) => {
    const original = error.config
    if (error.response?.status === 401 && !original._retry) {
      original._retry = true
      try {
        const refresh = localStorage.getItem('refresh_token')
        const res = await axios.post(`${API_BASE}/auth/refresh`, { refresh_token: refresh })
        localStorage.setItem('access_token', res.data.access_token)
        localStorage.setItem('refresh_token', res.data.refresh_token)
        original.headers.Authorization = `Bearer ${res.data.access_token}`
        return api(original)
      } catch {
        localStorage.removeItem('access_token')
        localStorage.removeItem('refresh_token')
        if (typeof window !== 'undefined') window.location.href = '/auth/login'
      }
    }
    return Promise.reject(error)
  }
)

export const authApi = {
  register: (data: { email: string; password: string; full_name?: string }) =>
    api.post('/auth/register', data),
  login: (data: { email: string; password: string }) =>
    api.post('/auth/login', data),
  me: () => api.get('/auth/me'),
  logout: () => api.delete('/auth/logout'),
}

export const connectionsApi = {
  list: () => api.get('/connections'),
  addLocal: () => api.post('/connections/local'),
  delete: (id: string) => api.delete(`/connections/${id}`),
  usage: (id: string) => api.get(`/connections/${id}/usage`),
  sync: (id: string) => api.post(`/connections/${id}/sync`),
}

export const cloudApi = {
  googleAuthorize: () => api.get('/connections/google/authorize'),
  dropboxAuthorize: () => api.get('/connections/dropbox/authorize'),
}

export const scansApi = {
  start: (data: { connection_id: string; scan_type?: string; files_total?: number }) =>
    api.post('/scans', data),
  ingestChunk: (data: { job_id: string; files: FileManifestItem[]; is_final_chunk?: boolean }) =>
    api.post('/scans/ingest', data),
  get: (id: string) => api.get(`/scans/${id}`),
  list: () => api.get('/scans'),
}

export const dashboardApi = {
  summary: () => api.get('/dashboard/summary'),
}

export const duplicatesApi = {
  listGroups: (params?: { match_type?: string; page?: number }) =>
    api.get('/duplicates/files', { params }),
  deleteFile: (fileId: string) => api.delete(`/duplicates/files/${fileId}`),
  undoDelete: (fileId: string) => api.post(`/duplicates/files/${fileId}/undo`),
}

export const similarApi = {
  listGroups: (params?: { threshold?: number; page?: number; page_size?: number }) =>
    api.get('/similar', { params }),
  stats: () => api.get('/similar/stats'),
  deleteFile: (fileId: string) => api.delete(`/similar/files/${fileId}`),
}

export interface FileManifestItem {
  remote_id?: string
  file_path: string
  file_name: string
  file_size: number
  mime_type?: string
  md5_hash?: string
  sha256_hash?: string
  perceptual_hash?: string
  last_modified?: string
}

export interface DashboardSummary {
  total_files: number
  total_size_bytes: number
  potential_savings_bytes: number
  low_risk_bytes: number
  review_needed_bytes: number
  duplicate_groups: number
  last_scan: string | null
  storage_connections: number
}

export interface SimilarGroup {
  match_type: string
  similarity: number
  wasted_bytes: number
  files: SimilarFile[]
}

export interface SimilarFile {
  id: string
  file_name: string
  file_path: string
  file_size: number
  mime_type?: string
  last_modified?: string
  thumbnail_url?: string
  perceptual_hash?: string
}

export function formatBytes(bytes: number): string {
  if (bytes === 0) return '0 B'
  const k = 1024
  const sizes = ['B', 'KB', 'MB', 'GB', 'TB']
  const i = Math.floor(Math.log(bytes) / Math.log(k))
  return `${parseFloat((bytes / Math.pow(k, i)).toFixed(1))} ${sizes[i]}`
}

export function formatDate(dateStr?: string): string {
  if (!dateStr) return '—'
  return new Date(dateStr).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })
}

// ── Suggestions (Month 3) ─────────────────────────────────────────────────
export const suggestionsApi = {
  list: (params?: { risk_level?: string; include_dismissed?: boolean }) =>
    api.get('/suggestions', { params }),
  stats: () => api.get('/suggestions/stats'),
  generate: () => api.post('/suggestions/generate'),
  apply: (id: string) => api.post(`/suggestions/${id}/apply`),
  dismiss: (id: string) => api.post(`/suggestions/${id}/dismiss`),
}

// ── AI Classification (Month 3) ───────────────────────────────────────────
export const classifyApi = {
  run: (params?: { use_ai?: boolean; limit?: number }) =>
    api.post('/classify/run', null, { params }),
  stats: () => api.get('/classify/stats'),
  files: (params?: { category?: string; is_blurry?: boolean; is_screenshot?: boolean; page?: number }) =>
    api.get('/classify/files', { params }),
}

// ── Billing (Month 3) ─────────────────────────────────────────────────────
export const billingApi = {
  checkout: (plan: 'monthly' | 'yearly') => api.post('/billing/checkout', { plan }),
  portal: () => api.post('/billing/portal'),
  status: () => api.get('/billing/status'),
}

// ── Cloud — OneDrive (Month 3) ────────────────────────────────────────────
// Added to cloudApi
export const oneDriveApi = {
  authorize: () => api.get('/connections/onedrive/authorize'),
}

// ── Types (Month 3) ───────────────────────────────────────────────────────
export interface Suggestion {
  id: string
  suggestion_type: string
  title: string
  description: string
  file_count: number
  bytes_savings: number
  risk_level: 'low' | 'medium' | 'high'
  action: string
  action_label: string
  dismissed: boolean
  applied: boolean
  applied_at: string | null
  created_at: string
}

export interface ClassifyStats {
  categories: { category: string; count: number; total_bytes: number }[]
  total_classified: number
  total_unclassified: number
  blurry_count: number
  blurry_bytes: number
  screenshot_count: number
  screenshot_bytes: number
}

// ── Share Links (Month 4) ─────────────────────────────────────────────────
export const shareApi = {
  create: (data: { link_type: string; label?: string; expires_days?: number }) =>
    api.post('/share', data),
  list: () => api.get('/share'),
  revoke: (id: string) => api.delete(`/share/${id}`),
  view: (slug: string) => api.get(`/share/view/${slug}`),
}

// ── Webhooks (Month 5) ────────────────────────────────────────────────────
export const webhooksApi = {
  create: (data: { url: string; events: string[]; label?: string }) =>
    api.post('/webhooks', data),
  list: () => api.get('/webhooks'),
  delete: (id: string) => api.delete(`/webhooks/${id}`),
  test: (id: string) => api.post(`/webhooks/${id}/test`),
}

// ── Export (Month 5) ──────────────────────────────────────────────────────
export const exportApi = {
  csvUrl: () => `${process.env.NEXT_PUBLIC_API_URL}/export/csv`,
  excelUrl: () => `${process.env.NEXT_PUBLIC_API_URL}/export/excel`,
  gdprUrl: () => `${process.env.NEXT_PUBLIC_API_URL}/export/gdpr`,
}

// ── Account (Month 6) ─────────────────────────────────────────────────────
export const accountApi = {
  getPreferences: () => api.get('/account/preferences'),
  updatePreferences: (prefs: any) => api.put('/account/preferences', prefs),
  changePassword: (data: { current_password: string; new_password: string }) =>
    api.post('/account/password', data),
  stats: () => api.get('/account/stats'),
  delete: (data: { confirm_email: string; reason?: string }) =>
    api.delete('/account', { data }),
}

// ── Admin (Month 5) ───────────────────────────────────────────────────────
export const adminApi = {
  stats: () => api.get('/admin/stats'),
  users: (params?: { page?: number; search?: string; tier?: string }) =>
    api.get('/admin/users', { params }),
  changeTier: (userId: string, tier: string) =>
    api.post(`/admin/users/${userId}/tier`, { tier }),
  audit: (params?: { page?: number; user_id?: string; action?: string }) =>
    api.get('/admin/audit', { params }),
}
