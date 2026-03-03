'use client'

import { useEffect, useState } from 'react'
import { dashboardApi, connectionsApi, scansApi, formatBytes, DashboardSummary } from '@/lib/api'
import { useAuthStore } from '@/lib/store'
import {
  HardDrive, Trash2, AlertTriangle, CheckCircle2,
  Copy, Files, Zap, RefreshCw, Plus, Cloud, Images, Sparkles
} from 'lucide-react'
import Link from 'next/link'
import toast from 'react-hot-toast'

export default function DashboardPage() {
  const { user } = useAuthStore()
  const [summary, setSummary] = useState<DashboardSummary | null>(null)
  const [connections, setConnections] = useState<any[]>([])
  const [isScanning, setIsScanning] = useState(false)
  const [scanProgress, setScanProgress] = useState(0)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    loadData()
  }, [])

  const loadData = async () => {
    try {
      const [sumRes, connRes] = await Promise.all([
        dashboardApi.summary(),
        connectionsApi.list(),
      ])
      setSummary(sumRes.data)
      setConnections(connRes.data)
    } catch (err) {
      // First time - no data yet
    } finally {
      setLoading(false)
    }
  }

  const handleStartScan = async () => {
    setIsScanning(true)
    setScanProgress(0)
    try {
      // Ensure local connection exists
      let connId: string
      const localConn = connections.find((c) => c.provider === 'local')
      if (localConn) {
        connId = localConn.id
      } else {
        const newConn = await connectionsApi.addLocal()
        connId = newConn.data.id
        setConnections((prev) => [...prev, newConn.data])
      }

      // Start scan job
      const jobRes = await scansApi.start({
        connection_id: connId,
        scan_type: 'full',
        files_total: 100,
      })
      const jobId = jobRes.data.id

      // Demo: simulate ingesting sample files
      const demoFiles = generateDemoManifest()
      const CHUNK_SIZE = 25
      for (let i = 0; i < demoFiles.length; i += CHUNK_SIZE) {
        const chunk = demoFiles.slice(i, i + CHUNK_SIZE)
        const isLast = i + CHUNK_SIZE >= demoFiles.length
        await scansApi.ingestChunk({ job_id: jobId, files: chunk, is_final_chunk: isLast })
        setScanProgress(Math.min(100, ((i + CHUNK_SIZE) / demoFiles.length) * 100))
        await sleep(300)
      }

      toast.success('Scan complete! Duplicates found.')
      await loadData()
    } catch (err: any) {
      toast.error(err?.response?.data?.detail || 'Scan failed')
    } finally {
      setIsScanning(false)
      setScanProgress(0)
    }
  }

  if (loading) {
    return <DashboardSkeleton />
  }

  const hasData = summary && summary.total_files > 0

  return (
    <div className="p-8 space-y-8 animate-fade-in">
      {/* Header */}
      <div className="flex items-start justify-between">
        <div>
          <h1 className="font-display text-3xl font-bold text-ink">
            Good {getTimeOfDay()}, {user?.full_name?.split(' ')[0] || 'there'}.
          </h1>
          <p className="text-ink-muted mt-1">
            {hasData
              ? `${summary.duplicate_groups} duplicate groups detected. ${formatBytes(summary.potential_savings_bytes)} can be freed.`
              : 'Run your first scan to see what can be cleaned up.'}
          </p>
        </div>
        <button
          onClick={handleStartScan}
          disabled={isScanning}
          className="btn-primary flex items-center gap-2"
        >
          {isScanning ? (
            <RefreshCw className="w-4 h-4 animate-spin" />
          ) : (
            <Zap className="w-4 h-4" />
          )}
          {isScanning ? 'Scanning...' : 'Start Scan'}
        </button>
      </div>

      {/* Scan progress bar */}
      {isScanning && (
        <div className="card p-4">
          <div className="flex items-center justify-between mb-2">
            <span className="text-sm text-ink-muted">Scanning files...</span>
            <span className="text-sm font-mono text-brand">{Math.round(scanProgress)}%</span>
          </div>
          <div className="w-full h-2 bg-surface-overlay rounded-full overflow-hidden">
            <div
              className="h-full progress-shimmer rounded-full transition-all duration-300"
              style={{ width: `${scanProgress}%` }}
            />
          </div>
        </div>
      )}

      {/* Stats grid */}
      {hasData && (
        <div className="grid grid-cols-2 xl:grid-cols-4 gap-4">
          <StatCard
            label="Total Files"
            value={summary.total_files.toLocaleString()}
            sub={formatBytes(summary.total_size_bytes)}
            icon={<Files className="w-5 h-5 text-brand" />}
            color="brand"
          />
          <StatCard
            label="Potential Savings"
            value={formatBytes(summary.potential_savings_bytes)}
            sub={`${summary.duplicate_groups} groups`}
            icon={<HardDrive className="w-5 h-5 text-accent-green" />}
            color="green"
            highlight
          />
          <StatCard
            label="Safe to Delete"
            value={formatBytes(summary.low_risk_bytes)}
            sub="Low risk"
            icon={<CheckCircle2 className="w-5 h-5 text-accent-green" />}
            color="green"
          />
          <StatCard
            label="Review Needed"
            value={formatBytes(summary.review_needed_bytes)}
            sub="Higher risk"
            icon={<AlertTriangle className="w-5 h-5 text-accent-amber" />}
            color="amber"
          />
        </div>
      )}

      {/* Empty state */}
      {!hasData && !isScanning && (
        <div className="card p-12 flex flex-col items-center text-center bg-grid">
          <div className="w-20 h-20 rounded-2xl bg-brand/10 border border-brand/20 flex items-center justify-center mb-6">
            <Zap className="w-10 h-10 text-brand" />
          </div>
          <h2 className="font-display text-2xl font-bold mb-2">Ready to declutter?</h2>
          <p className="text-ink-muted max-w-md leading-relaxed mb-8">
            Run a scan to discover duplicate files, free up storage space, and get AI-powered organization suggestions.
          </p>
          <button onClick={handleStartScan} className="btn-primary flex items-center gap-2 text-base px-8 py-3">
            <Zap className="w-5 h-5" /> Run First Scan
          </button>
        </div>
      )}

      {/* Quick actions */}
      {hasData && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <ActionCard
            href="/duplicates"
            icon={<Copy className="w-6 h-6 text-accent-red" />}
            title="Review Duplicates"
            description={`${summary.duplicate_groups} groups found — ${formatBytes(summary.potential_savings_bytes)} wasted`}
            badge="Action needed"
            badgeColor="red"
          />
          <ActionCard
            href="/suggestions"
            icon={<Sparkles className="w-6 h-6 text-accent-green" />}
            title="Smart Suggestions"
            description="AI-powered cleanup recommendations for screenshots, blurry photos & more"
            badge="New"
            badgeColor="green"
          />
          <ActionCard
            href="/files"
            icon={<Files className="w-6 h-6 text-brand" />}
            title="Browse All Files"
            description={`${summary.total_files.toLocaleString()} files indexed across ${summary.storage_connections} connection${summary.storage_connections !== 1 ? 's' : ''}`}
            badge="Browse"
            badgeColor="brand"
          />
        </div>
      )}

      {/* Connections */}
      <div className="card p-6">
        <div className="flex items-center justify-between mb-4">
          <h2 className="font-display font-bold text-lg">Storage Connections</h2>
          <button
            className="btn-ghost text-sm flex items-center gap-1.5"
            onClick={async () => {
              await connectionsApi.addLocal()
              loadData()
              toast.success('Local connection added')
            }}
          >
            <Plus className="w-4 h-4" /> Add Local
          </button>
        </div>

        {connections.length === 0 ? (
          <p className="text-ink-faint text-sm py-4 text-center">No storage connections yet. Add one to start scanning.</p>
        ) : (
          <div className="space-y-2">
            {connections.map((conn) => (
              <ConnectionRow key={conn.id} conn={conn} />
            ))}
          </div>
        )}

        {user?.is_pro && connections.filter(c => c.provider !== 'local').length === 0 && (
          <div className="mt-4 grid grid-cols-2 gap-2">
            <CloudConnectPrompt provider="Google Drive" icon="🗂" href="/settings" />
            <CloudConnectPrompt provider="Dropbox" icon="📦" href="/settings" />
          </div>
        )}
        {!user?.is_pro && (
          <div className="mt-4 p-3 rounded-xl bg-surface-overlay border border-surface-border text-sm text-ink-muted flex items-center gap-3">
            <Cloud className="w-4 h-4 text-brand shrink-0" />
            <span>Google Drive, Dropbox & OneDrive integrations available on <Link href="/settings" className="text-brand hover:underline">Pro plan</Link>.</span>
          </div>
        )}
      </div>

      {/* Similar photos card (Month 2) */}
      {hasData && (
        <ActionCard
          href="/similar"
          icon={<Images className="w-6 h-6 text-brand" />}
          title="Similar Photos"
          description={user?.is_pro ? 'Find near-duplicate and edited photo versions with AI' : 'Upgrade to Pro to detect visually similar photos'}
          badge={user?.is_pro ? 'Pro' : 'Upgrade'}
          badgeColor="brand"
        />
      )}
    </div>
  )
}

function CloudConnectPrompt({ provider, icon, href }: { provider: string; icon: string; href: string }) {
  return (
    <Link href={href} className="flex items-center gap-3 p-3 rounded-xl bg-surface-overlay border border-surface-border hover:border-brand/30 transition-all text-sm">
      <span className="text-lg">{icon}</span>
      <div className="flex-1 min-w-0">
        <p className="text-ink-muted text-xs">Connect</p>
        <p className="font-medium text-ink text-xs truncate">{provider}</p>
      </div>
      <Plus className="w-3.5 h-3.5 text-brand shrink-0" />
    </Link>
  )
}

function StatCard({ label, value, sub, icon, color, highlight = false }: {
  label: string; value: string; sub: string; icon: React.ReactNode; color: string; highlight?: boolean
}) {
  const colorMap: Record<string, string> = {
    brand: 'shadow-glow-brand',
    green: 'shadow-glow-green',
    amber: '',
  }
  return (
    <div className={`stat-card ${highlight ? colorMap[color] : ''}`}>
      <div className="flex items-start justify-between">
        <div className="w-10 h-10 rounded-xl bg-surface-overlay flex items-center justify-center">
          {icon}
        </div>
      </div>
      <div>
        <p className="text-2xl font-display font-bold">{value}</p>
        <p className="text-xs text-ink-muted mt-0.5">{sub}</p>
      </div>
      <p className="text-xs text-ink-faint uppercase tracking-wider font-mono">{label}</p>
    </div>
  )
}

function ActionCard({ href, icon, title, description, badge, badgeColor }: {
  href: string; icon: React.ReactNode; title: string; description: string; badge: string; badgeColor: string
}) {
  const badgeStyle: Record<string, string> = {
    red: 'bg-accent-red/15 text-accent-red border-accent-red/20',
    brand: 'bg-brand/15 text-brand border-brand/20',
    green: 'bg-accent-green/15 text-accent-green border-accent-green/20',
  }
  return (
    <Link href={href} className="card p-5 flex items-center gap-4 hover:border-surface-overlay hover:bg-surface-overlay/50 transition-all group">
      <div className="w-12 h-12 rounded-xl bg-surface-overlay flex items-center justify-center shrink-0 group-hover:scale-110 transition-transform">
        {icon}
      </div>
      <div className="flex-1 min-w-0">
        <p className="font-semibold text-ink">{title}</p>
        <p className="text-sm text-ink-muted mt-0.5 truncate">{description}</p>
      </div>
      <span className={`text-xs px-2.5 py-1 rounded-full border font-medium shrink-0 ${badgeStyle[badgeColor]}`}>
        {badge}
      </span>
    </Link>
  )
}

function ConnectionRow({ conn }: { conn: any }) {
  const providerColors: Record<string, string> = {
    local: 'bg-brand/20 text-brand',
    google_drive: 'bg-accent-green/20 text-accent-green',
    dropbox: 'bg-blue-400/20 text-blue-400',
  }
  return (
    <div className="flex items-center gap-3 p-3 rounded-xl bg-surface-overlay/50">
      <div className={`w-2 h-2 rounded-full ${conn.provider === 'local' ? 'bg-accent-green' : 'bg-ink-faint'}`} />
      <span className={`text-xs font-mono px-2 py-0.5 rounded-full ${providerColors[conn.provider] || 'bg-surface-border text-ink-muted'}`}>
        {conn.provider}
      </span>
      <span className="text-sm text-ink-muted">{conn.account_email || 'Local storage'}</span>
      {conn.last_synced && (
        <span className="ml-auto text-xs text-ink-faint font-mono">
          {new Date(conn.last_synced).toLocaleDateString()}
        </span>
      )}
    </div>
  )
}

function DashboardSkeleton() {
  return (
    <div className="p-8 space-y-8 animate-pulse">
      <div className="h-12 bg-surface-raised rounded-xl w-64" />
      <div className="grid grid-cols-4 gap-4">
        {[...Array(4)].map((_, i) => (
          <div key={i} className="h-36 bg-surface-raised rounded-2xl" />
        ))}
      </div>
      <div className="h-48 bg-surface-raised rounded-2xl" />
    </div>
  )
}

// ── Helpers ───────────────────────────────────────────────────────────────
function getTimeOfDay() {
  const h = new Date().getHours()
  if (h < 12) return 'morning'
  if (h < 17) return 'afternoon'
  return 'evening'
}

function sleep(ms: number) {
  return new Promise((r) => setTimeout(r, ms))
}

function generateDemoManifest() {
  const files = []
  const basePath = '/Users/demo/Documents'
  const names = ['report.pdf', 'invoice.pdf', 'photo.jpg', 'screenshot.png', 'backup.zip', 'presentation.pptx']
  for (let i = 0; i < 100; i++) {
    const name = names[i % names.length]
    const nameWithNum = i < 5 ? name : `${name.split('.')[0]}_${i}.${name.split('.').pop()}`
    files.push({
      file_path: `${basePath}/${nameWithNum}`,
      file_name: nameWithNum,
      file_size: Math.floor(Math.random() * 10_000_000) + 50_000,
      mime_type: name.endsWith('.jpg') ? 'image/jpeg' : name.endsWith('.pdf') ? 'application/pdf' : 'application/octet-stream',
      md5_hash: i < 10 ? `dupe_hash_${Math.floor(i / 2)}` : `unique_${i}`,
      last_modified: new Date(Date.now() - Math.random() * 365 * 24 * 60 * 60 * 1000).toISOString(),
    })
  }
  return files
}
