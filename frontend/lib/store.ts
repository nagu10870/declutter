import { create } from 'zustand'
import { authApi } from './api'

interface User {
  id: string
  email: string
  full_name: string | null
  tier: string
  is_active: boolean
  is_pro?: boolean
}

interface AuthState {
  user: User | null
  isLoading: boolean
  isAuthenticated: boolean
  login: (email: string, password: string) => Promise<void>
  register: (email: string, password: string, fullName?: string) => Promise<void>
  logout: () => Promise<void>
  fetchMe: () => Promise<void>
}

export const useAuthStore = create<AuthState>((set) => ({
  user: null,
  isLoading: false,
  isAuthenticated: false,

  fetchMe: async () => {
    const token = localStorage.getItem('access_token')
    if (!token) return
    try {
      set({ isLoading: true })
      const res = await authApi.me()
      set({ user: res.data, isAuthenticated: true })
    } catch {
      localStorage.removeItem('access_token')
      localStorage.removeItem('refresh_token')
      set({ user: null, isAuthenticated: false })
    } finally {
      set({ isLoading: false })
    }
  },

  login: async (email, password) => {
    set({ isLoading: true })
    try {
      const res = await authApi.login({ email, password })
      localStorage.setItem('access_token', res.data.access_token)
      localStorage.setItem('refresh_token', res.data.refresh_token)
      const me = await authApi.me()
      set({ user: me.data, isAuthenticated: true })
    } finally {
      set({ isLoading: false })
    }
  },

  register: async (email, password, fullName) => {
    set({ isLoading: true })
    try {
      await authApi.register({ email, password, full_name: fullName })
      const loginRes = await authApi.login({ email, password })
      localStorage.setItem('access_token', loginRes.data.access_token)
      localStorage.setItem('refresh_token', loginRes.data.refresh_token)
      const me = await authApi.me()
      set({ user: me.data, isAuthenticated: true })
    } finally {
      set({ isLoading: false })
    }
  },

  logout: async () => {
    await authApi.logout().catch(() => {})
    localStorage.removeItem('access_token')
    localStorage.removeItem('refresh_token')
    set({ user: null, isAuthenticated: false })
  },
}))
