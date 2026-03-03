'use client'

import { useEffect, useState, useCallback } from 'react'
import { classifyApi, formatBytes, formatDate } from '@/lib/api'
import { api } from '@/lib/api'
import { Sidebar } from '@/components/layout/Sidebar'
import { Toaster } from 'react-hot-toast'
import toast from 'react-hot-toast'
import {
  Search, Filter, SortDesc, FileText, Image, Film,
  Archive, Music, Code, File, Camera, Receipt,
  ChevronLeft, ChevronRight, Trash2, Star, RefreshCw
} from 'lucide-react'
import clsx from 'clsx'

const CATEGORIES = [
  { value: '', label: 'All Files', icon: File },
  { value: 'photo', label: 'Photos', icon: Image },
  { value: 'screenshot', label: 'Screenshots', icon: Camera },
  { value: 'document', label: 'Documents', icon: FileText },
  { value: 'video', label: 'Videos', icon: Film },
  { value: 'audio', label: 'Audio', icon: Music },
  { value: 'archive', label: 'Archives', icon: Archive },
  { value: 'receipt', label: 'Receipts', icon: Receipt },
  { value: 'other', label: 'Other', icon: Code },
]

const SORT_OPTIONS = [
  { value: 'size_desc', label: 'Largest first' },
  { value: 'size_asc', label: 'Smallest first' },
  { value: 'name_asc', label: 'Name A–Z' },
  { value: 'modified_desc', label: 'Recently modified' },
]

export default function FilesPage() {
  return (
    <div className="flex h-screen overflow-hidden">
      <Sidebar />
      <main className="flex-1 overflow-y-auto bg-surface">
        <FilesContent />
      </main>
      <Toaster position="bottom-right" toastOptions={{
        style: { background: '#13161e', color: '#f0f2ff', border: '1px solid #252a38' },
      }} />
    </div>
  )
}

function FilesContent() {
  const [files, setFiles] = useState<any[]>([])
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(true)
  const [search, setSearch] = useState('')
  const [category, setCategory] = useState('')
  const [isBlurry, setIsBlurry] = useState<boolean | undefined>()
  const [isScreenshot, setIsScreenshot] = useState<boolean | undefined>()
  const [page, setPage] = useState(1)
  const PAGE_SIZE = 50

  const loadFiles = useCallback(async () => {
    setLoading(true)
    try {
      const params: any = { page, page_size: PAGE_SIZE }
      if (category) params.category = category
      if (isBlurry !== undefined) params.is_blurry = isBlurry
      if (isScreenshot !== undefined) params.is_screenshot = isScreenshot
      const res = await classifyApi.files(params)
      let data = res.data.files || []
      if (search) {
        data = data.filter((f: any) =>
          f.file_name.toLowerCase().includes(search.toLowerCase())
        )
      }
      setFiles(data)
      setTotal(res.data.total || 0)
    } catch {
      setFiles([])
    } finally {
      setLoading(false)
    }
  }, [page, category, isBlurry, isScreenshot, search])

  useEffect(() => { loadFiles() }, [loadFiles])

  const totalPages = Math.ceil(total / PAGE_SIZE)

  return (
    <div className="p-8 animate-fade-in">
      {/* Header */}
      <div className="mb-6">
        <h1 className="font-display text-3xl font-bold">All Files</h1>
        <p className="text-ink-muted mt-1">
          {total.toLocaleString()} files indexed
        </p>
      </div>

      {/* Filter bar */}
      <div className="flex flex-wrap items-center gap-3 mb-6">
        {/* Search */}
        <div className="relative flex-1 min-w-[200px]">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-ink-faint" />
          <input
            className="input pl-10"
            placeholder="Search by filename..."
            value={search}
            onChange={e => { setSearch(e.target.value); setPage(1) }}
          />
        </div>

        {/* Quality filters */}
        <button
          onClick={() => setIsBlurry(isBlurry === true ? undefined : true)}
          className={clsx(
            'text-xs px-3 py-2 rounded-xl border transition-colors font-medium',
            isBlurry
              ? 'bg-accent-red/15 text-accent-red border-accent-red/30'
              : 'bg-surface-overlay text-ink-muted border-surface-border hover:border-accent-red/30'
          )}
        >
          Blurry only
        </button>

        <button
          onClick={() => setIsScreenshot(isScreenshot === true ? undefined : true)}
          className={clsx(
            'text-xs px-3 py-2 rounded-xl border transition-colors font-medium',
            isScreenshot
              ? 'bg-accent-amber/15 text-accent-amber border-accent-amber/30'
              : 'bg-surface-overlay text-ink-muted border-surface-border hover:border-accent-amber/30'
          )}
        >
          Screenshots only
        </button>

        <button
          onClick={() => { setCategory(''); setIsBlurry(undefined); setIsScreenshot(undefined); setSearch('') }}
          className="btn-ghost text-xs flex items-center gap-1.5"
        >
          <RefreshCw className="w-3.5 h-3.5" /> Clear
        </button>
      </div>

      {/* Category tabs */}
      <div className="flex gap-1.5 overflow-x-auto pb-2 mb-5 scrollbar-none">
        {CATEGORIES.map(cat => {
          const Icon = cat.icon
          return (
            <button
              key={cat.value}
              onClick={() => { setCategory(cat.value); setPage(1) }}
              className={clsx(
                'flex items-center gap-1.5 px-3 py-1.5 rounded-xl text-xs font-medium whitespace-nowrap transition-colors',
                category === cat.value
                  ? 'bg-brand/15 text-brand border border-brand/20'
                  : 'bg-surface-overlay text-ink-muted border border-surface-border hover:text-ink'
              )}
            >
              <Icon className="w-3.5 h-3.5" />
              {cat.label}
            </button>
          )
        })}
      </div>

      {/* File table */}
      {loading ? (
        <div className="space-y-1.5">
          {[...Array(10)].map((_, i) => (
            <div key={i} className="h-12 bg-surface-raised rounded-xl animate-pulse" />
          ))}
        </div>
      ) : files.length === 0 ? (
        <div className="card p-16 flex flex-col items-center text-center">
          <File className="w-10 h-10 text-ink-faint mb-4" />
          <h3 className="font-display font-bold text-lg mb-2">No files found</h3>
          <p className="text-ink-muted text-sm">
            {search || category ? 'Try adjusting your filters' : 'Run a scan first to index your files'}
          </p>
        </div>
      ) : (
        <>
          <div className="card overflow-hidden">
            {/* Table header */}
            <div className="grid grid-cols-[1fr_120px_100px_100px_80px] gap-4 px-5 py-3 bg-surface-overlay border-b border-surface-border text-xs font-mono text-ink-faint uppercase tracking-wider">
              <span>Name</span>
              <span>Category</span>
              <span>Size</span>
              <span>Modified</span>
              <span>Quality</span>
            </div>

            {/* Rows */}
            <div className="divide-y divide-surface-border">
              {files.map(file => (
                <FileRow key={file.id} file={file} onRefresh={loadFiles} />
              ))}
            </div>
          </div>

          {/* Pagination */}
          {totalPages > 1 && (
            <div className="flex items-center justify-between mt-5">
              <button
                onClick={() => setPage(p => Math.max(1, p - 1))}
                disabled={page === 1}
                className="btn-ghost flex items-center gap-2 text-sm disabled:opacity-40"
              >
                <ChevronLeft className="w-4 h-4" /> Previous
              </button>
              <span className="text-sm text-ink-muted font-mono">
                Page {page} of {totalPages}
              </span>
              <button
                onClick={() => setPage(p => Math.min(totalPages, p + 1))}
                disabled={page === totalPages}
                className="btn-ghost flex items-center gap-2 text-sm disabled:opacity-40"
              >
                Next <ChevronRight className="w-4 h-4" />
              </button>
            </div>
          )}
        </>
      )}
    </div>
  )
}

// ── File Row ──────────────────────────────────────────────────────────────

function FileRow({ file, onRefresh }: { file: any; onRefresh: () => void }) {
  const [deleting, setDeleting] = useState(false)

  const handleDelete = async () => {
    if (!confirm(`Delete ${file.file_name}?`)) return
    setDeleting(true)
    try {
      await api.delete(`/duplicates/files/${file.id}`)
      toast.success(`Deleted ${file.file_name}`)
      onRefresh()
    } catch {
      toast.error('Delete failed')
    } finally {
      setDeleting(false)
    }
  }

  const fileIcon = getFileIcon(file.mime_type, file.category)

  return (
    <div className="grid grid-cols-[1fr_120px_100px_100px_80px] gap-4 px-5 py-3 items-center hover:bg-surface-overlay/50 group transition-colors">
      {/* Name */}
      <div className="flex items-center gap-3 min-w-0">
        <span className="text-lg shrink-0">{fileIcon}</span>
        <div className="min-w-0">
          <p className="text-sm font-medium truncate">{file.file_name}</p>
          <p className="text-xs text-ink-faint truncate">{file.file_path}</p>
        </div>
      </div>

      {/* Category */}
      <div>
        {file.category && (
          <span className={clsx(
            'text-[10px] font-mono px-2 py-0.5 rounded-full capitalize',
            getCategoryStyle(file.category)
          )}>
            {file.category}
          </span>
        )}
      </div>

      {/* Size */}
      <span className="text-sm font-mono text-ink-muted">{formatBytes(file.file_size)}</span>

      {/* Modified */}
      <span className="text-xs text-ink-faint">{formatDate(file.last_modified)}</span>

      {/* Quality badges + actions */}
      <div className="flex items-center gap-1.5">
        {file.is_blurry && (
          <span className="text-[9px] bg-accent-red/10 text-accent-red px-1.5 py-0.5 rounded-full">blur</span>
        )}
        {file.is_screenshot && (
          <span className="text-[9px] bg-accent-amber/10 text-accent-amber px-1.5 py-0.5 rounded-full">scr</span>
        )}
        <button
          onClick={handleDelete}
          disabled={deleting}
          className="opacity-0 group-hover:opacity-100 p-1 rounded-lg hover:bg-accent-red/10 text-ink-faint hover:text-accent-red transition-all ml-auto"
        >
          <Trash2 className="w-3.5 h-3.5" />
        </button>
      </div>
    </div>
  )
}

// ── Helpers ────────────────────────────────────────────────────────────────

function getFileIcon(mimeType: string | null, category: string | null): string {
  if (category === 'screenshot') return '📸'
  if (category === 'receipt') return '🧾'
  if (mimeType?.startsWith('image/')) return '🖼'
  if (mimeType?.startsWith('video/')) return '🎬'
  if (mimeType?.startsWith('audio/')) return '🎵'
  if (mimeType === 'application/pdf') return '📄'
  if (mimeType?.includes('spreadsheet') || mimeType?.includes('excel')) return '📊'
  if (mimeType?.includes('presentation')) return '📑'
  if (mimeType?.includes('zip') || mimeType?.includes('archive')) return '📦'
  return '📁'
}

function getCategoryStyle(category: string): string {
  const styles: Record<string, string> = {
    photo: 'bg-brand/10 text-brand',
    screenshot: 'bg-accent-amber/10 text-accent-amber',
    document: 'bg-accent-green/10 text-accent-green',
    video: 'bg-purple-400/10 text-purple-400',
    audio: 'bg-pink-400/10 text-pink-400',
    archive: 'bg-ink-muted/10 text-ink-muted',
    receipt: 'bg-accent-red/10 text-accent-red',
    other: 'bg-surface-border text-ink-faint',
  }
  return styles[category] || styles.other
}
