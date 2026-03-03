'use client'

import Link from 'next/link'
import { usePathname } from 'next/navigation'
import {
  LayoutDashboard, Copy, Files, Settings,
  Zap, LogOut, ChevronRight, Images, Sparkles,
  Key, User
} from 'lucide-react'
import { useAuthStore } from '@/lib/store'
import { useRouter } from 'next/navigation'
import clsx from 'clsx'

const navItems = [
  { href: '/dashboard', label: 'Dashboard', icon: LayoutDashboard },
  { href: '/duplicates', label: 'Duplicates', icon: Copy, badge: 'hot' },
  { href: '/similar', label: 'Similar Photos', icon: Images, badge: 'pro' },
  { href: '/suggestions', label: 'Suggestions', icon: Sparkles, badge: 'new' },
  { href: '/files', label: 'All Files', icon: Files },
  { href: '/api-keys', label: 'API Keys', icon: Key, badge: 'pro' },
  { href: '/account', label: 'Account', icon: User },
  { href: '/settings', label: 'Settings', icon: Settings },
]

export function Sidebar() {
  const pathname = usePathname()
  const { user, logout } = useAuthStore()
  const router = useRouter()

  const handleLogout = async () => {
    await logout()
    router.push('/auth/login')
  }

  return (
    <aside className="w-64 h-screen bg-surface-raised border-r border-surface-border flex flex-col sticky top-0 shrink-0">
      {/* Logo */}
      <div className="p-6 border-b border-surface-border">
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 rounded-xl bg-brand-gradient flex items-center justify-center shadow-glow-brand">
            <Zap className="w-5 h-5 text-white" fill="white" />
          </div>
          <div>
            <p className="font-display font-bold text-ink leading-none">Declutter</p>
            <p className="text-[10px] text-ink-faint font-mono uppercase tracking-widest mt-0.5">AI Organizer</p>
          </div>
        </div>
      </div>

      {/* Nav */}
      <nav className="flex-1 p-3 space-y-0.5 overflow-y-auto">
        {navItems.map(({ href, label, icon: Icon, badge }) => {
          const active = pathname.startsWith(href)
          const isProLocked = badge === 'pro' && user?.tier === 'free'
          return (
            <Link
              key={href}
              href={href}
              className={clsx(
                'flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm font-medium transition-all duration-200 group relative',
                active
                  ? 'bg-brand/15 text-brand border border-brand/20'
                  : 'text-ink-muted hover:text-ink hover:bg-surface-overlay'
              )}
            >
              <Icon className={clsx('w-4 h-4 shrink-0', active ? 'text-brand' : '')} />
              <span className="flex-1">{label}</span>
              {badge === 'hot' && (
                <span className="text-[9px] font-mono bg-accent-red/20 text-accent-red px-1.5 py-0.5 rounded-full uppercase tracking-wider">
                  hot
                </span>
              )}
              {badge === 'new' && (
                <span className="text-[9px] font-mono bg-accent-green/20 text-accent-green px-1.5 py-0.5 rounded-full uppercase tracking-wider">
                  new
                </span>
              )}
              {badge === 'pro' && (
                <span className={clsx(
                  'text-[9px] font-mono px-1.5 py-0.5 rounded-full uppercase tracking-wider',
                  isProLocked
                    ? 'bg-ink-faint/10 text-ink-faint'
                    : 'bg-brand/20 text-brand'
                )}>
                  pro
                </span>
              )}
              {active && <ChevronRight className="w-3 h-3 opacity-60" />}
            </Link>
          )
        })}
      </nav>

      {/* User + tier */}
      <div className="p-3 border-t border-surface-border">
        {user?.tier === 'free' && (
          <div className="mb-3 p-3 rounded-xl bg-brand/10 border border-brand/20 text-xs">
            <p className="text-brand font-semibold mb-1">Upgrade to Pro</p>
            <p className="text-ink-muted leading-relaxed">Unlock AI similarity detection, cloud integrations, API access & more.</p>
            <Link href="/settings" className="inline-block mt-2 text-brand font-semibold hover:underline">
              View plans →
            </Link>
          </div>
        )}

        <div
          className="flex items-center gap-3 px-3 py-2 rounded-xl hover:bg-surface-overlay transition-colors group cursor-pointer"
          onClick={handleLogout}
        >
          <div className="w-8 h-8 rounded-full bg-brand/20 flex items-center justify-center text-brand text-xs font-bold">
            {user?.email?.[0]?.toUpperCase() || 'U'}
          </div>
          <div className="flex-1 min-w-0">
            <p className="text-xs font-medium text-ink truncate">{user?.email}</p>
            <p className="text-[10px] text-ink-faint capitalize font-mono">{user?.tier}</p>
          </div>
          <LogOut className="w-4 h-4 text-ink-faint opacity-0 group-hover:opacity-100 transition-opacity" />
        </div>
      </div>
    </aside>
  )
}
