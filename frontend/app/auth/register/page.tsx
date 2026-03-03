'use client'

import { useState } from 'react'
import { useAuthStore } from '@/lib/store'
import { useRouter } from 'next/navigation'
import Link from 'next/link'
import { Zap, ArrowRight, CheckCircle2 } from 'lucide-react'
import toast from 'react-hot-toast'
import { Toaster } from 'react-hot-toast'

const PERKS = [
  'Find & delete duplicate files instantly',
  'Free up gigabytes of wasted space',
  'AI-powered file organization',
  'Local storage scanning, forever free',
]

export default function RegisterPage() {
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [name, setName] = useState('')
  const { register, isLoading } = useAuthStore()
  const router = useRouter()

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (password.length < 8) {
      toast.error('Password must be at least 8 characters')
      return
    }
    try {
      await register(email, password, name || undefined)
      toast.success('Account created!')
      router.push('/dashboard')
    } catch (err: any) {
      toast.error(err?.response?.data?.detail || 'Registration failed')
    }
  }

  return (
    <div className="min-h-screen bg-surface flex items-center justify-center bg-grid p-4">
      <Toaster position="top-center" toastOptions={{
        style: { background: '#13161e', color: '#f0f2ff', border: '1px solid #252a38' },
      }} />

      <div className="absolute inset-0 overflow-hidden pointer-events-none">
        <div className="absolute top-1/3 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[500px] h-[500px] bg-accent-green/5 rounded-full blur-3xl" />
      </div>

      <div className="w-full max-w-md relative">
        {/* Logo */}
        <div className="flex items-center justify-center gap-3 mb-10">
          <div className="w-11 h-11 rounded-2xl bg-brand-gradient flex items-center justify-center shadow-glow-brand">
            <Zap className="w-6 h-6 text-white" fill="white" />
          </div>
          <p className="font-display text-xl font-bold">Declutter</p>
        </div>

        <div className="card p-8 shadow-card">
          <h1 className="font-display text-2xl font-bold text-center mb-1">Start for free</h1>
          <p className="text-ink-muted text-sm text-center mb-6">No credit card required</p>

          {/* Perks */}
          <div className="space-y-2 mb-7 p-4 rounded-xl bg-surface-overlay">
            {PERKS.map((p) => (
              <div key={p} className="flex items-center gap-2.5 text-sm">
                <CheckCircle2 className="w-4 h-4 text-accent-green shrink-0" />
                <span className="text-ink-muted">{p}</span>
              </div>
            ))}
          </div>

          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="block text-xs font-medium text-ink-muted uppercase tracking-wider mb-1.5">Name (optional)</label>
              <input type="text" className="input" placeholder="Alex Johnson" value={name} onChange={(e) => setName(e.target.value)} autoComplete="name" />
            </div>
            <div>
              <label className="block text-xs font-medium text-ink-muted uppercase tracking-wider mb-1.5">Email</label>
              <input type="email" className="input" placeholder="you@example.com" value={email} onChange={(e) => setEmail(e.target.value)} required autoComplete="email" />
            </div>
            <div>
              <label className="block text-xs font-medium text-ink-muted uppercase tracking-wider mb-1.5">Password</label>
              <input type="password" className="input" placeholder="Min. 8 characters" value={password} onChange={(e) => setPassword(e.target.value)} required autoComplete="new-password" />
            </div>

            <button type="submit" disabled={isLoading} className="btn-primary w-full flex items-center justify-center gap-2 mt-2">
              {isLoading
                ? <div className="w-5 h-5 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                : <>Create free account <ArrowRight className="w-4 h-4" /></>
              }
            </button>
          </form>

          <p className="text-center text-sm text-ink-muted mt-6">
            Already have an account?{' '}
            <Link href="/auth/login" className="text-brand hover:underline font-medium">Sign in</Link>
          </p>
        </div>
      </div>
    </div>
  )
}
