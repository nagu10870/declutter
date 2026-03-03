'use client'

import { useEffect, useState, useCallback } from 'react'
import { similarApi, formatBytes, formatDate, SimilarGroup, SimilarFile } from '@/lib/api'
import { useAuthStore } from '@/lib/store'
import { Sidebar } from '@/components/layout/Sidebar'
import {
  Images, Trash2, RefreshCw, Shield, Lock,
  ChevronLeft, ChevronRight, ZoomIn, Check, X
} from 'lucide-react'
import { Toaster } from 'react-hot-toast'
import toast from 'react-hot-toast'
import clsx from 'clsx'
import Link from 'next/link'

export default function SimilarPage() {
  return (
    <div className="flex h-screen overflow-hidden">
      <Sidebar />
      <main className="flex-1 overflow-y-auto bg-surface">
        <SimilarContent />
      </main>
      <Toaster position="bottom-right" toastOptions={{
        style: { background: '#13161e', color: '#f0f2ff', border: '1px solid #252a38' },
        success: { iconTheme: { primary: '#1de9a4', secondary: '#0d0f14' } },
      }} />
    </div>
  )
}

function SimilarContent() {
  const { user } = useAuthStore()
  const [groups, setGroups] = useState<SimilarGroup[]>([])
  const [stats, setStats] = useState<any>(null)
  const [loading, setLoading] = useState(true)
  const [threshold, setThreshold] = useState(10)
  const [page, setPage] = useState(1)
  const [totalGroups, setTotalGroups] = useState(0)
  const [deleted, setDeleted] = useState<Set<string>>(new Set())
  const [selectedGroup, setSelectedGroup] = useState<SimilarGroup | null>(null)
  const [isDeleting, setIsDeleting] = useState<Set<string>>(new Set())

  const PAGE_SIZE = 8

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const [groupRes, statsRes] = await Promise.all([
        similarApi.listGroups({ threshold, page, page_size: PAGE_SIZE }),
        similarApi.stats(),
      ])
      setGroups(groupRes.data.groups || [])
      setTotalGroups(groupRes.data.total_groups || 0)
      setStats(statsRes.data)
    } catch (err: any) {
      if (err?.response?.status !== 403) {
        toast.error('Failed to load similar images')
      }
    } finally {
      setLoading(false)
    }
  }, [threshold, page])

  useEffect(() => {
    if (user?.tier !== 'free') load()
    else setLoading(false)
  }, [user, load])

  const handleDelete = async (fileId: string, fileSize: number) => {
    setIsDeleting(prev => new Set(prev).add(fileId))
    try {
      await similarApi.deleteFile(fileId)
      setDeleted(prev => new Set(prev).add(fileId))
      toast.success(`${formatBytes(fileSize)} freed`)
      // Refresh after deletion
      await load()
    } catch (err: any) {
      toast.error(err?.response?.data?.detail || 'Delete failed')
    } finally {
      setIsDeleting(prev => { const n = new Set(prev); n.delete(fileId); return n })
    }
  }

  // Pro gate
  if (user?.tier === 'free') {
    return <ProGate />
  }

  const totalPages = Math.ceil(totalGroups / PAGE_SIZE)
  const totalWasted = groups.reduce((s, g) => s + g.wasted_bytes, 0)

  return (
    <div className="p-8 space-y-6 animate-fade-in">
      {/* Header */}
      <div className="flex items-start justify-between">
        <div>
          <h1 className="font-display text-3xl font-bold">Similar Photos</h1>
          <p className="text-ink-muted mt-1">
            {stats
              ? `${stats.similar_groups} groups · ${formatBytes(stats.wasted_bytes)} recoverable`
              : 'Finding visually similar images using perceptual hashing…'}
          </p>
        </div>
        <div className="flex items-center gap-3">
          {/* Threshold slider */}
          <div className="flex items-center gap-3 card px-4 py-2.5">
            <span className="text-xs text-ink-muted whitespace-nowrap">Sensitivity</span>
            <input
              type="range" min={3} max={20} value={threshold}
              onChange={e => { setThreshold(+e.target.value); setPage(1) }}
              className="w-24 accent-brand"
            />
            <span className="text-xs font-mono text-brand w-4">{threshold}</span>
          </div>
          <button onClick={load} className="btn-ghost flex items-center gap-1.5 text-sm">
            <RefreshCw className="w-4 h-4" /> Refresh
          </button>
        </div>
      </div>

      {/* Stats bar */}
      {stats && (
        <div className="grid grid-cols-3 gap-4">
          <StatPill label="Total Images" value={stats.total_images?.toLocaleString() ?? '—'} />
          <StatPill label="With Perceptual Hash" value={stats.images_with_phash?.toLocaleString() ?? '—'} />
          <StatPill label="Space to Recover" value={formatBytes(stats.wasted_bytes || 0)} highlight />
        </div>
      )}

      {/* Threshold info */}
      <div className="card p-3 flex items-center gap-3 text-xs text-ink-muted">
        <div className="flex gap-2">
          <ThresholdTag label="Identical" range="0–2" color="green" />
          <ThresholdTag label="Near-identical" range="3–5" color="brand" />
          <ThresholdTag label="Visually similar" range="6–12" color="amber" />
          <ThresholdTag label="Loosely related" range="13+" color="red" />
        </div>
        <span className="ml-auto">
          Current threshold: <span className="text-brand font-mono">{threshold}</span>
          {' '}— {threshold <= 5 ? 'showing near-exact duplicates' : threshold <= 12 ? 'showing edited versions too' : 'showing loosely related images'}
        </span>
      </div>

      {/* Loading */}
      {loading && (
        <div className="grid grid-cols-2 gap-4">
          {[...Array(4)].map((_, i) => (
            <div key={i} className="h-64 bg-surface-raised rounded-2xl animate-pulse" />
          ))}
        </div>
      )}

      {/* Groups grid */}
      {!loading && groups.length > 0 && (
        <div className="space-y-4">
          {groups.map((group, gi) => (
            <SimilarGroupCard
              key={gi}
              group={group}
              deleted={deleted}
              isDeleting={isDeleting}
              onDelete={handleDelete}
              onExpand={() => setSelectedGroup(group)}
            />
          ))}
        </div>
      )}

      {/* Empty */}
      {!loading && groups.length === 0 && (
        <div className="card p-12 text-center">
          <div className="w-16 h-16 rounded-2xl bg-accent-green/10 flex items-center justify-center mx-auto mb-4">
            <Images className="w-8 h-8 text-accent-green" />
          </div>
          <p className="font-display text-xl font-bold mb-2">No similar images found</p>
          <p className="text-ink-muted">Try increasing the sensitivity slider to find more matches.</p>
        </div>
      )}

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="flex items-center justify-center gap-3">
          <button
            onClick={() => setPage(p => Math.max(1, p - 1))}
            disabled={page === 1}
            className="btn-ghost p-2 disabled:opacity-30"
          >
            <ChevronLeft className="w-4 h-4" />
          </button>
          <span className="text-sm text-ink-muted font-mono">
            {page} / {totalPages}
          </span>
          <button
            onClick={() => setPage(p => Math.min(totalPages, p + 1))}
            disabled={page === totalPages}
            className="btn-ghost p-2 disabled:opacity-30"
          >
            <ChevronRight className="w-4 h-4" />
          </button>
        </div>
      )}

      {/* Comparison modal */}
      {selectedGroup && (
        <ComparisonModal
          group={selectedGroup}
          deleted={deleted}
          isDeleting={isDeleting}
          onDelete={handleDelete}
          onClose={() => setSelectedGroup(null)}
        />
      )}
    </div>
  )
}

// ── Similar Group Card ─────────────────────────────────────────────────────

function SimilarGroupCard({
  group, deleted, isDeleting, onDelete, onExpand
}: {
  group: SimilarGroup
  deleted: Set<string>
  isDeleting: Set<string>
  onDelete: (id: string, size: number) => void
  onExpand: () => void
}) {
  const [keepId, setKeepId] = useState(group.files[0]?.id)
  const liveFiles = group.files.filter(f => !deleted.has(f.id))
  const similarityPct = Math.round(group.similarity * 100)

  return (
    <div className="card overflow-hidden">
      {/* Group header */}
      <div className="px-5 py-3.5 border-b border-surface-border flex items-center justify-between">
        <div className="flex items-center gap-3">
          <SimilarityBadge similarity={group.similarity} />
          <span className="text-sm text-ink-muted">
            {liveFiles.length} photos · {formatBytes(group.wasted_bytes)} recoverable
          </span>
        </div>
        <button
          onClick={onExpand}
          className="btn-ghost text-xs flex items-center gap-1.5"
        >
          <ZoomIn className="w-3.5 h-3.5" /> Compare
        </button>
      </div>

      {/* Photo strip */}
      <div className="p-4 flex gap-3 overflow-x-auto">
        {liveFiles.map((file) => {
          const isKeep = file.id === keepId
          return (
            <div
              key={file.id}
              className={clsx(
                'relative shrink-0 rounded-xl overflow-hidden border-2 transition-all cursor-pointer group',
                isKeep ? 'border-accent-green shadow-glow-green' : 'border-surface-border hover:border-brand/40'
              )}
              style={{ width: 160, height: 160 }}
              onClick={() => setKeepId(file.id)}
            >
              <ThumbnailImage file={file} />
              {/* Overlay actions */}
              <div className="absolute inset-0 bg-surface/70 opacity-0 group-hover:opacity-100 transition-opacity flex flex-col items-center justify-center gap-2">
                {!isKeep && (
                  <>
                    <button
                      onClick={(e) => { e.stopPropagation(); setKeepId(file.id) }}
                      className="text-xs bg-accent-green/90 text-surface font-semibold px-3 py-1.5 rounded-full flex items-center gap-1"
                    >
                      <Check className="w-3 h-3" /> Keep
                    </button>
                    <button
                      onClick={(e) => { e.stopPropagation(); onDelete(file.id, file.file_size) }}
                      disabled={isDeleting.has(file.id)}
                      className="text-xs bg-accent-red/90 text-white font-semibold px-3 py-1.5 rounded-full flex items-center gap-1 disabled:opacity-50"
                    >
                      {isDeleting.has(file.id)
                        ? <RefreshCw className="w-3 h-3 animate-spin" />
                        : <Trash2 className="w-3 h-3" />}
                      Delete
                    </button>
                  </>
                )}
              </div>
              {/* Keep badge */}
              {isKeep && (
                <div className="absolute top-2 left-2 bg-accent-green text-surface text-[10px] font-bold px-2 py-0.5 rounded-full">
                  KEEP
                </div>
              )}
              {/* File size */}
              <div className="absolute bottom-0 left-0 right-0 bg-surface/80 backdrop-blur-sm px-2 py-1">
                <p className="text-[10px] font-mono text-ink-muted truncate">{file.file_name}</p>
                <p className="text-[10px] font-mono text-ink-faint">{formatBytes(file.file_size)}</p>
              </div>
            </div>
          )
        })}
      </div>

      {/* Footer action */}
      {liveFiles.length > 1 && (
        <div className="px-4 pb-4 flex items-center justify-between">
          <p className="text-xs text-ink-faint">
            Select which to keep, then delete the rest
          </p>
          <button
            onClick={() => {
              liveFiles.filter(f => f.id !== keepId).forEach(f => onDelete(f.id, f.file_size))
            }}
            className="text-xs font-semibold text-accent-red hover:text-red-400 flex items-center gap-1.5"
          >
            <Trash2 className="w-3.5 h-3.5" />
            Delete {liveFiles.length - 1} duplicate{liveFiles.length - 1 !== 1 ? 's' : ''}
          </button>
        </div>
      )}
    </div>
  )
}

// ── Comparison Modal ───────────────────────────────────────────────────────

function ComparisonModal({
  group, deleted, isDeleting, onDelete, onClose
}: {
  group: SimilarGroup
  deleted: Set<string>
  isDeleting: Set<string>
  onDelete: (id: string, size: number) => void
  onClose: () => void
}) {
  const [idx, setIdx] = useState(0)
  const liveFiles = group.files.filter(f => !deleted.has(f.id))
  const file = liveFiles[idx]
  if (!file) return null

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-surface/90 backdrop-blur-sm">
      <div className="card w-full max-w-3xl mx-4 overflow-hidden shadow-card">
        {/* Header */}
        <div className="flex items-center justify-between px-5 py-4 border-b border-surface-border">
          <div>
            <h3 className="font-display font-bold">Compare Similar Photos</h3>
            <p className="text-xs text-ink-muted mt-0.5">
              {liveFiles.length} photos · {formatBytes(group.wasted_bytes)} recoverable
            </p>
          </div>
          <button onClick={onClose} className="btn-ghost p-2">
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Main image */}
        <div className="p-5 grid grid-cols-2 gap-4">
          {/* Current file */}
          <div className="space-y-3">
            <div className="aspect-square rounded-xl overflow-hidden bg-surface-overlay relative">
              <ThumbnailImage file={file} large />
            </div>
            <div className="card p-3 text-xs space-y-1">
              <p className="font-medium text-ink truncate">{file.file_name}</p>
              <p className="text-ink-faint font-mono truncate">{file.file_path}</p>
              <p className="text-ink-muted">{formatBytes(file.file_size)} · {formatDate(file.last_modified)}</p>
            </div>
          </div>

          {/* Thumbnail strip of all files */}
          <div className="flex flex-col gap-3">
            <p className="text-xs text-ink-faint uppercase tracking-wider font-mono">All in group</p>
            <div className="space-y-2 overflow-y-auto max-h-[360px] pr-1">
              {liveFiles.map((f, i) => (
                <button
                  key={f.id}
                  onClick={() => setIdx(i)}
                  className={clsx(
                    'w-full flex items-center gap-3 p-2.5 rounded-xl transition-all text-left',
                    i === idx ? 'bg-brand/15 border border-brand/30' : 'hover:bg-surface-overlay border border-transparent'
                  )}
                >
                  <div className="w-10 h-10 rounded-lg overflow-hidden shrink-0 bg-surface-overlay">
                    <ThumbnailImage file={f} />
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className="text-xs font-medium text-ink truncate">{f.file_name}</p>
                    <p className="text-[10px] text-ink-faint">{formatBytes(f.file_size)}</p>
                  </div>
                  {i === idx && <div className="w-1.5 h-1.5 rounded-full bg-brand shrink-0" />}
                </button>
              ))}
            </div>
          </div>
        </div>

        {/* Actions */}
        <div className="px-5 pb-5 flex items-center justify-between">
          <div className="flex gap-2">
            <button onClick={() => setIdx(i => Math.max(0, i - 1))} disabled={idx === 0} className="btn-ghost p-2 disabled:opacity-30">
              <ChevronLeft className="w-4 h-4" />
            </button>
            <span className="text-xs text-ink-faint self-center font-mono">{idx + 1}/{liveFiles.length}</span>
            <button onClick={() => setIdx(i => Math.min(liveFiles.length - 1, i + 1))} disabled={idx === liveFiles.length - 1} className="btn-ghost p-2 disabled:opacity-30">
              <ChevronRight className="w-4 h-4" />
            </button>
          </div>
          <div className="flex gap-2">
            <button
              onClick={() => onDelete(file.id, file.file_size)}
              disabled={isDeleting.has(file.id)}
              className="flex items-center gap-2 px-4 py-2 rounded-xl bg-accent-red/15 text-accent-red border border-accent-red/20 text-sm font-medium hover:bg-accent-red/25 transition-colors disabled:opacity-40"
            >
              {isDeleting.has(file.id) ? <RefreshCw className="w-4 h-4 animate-spin" /> : <Trash2 className="w-4 h-4" />}
              Delete this one
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}

// ── Sub-components ─────────────────────────────────────────────────────────

function ThumbnailImage({ file, large }: { file: SimilarFile; large?: boolean }) {
  const [errored, setErrored] = useState(false)

  if (file.thumbnail_url && !errored) {
    return (
      <img
        src={file.thumbnail_url}
        alt={file.file_name}
        onError={() => setErrored(true)}
        className={clsx('w-full h-full object-cover', large ? 'aspect-square' : '')}
      />
    )
  }

  // Fallback: file extension icon
  const ext = file.file_name.split('.').pop()?.toLowerCase() || ''
  return (
    <div className="w-full h-full flex flex-col items-center justify-center bg-surface-overlay text-ink-faint gap-1">
      <Images className="w-6 h-6" />
      <span className="text-[10px] font-mono uppercase">{ext}</span>
    </div>
  )
}

function SimilarityBadge({ similarity }: { similarity: number }) {
  const pct = Math.round(similarity * 100)
  if (pct >= 98) return <span className="text-xs font-mono px-2 py-0.5 rounded-full bg-accent-green/15 text-accent-green border border-accent-green/20">~identical</span>
  if (pct >= 90) return <span className="text-xs font-mono px-2 py-0.5 rounded-full bg-brand/15 text-brand border border-brand/20">{pct}% similar</span>
  return <span className="text-xs font-mono px-2 py-0.5 rounded-full bg-accent-amber/15 text-accent-amber border border-accent-amber/20">{pct}% similar</span>
}

function StatPill({ label, value, highlight }: { label: string; value: string; highlight?: boolean }) {
  return (
    <div className={clsx('card p-4', highlight && 'glow-border')}>
      <p className={clsx('text-xl font-display font-bold', highlight ? 'text-accent-green' : 'text-ink')}>{value}</p>
      <p className="text-xs text-ink-faint font-mono uppercase tracking-wider mt-1">{label}</p>
    </div>
  )
}

function ThresholdTag({ label, range, color }: { label: string; range: string; color: string }) {
  const colors: Record<string, string> = {
    green: 'bg-accent-green/10 text-accent-green',
    brand: 'bg-brand/10 text-brand',
    amber: 'bg-accent-amber/10 text-accent-amber',
    red: 'bg-accent-red/10 text-accent-red',
  }
  return (
    <span className={clsx('px-2 py-0.5 rounded-full text-[10px] font-mono', colors[color])}>
      {label} ({range})
    </span>
  )
}

function ProGate() {
  return (
    <div className="p-8">
      <div className="card p-12 flex flex-col items-center text-center max-w-lg mx-auto">
        <div className="w-16 h-16 rounded-2xl bg-brand/10 border border-brand/20 flex items-center justify-center mb-6">
          <Lock className="w-8 h-8 text-brand" />
        </div>
        <h2 className="font-display text-2xl font-bold mb-2">Pro Feature</h2>
        <p className="text-ink-muted leading-relaxed mb-8">
          Visual similarity detection uses perceptual hashing to find edited, resized, or filtered duplicates that byte-matching misses.
          Available on Pro plan.
        </p>
        <div className="space-y-2 text-sm text-ink-muted text-left w-full bg-surface-overlay rounded-xl p-4 mb-8">
          {[
            'Same photo saved at different resolutions',
            'Photos + edited versions (crop, filter, brightness)',
            'Screenshots taken at slightly different times',
            'RAW + JPEG pairs from camera imports',
          ].map(item => (
            <div key={item} className="flex items-center gap-2">
              <Images className="w-3.5 h-3.5 text-brand shrink-0" />
              <span>{item}</span>
            </div>
          ))}
        </div>
        <Link href="/settings" className="btn-primary px-8 py-3 text-base">
          Upgrade to Pro
        </Link>
      </div>
    </div>
  )
}
