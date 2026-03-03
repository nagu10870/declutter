'use client'

import { useEffect, useState, useCallback } from 'react'
import { suggestionsApi, classifyApi, formatBytes, Suggestion } from '@/lib/api'
import { useAuthStore } from '@/lib/store'
import { Sidebar } from '@/components/layout/Sidebar'
import { Toaster } from 'react-hot-toast'
import toast from 'react-hot-toast'
import {
  Lightbulb, Trash2, Archive, Eye, ChevronRight,
  RefreshCw, Sparkles, Shield, X, CheckCircle2,
  Camera, FileText, Image, HardDrive, Download, Zap
} from 'lucide-react'
import clsx from 'clsx'

export default function SuggestionsPage() {
  return (
    <div className="flex h-screen overflow-hidden">
      <Sidebar />
      <main className="flex-1 overflow-y-auto bg-surface">
        <SuggestionsContent />
      </main>
      <Toaster position="bottom-right" toastOptions={{
        style: { background: '#13161e', color: '#f0f2ff', border: '1px solid #252a38' },
        success: { iconTheme: { primary: '#1de9a4', secondary: '#0d0f14' } },
      }} />
    </div>
  )
}

function SuggestionsContent() {
  const { user } = useAuthStore()
  const [suggestions, setSuggestions] = useState<Suggestion[]>([])
  const [stats, setStats] = useState<any>(null)
  const [classifyStats, setClassifyStats] = useState<any>(null)
  const [loading, setLoading] = useState(true)
  const [classifying, setClassifying] = useState(false)
  const [generating, setGenerating] = useState(false)
  const [applying, setApplying] = useState<Set<string>>(new Set())
  const [dismissed, setDismissed] = useState<Set<string>>(new Set())
  const [applied, setApplied] = useState<Set<string>>(new Set())

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const [sugRes, statsRes, classRes] = await Promise.all([
        suggestionsApi.list(),
        suggestionsApi.stats(),
        classifyApi.stats(),
      ])
      setSuggestions(sugRes.data)
      setStats(statsRes.data)
      setClassifyStats(classRes.data)
    } catch {
      // No data yet
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { load() }, [load])

  const handleClassify = async () => {
    setClassifying(true)
    try {
      await classifyApi.run({ limit: 1000 })
      await suggestionsApi.generate()
      toast.success('Files classified and suggestions refreshed!')
      await load()
    } catch (err: any) {
      toast.error(err?.response?.data?.detail || 'Classification failed')
    } finally {
      setClassifying(false)
    }
  }

  const handleGenerate = async () => {
    setGenerating(true)
    try {
      const res = await suggestionsApi.generate()
      toast.success(`${res.data.generated} suggestions refreshed`)
      await load()
    } catch {
      toast.error('Failed to refresh suggestions')
    } finally {
      setGenerating(false)
    }
  }

  const handleApply = async (suggestion: Suggestion) => {
    if (!confirm(`Delete ${suggestion.file_count} files and free ${formatBytes(suggestion.bytes_savings)}?`)) return
    setApplying(prev => new Set(prev).add(suggestion.id))
    try {
      const res = await suggestionsApi.apply(suggestion.id)
      setApplied(prev => new Set(prev).add(suggestion.id))
      toast.success(`✓ ${formatBytes(res.data.bytes_freed)} freed — ${res.data.files_deleted} files removed`)
      await load()
    } catch (err: any) {
      toast.error(err?.response?.data?.detail || 'Failed to apply suggestion')
    } finally {
      setApplying(prev => { const n = new Set(prev); n.delete(suggestion.id); return n })
    }
  }

  const handleDismiss = async (id: string) => {
    try {
      await suggestionsApi.dismiss(id)
      setDismissed(prev => new Set(prev).add(id))
      setSuggestions(prev => prev.filter(s => s.id !== id))
    } catch {
      toast.error('Failed to dismiss')
    }
  }

  const visibleSuggestions = suggestions.filter(
    s => !dismissed.has(s.id) && !applied.has(s.id)
  )
  const totalSavings = visibleSuggestions.reduce((sum, s) => sum + s.bytes_savings, 0)

  return (
    <div className="p-8 space-y-6 animate-fade-in max-w-4xl">
      {/* Header */}
      <div className="flex items-start justify-between">
        <div>
          <h1 className="font-display text-3xl font-bold flex items-center gap-3">
            <Sparkles className="w-7 h-7 text-brand" />
            Smart Suggestions
          </h1>
          <p className="text-ink-muted mt-1">
            {stats
              ? `${stats.total_suggestions} suggestions · ${formatBytes(stats.total_savings_bytes)} recoverable`
              : 'AI-powered cleanup recommendations based on your files'}
          </p>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={handleClassify}
            disabled={classifying}
            className="btn-ghost text-sm flex items-center gap-2"
          >
            {classifying
              ? <RefreshCw className="w-4 h-4 animate-spin" />
              : <Sparkles className="w-4 h-4" />}
            {classifying ? 'Classifying…' : 'Classify Files'}
          </button>
          <button
            onClick={handleGenerate}
            disabled={generating}
            className="btn-ghost text-sm flex items-center gap-2"
          >
            {generating
              ? <RefreshCw className="w-4 h-4 animate-spin" />
              : <RefreshCw className="w-4 h-4" />}
            Refresh
          </button>
        </div>
      </div>

      {/* Classification stats bar */}
      {classifyStats && classifyStats.total_classified > 0 && (
        <div className="grid grid-cols-4 gap-3">
          <MiniStat
            icon={<Camera className="w-4 h-4 text-accent-amber" />}
            label="Screenshots"
            value={classifyStats.screenshot_count?.toLocaleString() ?? '0'}
            sub={formatBytes(classifyStats.screenshot_bytes || 0)}
            color="amber"
          />
          <MiniStat
            icon={<Image className="w-4 h-4 text-accent-red" />}
            label="Blurry Photos"
            value={classifyStats.blurry_count?.toLocaleString() ?? '0'}
            sub={formatBytes(classifyStats.blurry_bytes || 0)}
            color="red"
          />
          <MiniStat
            icon={<FileText className="w-4 h-4 text-brand" />}
            label="Classified"
            value={classifyStats.total_classified?.toLocaleString() ?? '0'}
            sub="files analyzed"
            color="brand"
          />
          <MiniStat
            icon={<Zap className="w-4 h-4 text-accent-green" />}
            label="Unclassified"
            value={classifyStats.total_unclassified?.toLocaleString() ?? '0'}
            sub="run classify to analyze"
            color="green"
          />
        </div>
      )}

      {/* Total savings banner */}
      {visibleSuggestions.length > 0 && totalSavings > 0 && (
        <div className="card p-5 glow-border flex items-center gap-4">
          <div className="w-12 h-12 rounded-2xl bg-accent-green/10 flex items-center justify-center shrink-0">
            <HardDrive className="w-6 h-6 text-accent-green" />
          </div>
          <div className="flex-1">
            <p className="font-display text-2xl font-bold text-accent-green">
              {formatBytes(totalSavings)}
            </p>
            <p className="text-sm text-ink-muted mt-0.5">
              recoverable across {visibleSuggestions.length} suggestions
            </p>
          </div>
          <button
            onClick={async () => {
              const lowRisk = visibleSuggestions.filter(s => s.risk_level === 'low')
              if (!lowRisk.length) return
              if (!confirm(`Apply all ${lowRisk.length} low-risk suggestions?`)) return
              for (const s of lowRisk) {
                await suggestionsApi.apply(s.id)
                setApplied(prev => new Set(prev).add(s.id))
              }
              toast.success(`All low-risk suggestions applied!`)
              await load()
            }}
            className="btn-primary text-sm flex items-center gap-2 shrink-0"
          >
            <Zap className="w-4 h-4" />
            Apply All Low-Risk
          </button>
        </div>
      )}

      {/* Loading skeletons */}
      {loading && (
        <div className="space-y-3">
          {[...Array(4)].map((_, i) => (
            <div key={i} className="h-28 bg-surface-raised rounded-2xl animate-pulse" />
          ))}
        </div>
      )}

      {/* Suggestion cards */}
      {!loading && visibleSuggestions.length > 0 && (
        <div className="space-y-3">
          {/* Low risk section */}
          {visibleSuggestions.some(s => s.risk_level === 'low') && (
            <div>
              <RiskSectionHeader risk="low" />
              <div className="space-y-2 mt-2">
                {visibleSuggestions
                  .filter(s => s.risk_level === 'low')
                  .map(s => (
                    <SuggestionCard
                      key={s.id}
                      suggestion={s}
                      isApplying={applying.has(s.id)}
                      onApply={() => handleApply(s)}
                      onDismiss={() => handleDismiss(s.id)}
                    />
                  ))}
              </div>
            </div>
          )}

          {/* Medium risk section */}
          {visibleSuggestions.some(s => s.risk_level === 'medium') && (
            <div className="mt-6">
              <RiskSectionHeader risk="medium" />
              <div className="space-y-2 mt-2">
                {visibleSuggestions
                  .filter(s => s.risk_level === 'medium')
                  .map(s => (
                    <SuggestionCard
                      key={s.id}
                      suggestion={s}
                      isApplying={applying.has(s.id)}
                      onApply={() => handleApply(s)}
                      onDismiss={() => handleDismiss(s.id)}
                    />
                  ))}
              </div>
            </div>
          )}
        </div>
      )}

      {/* Empty state */}
      {!loading && visibleSuggestions.length === 0 && (
        <div className="card p-12 flex flex-col items-center text-center">
          <div className="w-16 h-16 rounded-2xl bg-accent-green/10 flex items-center justify-center mb-5">
            <CheckCircle2 className="w-8 h-8 text-accent-green" />
          </div>
          <h2 className="font-display text-xl font-bold mb-2">All clean!</h2>
          <p className="text-ink-muted leading-relaxed max-w-sm mb-6">
            No cleanup suggestions right now. Run a scan and classify your files to generate new suggestions.
          </p>
          <button onClick={handleClassify} disabled={classifying} className="btn-primary flex items-center gap-2">
            {classifying ? <RefreshCw className="w-4 h-4 animate-spin" /> : <Sparkles className="w-4 h-4" />}
            {classifying ? 'Classifying…' : 'Classify My Files'}
          </button>
        </div>
      )}

      {/* Category breakdown */}
      {classifyStats?.categories?.length > 0 && (
        <div className="card p-5">
          <h2 className="font-display font-bold mb-4">File Categories</h2>
          <div className="space-y-2">
            {classifyStats.categories.slice(0, 8).map((cat: any) => (
              <CategoryBar
                key={cat.category}
                category={cat.category}
                count={cat.count}
                bytes={cat.total_bytes}
                total={classifyStats.total_classified}
              />
            ))}
          </div>
        </div>
      )}
    </div>
  )
}

// ── Suggestion Card ────────────────────────────────────────────────────────

function SuggestionCard({
  suggestion, isApplying, onApply, onDismiss
}: {
  suggestion: Suggestion
  isApplying: boolean
  onApply: () => void
  onDismiss: () => void
}) {
  const [expanded, setExpanded] = useState(false)

  const typeIcon: Record<string, React.ReactNode> = {
    old_screenshots:   <Camera className="w-5 h-5 text-accent-amber" />,
    blurry_photos:     <Image className="w-5 h-5 text-accent-red" />,
    receipt_archive:   <FileText className="w-5 h-5 text-brand" />,
    large_unused_files: <HardDrive className="w-5 h-5 text-accent-amber" />,
    duplicate_videos:  <Eye className="w-5 h-5 text-accent-green" />,
    old_downloads:     <Download className="w-5 h-5 text-ink-muted" />,
    tiny_files:        <Trash2 className="w-5 h-5 text-ink-faint" />,
  }

  const icon = typeIcon[suggestion.suggestion_type] || <Lightbulb className="w-5 h-5 text-brand" />

  const actionIcon: Record<string, React.ReactNode> = {
    delete:  <Trash2 className="w-4 h-4" />,
    archive: <Archive className="w-4 h-4" />,
    review:  <Eye className="w-4 h-4" />,
  }

  return (
    <div className={clsx(
      'card overflow-hidden transition-all',
      suggestion.risk_level === 'low' && 'hover:border-accent-green/30',
      suggestion.risk_level === 'medium' && 'hover:border-accent-amber/30',
    )}>
      <div className="p-4 flex items-start gap-4">
        {/* Icon */}
        <div className="w-10 h-10 rounded-xl bg-surface-overlay flex items-center justify-center shrink-0 mt-0.5">
          {icon}
        </div>

        {/* Content */}
        <div className="flex-1 min-w-0">
          <div className="flex items-start justify-between gap-3">
            <div>
              <h3 className="font-semibold text-ink">{suggestion.title}</h3>
              <p className="text-xs text-ink-muted mt-0.5">
                {suggestion.file_count} files · {formatBytes(suggestion.bytes_savings)} recoverable
              </p>
            </div>
            <div className="flex items-center gap-2 shrink-0">
              <span className={clsx(
                'text-[10px] font-mono px-2 py-0.5 rounded-full border',
                suggestion.risk_level === 'low'
                  ? 'bg-accent-green/10 text-accent-green border-accent-green/20'
                  : 'bg-accent-amber/10 text-accent-amber border-accent-amber/20'
              )}>
                {suggestion.risk_level} risk
              </span>
              <button
                onClick={() => setExpanded(e => !e)}
                className="btn-ghost p-1.5 text-ink-faint"
              >
                <ChevronRight className={clsx('w-4 h-4 transition-transform', expanded && 'rotate-90')} />
              </button>
            </div>
          </div>

          {expanded && (
            <p className="text-sm text-ink-muted mt-3 leading-relaxed">{suggestion.description}</p>
          )}
        </div>
      </div>

      {/* Actions */}
      <div className="px-4 pb-4 flex items-center justify-between">
        <button
          onClick={onDismiss}
          className="text-xs text-ink-faint hover:text-ink-muted flex items-center gap-1.5 transition-colors"
        >
          <X className="w-3.5 h-3.5" /> Dismiss
        </button>

        <button
          onClick={onApply}
          disabled={isApplying}
          className={clsx(
            'flex items-center gap-2 px-4 py-2 rounded-xl text-sm font-semibold transition-all',
            suggestion.risk_level === 'low'
              ? 'bg-accent-green/15 text-accent-green border border-accent-green/20 hover:bg-accent-green/25'
              : 'bg-accent-amber/15 text-accent-amber border border-accent-amber/20 hover:bg-accent-amber/25',
            'disabled:opacity-40'
          )}
        >
          {isApplying
            ? <RefreshCw className="w-4 h-4 animate-spin" />
            : actionIcon[suggestion.action] || <Trash2 className="w-4 h-4" />}
          {isApplying ? 'Applying…' : suggestion.action_label}
        </button>
      </div>
    </div>
  )
}

// ── Sub-components ─────────────────────────────────────────────────────────

function RiskSectionHeader({ risk }: { risk: 'low' | 'medium' }) {
  return (
    <div className="flex items-center gap-2">
      {risk === 'low'
        ? <Shield className="w-4 h-4 text-accent-green" />
        : <Eye className="w-4 h-4 text-accent-amber" />}
      <span className={clsx(
        'text-xs font-mono uppercase tracking-wider font-semibold',
        risk === 'low' ? 'text-accent-green' : 'text-accent-amber'
      )}>
        {risk === 'low' ? 'Safe to clean' : 'Review recommended'}
      </span>
    </div>
  )
}

function MiniStat({ icon, label, value, sub, color }: {
  icon: React.ReactNode; label: string; value: string; sub: string; color: string
}) {
  return (
    <div className="card p-3">
      <div className="flex items-center gap-2 mb-2">{icon}</div>
      <p className="font-display font-bold text-lg">{value}</p>
      <p className="text-[10px] text-ink-faint font-mono uppercase tracking-wide">{label}</p>
      <p className="text-xs text-ink-muted mt-0.5">{sub}</p>
    </div>
  )
}

function CategoryBar({ category, count, bytes, total }: {
  category: string; count: number; bytes: number; total: number
}) {
  const pct = total ? Math.round((count / total) * 100) : 0
  const catColors: Record<string, string> = {
    screenshot: 'bg-accent-amber',
    photo: 'bg-brand',
    document: 'bg-accent-green',
    video: 'bg-purple-400',
    audio: 'bg-pink-400',
    archive: 'bg-ink-muted',
    receipt: 'bg-accent-red',
    other: 'bg-ink-faint',
  }
  const color = catColors[category] || 'bg-ink-faint'

  return (
    <div className="flex items-center gap-3">
      <span className="text-xs text-ink-muted w-20 capitalize shrink-0">{category}</span>
      <div className="flex-1 h-1.5 bg-surface-overlay rounded-full overflow-hidden">
        <div className={clsx('h-full rounded-full', color)} style={{ width: `${pct}%` }} />
      </div>
      <span className="text-xs font-mono text-ink-faint w-12 text-right">{count}</span>
      <span className="text-xs font-mono text-ink-faint w-16 text-right">{formatBytes(bytes)}</span>
    </div>
  )
}
