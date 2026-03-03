'use client'

import { useEffect, useState } from 'react'
import { api, formatBytes, formatDate } from '@/lib/api'
import { useAuthStore } from '@/lib/store'
import { Sidebar } from '@/components/layout/Sidebar'
import { Toaster } from 'react-hot-toast'
import toast from 'react-hot-toast'
import { useRouter } from 'next/navigation'
import {
  User, Lock, Bell, BarChart2, Trash2, Shield,
  RefreshCw, CheckCircle2, AlertTriangle, TrendingUp
} from 'lucide-react'
import clsx from 'clsx'

export default function AccountPage() {
  return (
    <div className="flex h-screen overflow-hidden">
      <Sidebar />
      <main className="flex-1 overflow-y-auto bg-surface">
        <AccountContent />
      </main>
      <Toaster position="bottom-right" toastOptions={{
        style: { background: '#13161e', color: '#f0f2ff', border: '1px solid #252a38' },
        success: { iconTheme: { primary: '#1de9a4', secondary: '#0d0f14' } },
      }} />
    </div>
  )
}

const TABS = [
  { id: 'stats', label: 'Usage Stats', icon: BarChart2 },
  { id: 'notifications', label: 'Notifications', icon: Bell },
  { id: 'security', label: 'Security', icon: Lock },
  { id: 'data', label: 'Data & Privacy', icon: Shield },
]

function AccountContent() {
  const { user } = useAuthStore()
  const [activeTab, setActiveTab] = useState('stats')

  return (
    <div className="p-8 max-w-3xl animate-fade-in">
      {/* Header */}
      <div className="flex items-center gap-4 mb-8">
        <div className="w-14 h-14 rounded-2xl bg-brand/20 flex items-center justify-center text-brand text-2xl font-bold">
          {user?.email?.[0]?.toUpperCase() || 'U'}
        </div>
        <div>
          <h1 className="font-display text-2xl font-bold">{user?.full_name || user?.email}</h1>
          <p className="text-ink-muted text-sm">{user?.email}</p>
          <span className={clsx(
            'text-xs font-mono px-2 py-0.5 rounded-full mt-1 inline-block capitalize',
            user?.is_pro
              ? 'bg-accent-green/15 text-accent-green'
              : 'bg-surface-overlay text-ink-muted'
          )}>
            {user?.tier} plan
          </span>
        </div>
      </div>

      {/* Tabs */}
      <div className="flex gap-1 bg-surface-raised rounded-xl p-1 mb-6">
        {TABS.map(tab => {
          const Icon = tab.icon
          return (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={clsx(
                'flex-1 flex items-center justify-center gap-2 py-2 text-sm font-medium rounded-lg transition-all',
                activeTab === tab.id
                  ? 'bg-brand text-white shadow-sm'
                  : 'text-ink-muted hover:text-ink'
              )}
            >
              <Icon className="w-4 h-4" />
              <span className="hidden sm:inline">{tab.label}</span>
            </button>
          )
        })}
      </div>

      {/* Tab content */}
      {activeTab === 'stats' && <StatsTab />}
      {activeTab === 'notifications' && <NotificationsTab />}
      {activeTab === 'security' && <SecurityTab />}
      {activeTab === 'data' && <DataPrivacyTab />}
    </div>
  )
}

// ── Stats Tab ──────────────────────────────────────────────────────────────

function StatsTab() {
  const [stats, setStats] = useState<any>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    api.get('/account/stats').then(r => setStats(r.data)).catch(() => {}).finally(() => setLoading(false))
  }, [])

  if (loading) return <div className="h-64 bg-surface-raised rounded-2xl animate-pulse" />

  if (!stats) return <div className="card p-8 text-center text-ink-muted">No stats yet. Run a scan first!</div>

  const { totals, monthly_breakdown, member_since } = stats

  return (
    <div className="space-y-5">
      {/* All-time stats */}
      <div className="grid grid-cols-2 gap-3">
        {[
          { label: 'Total Files', value: totals.total_files?.toLocaleString(), color: 'text-brand' },
          { label: 'Total Storage', value: formatBytes(totals.total_bytes || 0), color: 'text-ink' },
          { label: 'Files Cleaned', value: totals.deleted_files?.toLocaleString(), color: 'text-accent-green' },
          { label: 'Space Freed', value: formatBytes(totals.total_bytes_freed || 0), color: 'text-accent-green' },
        ].map(stat => (
          <div key={stat.label} className="card p-4">
            <p className={clsx('font-display text-2xl font-bold', stat.color)}>{stat.value}</p>
            <p className="text-xs text-ink-faint font-mono uppercase tracking-wider mt-1">{stat.label}</p>
          </div>
        ))}
      </div>

      {/* Monthly chart */}
      {monthly_breakdown?.length > 0 && (
        <div className="card p-5">
          <div className="flex items-center gap-2 mb-4">
            <TrendingUp className="w-4 h-4 text-brand" />
            <h3 className="font-semibold">Files Added (Last 6 Months)</h3>
          </div>
          <div className="flex items-end gap-2 h-32">
            {monthly_breakdown.map((m: any, i: number) => {
              const maxFiles = Math.max(...monthly_breakdown.map((x: any) => x.files_added))
              const height = maxFiles > 0 ? (m.files_added / maxFiles) * 100 : 0
              return (
                <div key={i} className="flex-1 flex flex-col items-center gap-1">
                  <span className="text-[10px] text-ink-faint font-mono">{m.files_added}</span>
                  <div
                    className="w-full bg-brand/40 rounded-t-md transition-all"
                    style={{ height: `${Math.max(height, 4)}%` }}
                  />
                  <span className="text-[9px] text-ink-faint font-mono">
                    {m.month.slice(5)}
                  </span>
                </div>
              )
            })}
          </div>
        </div>
      )}

      <p className="text-xs text-ink-faint text-center">
        Member since {formatDate(member_since)}
      </p>
    </div>
  )
}

// ── Notifications Tab ──────────────────────────────────────────────────────

function NotificationsTab() {
  const [prefs, setPrefs] = useState<any>(null)
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    api.get('/account/preferences').then(r => setPrefs(r.data)).catch(() => {})
  }, [])

  const handleSave = async () => {
    setSaving(true)
    try {
      await api.put('/account/preferences', prefs)
      toast.success('Preferences saved')
    } catch {
      toast.error('Failed to save')
    } finally {
      setSaving(false)
    }
  }

  if (!prefs) return <div className="h-32 bg-surface-raised rounded-2xl animate-pulse" />

  const TOGGLES = [
    { key: 'email_scan_digest', label: 'Scan completion email', description: 'Get notified when a scan finishes' },
    { key: 'email_weekly_report', label: 'Weekly storage report', description: 'Storage health summary every Monday' },
    { key: 'email_trial_reminders', label: 'Trial ending reminders', description: '3 days before your trial ends' },
    { key: 'email_product_updates', label: 'Product updates', description: 'New features and improvements' },
  ]

  return (
    <div className="space-y-4">
      <div className="card divide-y divide-surface-border">
        {TOGGLES.map(t => (
          <div key={t.key} className="flex items-center justify-between px-5 py-4">
            <div>
              <p className="font-medium text-sm">{t.label}</p>
              <p className="text-xs text-ink-muted mt-0.5">{t.description}</p>
            </div>
            <button
              onClick={() => setPrefs((p: any) => ({ ...p, [t.key]: !p[t.key] }))}
              className={clsx(
                'w-10 h-6 rounded-full transition-colors relative',
                prefs[t.key] ? 'bg-brand' : 'bg-surface-border'
              )}
            >
              <div className={clsx(
                'w-4 h-4 bg-white rounded-full absolute top-1 transition-all',
                prefs[t.key] ? 'left-5' : 'left-1'
              )} />
            </button>
          </div>
        ))}
      </div>

      <button onClick={handleSave} disabled={saving} className="btn-primary flex items-center gap-2">
        {saving ? <RefreshCw className="w-4 h-4 animate-spin" /> : <CheckCircle2 className="w-4 h-4" />}
        {saving ? 'Saving…' : 'Save Preferences'}
      </button>
    </div>
  )
}

// ── Security Tab ───────────────────────────────────────────────────────────

function SecurityTab() {
  const [current, setCurrent] = useState('')
  const [newPw, setNewPw] = useState('')
  const [confirm, setConfirm] = useState('')
  const [saving, setSaving] = useState(false)

  const handleChange = async () => {
    if (newPw !== confirm) return toast.error('Passwords do not match')
    if (newPw.length < 8) return toast.error('Password must be at least 8 characters')
    setSaving(true)
    try {
      await api.post('/account/password', { current_password: current, new_password: newPw })
      toast.success('Password changed successfully')
      setCurrent(''); setNewPw(''); setConfirm('')
    } catch (err: any) {
      toast.error(err?.response?.data?.detail || 'Failed to change password')
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="space-y-4">
      <div className="card p-5 space-y-4">
        <h3 className="font-semibold">Change Password</h3>
        <input className="input" type="password" placeholder="Current password" value={current} onChange={e => setCurrent(e.target.value)} />
        <input className="input" type="password" placeholder="New password (8+ chars)" value={newPw} onChange={e => setNewPw(e.target.value)} />
        <input className="input" type="password" placeholder="Confirm new password" value={confirm} onChange={e => setConfirm(e.target.value)} />
        <button onClick={handleChange} disabled={saving || !current || !newPw} className="btn-primary flex items-center gap-2">
          {saving ? <RefreshCw className="w-4 h-4 animate-spin" /> : <Lock className="w-4 h-4" />}
          {saving ? 'Saving…' : 'Update Password'}
        </button>
      </div>

      <div className="card p-5">
        <h3 className="font-semibold mb-2">Active Sessions</h3>
        <p className="text-sm text-ink-muted">Session management coming in a future update.</p>
      </div>
    </div>
  )
}

// ── Data & Privacy Tab ─────────────────────────────────────────────────────

function DataPrivacyTab() {
  const { user, logout } = useAuthStore()
  const router = useRouter()
  const [confirmEmail, setConfirmEmail] = useState('')
  const [deleting, setDeleting] = useState(false)
  const [showDeleteForm, setShowDeleteForm] = useState(false)

  const handleExportCsv = () => {
    window.open(`${process.env.NEXT_PUBLIC_API_URL}/export/csv?token=${localStorage.getItem('access_token')}`, '_blank')
  }

  const handleExportGdpr = () => {
    window.open(`${process.env.NEXT_PUBLIC_API_URL}/export/gdpr?token=${localStorage.getItem('access_token')}`, '_blank')
  }

  const handleDelete = async () => {
    if (confirmEmail !== user?.email) return toast.error('Email does not match')
    setDeleting(true)
    try {
      await api.delete('/account', { data: { confirm_email: confirmEmail } })
      await logout()
      router.push('/auth/login')
      toast.success('Account deleted')
    } catch (err: any) {
      toast.error(err?.response?.data?.detail || 'Deletion failed')
      setDeleting(false)
    }
  }

  return (
    <div className="space-y-4">
      {/* Export */}
      <div className="card p-5 space-y-3">
        <h3 className="font-semibold">Export Your Data</h3>
        <p className="text-sm text-ink-muted">Download a copy of your file index and account data.</p>
        <div className="flex gap-2">
          <button onClick={handleExportCsv} className="btn-ghost text-sm">
            Export CSV (file index)
          </button>
          <button onClick={() => window.open(`${process.env.NEXT_PUBLIC_API_URL?.replace('/api/v1', '')}/api/v1/export/excel`, '_blank')} className="btn-ghost text-sm">
            Export Excel
          </button>
          <button onClick={handleExportGdpr} className="btn-ghost text-sm">
            GDPR Export (JSON)
          </button>
        </div>
      </div>

      {/* Delete account */}
      <div className="card p-5 border-accent-red/20 space-y-3">
        <div className="flex items-center gap-2">
          <AlertTriangle className="w-5 h-5 text-accent-red" />
          <h3 className="font-semibold text-accent-red">Delete Account</h3>
        </div>
        <p className="text-sm text-ink-muted">
          Permanently delete your account and all associated data. This cannot be undone.
          Any active subscriptions will be cancelled.
        </p>

        {!showDeleteForm ? (
          <button
            onClick={() => setShowDeleteForm(true)}
            className="text-sm font-semibold text-accent-red border border-accent-red/30 hover:border-accent-red/60 px-4 py-2 rounded-xl transition-colors"
          >
            I want to delete my account
          </button>
        ) : (
          <div className="space-y-3">
            <p className="text-sm text-ink-muted">
              Type <strong className="text-ink">{user?.email}</strong> to confirm:
            </p>
            <input
              className="input border-accent-red/30 focus:border-accent-red/60"
              placeholder="your@email.com"
              value={confirmEmail}
              onChange={e => setConfirmEmail(e.target.value)}
            />
            <div className="flex gap-2">
              <button
                onClick={handleDelete}
                disabled={deleting || confirmEmail !== user?.email}
                className="bg-accent-red/90 hover:bg-accent-red text-white font-semibold px-5 py-2.5 rounded-xl transition-colors disabled:opacity-40 flex items-center gap-2"
              >
                {deleting ? <RefreshCw className="w-4 h-4 animate-spin" /> : <Trash2 className="w-4 h-4" />}
                {deleting ? 'Deleting…' : 'Delete My Account'}
              </button>
              <button onClick={() => { setShowDeleteForm(false); setConfirmEmail('') }} className="btn-ghost">Cancel</button>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
