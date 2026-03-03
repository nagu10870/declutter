'use client'

import { useEffect, useState } from 'react'
import { useParams } from 'next/navigation'
import { shareApi, formatBytes } from '@/lib/api'
import { Zap, AlertTriangle, Copy, CheckCircle2, HardDrive, Files } from 'lucide-react'
import toast, { Toaster } from 'react-hot-toast'

export default function ShareViewPage() {
  const params = useParams()
  const slug = params?.slug as string

  const [data, setData] = useState<any>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    if (!slug) return
    shareApi.view(slug)
      .then(r => setData(r.data))
      .catch((err) => {
        const msg = err?.response?.data?.detail || 'This link is invalid or has expired.'
        setError(msg)
      })
      .finally(() => setLoading(false))
  }, [slug])

  return (
    <div className="min-h-screen bg-surface flex flex-col items-center justify-start pt-16 px-4">
      <Toaster position="bottom-right" toastOptions={{
        style: { background: '#13161e', color: '#f0f2ff', border: '1px solid #252a38' },
      }} />

      {/* Declutter branding */}
      <div className="flex items-center gap-3 mb-10">
        <div className="w-10 h-10 rounded-xl bg-brand-gradient flex items-center justify-center shadow-glow-brand">
          <Zap className="w-5 h-5 text-white" fill="white" />
        </div>
        <div>
          <p className="font-display font-bold text-ink leading-none">Declutter</p>
          <p className="text-[10px] text-ink-faint font-mono uppercase tracking-widest">Shared Report</p>
        </div>
      </div>

      {/* Content card */}
      <div className="w-full max-w-2xl">
        {loading && (
          <div className="card p-12 flex items-center justify-center">
            <div className="w-8 h-8 border-2 border-brand border-t-transparent rounded-full animate-spin" />
          </div>
        )}

        {error && !loading && (
          <div className="card p-12 flex flex-col items-center text-center">
            <AlertTriangle className="w-12 h-12 text-accent-red mb-4" />
            <h2 className="font-display text-xl font-bold mb-2">Link Unavailable</h2>
            <p className="text-ink-muted">{error}</p>
          </div>
        )}

        {data && !loading && (
          <>
            {/* Header */}
            <div className="mb-6">
              <h1 className="font-display text-2xl font-bold capitalize">
                {data.label || (data.link_type === 'duplicates' ? 'Duplicate Files Report' : 'Cleanup Suggestions')}
              </h1>
              <p className="text-ink-muted mt-1 text-sm">Shared via Declutter — view-only snapshot</p>
            </div>

            {/* Duplicates view */}
            {data.link_type === 'duplicates' && data.groups && (
              <div className="space-y-3">
                <div className="flex items-center justify-between mb-4">
                  <div className="flex items-center gap-2">
                    <Files className="w-5 h-5 text-accent-red" />
                    <span className="font-semibold">{data.groups.length} duplicate groups</span>
                  </div>
                  <span className="text-sm text-ink-muted">
                    {formatBytes(data.groups.reduce((s: number, g: any) => s + (g.total_wasted_bytes || 0), 0))} wasted
                  </span>
                </div>

                <div className="card overflow-hidden divide-y divide-surface-border">
                  {data.groups.slice(0, 20).map((g: any) => (
                    <div key={g.id} className="flex items-center gap-4 px-5 py-3">
                      <div className="flex-1">
                        <span className={`text-[10px] font-mono px-2 py-0.5 rounded-full ${g.match_type === 'exact' ? 'bg-accent-red/10 text-accent-red' : 'bg-accent-amber/10 text-accent-amber'}`}>
                          {g.match_type}
                        </span>
                      </div>
                      <span className="text-sm font-mono text-ink-muted">
                        {formatBytes(g.total_wasted_bytes || 0)} wasted
                      </span>
                    </div>
                  ))}
                  {data.groups.length > 20 && (
                    <div className="px-5 py-3 text-sm text-ink-faint text-center">
                      +{data.groups.length - 20} more groups not shown
                    </div>
                  )}
                </div>
              </div>
            )}

            {/* Suggestions view */}
            {data.link_type === 'suggestions' && data.suggestions && (
              <div className="space-y-3">
                <div className="flex items-center justify-between mb-4">
                  <div className="flex items-center gap-2">
                    <HardDrive className="w-5 h-5 text-accent-green" />
                    <span className="font-semibold">{data.suggestions.length} cleanup suggestions</span>
                  </div>
                  <span className="text-sm text-ink-muted">
                    {formatBytes(data.suggestions.reduce((s: number, sg: any) => s + (sg.bytes_savings || 0), 0))} recoverable
                  </span>
                </div>

                <div className="space-y-2">
                  {data.suggestions.map((s: any, i: number) => (
                    <div key={i} className="card p-4 flex items-center gap-4">
                      <div className={`w-2 h-2 rounded-full shrink-0 ${s.risk_level === 'low' ? 'bg-accent-green' : 'bg-accent-amber'}`} />
                      <div className="flex-1">
                        <p className="text-sm font-medium">{s.title}</p>
                        <p className="text-xs text-ink-faint mt-0.5">{formatBytes(s.bytes_savings)} recoverable · {s.risk_level} risk</p>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* CTA footer */}
            <div className="mt-8 card p-6 flex items-center justify-between">
              <div>
                <p className="font-semibold">Get Declutter for your own storage</p>
                <p className="text-sm text-ink-muted mt-0.5">Find duplicates, free up space, and organize with AI.</p>
              </div>
              <a href="/" className="btn-primary text-sm shrink-0">
                Try Free →
              </a>
            </div>

            {/* Share this URL */}
            <div className="mt-4 flex items-center gap-2">
              <span className="text-xs text-ink-faint flex-1 font-mono truncate">
                {typeof window !== 'undefined' ? window.location.href : ''}
              </span>
              <button
                onClick={() => {
                  navigator.clipboard.writeText(window.location.href)
                  toast.success('Link copied!')
                }}
                className="btn-ghost text-xs flex items-center gap-1.5 shrink-0"
              >
                <Copy className="w-3.5 h-3.5" /> Copy link
              </button>
            </div>
          </>
        )}
      </div>
    </div>
  )
}
