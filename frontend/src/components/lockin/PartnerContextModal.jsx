import { useState, useEffect } from 'react'
import {
  X, Target, AlertTriangle, UserCheck, CheckCircle2, Plus,
  Trash2, Edit3, Shield, Loader2, Sparkles, Clock
} from 'lucide-react'
import { lockinApi } from '../../api/lockin'

export default function PartnerContextModal({ isOpen, onClose, blueprintId, onContextUpdated }) {
  const [context, setContext] = useState(null)
  const [loading, setLoading] = useState(false)
  const [saving, setSaving] = useState(false)
  const [activeTab, setActiveTab] = useState('priorities') // 'priorities' | 'blockers' | 'followups'
  const [error, setError] = useState('')
  const [successMsg, setSuccessMsg] = useState('')

  // Form inputs
  const [newPriority, setNewPriority] = useState('')
  const [newBlockerTitle, setNewBlockerTitle] = useState('')
  const [newBlockerDesc, setNewBlockerDesc] = useState('')
  const [newFollowupName, setNewFollowupName] = useState('')
  const [newFollowupEmail, setNewFollowupEmail] = useState('')
  const [newFollowupReason, setNewFollowupReason] = useState('')

  const fetchContext = async () => {
    if (!blueprintId) return
    setLoading(true)
    try {
      const { data } = await lockinApi.getPartnerContext(blueprintId)
      setContext(data)
    } catch (e) {
      setError('Failed to load partner context.')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    if (isOpen) fetchContext()
  }, [isOpen, blueprintId])

  if (!isOpen) return null

  const handleSaveContext = async (updated) => {
    setSaving(true)
    setError('')
    try {
      const { data } = await lockinApi.updatePartnerContext(blueprintId, updated)
      setContext(data)
      setSuccessMsg('✓ Business partner context updated.')
      if (onContextUpdated) onContextUpdated(data)
      setTimeout(() => setSuccessMsg(''), 2000)
    } catch (e) {
      setError(e.response?.data?.detail || 'Failed to update context.')
    } finally {
      setSaving(false)
    }
  }

  // 1. Add / Remove Priorities
  const handleAddPriority = (e) => {
    e.preventDefault()
    if (!newPriority.trim()) return
    const current = context?.weekly_priorities || []
    const updated = [...current, { id: Date.now().toString(), text: newPriority.trim() }]
    setNewPriority('')
    handleSaveContext({ weekly_priorities: updated })
  }

  const handleRemovePriority = (id) => {
    const current = context?.weekly_priorities || []
    const updated = current.filter(p => (typeof p === 'string' ? p !== id : p.id !== id))
    handleSaveContext({ weekly_priorities: updated })
  }

  // 2. Add / Resolve Blockers
  const handleAddBlocker = (e) => {
    e.preventDefault()
    if (!newBlockerTitle.trim()) return
    const current = context?.blockers || []
    const updated = [
      ...current,
      {
        id: `blk_${Date.now()}`,
        title: newBlockerTitle.trim(),
        description: newBlockerDesc.trim(),
        status: 'active',
        created_at: new Date().toISOString(),
      }
    ]
    setNewBlockerTitle('')
    setNewBlockerDesc('')
    handleSaveContext({ blockers: updated })
  }

  const handleToggleBlocker = (id) => {
    const current = context?.blockers || []
    const updated = current.map(b => {
      if (b.id === id) {
        return {
          ...b,
          status: b.status === 'active' ? 'resolved' : 'active',
          resolved_at: b.status === 'active' ? new Date().toISOString() : null,
        }
      }
      return b
    })
    handleSaveContext({ blockers: updated })
  }

  // 3. Add / Complete Follow-ups
  const handleAddFollowup = (e) => {
    e.preventDefault()
    if (!newFollowupName.trim()) return
    const current = context?.pending_followups || []
    const updated = [
      ...current,
      {
        id: `fu_${Date.now()}`,
        contact_name: newFollowupName.trim(),
        contact_email: newFollowupEmail.trim(),
        reason: newFollowupReason.trim(),
        status: 'pending',
        created_at: new Date().toISOString(),
      }
    ]
    setNewFollowupName('')
    setNewFollowupEmail('')
    setNewFollowupReason('')
    handleSaveContext({ pending_followups: updated })
  }

  const handleToggleFollowup = (id) => {
    const current = context?.pending_followups || []
    const updated = current.map(f => {
      if (f.id === id) {
        return {
          ...f,
          status: f.status === 'pending' ? 'completed' : 'pending',
          completed_at: f.status === 'pending' ? new Date().toISOString() : null,
        }
      }
      return f
    })
    handleSaveContext({ pending_followups: updated })
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-md animate-fadeIn">
      <div className="relative w-full max-w-2xl rounded-2xl border border-white/[0.08] bg-[#0c142b] shadow-2xl flex flex-col overflow-hidden max-h-[85vh]">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-white/[0.08] bg-slate-900/60">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-xl bg-purple-500/15 border border-purple-500/30 flex items-center justify-center text-purple-400">
              <Target size={18} />
            </div>
            <div>
              <h3 className="text-base font-900 text-slate-100">Persistent Business Partner Context</h3>
              <p className="text-xs text-slate-400">Your editable priorities, active blockers, and commitments</p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="text-slate-400 hover:text-slate-200 p-1.5 rounded-lg hover:bg-white/[0.05]"
          >
            <X size={18} />
          </button>
        </div>

        {/* Tab Selector */}
        <div className="flex border-b border-white/[0.08] px-6 pt-3 gap-3 bg-slate-900/20">
          {[
            { id: 'priorities', label: 'Weekly Priorities', icon: Target },
            { id: 'blockers', label: 'Blockers & Bottlenecks', icon: AlertTriangle },
            { id: 'followups', label: 'Pending Follow-Ups', icon: UserCheck },
          ].map(t => {
            const Icon = t.icon
            const isActive = activeTab === t.id
            return (
              <button
                key={t.id}
                onClick={() => setActiveTab(t.id)}
                className={`pb-3 text-xs font-bold flex items-center gap-1.5 border-b-2 transition-all
                  ${isActive ? 'border-purple-500 text-purple-300' : 'border-transparent text-slate-400 hover:text-slate-200'}`}
              >
                <Icon size={14} /> {t.label}
              </button>
            )
          })}
        </div>

        {/* Status / Alert */}
        {error && (
          <div className="px-6 py-2 bg-red-500/10 border-b border-red-500/20 text-xs text-red-300">
            {error}
          </div>
        )}
        {successMsg && (
          <div className="px-6 py-2 bg-emerald-500/10 border-b border-emerald-500/20 text-xs text-emerald-300">
            {successMsg}
          </div>
        )}

        {/* Content Body */}
        <div className="flex-1 p-6 space-y-4 overflow-y-auto">
          {loading ? (
            <div className="py-12 text-center text-slate-500 text-xs">
              <Loader2 size={18} className="animate-spin mx-auto mb-2 opacity-50" /> Loading context...
            </div>
          ) : activeTab === 'priorities' ? (
            /* TAB 1: PRIORITIES */
            <div className="space-y-4">
              <form onSubmit={handleAddPriority} className="flex gap-2">
                <input
                  type="text"
                  placeholder="Add a weekly priority (e.g. Conduct 5 customer interviews)..."
                  value={newPriority}
                  onChange={(e) => setNewPriority(e.target.value)}
                  className="flex-1 px-3.5 py-2.5 rounded-xl bg-slate-900 border border-white/[0.08] text-xs text-slate-100 focus:outline-none focus:border-purple-500"
                />
                <button
                  type="submit"
                  disabled={saving || !newPriority.trim()}
                  className="px-4 py-2.5 rounded-xl text-xs font-bold text-white bg-purple-600 hover:bg-purple-500 transition-all flex items-center gap-1"
                >
                  <Plus size={14} /> Add
                </button>
              </form>

              <div className="space-y-2">
                {(context?.weekly_priorities || []).length === 0 ? (
                  <p className="text-xs text-slate-500 italic py-4 text-center">
                    No weekly priorities added yet. Add items above to guide daily briefings.
                  </p>
                ) : (
                  context?.weekly_priorities?.map((p, idx) => {
                    const text = typeof p === 'string' ? p : p.text
                    const id = typeof p === 'string' ? p : p.id
                    return (
                      <div
                        key={id || idx}
                        className="flex items-center justify-between p-3 rounded-xl bg-white/[0.02] border border-white/[0.06]"
                      >
                        <span className="text-xs text-slate-200 font-medium flex items-center gap-2">
                          <span className="w-1.5 h-1.5 rounded-full bg-purple-400" />
                          {text}
                        </span>
                        <button
                          onClick={() => handleRemovePriority(id)}
                          className="text-slate-500 hover:text-red-400 transition-colors p-1"
                        >
                          <Trash2 size={13} />
                        </button>
                      </div>
                    )
                  })
                )}
              </div>
            </div>
          ) : activeTab === 'blockers' ? (
            /* TAB 2: BLOCKERS */
            <div className="space-y-4">
              <form onSubmit={handleAddBlocker} className="p-3.5 rounded-xl border border-white/[0.06] bg-white/[0.015] space-y-2.5">
                <div className="text-xs font-bold text-slate-300">Record an Active Blocker</div>
                <input
                  type="text"
                  placeholder="Blocker Title (e.g. Waiting on third-party payment gateway approval)"
                  value={newBlockerTitle}
                  onChange={(e) => setNewBlockerTitle(e.target.value)}
                  className="w-full px-3 py-2 rounded-lg bg-slate-900 border border-white/[0.08] text-xs text-slate-100 focus:outline-none focus:border-amber-500"
                />
                <textarea
                  rows={2}
                  placeholder="Description or dependencies..."
                  value={newBlockerDesc}
                  onChange={(e) => setNewBlockerDesc(e.target.value)}
                  className="w-full px-3 py-2 rounded-lg bg-slate-900 border border-white/[0.08] text-xs text-slate-100 focus:outline-none focus:border-amber-500"
                />
                <button
                  type="submit"
                  disabled={saving || !newBlockerTitle.trim()}
                  className="px-4 py-2 rounded-lg text-xs font-bold text-amber-950 bg-amber-400 hover:bg-amber-300 transition-all flex items-center gap-1"
                >
                  <Plus size={13} /> Add Blocker
                </button>
              </form>

              <div className="space-y-2">
                {(context?.blockers || []).length === 0 ? (
                  <p className="text-xs text-slate-500 italic py-4 text-center">
                    No active blockers recorded. Great execution momentum!
                  </p>
                ) : (
                  context?.blockers?.map((b) => {
                    const isResolved = b.status === 'resolved'
                    return (
                      <div
                        key={b.id}
                        className={`p-3 rounded-xl border transition-all flex items-start justify-between gap-3
                          ${isResolved ? 'bg-white/[0.01] border-white/[0.04] opacity-60' : 'bg-amber-500/[0.04] border-amber-500/25'}`}
                      >
                        <div>
                          <div className={`text-xs font-bold ${isResolved ? 'text-slate-400 line-through' : 'text-amber-200'}`}>
                            {b.title}
                          </div>
                          {b.description && (
                            <div className="text-[0.7rem] text-slate-400 mt-0.5">{b.description}</div>
                          )}
                        </div>
                        <button
                          onClick={() => handleToggleBlocker(b.id)}
                          className={`text-[0.68rem] px-2.5 py-1 rounded-lg font-bold border transition-all flex-shrink-0
                            ${isResolved ? 'border-white/10 text-slate-400' : 'border-amber-500/30 text-amber-300 hover:bg-amber-500/10'}`}
                        >
                          {isResolved ? 'Resolved' : 'Mark Resolved'}
                        </button>
                      </div>
                    )
                  })
                )}
              </div>
            </div>
          ) : (
            /* TAB 3: FOLLOWUPS */
            <div className="space-y-4">
              <form onSubmit={handleAddFollowup} className="p-3.5 rounded-xl border border-white/[0.06] bg-white/[0.015] space-y-2.5">
                <div className="text-xs font-bold text-slate-300">Add Pending Follow-Up Commitment</div>
                <div className="grid grid-cols-2 gap-2">
                  <input
                    type="text"
                    placeholder="Contact Name"
                    value={newFollowupName}
                    onChange={(e) => setNewFollowupName(e.target.value)}
                    className="px-3 py-2 rounded-lg bg-slate-900 border border-white/[0.08] text-xs text-slate-100 focus:outline-none"
                  />
                  <input
                    type="email"
                    placeholder="Contact Email (Optional)"
                    value={newFollowupEmail}
                    onChange={(e) => setNewFollowupEmail(e.target.value)}
                    className="px-3 py-2 rounded-lg bg-slate-900 border border-white/[0.08] text-xs text-slate-100 focus:outline-none"
                  />
                </div>
                <input
                  type="text"
                  placeholder="Reason / Context (e.g. Follow up on API partnership proposal)"
                  value={newFollowupReason}
                  onChange={(e) => setNewFollowupReason(e.target.value)}
                  className="w-full px-3 py-2 rounded-lg bg-slate-900 border border-white/[0.08] text-xs text-slate-100 focus:outline-none"
                />
                <button
                  type="submit"
                  disabled={saving || !newFollowupName.trim()}
                  className="px-4 py-2 rounded-lg text-xs font-bold text-white bg-blue-600 hover:bg-blue-500 transition-all flex items-center gap-1"
                >
                  <Plus size={13} /> Add Follow-Up
                </button>
              </form>

              <div className="space-y-2">
                {(context?.pending_followups || []).length === 0 ? (
                  <p className="text-xs text-slate-500 italic py-4 text-center">
                    No pending follow-ups recorded.
                  </p>
                ) : (
                  context?.pending_followups?.map((f) => {
                    const isDone = f.status === 'completed'
                    return (
                      <div
                        key={f.id}
                        className={`p-3 rounded-xl border transition-all flex items-center justify-between gap-3
                          ${isDone ? 'bg-white/[0.01] border-white/[0.04] opacity-60' : 'bg-blue-500/[0.03] border-blue-500/25'}`}
                      >
                        <div>
                          <div className={`text-xs font-bold ${isDone ? 'text-slate-400 line-through' : 'text-slate-100'}`}>
                            {f.contact_name} {f.contact_email && <span className="text-slate-500 font-normal">({f.contact_email})</span>}
                          </div>
                          {f.reason && (
                            <div className="text-[0.7rem] text-slate-400 mt-0.5">{f.reason}</div>
                          )}
                        </div>
                        <button
                          onClick={() => handleToggleFollowup(f.id)}
                          className={`text-[0.68rem] px-2.5 py-1 rounded-lg font-bold border transition-all flex-shrink-0
                            ${isDone ? 'border-white/10 text-slate-400' : 'border-blue-500/30 text-blue-300 hover:bg-blue-500/10'}`}
                        >
                          {isDone ? 'Done' : 'Mark Done'}
                        </button>
                      </div>
                    )
                  })
                )}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
