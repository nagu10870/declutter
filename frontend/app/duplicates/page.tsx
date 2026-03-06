'use client'

import { useEffect, useState } from 'react'
import { duplicatesApi, formatBytes } from '@/lib/api'
import {
  Trash2, Shield, RefreshCw, ChevronDown, ChevronUp,
  FileText, Image, Archive, Copy, RotateCcw, FolderOpen, X, Check
} from 'lucide-react'
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

interface DeletedRecord {
  id: string
  file_name: string
  file_path: string
  file_size: number
}

// ── Copy-to-clipboard helper ───────────────────────────────────────────────
function useCopyPath() {
  const [copiedPath, setCopiedPath] = useState<string | null>(null)
  const copy = async (path: string) => {
    try {
      await navigator.clipboard.writeText(path)
      setCopiedPath(path)
      setTimeout(() => setCopiedPath(null), 2000)
    } catch {
      toast.error('Could not copy to clipboard')
    }
  }
  return { copy, copiedPath }
}

// ── Deletion panel shown after files are deleted ───────────────────────────
function DeletedFilesPanel({
  records,
  onUndo,
  onDismiss,
}: {
  records: DeletedRecord[]
  onUndo: (id: string) => void
  onDismiss: () => void
}) {
  const { copy, copiedPath } = useCopyPath()
  const totalSize = records.reduce((acc, r) => acc + r.file_size, 0)

  if (records.length === 0) return null

  return (
    <div className="card border border-accent-amber/30 bg-accent-amber/5 overflow-hidden">
      {/* Panel header */}
      <div className="flex items-center justify-between px-5 py-4 border-b border-accent-amber/20">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-lg bg-accent-amber/15 flex items-center justify-center">
            <FolderOpen className="w-4 h-4 text-accent-amber" />
          </div>
          <div>
            <p className="font-semibold text-sm text-ink">
              {records.length} file{records.length !== 1 ? 's' : ''} marked for deletion
            </p>
            <p className="text-xs text-ink-muted">
              {formatBytes(totalSize)} freed · Go to these paths on your computer to delete the actual files
            </p>
          </div>
        </div>
        <button
          onClick={onDismiss}
          className="p-1.5 rounded-lg text-ink-faint hover:text-ink hover:bg-surface-overlay transition-colors"
          title="Dismiss panel"
        >
          <X className="w-4 h-4" />
        </button>
      </div>

      {/* Copy all paths button */}
      <div className="px-5 pt-3 pb-2 flex items-center justify-between">
        <p className="text-xs text-ink-faint">
          Copy each path, open Finder / File Explorer, navigate there, and delete the file.
        </p>
        <button
          onClick={() => copy(records.map((r) => r.file_path).join('\n'))}
          className="text-xs font-semibold text-brand hover:text-brand/80 flex items-center gap-1.5 shrink-0 ml-4"
        >
          {copiedPath === records.map((r) => r.file_path).join('\n') ? (
            <><Check className="w-3.5 h-3.5 text-accent-green" /><span className="text-accent-green">Copied all!</span></>
          ) : (
            <><Copy className="w-3.5 h-3.5" />Copy all paths</>
          )}
        </button>
      </div>

      {/* File path rows */}
      <div className="px-5 pb-4 space-y-2">
        {records.map((record) => (
          <div
            key={record.id}
            className="flex items-center gap-3 p-3 rounded-xl bg-surface-overlay/60 border border-surface-border group"
          >
            <div className="flex-1 min-w-0">
              <p className="text-xs font-semibold text-ink truncate">{record.file_name}</p>
              <p className="text-xs font-mono text-ink-muted mt-0.5 break-all leading-relaxed">
                {record.file_path}
              </p>
              <p className="text-xs text-ink-faint mt-0.5">{formatBytes(record.file_size)}</p>
            </div>
            <div className="flex items-center gap-2 shrink-0">
              {/* Copy path button */}
              <button
                onClick={() => copy(record.file_path)}
                title="Copy file path"
                className="p-2 rounded-lg text-ink-faint hover:text-brand hover:bg-brand/10 transition-colors"
              >
                {copiedPath === record.file_path ? (
                  <Check className="w-3.5 h-3.5 text-accent-green" />
                ) : (
                  <Copy className="w-3.5 h-3.5" />
                )}
              </button>
              {/* Undo button */}
              <button
                onClick={() => onUndo(record.id)}
                title="Restore this file in Declutter"
                className="p-2 rounded-lg text-ink-faint hover:text-accent-green hover:bg-accent-green/10 transition-colors flex items-center gap-1"
              >
                <RotateCcw className="w-3.5 h-3.5" />
                <span className="text-xs">Undo</span>
              </button>
            </div>
          </div>
        ))}
      </div>

      {/* OS-specific instructions */}
      <div className="mx-5 mb-4 p-3 rounded-xl bg-surface-overlay/40 border border-surface-border">
        <p className="text-xs font-semibold text-ink-muted mb-2">How to delete on your OS:</p>
        <div className="grid grid-cols-2 gap-3 text-xs text-ink-faint">
          <div>
            <p className="font-semibold text-ink-muted mb-1">🪟 Windows</p>
            <p>Open File Explorer → paste path in address bar → Delete file</p>
          </div>
          <div>
            <p className="font-semibold text-ink-muted mb-1">🍎 Mac</p>
            <p>Open Finder → Go → Go to Folder → paste path → Move to Trash</p>
          </div>
        </div>
      </div>
    </div>
  )
}

// ── Main page ──────────────────────────────────────────────────────────────
export default function DuplicatesPage() {
  const [groups, setGroups] = useState<DupGroup[]>([])
  const [loading, setLoading] = useState(true)
  const [expanded, setExpanded] = useState<Set<string>>(new Set())
  const [deleting, setDeleting] = useState<Set<string>>(new Set())
  const [deleted, setDeleted] = useState<Set<string>>(new Set())
  const [deletedRecords, setDeletedRecords] = useState<DeletedRecord[]>([])
  const [panelDismissed, setPanelDismissed] = useState(false)

  useEffect(() => {
    loadDuplicates()
  }, [])

  const loadDuplicates = async () => {
    setLoading(true)
    try {
      const res = await duplicatesApi.listGroups()
      const grps: DupGroup[] = res.data.groups || []
      setGroups(grps)
      // Auto-expand all groups
      setExpanded(new Set(grps.map((g) => g.md5_hash)))
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

  const handleDelete = async (file: FileEntry) => {
    setDeleting((prev) => new Set(prev).add(file.id))
    try {
      await duplicatesApi.deleteFile(file.id)
      setDeleted((prev) => new Set(prev).add(file.id))
      // Add to deletion panel records
      setDeletedRecords((prev) => {
        if (prev.find((r) => r.id === file.id)) return prev
        return [...prev, {
          id: file.id,
          file_name: file.file_name,
          file_path: file.file_path,
          file_size: file.file_size,
        }]
      })
      setPanelDismissed(false)
      toast.success(`${file.file_name} marked for deletion`)
    } catch (err: any) {
      toast.error(err?.response?.data?.detail || 'Delete failed')
    } finally {
      setDeleting((prev) => {
        const next = new Set(prev)
        next.delete(file.id)
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
      setDeletedRecords((prev) => prev.filter((r) => r.id !== fileId))
      toast.success('File restored in Declutter')
    } catch {
      toast.error('Undo failed')
    }
  }

  const handleDeleteAll = async (group: DupGroup, keepFileId: string) => {
    const toDelete = group.files.filter(
      (f) => f.id !== keepFileId && !deleted.has(f.id)
    )
    for (const f of toDelete) {
      await handleDelete(f)
    }
  }

  const totalWasted = groups.reduce((acc, g) => acc + g.wasted_bytes, 0)
  const visibleGroups = groups.filter((g) =>
    g.files.some((f) => !deleted.has(f.id))
  )
  const showPanel = deletedRecords.length > 0 && !panelDismissed

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
      <div className="flex items-start justify-between">
        <div>
          <h1 className="font-display text-3xl font-bold">Duplicate Files</h1>
          <p className="text-ink-muted mt-1">
            {visibleGroups.length > 0
              ? `${visibleGroups.length} groups · ${formatBytes(totalWasted)} wasted storage`
              : 'No duplicates found. Run a scan from the dashboard.'}
          </p>
        </div>
        {deletedRecords.length > 0 && (
          <button
            onClick={() => setPanelDismissed(false)}
            className="text-sm text-brand hover:underline flex items-center gap-1.5"
          >
            <FolderOpen className="w-4 h-4" />
            View {deletedRecords.length} deleted file path{deletedRecords.length !== 1 ? 's' : ''}
          </button>
        )}
      </div>

      {/* Summary banner */}
      {totalWasted > 0 && (
        <div className="card p-5 glow-border flex items-center gap-5">
          <div className="w-12 h-12 rounded-xl bg-accent-green/15 flex items-center justify-center shrink-0">
            <Shield className="w-6 h-6 text-accent-green" />
          </div>
          <div className="flex-1">
            <p className="font-semibold">
              Deleting all duplicates saves{' '}
              <span className="text-accent-green">{formatBytes(totalWasted)}</span>
            </p>
            <p className="text-sm text-ink-muted mt-0.5">
              Keep the original, delete the rest. All actions are reversible for 30 days.
            </p>
          </div>
          <div className="text-right shrink-0">
            <p className="text-2xl font-display font-bold text-accent-green">
              {formatBytes(totalWasted)}
            </p>
            <p className="text-xs text-ink-faint font-mono uppercase">recoverable</p>
          </div>
        </div>
      )}

      {/* Deleted files panel — shows file paths to delete on disk */}
      {showPanel && (
        <DeletedFilesPanel
          records={deletedRecords}
          onUndo={handleUndo}
          onDismiss={() => setPanelDismissed(true)}
        />
      )}

      {/* How-to hint */}
      {visibleGroups.length > 0 && (
        <div className="flex items-center gap-2 text-xs text-ink-faint px-1">
          <Copy className="w-3.5 h-3.5 shrink-0" />
          <span>
            Select which copy to <strong className="text-accent-green">keep</strong> using the radio button,
            then click <strong className="text-accent-red">🗑 Delete</strong> on copies to remove.
            A panel will appear with the exact file paths to delete from your computer.
          </span>
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
            onDeleteAll={handleDeleteAll}
            onUndo={handleUndo}
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
            <p className="text-ink-muted">No duplicate files detected.</p>
          </div>
        )}
      </div>
    </div>
  )
}

// ── Duplicate Group Card ───────────────────────────────────────────────────
function DuplicateGroupCard({
  group, isExpanded, onToggle, onDelete, onDeleteAll, onUndo, deleting, deleted,
}: {
  group: DupGroup
  isExpanded: boolean
  onToggle: () => void
  onDelete: (file: FileEntry) => void
  onDeleteAll: (group: DupGroup, keepId: string) => void
  onUndo: (id: string) => void
  deleting: Set<string>
  deleted: Set<string>
}) {
  const [keepFileId, setKeepFileId] = useState(group.files[0]?.id)
  const visibleFiles = group.files.filter((f) => !deleted.has(f.id))
  const duplicatesToDelete = group.files.filter(
    (f) => f.id !== keepFileId && !deleted.has(f.id)
  )

  useEffect(() => {
    if (deleted.has(keepFileId) && visibleFiles.length > 0) {
      setKeepFileId(visibleFiles[0].id)
    }
  }, [deleted, keepFileId, visibleFiles])

  return (
    <div className="card overflow-hidden">
      <button
        onClick={onToggle}
        className="w-full flex items-center gap-4 p-4 hover:bg-surface-overlay/50 transition-colors text-left"
      >
        <FileTypeIcon mime={group.files[0]?.mime_type} />
        <div className="flex-1 min-w-0">
          <p className="font-medium text-ink truncate">{group.files[0]?.file_name}</p>
          <p className="text-xs text-ink-muted mt-0.5">
            <span className="text-accent-amber font-mono">{group.file_count} copies</span>
            {' · '}{formatBytes(group.wasted_bytes)} wasted
            {' · '}{formatBytes(group.files[0]?.file_size)} each
          </p>
        </div>
        <div className="flex items-center gap-3 shrink-0">
          <RiskBadge count={group.file_count} />
          {isExpanded
            ? <ChevronUp className="w-4 h-4 text-ink-faint" />
            : <ChevronDown className="w-4 h-4 text-ink-faint" />}
        </div>
      </button>

      {isExpanded && (
        <div className="border-t border-surface-border divide-y divide-surface-border">
          {group.files.map((file) => {
            const isDeleted = deleted.has(file.id)
            const isKeep = file.id === keepFileId
            const isDeletingNow = deleting.has(file.id)

            return (
              <div
                key={file.id}
                className={clsx(
                  'flex items-center gap-3 px-4 py-3 transition-all',
                  isDeleted ? 'opacity-30 bg-accent-red/5' :
                  isKeep ? 'bg-accent-green/5' : 'hover:bg-surface-overlay/30'
                )}
              >
                <input
                  type="radio"
                  name={`keep-${group.md5_hash}`}
                  checked={isKeep}
                  onChange={() => !isDeleted && setKeepFileId(file.id)}
                  className="accent-brand shrink-0 cursor-pointer"
                  disabled={isDeleted}
                  title="Keep this copy"
                />
                <div className="flex-1 min-w-0">
                  <p className={clsx(
                    'text-sm font-medium truncate',
                    isDeleted ? 'line-through text-ink-faint' : 'text-ink'
                  )}>
                    {file.file_name}
                  </p>
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
                  <span className="text-xs font-mono bg-accent-green/15 text-accent-green px-2 py-0.5 rounded-full border border-accent-green/20 shrink-0">
                    keep
                  </span>
                )}
                {!isKeep && !isDeleted && (
                  <button
                    onClick={() => onDelete(file)}
                    disabled={isDeletingNow}
                    title="Mark for deletion"
                    className="shrink-0 p-2 rounded-xl text-ink-faint hover:text-accent-red hover:bg-accent-red/10 transition-colors disabled:opacity-40"
                  >
                    {isDeletingNow
                      ? <RefreshCw className="w-4 h-4 animate-spin" />
                      : <Trash2 className="w-4 h-4" />}
                  </button>
                )}
                {isDeleted && (
                  <button
                    onClick={() => onUndo(file.id)}
                    title="Restore in Declutter"
                    className="shrink-0 p-2 rounded-xl text-ink-faint hover:text-accent-green hover:bg-accent-green/10 transition-colors flex items-center gap-1"
                  >
                    <RotateCcw className="w-3.5 h-3.5" />
                    <span className="text-xs">Undo</span>
                  </button>
                )}
              </div>
            )
          })}

          {duplicatesToDelete.length > 0 && (
            <div className="px-4 py-3 bg-surface-overlay/30 flex items-center justify-between">
              <p className="text-xs text-ink-muted">
                {duplicatesToDelete.length} duplicate{duplicatesToDelete.length !== 1 ? 's' : ''} to delete
              </p>
              <button
                onClick={() => onDeleteAll(group, keepFileId)}
                className="text-xs font-semibold text-accent-red hover:text-red-400 flex items-center gap-1.5 transition-colors"
              >
                <Trash2 className="w-3.5 h-3.5" />
                Delete all duplicates
              </button>
            </div>
          )}

          {duplicatesToDelete.length === 0 && visibleFiles.length > 0 && (
            <div className="px-4 py-3 bg-accent-green/5 flex items-center gap-2">
              <Shield className="w-3.5 h-3.5 text-accent-green" />
              <p className="text-xs text-accent-green font-medium">
                All duplicates removed — keeping 1 copy
              </p>
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
      <Image className="w-4 h-4 text-brand" />
    </div>
  )
  if (isArchive) return (
    <div className="w-9 h-9 rounded-lg bg-accent-amber/15 flex items-center justify-center shrink-0">
      <Archive className="w-4 h-4 text-accent-amber" />
    </div>
  )
  return (
    <div className="w-9 h-9 rounded-lg bg-surface-overlay flex items-center justify-center shrink-0">
      <FileText className="w-4 h-4 text-ink-muted" />
    </div>
  )
}

function RiskBadge({ count }: { count: number }) {
  if (count <= 2) return (
    <span className="text-xs font-mono px-2 py-0.5 rounded-full bg-accent-green/15 text-accent-green border border-accent-green/20">low risk</span>
  )
  if (count <= 5) return (
    <span className="text-xs font-mono px-2 py-0.5 rounded-full bg-accent-amber/15 text-accent-amber border border-accent-amber/20">medium</span>
  )
  return (
    <span className="text-xs font-mono px-2 py-0.5 rounded-full bg-accent-red/15 text-accent-red border border-accent-red/20">review</span>
  )
}
