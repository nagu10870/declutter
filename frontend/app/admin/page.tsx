'use client'

import { useEffect, useState, useCallback } from 'react'
import { adminApi, formatBytes, formatDate } from '@/lib/api'
import { Sidebar } from '@/components/layout/Sidebar'
import { Toaster } from 'react-hot-toast'
import toast from 'react-hot-toast'
import { useAuthStore } from '@/lib/store'
import {
  BarChart2, Users, Shield, ScrollText, RefreshCw,
  TrendingUp, AlertCircle, Search, ChevronDown
} from 'lucide-react'
import clsx from 'clsx'

const TABS = [
  { id: 'stats', label: 'Stats', icon: BarChart2 },
  { id: 'users', label: 'Users', icon: Users },
  { id: 'audit', label: 'Audit Log', icon: ScrollText },
]

export default function AdminPage() {
  return (
    <div className="flex h-screen overflow-hidden">
      <Sidebar />
      <main className="flex-1 overflow-y-auto bg-surface">
        <AdminContent />
      </main>
      <Toaster position="bottom-right" toastOptions={{
        style: { background: '#13161e', color: '#f0f2ff', border: '1px solid #252a38' },
        success: { iconTheme: { primary: '#1de9a4', secondary: '#0d0f14' } },
      }} />
    </div>
  )
}

function AdminContent() {
  const { user } = useAuthStore()
  const [activeTab, setActiveTab] = useState('stats')
  const [adminSecret, setAdminSecret] = useState('')
  const [authorized, setAuthorized] = useState(false)
  const [checking, setChecking] = useState(false)

  const checkAuth = async () => {
    setChecking(true)
    try {
      // Set the admin secret header for subsequent requests
      localStorage.setItem('admin_secret', adminSecret)
      const res = await adminApi.stats()
      if (res.data) setAuthorized(true)
    } catch {
      toast.error('Invalid admin secret or insufficient permissions')
      localStorage.removeItem('admin_secret')
    } finally {
      setChecking(false)
    }
  }

  // Check if already authorized
  useEffect(() => {
    const secret = localStorage.getItem('admin_secret')
    if (secret || user?.tier === 'admin') {
      setAuthorized(true)
      if (secret) setAdminSecret(secret)
    }
  }, [user])

  if (!authorized) {
    return (
      <div className="p-8 max-w-md">
        <div className="card p-8 text-center">
          <Shield className="w-12 h-12 text-brand mx-auto mb-4" />
          <h1 className="font-display text-2xl font-bold mb-2">Admin Access</h1>
          <p className="text-ink-muted mb-6 text-sm">Enter your admin secret to access the platform dashboard.</p>
          <input
            className="input mb-4"
            type="password"
            placeholder="Admin secret key"
            value={adminSecret}
            onChange={e => setAdminSecret(e.target.value)}
            onKeyDown={e => e.key === 'Enter' && checkAuth()}
          />
          <button onClick={checkAuth} disabled={checking || !adminSecret} className="btn-primary w-full flex items-center justify-center gap-2">
            {checking ? <RefreshCw className="w-4 h-4 animate-spin" /> : <Shield className="w-4 h-4" />}
            {checking ? 'Checking…' : 'Access Admin Panel'}
          </button>
        </div>
      </div>
    )
  }

  return (
    <div className="p-8 max-w-5xl animate-fade-in">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="font-display text-3xl font-bold flex items-center gap-3">
            <Shield className="w-7 h-7 text-accent-red" />
            Admin Panel
          </h1>
          <p className="text-ink-muted mt-1">Platform management and monitoring</p>
        </div>
        <span className="text-xs font-mono bg-accent-red/10 text-accent-red border border-accent-red/20 px-3 py-1.5 rounded-full">
          ADMIN
        </span>
      </div>

      {/* Tab bar */}
      <div className="flex gap-1 bg-surface-raised rounded-xl p-1 mb-6 w-fit">
        {TABS.map(tab => {
          const Icon = tab.icon
          return (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={clsx(
                'flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-all',
                activeTab === tab.id
                  ? 'bg-brand text-white shadow-sm'
                  : 'text-ink-muted hover:text-ink'
              )}
            >
              <Icon className="w-4 h-4" />
              {tab.label}
            </button>
          )
        })}
      </div>

      {activeTab === 'stats' && <PlatformStats adminSecret={adminSecret} />}
      {activeTab === 'users' && <UsersTab adminSecret={adminSecret} />}
      {activeTab === 'audit' && <AuditTab adminSecret={adminSecret} />}
    </div>
  )
}

// ── Platform Stats ─────────────────────────────────────────────────────────

function PlatformStats({ adminSecret }: { adminSecret: string }) {
  const [stats, setStats] = useState<any>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    adminApi.stats().then(r => setStats(r.data)).catch(() => {}).finally(() => setLoading(false))
  }, [])

  if (loading) return <div className="grid grid-cols-3 gap-4">{[...Array(6)].map((_, i) => <div key={i} className="h-24 bg-surface-raised rounded-2xl animate-pulse" />)}</div>

  if (!stats) return <div className="card p-8 text-center text-ink-muted">Failed to load stats</div>

  const conversionPct = stats.users?.conversion_rate || 0

  return (
    <div className="space-y-6">
      {/* KPI grid */}
      <div className="grid grid-cols-3 gap-4">
        {[
          { label: 'Total Users', value: stats.users?.total?.toLocaleString(), color: 'text-brand', icon: '👤' },
          { label: 'Pro Users', value: stats.users?.pro?.toLocaleString(), color: 'text-accent-green', icon: '⚡' },
          { label: 'Conversion Rate', value: `${conversionPct}%`, color: conversionPct > 5 ? 'text-accent-green' : 'text-accent-amber', icon: '📈' },
          { label: 'Total Files', value: stats.files?.total?.toLocaleString(), color: 'text-ink', icon: '📁' },
          { label: 'Storage Indexed', value: formatBytes(stats.files?.total_bytes || 0), color: 'text-ink-muted', icon: '💾' },
          { label: 'Scans Today', value: stats.scans?.today?.toLocaleString(), color: 'text-brand', icon: '🔍' },
        ].map(kpi => (
          <div key={kpi.label} className="card p-5">
            <div className="text-2xl mb-2">{kpi.icon}</div>
            <p className={clsx('font-display text-2xl font-bold', kpi.color)}>{kpi.value}</p>
            <p className="text-xs text-ink-faint font-mono uppercase tracking-wider mt-1">{kpi.label}</p>
          </div>
        ))}
      </div>

      {/* Conversion funnel */}
      <div className="card p-6">
        <h2 className="font-display font-bold mb-4 flex items-center gap-2">
          <TrendingUp className="w-5 h-5 text-brand" />
          User Funnel
        </h2>
        <div className="space-y-3">
          {[
            { label: 'Registered', value: stats.users?.total, max: stats.users?.total, color: 'bg-brand' },
            { label: 'Active', value: stats.users?.active, max: stats.users?.total, color: 'bg-brand/70' },
            { label: 'New (30d)', value: stats.users?.new_30d, max: stats.users?.total, color: 'bg-accent-amber' },
            { label: 'Pro Subscribers', value: stats.users?.pro, max: stats.users?.total, color: 'bg-accent-green' },
          ].map(row => (
            <div key={row.label} className="flex items-center gap-4">
              <span className="text-xs text-ink-muted w-24 shrink-0">{row.label}</span>
              <div className="flex-1 h-2 bg-surface-overlay rounded-full overflow-hidden">
                <div
                  className={clsx('h-full rounded-full transition-all', row.color)}
                  style={{ width: `${row.max > 0 ? (row.value / row.max) * 100 : 0}%` }}
                />
              </div>
              <span className="text-xs font-mono text-ink-faint w-12 text-right">{row.value?.toLocaleString()}</span>
            </div>
          ))}
        </div>
      </div>

      {/* Scans summary */}
      <div className="grid grid-cols-3 gap-4">
        <div className="card p-5">
          <p className="text-xs text-ink-faint font-mono uppercase tracking-wider mb-2">Total Scans</p>
          <p className="font-display text-2xl font-bold text-ink">{stats.scans?.total?.toLocaleString()}</p>
        </div>
        <div className="card p-5">
          <p className="text-xs text-ink-faint font-mono uppercase tracking-wider mb-2">Completed</p>
          <p className="font-display text-2xl font-bold text-accent-green">{stats.scans?.completed?.toLocaleString()}</p>
        </div>
        <div className="card p-5">
          <p className="text-xs text-ink-faint font-mono uppercase tracking-wider mb-2">Files Indexed Today</p>
          <p className="font-display text-2xl font-bold text-brand">{stats.files?.indexed_today?.toLocaleString()}</p>
        </div>
      </div>
    </div>
  )
}

// ── Users Tab ──────────────────────────────────────────────────────────────

function UsersTab({ adminSecret }: { adminSecret: string }) {
  const [users, setUsers] = useState<any[]>([])
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(true)
  const [search, setSearch] = useState('')
  const [tierFilter, setTierFilter] = useState('')
  const [page, setPage] = useState(1)
  const [changingTier, setChangingTier] = useState<string | null>(null)

  const loadUsers = useCallback(async () => {
    setLoading(true)
    try {
      const res = await adminApi.users({ page, search: search || undefined, tier: tierFilter || undefined })
      setUsers(res.data.users || [])
      setTotal(res.data.total || 0)
    } catch { }
    finally { setLoading(false) }
  }, [page, search, tierFilter])

  useEffect(() => { loadUsers() }, [loadUsers])

  const handleTierChange = async (userId: string, newTier: string) => {
    setChangingTier(userId)
    try {
      await adminApi.changeTier(userId, newTier)
      toast.success(`User tier updated to ${newTier}`)
      await loadUsers()
    } catch {
      toast.error('Failed to update tier')
    } finally {
      setChangingTier(null)
    }
  }

  return (
    <div className="space-y-4">
      {/* Filters */}
      <div className="flex gap-3">
        <div className="relative flex-1">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-ink-faint" />
          <input
            className="input pl-10"
            placeholder="Search by email..."
            value={search}
            onChange={e => { setSearch(e.target.value); setPage(1) }}
          />
        </div>
        <select
          className="input w-40"
          value={tierFilter}
          onChange={e => { setTierFilter(e.target.value); setPage(1) }}
        >
          <option value="">All tiers</option>
          <option value="free">Free</option>
          <option value="pro">Pro</option>
          <option value="admin">Admin</option>
        </select>
      </div>

      <p className="text-xs text-ink-faint">{total.toLocaleString()} users total</p>

      {/* User table */}
      {loading ? (
        <div className="space-y-2">
          {[...Array(8)].map((_, i) => <div key={i} className="h-14 bg-surface-raised rounded-xl animate-pulse" />)}
        </div>
      ) : (
        <div className="card overflow-hidden">
          <div className="grid grid-cols-[1fr_80px_140px_80px] gap-4 px-5 py-3 bg-surface-overlay border-b border-surface-border text-xs font-mono text-ink-faint uppercase">
            <span>Email</span>
            <span>Tier</span>
            <span>Joined</span>
            <span>Actions</span>
          </div>
          <div className="divide-y divide-surface-border">
            {users.map(u => (
              <div key={u.id} className="grid grid-cols-[1fr_80px_140px_80px] gap-4 px-5 py-3 items-center hover:bg-surface-overlay/50 transition-colors">
                <div>
                  <p className="text-sm font-medium">{u.email}</p>
                  {u.full_name && <p className="text-xs text-ink-faint">{u.full_name}</p>}
                </div>
                <span className={clsx(
                  'text-[10px] font-mono px-2 py-0.5 rounded-full w-fit capitalize',
                  u.tier === 'pro' ? 'bg-accent-green/10 text-accent-green' :
                    u.tier === 'admin' ? 'bg-accent-red/10 text-accent-red' :
                      'bg-surface-border text-ink-faint'
                )}>
                  {u.tier}
                </span>
                <span className="text-xs text-ink-faint">{formatDate(u.created_at)}</span>
                <div className="relative">
                  <select
                    className="text-xs bg-surface-overlay border border-surface-border rounded-lg px-2 py-1 text-ink-muted w-full"
                    value={u.tier}
                    disabled={changingTier === u.id}
                    onChange={e => handleTierChange(u.id, e.target.value)}
                  >
                    <option value="free">→ Free</option>
                    <option value="pro">→ Pro</option>
                    <option value="admin">→ Admin</option>
                  </select>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Pagination */}
      <div className="flex items-center justify-between">
        <button onClick={() => setPage(p => Math.max(1, p - 1))} disabled={page === 1} className="btn-ghost text-sm disabled:opacity-40">← Prev</button>
        <span className="text-sm text-ink-muted font-mono">Page {page}</span>
        <button onClick={() => setPage(p => p + 1)} disabled={users.length < 50} className="btn-ghost text-sm disabled:opacity-40">Next →</button>
      </div>
    </div>
  )
}

// ── Audit Log Tab ──────────────────────────────────────────────────────────

function AuditTab({ adminSecret }: { adminSecret: string }) {
  const [logs, setLogs] = useState<any[]>([])
  const [loading, setLoading] = useState(true)
  const [page, setPage] = useState(1)
  const [actionFilter, setActionFilter] = useState('')

  const loadLogs = useCallback(async () => {
    setLoading(true)
    try {
      const res = await adminApi.audit({ page, action: actionFilter || undefined })
      setLogs(res.data || [])
    } catch { }
    finally { setLoading(false) }
  }, [page, actionFilter])

  useEffect(() => { loadLogs() }, [loadLogs])

  const ACTION_COLORS: Record<string, string> = {
    'admin.change_tier': 'text-accent-amber',
    'file.deleted': 'text-accent-red',
    'scan.completed': 'text-accent-green',
    'auth.login': 'text-brand',
    'auth.register': 'text-brand',
  }

  return (
    <div className="space-y-4">
      <div className="flex gap-3">
        <input
          className="input"
          placeholder="Filter by action (e.g. delete, admin)"
          value={actionFilter}
          onChange={e => { setActionFilter(e.target.value); setPage(1) }}
        />
        <button onClick={loadLogs} className="btn-ghost flex items-center gap-2">
          <RefreshCw className="w-4 h-4" /> Refresh
        </button>
      </div>

      {loading ? (
        <div className="space-y-2">
          {[...Array(10)].map((_, i) => <div key={i} className="h-12 bg-surface-raised rounded-xl animate-pulse" />)}
        </div>
      ) : logs.length === 0 ? (
        <div className="card p-8 text-center text-ink-muted">No audit log entries found</div>
      ) : (
        <div className="card overflow-hidden">
          <div className="divide-y divide-surface-border">
            {logs.map(log => (
              <div key={log.id} className="flex items-start gap-4 px-5 py-3 hover:bg-surface-overlay/50 transition-colors">
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-3">
                    <span className={clsx('text-xs font-mono', ACTION_COLORS[log.action] || 'text-ink-muted')}>
                      {log.action}
                    </span>
                    {log.resource_type && (
                      <span className="text-[10px] text-ink-faint border border-surface-border px-1.5 py-0.5 rounded">
                        {log.resource_type}
                      </span>
                    )}
                  </div>
                  <p className="text-xs text-ink-faint mt-0.5">
                    {log.user_id ? `User: ${log.user_id.slice(0, 8)}…` : 'System'} · {log.ip_address || 'unknown IP'}
                  </p>
                </div>
                <span className="text-[10px] text-ink-faint font-mono shrink-0 mt-0.5">
                  {formatDate(log.created_at)}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}

      <div className="flex items-center justify-between">
        <button onClick={() => setPage(p => Math.max(1, p - 1))} disabled={page === 1} className="btn-ghost text-sm disabled:opacity-40">← Prev</button>
        <span className="text-sm text-ink-muted font-mono">Page {page}</span>
        <button onClick={() => setPage(p => p + 1)} disabled={logs.length < 100} className="btn-ghost text-sm disabled:opacity-40">Next →</button>
      </div>
    </div>
  )
}
