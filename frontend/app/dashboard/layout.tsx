'use client'

import { useEffect } from 'react'
import { useRouter } from 'next/navigation'
import { Sidebar } from '@/components/layout/Sidebar'
import { useAuthStore } from '@/lib/store'
import { Toaster } from 'react-hot-toast'

export default function AppLayout({ children }: { children: React.ReactNode }) {
  const { isAuthenticated, isLoading, fetchMe } = useAuthStore()
  const router = useRouter()

  useEffect(() => {
    fetchMe().then(() => {
      const auth = useAuthStore.getState()
      if (!auth.isAuthenticated) {
        router.push('/auth/login')
      }
    })
  }, [])

  if (isLoading) {
    return (
      <div className="h-screen flex items-center justify-center bg-surface">
        <div className="w-10 h-10 border-2 border-brand border-t-transparent rounded-full animate-spin" />
      </div>
    )
  }

  return (
    <div className="flex h-screen overflow-hidden">
      <Sidebar />
      <main className="flex-1 overflow-y-auto bg-surface">
        {children}
      </main>
      <Toaster
        position="bottom-right"
        toastOptions={{
          style: {
            background: '#13161e',
            color: '#f0f2ff',
            border: '1px solid #252a38',
            fontFamily: 'var(--font-body)',
          },
          success: { iconTheme: { primary: '#1de9a4', secondary: '#0d0f14' } },
          error: { iconTheme: { primary: '#ff4d6a', secondary: '#0d0f14' } },
        }}
      />
    </div>
  )
}
