'use client'

import { useEffect, useState } from 'react'
import { duplicatesApi, formatBytes } from '@/lib/api'
import { Trash2, Shield, RefreshCw, ChevronDown, ChevronUp, FileText, Image, Archive } from 'lucide-react'
import toast from 'react-hot-toast'
import clsx from 'clsx'

interface DupGroup {
  md5_hash: string
  file_count: number
  wasted_bytes: number
  files: FileEntry[]
}

interface FileEntry {
  id: string
  file_name: string
  file_path: string
  file_size: number
  mime_type?: string
  last_modified?: string
}

export default function DuplicatesPage() {
  const [groups, setGroups] = useState<DupGroup[]>([])
  const [loading, setLoading] = useState(true)
  const [expanded, setExpanded] = useState<Set<string>>(new Set())
  const [deleting, setDeleting] = useState<Set<string>>(new Set())
  const [deleted, setDeleted] = useState<Set<string>>(new Set())

  useEffect(() => {
    loadDuplicates()
  }, [])

  const loadDuplicates = async () => {
    setLoading(true)
    try {
      const res = await duplicatesApi.listGroups()
      setGroups(res.data.groups || [])
    } catch {
      setGroups([])
    } finally {
      setLoading(false)
    }
  }

  const toggleExpand = (hash: string) => {
    setExpanded((prev) => {
      const next = new Set(prev)
      next.has(hash) ? next.delete(hash) : next.add(hash)
      return next
    })
  }

  const handleDelete = async (fileId: string) => {
    setDeleting((prev) => new Set(prev).add(fileId))
    try {
      const res = await duplicatesApi.deleteFile(fileId)
      setDeleted((prev) => new Set(prev).add(fileId))
      toast.success(`File deleted · ${formatBytes(res.data.bytes_freed)} freed`, {
        action: {
          label: 'Undo',
          onClick: () => handleUndo(fileId),
        },
      } as any)
    } catch (err: any) {
      toast.error(err?.response?.data?.detail || 'Delete failed')
    } finally {
      setDeleting((prev) => {
        const next = new Set(prev)
        next.delete(fileId)
        return next
      })
    }
  }

  const handleUndo = async (fileId: string) => {
    try {
      await duplicatesApi.undoDelete(fileId)
      setDeleted((prev) => {
        const next = new Set(prev)
        next.delete(fileId)
        return next
      })
      toast.success('File restored')
    } catch {
      toast.error('Undo failed')
    }
  }

  const totalWasted = groups.reduce((acc, g) => acc + g.wasted_bytes, 0)
  const visibleGroups = groups.filter((g) => !allFilesDeleted(g, deleted))

  function allFilesDeleted(g: DupGroup, del: Set<string>) {
    return g.files.slice(1).every((f) => del.has(f.id))
  }

  if (loading) {
    return (
      <div className="p-8 space-y-4">
        {[...Array(5)].map((_, i) => (
          <div key={i} className="h-24 bg-surface-raised rounded-2xl animate-pulse" />
        ))}
      </div>
    )
  }

  return (
    <div className="p-8 space-y-6 animate-fade-in">
      {/* Header */}
      <div>
        <h1 className="font-display text-3xl font-bold">Duplicate Files</h1>
        <p className="text-ink-muted mt-1">
          {visibleGroups.length > 0
            ? `${visibleGroups.length} groups · ${formatBytes(totalWasted)} wasted storage`
            : 'No duplicates found. Run a scan from the dashboard.'}
        </p>
      </div>

      {/* Summary banner */}
      {totalWasted > 0 && (
        <div className="card p-5 glow-border flex items-center gap-5">
          <div className="w-12 h-12 rounded-xl bg-accent-green/15 flex items-center justify-center shrink-0">
            <Shield className="w-6 h-6 text-accent-green" />
          </div>
          <div className="flex-1">
            <p className="font-semibold">
              Deleting all duplicates saves <span className="text-accent-green">{formatBytes(totalWasted)}</span>
            </p>
            <p className="text-sm text-ink-muted mt-0.5">
              Keep the original, delete the rest. All actions are reversible for 30 days.
            </p>
          </div>
          <div className="text-right shrink-0">
            <p className="text-2xl font-display font-bold text-accent-green">{formatBytes(totalWasted)}</p>
            <p className="text-xs text-ink-faint font-mono uppercase">recoverable</p>
          </div>
        </div>
      )}

      {/* Groups list */}
      <div className="space-y-3">
        {visibleGroups.map((group) => (
          <DuplicateGroupCard
            key={group.md5_hash}
            group={group}
            isExpanded={expanded.has(group.md5_hash)}
            onToggle={() => toggleExpand(group.md5_hash)}
            onDelete={handleDelete}
            deleting={deleting}
            deleted={deleted}
          />
        ))}

        {visibleGroups.length === 0 && (
          <div className="card p-12 text-center">
            <div className="w-16 h-16 rounded-2xl bg-accent-green/10 flex items-center justify-center mx-auto mb-4">
              <Shield className="w-8 h-8 text-accent-green" />
            </div>
            <p className="font-display text-xl font-bold mb-2">All clean!</p>
            <p className="text-ink-muted">No duplicate files detected. Great work.</p>
          </div>
        )}
      </div>
    </div>
  )
}

function DuplicateGroupCard({
  group, isExpanded, onToggle, onDelete, deleting, deleted
}: {
  group: DupGroup
  isExpanded: boolean
  onToggle: () => void
  onDelete: (id: string) => void
  deleting: Set<string>
  deleted: Set<string>
}) {
  const [keepFileId, setKeepFileId] = useState(group.files[0]?.id)
  const duplicates = group.files.filter((f) => f.id !== keepFileId && !deleted.has(f.id))

  return (
    <div className="card overflow-hidden">
      {/* Group header */}
      <button
        onClick={onToggle}
        className="w-full flex items-center gap-4 p-4 hover:bg-surface-overlay/50 transition-colors text-left"
      >
        <FileTypeIcon mime={group.files[0]?.mime_type} />
        <div className="flex-1 min-w-0">
          <p className="font-medium text-ink truncate">
            {group.files[0]?.file_name}
          </p>
          <p className="text-xs text-ink-muted mt-0.5">
            <span className="text-accent-amber font-mono">{group.file_count} copies</span>
            {' · '}
            {formatBytes(group.wasted_bytes)} wasted
            {' · '}
            {formatBytes(group.files[0]?.file_size)} each
          </p>
        </div>
        <div className="flex items-center gap-3 shrink-0">
          <RiskBadge count={group.file_count} />
          {isExpanded ? <ChevronUp className="w-4 h-4 text-ink-faint" /> : <ChevronDown className="w-4 h-4 text-ink-faint" />}
        </div>
      </button>

      {/* Expanded file list */}
      {isExpanded && (
        <div className="border-t border-surface-border divide-y divide-surface-border">
          {group.files.map((file, idx) => {
            const isDeleted = deleted.has(file.id)
            const isKeep = file.id === keepFileId
            const isDeletingNow = deleting.has(file.id)

            return (
              <div
                key={file.id}
                className={clsx(
                  'flex items-center gap-3 px-4 py-3 transition-all',
                  isDeleted ? 'opacity-30 line-through' : 'hover:bg-surface-overlay/30',
                  isKeep && !isDeleted && 'bg-accent-green/5'
                )}
              >
                <input
                  type="radio"
                  name={`keep-${group.md5_hash}`}
                  checked={isKeep}
                  onChange={() => setKeepFileId(file.id)}
                  className="accent-brand"
                  disabled={isDeleted}
                />
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-medium text-ink truncate">{file.file_name}</p>
                  <p className="text-xs text-ink-faint truncate font-mono">{file.file_path}</p>
                  {file.last_modified && (
                    <p className="text-xs text-ink-faint mt-0.5">
                      Modified {new Date(file.last_modified).toLocaleDateString()}
                    </p>
                  )}
                </div>
                <span className="text-xs font-mono text-ink-muted shrink-0">
                  {formatBytes(file.file_size)}
                </span>
                {isKeep && !isDeleted && (
                  <span className="text-xs font-mono bg-accent-green/15 text-accent-green px-2 py-0.5 rounded-full shrink-0">
                    keep
                  </span>
                )}
                {!isKeep && !isDeleted && (
                  <button
                    onClick={() => onDelete(file.id)}
                    disabled={isDeletingNow}
                    className="shrink-0 p-2 rounded-xl text-ink-faint hover:text-accent-red hover:bg-accent-red/10 transition-colors disabled:opacity-40"
                  >
                    {isDeletingNow ? <RefreshCw className="w-4 h-4 animate-spin" /> : <Trash2 className="w-4 h-4" />}
                  </button>
                )}
              </div>
            )
          })}

          {/* Quick action: delete all duplicates */}
          {duplicates.length > 0 && (
            <div className="px-4 py-3 bg-surface-overlay/30 flex items-center justify-between">
              <p className="text-xs text-ink-muted">{duplicates.length} duplicate{duplicates.length !== 1 ? 's' : ''} to delete</p>
              <button
                onClick={() => duplicates.forEach((f) => onDelete(f.id))}
                className="text-xs font-semibold text-accent-red hover:text-red-400 flex items-center gap-1.5 transition-colors"
              >
                <Trash2 className="w-3.5 h-3.5" />
                Delete all duplicates
              </button>
            </div>
          )}
        </div>
      )}
    </div>
  )
}

function FileTypeIcon({ mime }: { mime?: string }) {
  const isImage = mime?.startsWith('image/')
  const isArchive = mime?.includes('zip') || mime?.includes('tar')

  if (isImage) return (
    <div className="w-9 h-9 rounded-lg bg-brand/15 flex items-center justify-center shrink-0">
      <Image className="w-4.5 h-4.5 text-brand" />
    </div>
  )
  if (isArchive) return (
    <div className="w-9 h-9 rounded-lg bg-accent-amber/15 flex items-center justify-center shrink-0">
      <Archive className="w-4.5 h-4.5 text-accent-amber" />
    </div>
  )
  return (
    <div className="w-9 h-9 rounded-lg bg-surface-overlay flex items-center justify-center shrink-0">
      <FileText className="w-4.5 h-4.5 text-ink-muted" />
    </div>
  )
}

function RiskBadge({ count }: { count: number }) {
  if (count <= 2) {
    return <span className="text-xs font-mono px-2 py-0.5 rounded-full bg-accent-green/15 text-accent-green border border-accent-green/20">low risk</span>
  }
  if (count <= 5) {
    return <span className="text-xs font-mono px-2 py-0.5 rounded-full bg-accent-amber/15 text-accent-amber border border-accent-amber/20">medium</span>
  }
  return <span className="text-xs font-mono px-2 py-0.5 rounded-full bg-accent-red/15 text-accent-red border border-accent-red/20">review</span>
}
