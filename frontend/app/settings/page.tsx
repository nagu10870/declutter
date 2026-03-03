'use client'

import { useEffect, useState } from 'react'
import { connectionsApi, cloudApi, billingApi, oneDriveApi, formatBytes } from '@/lib/api'
import { useAuthStore } from '@/lib/store'
import { Sidebar } from '@/components/layout/Sidebar'
import { Toaster } from 'react-hot-toast'
import toast from 'react-hot-toast'
import {
  HardDrive, Cloud, RefreshCw, Trash2, CheckCircle2,
  AlertCircle, ExternalLink, Zap, Lock, Plus, CreditCard
} from 'lucide-react'
import clsx from 'clsx'
import { useSearchParams } from 'next/navigation'
import { Suspense } from 'react'

export default function SettingsPage() {
  return (
    <div className="flex h-screen overflow-hidden">
      <Sidebar />
      <main className="flex-1 overflow-y-auto bg-surface">
        <Suspense fallback={null}>
          <SettingsContent />
        </Suspense>
      </main>
      <Toaster position="bottom-right" toastOptions={{
        style: { background: '#13161e', color: '#f0f2ff', border: '1px solid #252a38' },
        success: { iconTheme: { primary: '#1de9a4', secondary: '#0d0f14' } },
      }} />
    </div>
  )
}

function SettingsContent() {
  const { user } = useAuthStore()
  const [connections, setConnections] = useState<any[]>([])
  const [loading, setLoading] = useState(true)
  const [syncing, setSyncing] = useState<Set<string>>(new Set())
  const [connectingProvider, setConnectingProvider] = useState<string | null>(null)
  const [billingStatus, setBillingStatus] = useState<any>(null)
  const [checkoutLoading, setCheckoutLoading] = useState<string | null>(null)
  const searchParams = useSearchParams()

  // Handle OAuth callback redirect: ?connected=google&job=xxx
  useEffect(() => {
    const connected = searchParams.get('connected')
    if (connected) {
      toast.success(`${capitalize(connected)} connected! Indexing your files in the background.`)
    }
    const billing = searchParams.get('billing')
    if (billing === 'success') toast.success('🎉 Pro plan activated! Welcome to the Pro experience.')
    if (billing === 'cancelled') toast.error('Checkout cancelled. You can upgrade anytime.')
    loadConnections()
    billingApi.status().then(r => setBillingStatus(r.data)).catch(() => {})
  }, [])

  const loadConnections = async () => {
    setLoading(true)
    try {
      const res = await connectionsApi.list()
      setConnections(res.data)
    } finally {
      setLoading(false)
    }
  }

  const handleConnectGoogle = async () => {
    if (!user?.is_pro) {
      toast.error('Google Drive requires Pro plan')
      return
    }
    setConnectingProvider('google')
    try {
      const res = await cloudApi.googleAuthorize()
      window.location.href = res.data.url
    } catch (err: any) {
      toast.error(err?.response?.data?.detail || 'Failed to initiate Google auth')
      setConnectingProvider(null)
    }
  }

  const handleConnectDropbox = async () => {
    if (!user?.is_pro) {
      toast.error('Dropbox requires Pro plan')
      return
    }
    setConnectingProvider('dropbox')
    try {
      const res = await cloudApi.dropboxAuthorize()
      window.location.href = res.data.url
    } catch (err: any) {
      toast.error(err?.response?.data?.detail || 'Failed to initiate Dropbox auth')
      setConnectingProvider(null)
    }
  }

  const handleSync = async (connId: string) => {
    setSyncing(prev => new Set(prev).add(connId))
    try {
      await connectionsApi.sync(connId)
      toast.success('Re-sync started. Files will update in the background.')
      await loadConnections()
    } catch (err: any) {
      toast.error(err?.response?.data?.detail || 'Sync failed')
    } finally {
      setSyncing(prev => { const n = new Set(prev); n.delete(connId); return n })
    }
  }

  const handleDisconnect = async (connId: string, provider: string) => {
    if (!confirm(`Disconnect ${provider}? Your indexed files will be removed.`)) return
    try {
      await connectionsApi.delete(connId)
      setConnections(prev => prev.filter(c => c.id !== connId))
      toast.success(`${capitalize(provider)} disconnected`)
    } catch {
      toast.error('Failed to disconnect')
    }
  }

  const handleConnectOneDrive = async () => {
    if (!user?.is_pro) { toast.error('OneDrive requires Pro plan'); return }
    setConnectingProvider('onedrive')
    try {
      const res = await oneDriveApi.authorize()
      window.location.href = res.data.url
    } catch (err: any) {
      toast.error(err?.response?.data?.detail || 'Failed to initiate OneDrive auth')
      setConnectingProvider(null)
    }
  }

  const handleCheckout = async (plan: 'monthly' | 'yearly') => {
    setCheckoutLoading(plan)
    try {
      const res = await billingApi.checkout(plan)
      window.location.href = res.data.url
    } catch (err: any) {
      toast.error(err?.response?.data?.detail || 'Checkout failed')
      setCheckoutLoading(null)
    }
  }

  const handlePortal = async () => {
    try {
      const res = await billingApi.portal()
      window.location.href = res.data.url
    } catch (err: any) {
      toast.error(err?.response?.data?.detail || 'Could not open billing portal')
    }
  }

  const localConn = connections.find(c => c.provider === 'local')
  const cloudConns = connections.filter(c => c.provider !== 'local')
  const googleConn = cloudConns.find(c => c.provider === 'google_drive')
  const dropboxConn = cloudConns.find(c => c.provider === 'dropbox')
  const onedriveConn = cloudConns.find(c => c.provider === 'onedrive')

  return (
    <div className="p-8 space-y-8 animate-fade-in max-w-3xl">
      <div>
        <h1 className="font-display text-3xl font-bold">Settings</h1>
        <p className="text-ink-muted mt-1">Manage your storage connections and account</p>
      </div>

      {/* Plan badge */}
      <div className="card p-5 flex items-center justify-between">
        <div className="flex items-center gap-4">
          <div className="w-10 h-10 rounded-xl bg-brand/15 flex items-center justify-center">
            <Zap className="w-5 h-5 text-brand" />
          </div>
          <div>
            <p className="font-semibold capitalize">{user?.tier} Plan</p>
            <p className="text-xs text-ink-muted mt-0.5">
              {user?.tier === 'free'
                ? 'Local scanning, basic deduplication'
                : 'All features including AI similarity & cloud sync'}
            </p>
          </div>
        </div>
        {user?.tier === 'free' && (
          <div className="text-right">
            <p className="text-2xl font-display font-bold text-brand">$7.99<span className="text-sm font-normal text-ink-muted">/mo</span></p>
            <button className="btn-primary mt-2 text-sm px-5 py-2">Upgrade to Pro</button>
          </div>
        )}
        {user?.tier !== 'free' && (
          <span className="text-xs font-mono bg-accent-green/15 text-accent-green border border-accent-green/20 px-3 py-1.5 rounded-full">Active</span>
        )}
      </div>

      {/* Local storage */}
      <section className="space-y-3">
        <h2 className="font-display font-bold text-lg">Local Storage</h2>
        {localConn ? (
          <ConnectionCard
            conn={localConn}
            onSync={() => {}}
            onDisconnect={() => handleDisconnect(localConn.id, 'local')}
            isSyncing={false}
            showSync={false}
          />
        ) : (
          <button
            onClick={async () => {
              await connectionsApi.addLocal()
              loadConnections()
              toast.success('Local connection added')
            }}
            className="card p-4 w-full flex items-center gap-3 hover:bg-surface-overlay/50 transition-colors text-left"
          >
            <Plus className="w-5 h-5 text-brand" />
            <span className="text-sm text-ink-muted">Add local storage connection</span>
          </button>
        )}
      </section>

      {/* Cloud connections */}
      <section className="space-y-3">
        <div className="flex items-center justify-between">
          <h2 className="font-display font-bold text-lg">Cloud Storage</h2>
          {!user?.is_pro && (
            <span className="text-xs font-mono bg-brand/10 text-brand border border-brand/20 px-2 py-1 rounded-full flex items-center gap-1">
              <Lock className="w-3 h-3" /> Pro only
            </span>
          )}
        </div>

        {/* Google Drive */}
        {googleConn ? (
          <ConnectionCard
            conn={googleConn}
            onSync={() => handleSync(googleConn.id)}
            onDisconnect={() => handleDisconnect(googleConn.id, 'Google Drive')}
            isSyncing={syncing.has(googleConn.id)}
          />
        ) : (
          <CloudConnectButton
            provider="google"
            label="Google Drive"
            description="Index Google Drive files (metadata only)"
            icon="🗂"
            isPro={!!user?.is_pro}
            isConnecting={connectingProvider === 'google'}
            onConnect={handleConnectGoogle}
          />
        )}

        {/* Dropbox */}
        {dropboxConn ? (
          <ConnectionCard
            conn={dropboxConn}
            onSync={() => handleSync(dropboxConn.id)}
            onDisconnect={() => handleDisconnect(dropboxConn.id, 'Dropbox')}
            isSyncing={syncing.has(dropboxConn.id)}
          />
        ) : (
          <CloudConnectButton
            provider="dropbox"
            label="Dropbox"
            description="Index Dropbox files and find duplicates"
            icon="📦"
            isPro={!!user?.is_pro}
            isConnecting={connectingProvider === 'dropbox'}
            onConnect={handleConnectDropbox}
          />
        )}

        {/* OneDrive — Month 3 */}
        {onedriveConn ? (
          <ConnectionCard
            conn={onedriveConn}
            onSync={() => handleSync(onedriveConn.id)}
            onDisconnect={() => handleDisconnect(onedriveConn.id, 'OneDrive')}
            isSyncing={syncing.has(onedriveConn.id)}
          />
        ) : (
          <CloudConnectButton
            provider="onedrive"
            label="OneDrive"
            description="Index Microsoft OneDrive files (metadata only)"
            icon="☁️"
            isPro={!!user?.is_pro}
            isConnecting={connectingProvider === 'onedrive'}
            onConnect={handleConnectOneDrive}
          />
        )}

        {/* Privacy notice */}
        <div className="card p-4 bg-surface-overlay/50 text-xs text-ink-muted space-y-1.5">
          <p className="flex items-center gap-2 text-ink font-medium">
            <CheckCircle2 className="w-4 h-4 text-accent-green" /> Privacy-first cloud scanning
          </p>
          <p>We request read-only access and only process file metadata (names, sizes, hashes). <strong className="text-ink">We never download your file contents.</strong></p>
          <p>OAuth tokens are encrypted at rest. You can revoke access from your Google/Dropbox settings at any time.</p>
        </div>
      </section>

      {/* Billing — Month 3 */}
      <section className="space-y-3">
        <h2 className="font-display font-bold text-lg">Billing</h2>

        {user?.tier === 'free' ? (
          <div className="card p-6 space-y-5">
            {/* Pricing toggle */}
            <div className="flex items-start justify-between">
              <div>
                <h3 className="font-semibold text-lg">Upgrade to Pro</h3>
                <p className="text-sm text-ink-muted mt-1">
                  14-day free trial · Cancel anytime
                </p>
              </div>
            </div>

            {/* Feature list */}
            <div className="grid grid-cols-2 gap-2 text-sm text-ink-muted">
              {[
                'Google Drive + Dropbox + OneDrive',
                'AI visual similarity detection',
                'Smart cleanup suggestions',
                'Blur & screenshot detection',
                'Unlimited scan jobs',
                'Priority support',
              ].map(f => (
                <div key={f} className="flex items-center gap-2">
                  <CheckCircle2 className="w-3.5 h-3.5 text-accent-green shrink-0" />
                  <span>{f}</span>
                </div>
              ))}
            </div>

            {/* Pricing cards */}
            <div className="grid grid-cols-2 gap-3">
              <div className="card p-4 border-surface-border hover:border-brand/30 transition-colors">
                <p className="text-xs text-ink-faint font-mono uppercase mb-2">Monthly</p>
                <p className="text-2xl font-display font-bold">$7.99<span className="text-sm font-normal text-ink-muted">/mo</span></p>
                <button
                  onClick={() => handleCheckout('monthly')}
                  disabled={checkoutLoading === 'monthly'}
                  className="btn-primary w-full mt-4 text-sm flex items-center justify-center gap-2"
                >
                  {checkoutLoading === 'monthly' ? <RefreshCw className="w-4 h-4 animate-spin" /> : <CreditCard className="w-4 h-4" />}
                  Start Free Trial
                </button>
              </div>

              <div className="card p-4 glow-border relative">
                <span className="absolute -top-2.5 right-4 text-[10px] font-mono bg-accent-green text-surface px-2 py-0.5 rounded-full">SAVE 25%</span>
                <p className="text-xs text-ink-faint font-mono uppercase mb-2">Yearly</p>
                <p className="text-2xl font-display font-bold text-accent-green">$5.99<span className="text-sm font-normal text-ink-muted">/mo</span></p>
                <p className="text-xs text-ink-faint">$71.88 billed annually</p>
                <button
                  onClick={() => handleCheckout('yearly')}
                  disabled={checkoutLoading === 'yearly'}
                  className="btn-primary w-full mt-3 text-sm flex items-center justify-center gap-2"
                >
                  {checkoutLoading === 'yearly' ? <RefreshCw className="w-4 h-4 animate-spin" /> : <CreditCard className="w-4 h-4" />}
                  Start Free Trial
                </button>
              </div>
            </div>
          </div>
        ) : (
          <div className="card p-5 flex items-center justify-between">
            <div className="flex items-center gap-4">
              <div className="w-10 h-10 rounded-xl bg-accent-green/10 flex items-center justify-center">
                <CheckCircle2 className="w-5 h-5 text-accent-green" />
              </div>
              <div>
                <p className="font-semibold">Pro Plan Active</p>
                {billingStatus?.subscriptions?.[0]?.current_period_end && (
                  <p className="text-xs text-ink-muted mt-0.5">
                    Renews {new Date(billingStatus.subscriptions[0].current_period_end * 1000).toLocaleDateString()}
                    {billingStatus.subscriptions[0].cancel_at_period_end && ' · Cancels at end of period'}
                  </p>
                )}
                {billingStatus?.subscriptions?.[0]?.trial_end && billingStatus.subscriptions[0].status === 'trialing' && (
                  <p className="text-xs text-accent-amber mt-0.5">
                    Trial ends {new Date(billingStatus.subscriptions[0].trial_end * 1000).toLocaleDateString()}
                  </p>
                )}
              </div>
            </div>
            <button onClick={handlePortal} className="btn-ghost text-sm flex items-center gap-2">
              <ExternalLink className="w-4 h-4" /> Manage Billing
            </button>
          </div>
        )}
      </section>

      {/* Danger zone */}
      <section className="space-y-3">
        <h2 className="font-display font-bold text-lg text-accent-red">Danger Zone</h2>
        <div className="card p-5 border-accent-red/20 space-y-3">
          <div className="flex items-start justify-between">
            <div>
              <p className="font-medium text-sm">Delete all indexed data</p>
              <p className="text-xs text-ink-muted mt-0.5">Remove all file records from our database. Does not delete actual files.</p>
            </div>
            <button className="text-xs font-semibold text-accent-red hover:text-red-400 border border-accent-red/30 hover:border-accent-red/60 px-3 py-1.5 rounded-xl transition-colors">
              Clear Index
            </button>
          </div>
          <div className="border-t border-surface-border pt-3 flex items-start justify-between">
            <div>
              <p className="font-medium text-sm">Delete account</p>
              <p className="text-xs text-ink-muted mt-0.5">Permanently delete your account and all associated data.</p>
            </div>
            <button className="text-xs font-semibold text-accent-red hover:text-red-400 border border-accent-red/30 hover:border-accent-red/60 px-3 py-1.5 rounded-xl transition-colors">
              Delete Account
            </button>
          </div>
        </div>
      </section>
    </div>
  )
}

// ── Connection Card ────────────────────────────────────────────────────────

function ConnectionCard({
  conn, onSync, onDisconnect, isSyncing, showSync = true
}: {
  conn: any
  onSync: () => void
  onDisconnect: () => void
  isSyncing: boolean
  showSync?: boolean
}) {
  const providerLabel: Record<string, string> = {
    local: 'Local Storage',
    google_drive: 'Google Drive',
    dropbox: 'Dropbox',
    onedrive: 'OneDrive',
  }
  const providerIcon: Record<string, string> = {
    local: '💻', google_drive: '🗂', dropbox: '📦', onedrive: '☁️'
  }

  return (
    <div className="card p-4 flex items-center gap-4">
      <div className="w-10 h-10 rounded-xl bg-accent-green/10 flex items-center justify-center text-xl shrink-0">
        {providerIcon[conn.provider] || '📁'}
      </div>
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2">
          <p className="font-medium text-sm">{providerLabel[conn.provider] || conn.provider}</p>
          <span className="w-1.5 h-1.5 rounded-full bg-accent-green" title="Connected" />
        </div>
        <p className="text-xs text-ink-muted mt-0.5">
          {conn.account_email || 'Local filesystem'}
          {conn.last_synced && ` · Last synced ${new Date(conn.last_synced).toLocaleDateString()}`}
        </p>
        {conn.used_bytes && conn.total_bytes && (
          <div className="mt-2">
            <div className="flex items-center justify-between text-[10px] text-ink-faint mb-1">
              <span>{formatBytes(conn.used_bytes)} used</span>
              <span>{formatBytes(conn.total_bytes)} total</span>
            </div>
            <div className="w-full h-1.5 bg-surface-overlay rounded-full overflow-hidden">
              <div
                className="h-full bg-brand rounded-full"
                style={{ width: `${Math.min(100, (conn.used_bytes / conn.total_bytes) * 100)}%` }}
              />
            </div>
          </div>
        )}
      </div>
      <div className="flex items-center gap-2 shrink-0">
        {showSync && (
          <button
            onClick={onSync}
            disabled={isSyncing}
            className="btn-ghost p-2 text-ink-muted disabled:opacity-40"
            title="Re-sync"
          >
            <RefreshCw className={clsx('w-4 h-4', isSyncing && 'animate-spin')} />
          </button>
        )}
        <button
          onClick={onDisconnect}
          className="btn-ghost p-2 text-ink-faint hover:text-accent-red"
          title="Disconnect"
        >
          <Trash2 className="w-4 h-4" />
        </button>
      </div>
    </div>
  )
}

function CloudConnectButton({
  provider, label, description, icon, isPro, isConnecting, onConnect
}: {
  provider: string; label: string; description: string; icon: string
  isPro: boolean; isConnecting: boolean; onConnect: () => void
}) {
  return (
    <button
      onClick={onConnect}
      disabled={!isPro || isConnecting}
      className={clsx(
        'card w-full p-4 flex items-center gap-4 transition-all text-left',
        isPro
          ? 'hover:bg-surface-overlay/50 hover:border-brand/30 cursor-pointer'
          : 'opacity-60 cursor-not-allowed'
      )}
    >
      <div className="w-10 h-10 rounded-xl bg-surface-overlay flex items-center justify-center text-xl shrink-0">
        {icon}
      </div>
      <div className="flex-1">
        <p className="font-medium text-sm flex items-center gap-2">
          {label}
          {!isPro && <Lock className="w-3 h-3 text-ink-faint" />}
        </p>
        <p className="text-xs text-ink-muted">{description}</p>
      </div>
      {isConnecting ? (
        <RefreshCw className="w-4 h-4 text-brand animate-spin shrink-0" />
      ) : isPro ? (
        <span className="text-xs font-medium text-brand shrink-0 flex items-center gap-1">
          Connect <ExternalLink className="w-3 h-3" />
        </span>
      ) : (
        <span className="text-xs text-ink-faint shrink-0">Pro</span>
      )}
    </button>
  )
}

function capitalize(s: string) {
  return s ? s.charAt(0).toUpperCase() + s.slice(1) : s
}
