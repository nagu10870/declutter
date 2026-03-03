import { Sidebar } from '@/components/layout/Sidebar'
import { Toaster } from 'react-hot-toast'

export default function DuplicatesLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex h-screen overflow-hidden">
      <Sidebar />
      <main className="flex-1 overflow-y-auto bg-surface">
        {children}
      </main>
      <Toaster position="bottom-right" toastOptions={{
        style: { background: '#13161e', color: '#f0f2ff', border: '1px solid #252a38' },
      }} />
    </div>
  )
}
