'use client'

import { useEffect, useState } from 'react'
import { api, formatDate } from '@/lib/api'
import { Sidebar } from '@/components/layout/Sidebar'
import { Toaster } from 'react-hot-toast'
import toast from 'react-hot-toast'
import { Key, Plus, Trash2, Copy, Eye, EyeOff, RefreshCw, Shield } from 'lucide-react'
import clsx from 'clsx'
import { useAuthStore } from '@/lib/store'

export default function ApiKeysPage() {
  return (
    <div className="flex h-screen overflow-hidden">
      <Sidebar />
      <main className="flex-1 overflow-y-auto bg-surface">
        <ApiKeysContent />
      </main>
      <Toaster position="bottom-right" toastOptions={{
        style: { background: '#13161e', color: '#f0f2ff', border: '1px solid #252a38' },
        success: { iconTheme: { primary: '#1de9a4', secondary: '#0d0f14' } },
      }} />
    </div>
  )
}

function ApiKeysContent() {
  const { user } = useAuthStore()
  const [keys, setKeys] = useState<any[]>([])
  const [loading, setLoading] = useState(true)
  const [creating, setCreating] = useState(false)
  const [newKeyName, setNewKeyName] = useState('')
  const [newKeyScopes, setNewKeyScopes] = useState(['read'])
  const [revealedKey, setRevealedKey] = useState<string | null>(null)
  const [showCreate, setShowCreate] = useState(false)

  const loadKeys = async () => {
    try {
      const res = await api.get('/api-keys')
      setKeys(res.data)
    } catch { }
    finally { setLoading(false) }
  }

  useEffect(() => { loadKeys() }, [])

  const handleCreate = async () => {
    if (!newKeyName.trim()) return toast.error('Enter a name for this key')
    setCreating(true)
    try {
      const res = await api.post('/api-keys', { name: newKeyName, scopes: newKeyScopes })
      setRevealedKey(res.data.key)
      setNewKeyName('')
      setNewKeyScopes(['read'])
      setShowCreate(false)
      await loadKeys()
      toast.success('API key created — save it now!')
    } catch (err: any) {
      toast.error(err?.response?.data?.detail || 'Failed to create key')
    } finally {
      setCreating(false)
    }
  }

  const handleRevoke = async (keyId: string, name: string) => {
    if (!confirm(`Revoke "${name}"? Any scripts using this key will stop working.`)) return
    try {
      await api.delete(`/api-keys/${keyId}`)
      setKeys(prev => prev.filter(k => k.id !== keyId))
      toast.success('API key revoked')
    } catch {
      toast.error('Failed to revoke key')
    }
  }

  if (!user?.is_pro) {
    return (
      <div className="p-8 max-w-3xl">
        <ProGate />
      </div>
    )
  }

  return (
    <div className="p-8 space-y-6 animate-fade-in max-w-3xl">
      {/* Header */}
      <div className="flex items-start justify-between">
        <div>
          <h1 className="font-display text-3xl font-bold flex items-center gap-3">
            <Key className="w-7 h-7 text-brand" />
            API Keys
          </h1>
          <p className="text-ink-muted mt-1">Use API keys for programmatic access to Declutter</p>
        </div>
        <button onClick={() => setShowCreate(true)} className="btn-primary flex items-center gap-2">
          <Plus className="w-4 h-4" /> New Key
        </button>
      </div>

      {/* One-time revealed key banner */}
      {revealedKey && (
        <div className="card p-5 border-accent-green/30 bg-accent-green/5">
          <div className="flex items-start gap-3 mb-3">
            <Shield className="w-5 h-5 text-accent-green shrink-0 mt-0.5" />
            <div>
              <p className="font-semibold text-accent-green">Save your API key now</p>
              <p className="text-sm text-ink-muted mt-0.5">This key will only be shown once. Store it somewhere safe.</p>
            </div>
          </div>
          <div className="bg-surface rounded-xl p-3 font-mono text-sm text-ink break-all flex items-center gap-3">
            <span className="flex-1">{revealedKey}</span>
            <button
              onClick={() => { navigator.clipboard.writeText(revealedKey); toast.success('Copied!') }}
              className="shrink-0 p-2 hover:bg-surface-overlay rounded-lg transition-colors"
            >
              <Copy className="w-4 h-4 text-brand" />
            </button>
          </div>
          <button onClick={() => setRevealedKey(null)} className="mt-3 text-xs text-ink-faint hover:text-ink-muted">
            I've saved it — dismiss
          </button>
        </div>
      )}

      {/* Create key form */}
      {showCreate && (
        <div className="card p-5 space-y-4">
          <h3 className="font-semibold">Create new API key</h3>
          <input
            className="input"
            placeholder="Key name (e.g. My Script, CI/CD Pipeline)"
            value={newKeyName}
            onChange={e => setNewKeyName(e.target.value)}
            onKeyDown={e => e.key === 'Enter' && handleCreate()}
          />

          <div>
            <p className="text-xs text-ink-muted mb-2">Scopes</p>
            <div className="flex gap-2 flex-wrap">
              {['read', 'write', 'delete'].map(scope => (
                <button
                  key={scope}
                  onClick={() => setNewKeyScopes(prev =>
                    prev.includes(scope) ? prev.filter(s => s !== scope) : [...prev, scope]
                  )}
                  className={clsx(
                    'text-xs px-3 py-1.5 rounded-xl border transition-colors font-mono',
                    newKeyScopes.includes(scope)
                      ? 'bg-brand/15 text-brand border-brand/30'
                      : 'bg-surface-overlay text-ink-muted border-surface-border'
                  )}
                >
                  {scope}
                </button>
              ))}
            </div>
          </div>

          <div className="flex gap-2">
            <button onClick={handleCreate} disabled={creating} className="btn-primary flex items-center gap-2">
              {creating ? <RefreshCw className="w-4 h-4 animate-spin" /> : <Plus className="w-4 h-4" />}
              {creating ? 'Creating…' : 'Create Key'}
            </button>
            <button onClick={() => setShowCreate(false)} className="btn-ghost">Cancel</button>
          </div>
        </div>
      )}

      {/* Keys list */}
      {loading ? (
        <div className="space-y-2">
          {[...Array(3)].map((_, i) => (
            <div key={i} className="h-20 bg-surface-raised rounded-xl animate-pulse" />
          ))}
        </div>
      ) : keys.length === 0 ? (
        <div className="card p-10 text-center">
          <Key className="w-8 h-8 text-ink-faint mx-auto mb-3" />
          <p className="text-ink-muted">No API keys yet. Create one to get started.</p>
        </div>
      ) : (
        <div className="space-y-2">
          {keys.map(k => (
            <div key={k.id} className="card p-4 flex items-center gap-4">
              <div className="w-9 h-9 rounded-xl bg-brand/10 flex items-center justify-center shrink-0">
                <Key className="w-4 h-4 text-brand" />
              </div>

              <div className="flex-1 min-w-0">
                <p className="font-medium text-sm">{k.name}</p>
                <div className="flex items-center gap-2 mt-0.5">
                  <span className="font-mono text-xs text-ink-faint">{k.prefix}••••••••</span>
                  {k.scopes.map((s: string) => (
                    <span key={s} className="text-[9px] font-mono bg-surface-overlay text-ink-faint px-1.5 py-0.5 rounded-full">
                      {s}
                    </span>
                  ))}
                </div>
              </div>

              <div className="text-right text-xs text-ink-faint shrink-0">
                <p>{k.last_used_at ? `Used ${formatDate(k.last_used_at)}` : 'Never used'}</p>
                <p>Created {formatDate(k.created_at)}</p>
              </div>

              <button
                onClick={() => handleRevoke(k.id, k.name)}
                className="p-2 rounded-xl hover:bg-accent-red/10 text-ink-faint hover:text-accent-red transition-colors"
              >
                <Trash2 className="w-4 h-4" />
              </button>
            </div>
          ))}
        </div>
      )}

      {/* Docs */}
      <div className="card p-5 text-sm">
        <h3 className="font-semibold mb-3">Using your API key</h3>
        <pre className="bg-surface rounded-xl p-4 text-xs font-mono text-ink-muted overflow-x-auto">
{`curl -H "Authorization: Bearer dcl_your_key_here" \\
  https://api.declutter.app/api/v1/dashboard/summary`}
        </pre>
        <p className="text-ink-faint text-xs mt-3">
          API keys authenticate as your user account with the specified scopes.
          Keep them secret — don't commit to version control.
        </p>
      </div>
    </div>
  )
}

function ProGate() {
  return (
    <div className="card p-12 flex flex-col items-center text-center">
      <div className="w-16 h-16 rounded-2xl bg-brand/10 flex items-center justify-center mb-5">
        <Key className="w-8 h-8 text-brand" />
      </div>
      <h2 className="font-display text-xl font-bold mb-2">API Access requires Pro</h2>
      <p className="text-ink-muted max-w-sm">
        Generate API keys to automate your cleanup workflows and integrate Declutter into your tools.
      </p>
      <a href="/settings" className="btn-primary mt-6">Upgrade to Pro</a>
    </div>
  )
}
