import { useState, useEffect } from 'react'
import {
  X, Mail, Send, CheckCircle2, AlertTriangle, Trash2, Edit3,
  Sparkles, Clock, RefreshCw, ChevronRight, User, Shield, Loader2, Plus
} from 'lucide-react'
import { lockinApi } from '../../api/lockin'

export default function EmailWorkspaceModal({ isOpen, onClose, blueprintId, onDraftSent }) {
  const [drafts, setDrafts] = useState([])
  const [loading, setLoading] = useState(false)
  const [selectedDraft, setSelectedDraft] = useState(null)
  const [activeTab, setActiveTab] = useState('pending_approval') // 'pending_approval' | 'sent' | 'all'
  const [actionLoading, setActionLoading] = useState(false)
  const [error, setError] = useState('')
  const [successMsg, setSuccessMsg] = useState('')
  const [composeMode, setComposeMode] = useState(false)

  // New draft form state
  const [newWorkflow, setNewWorkflow] = useState('followup')
  const [newRecipient, setNewRecipient] = useState('')
  const [newSubject, setNewSubject] = useState('')
  const [newContent, setNewContent] = useState('')

  const fetchDrafts = async () => {
    if (!blueprintId) return
    setLoading(true)
    setError('')
    try {
      const statusFilter = activeTab === 'all' ? null : activeTab
      const { data } = await lockinApi.getDrafts(blueprintId, statusFilter)
      const list = data.drafts || []
      setDrafts(list)
      if (list.length > 0 && !selectedDraft) {
        setSelectedDraft(list[0])
      } else if (selectedDraft) {
        // Refresh selected draft in view
        const updated = list.find(d => d.id === selectedDraft.id)
        if (updated) setSelectedDraft(updated)
      }
    } catch (e) {
      setError(e.response?.data?.detail || 'Failed to load drafts.')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    if (isOpen) {
      fetchDrafts()
    }
  }, [isOpen, blueprintId, activeTab])

  if (!isOpen) return null

  // Approve & Send
  const handleApproveAndSend = async () => {
    if (!selectedDraft) return
    setActionLoading(true)
    setError('')
    setSuccessMsg('')
    try {
      const { data } = await lockinApi.sendDraft(blueprintId, selectedDraft.id)
      setSuccessMsg(`✓ Email successfully sent to ${selectedDraft.recipient}!`)
      if (onDraftSent) onDraftSent(data)
      setTimeout(() => {
        fetchDrafts()
        setSuccessMsg('')
      }, 1200)
    } catch (e) {
      setError(e.response?.data?.detail || 'Failed to send email. Check Gmail connection.')
    } finally {
      setActionLoading(false)
    }
  }

  // Save edits
  const handleSaveDraftEdits = async () => {
    if (!selectedDraft) return
    setActionLoading(true)
    setError('')
    try {
      const { data } = await lockinApi.updateDraft(blueprintId, selectedDraft.id, {
        recipient: selectedDraft.recipient,
        subject: selectedDraft.subject,
        body_text: selectedDraft.body_text,
      })
      setSelectedDraft(data.draft)
      setSuccessMsg('✓ Draft changes saved.')
      fetchDrafts()
      setTimeout(() => setSuccessMsg(''), 2000)
    } catch (e) {
      setError(e.response?.data?.detail || 'Failed to update draft.')
    } finally {
      setActionLoading(false)
    }
  }

  // Discard draft
  const handleDiscard = async () => {
    if (!selectedDraft) return
    if (!window.confirm('Are you sure you want to discard this email draft?')) return
    setActionLoading(true)
    try {
      await lockinApi.discardDraft(blueprintId, selectedDraft.id)
      setSelectedDraft(null)
      fetchDrafts()
    } catch (e) {
      setError(e.response?.data?.detail || 'Failed to discard draft.')
    } finally {
      setActionLoading(false)
    }
  }

  // Create custom draft
  const handleCreateCustomDraft = async (e) => {
    e.preventDefault()
    if (!newRecipient || !newSubject) {
      setError('Please provide recipient email and subject.')
      return
    }
    setActionLoading(true)
    setError('')
    try {
      const { data } = await lockinApi.createDraft(blueprintId, {
        workflow_type: newWorkflow,
        recipient: newRecipient,
        subject: newSubject,
        body_text: newContent,
      })
      setComposeMode(false)
      setNewRecipient('')
      setNewSubject('')
      setNewContent('')
      setSelectedDraft(data.draft)
      fetchDrafts()
      setSuccessMsg('✓ New draft created in workspace.')
      setTimeout(() => setSuccessMsg(''), 2500)
    } catch (e) {
      setError(e.response?.data?.detail || 'Failed to create draft.')
    } finally {
      setActionLoading(false)
    }
  }

  const getWorkflowBadge = (wf) => {
    const map = {
      daily_briefing: { label: 'Daily Briefing', color: 'bg-blue-500/15 text-blue-300 border-blue-500/30' },
      weekly_review: { label: 'Weekly Review', color: 'bg-purple-500/15 text-purple-300 border-purple-500/30' },
      followup: { label: 'Follow-Up', color: 'bg-emerald-500/15 text-emerald-300 border-emerald-500/30' },
      meeting_request: { label: 'Meeting Request', color: 'bg-indigo-500/15 text-indigo-300 border-indigo-500/30' },
      progress_update: { label: 'Progress Update', color: 'bg-teal-500/15 text-teal-300 border-teal-500/30' },
      networking_outreach: { label: 'Outreach', color: 'bg-amber-500/15 text-amber-300 border-amber-500/30' },
      deadline: { label: 'Deadline Alert', color: 'bg-red-500/15 text-red-300 border-red-500/30' },
    }
    return map[wf] || { label: wf, color: 'bg-slate-700/50 text-slate-300 border-white/10' }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-3 sm:p-6 bg-black/80 backdrop-blur-md animate-fadeIn">
      <div className="relative w-full max-w-5xl h-[88vh] rounded-2xl border border-white/[0.08] bg-[#0c1326] shadow-2xl flex flex-col overflow-hidden">
        {/* Top Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-white/[0.08] bg-slate-900/60">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-xl bg-gradient-to-br from-blue-600 to-indigo-700 flex items-center justify-center text-white shadow-glow-blue flex-shrink-0">
              <Mail size={18} />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h3 className="text-base font-900 text-slate-100 tracking-tight">LOCK IN Email Workspace</h3>
                <span className="text-[0.65rem] px-2 py-0.5 rounded-full bg-emerald-500/15 text-emerald-300 border border-emerald-500/30 font-bold uppercase">
                  Human-in-the-Loop
                </span>
              </div>
              <p className="text-xs text-slate-400">Review, edit, and approve natural AI-crafted emails before dispatch</p>
            </div>
          </div>

          <div className="flex items-center gap-2">
            <button
              onClick={() => setComposeMode(!composeMode)}
              className="px-3 py-1.5 rounded-lg text-xs font-700 text-blue-300 bg-blue-500/10 hover:bg-blue-500/20 border border-blue-500/30 flex items-center gap-1.5 transition-all"
            >
              <Plus size={14} /> {composeMode ? 'View Drafts' : 'New Draft'}
            </button>
            <button
              onClick={onClose}
              className="text-slate-400 hover:text-slate-200 p-1.5 rounded-lg hover:bg-white/[0.05]"
            >
              <X size={18} />
            </button>
          </div>
        </div>

        {/* Status / Alert Banner */}
        {error && (
          <div className="px-6 py-2.5 bg-red-500/10 border-b border-red-500/20 text-xs font-medium text-red-300 flex items-center justify-between">
            <span className="flex items-center gap-2">
              <AlertTriangle size={14} className="text-red-400 flex-shrink-0" /> {error}
            </span>
            <button onClick={() => setError('')} className="text-slate-400 hover:text-white">✕</button>
          </div>
        )}
        {successMsg && (
          <div className="px-6 py-2.5 bg-emerald-500/10 border-b border-emerald-500/20 text-xs font-medium text-emerald-300 flex items-center gap-2">
            <CheckCircle2 size={14} className="text-emerald-400 flex-shrink-0" /> {successMsg}
          </div>
        )}

        {/* Compose Mode Form */}
        {composeMode ? (
          <form onSubmit={handleCreateCustomDraft} className="flex-1 p-6 space-y-4 overflow-y-auto">
            <h4 className="text-sm font-800 text-slate-100 flex items-center gap-2">
              <Edit3 size={15} className="text-blue-400" /> Draft New Business Outreach Email
            </h4>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <label className="text-[0.7rem] uppercase font-bold text-slate-400 block mb-1">Workflow Type</label>
                <select
                  value={newWorkflow}
                  onChange={(e) => setNewWorkflow(e.target.value)}
                  className="w-full px-3 py-2 rounded-xl bg-slate-900 border border-white/[0.08] text-xs text-slate-200 focus:outline-none focus:border-blue-500"
                >
                  <option value="followup">Follow-Up (Pending Commitment)</option>
                  <option value="meeting_request">Meeting Request (With Agenda)</option>
                  <option value="progress_update">Progress Update (Verified Milestones)</option>
                  <option value="networking_outreach">Mentor & Networking Outreach</option>
                  <option value="daily_briefing">Daily Briefing</option>
                </select>
              </div>

              <div>
                <label className="text-[0.7rem] uppercase font-bold text-slate-400 block mb-1">Recipient Email</label>
                <input
                  type="email"
                  required
                  placeholder="advisor@example.com"
                  value={newRecipient}
                  onChange={(e) => setNewRecipient(e.target.value)}
                  className="w-full px-3 py-2 rounded-xl bg-slate-900 border border-white/[0.08] text-xs text-slate-200 focus:outline-none focus:border-blue-500"
                />
              </div>
            </div>

            <div>
              <label className="text-[0.7rem] uppercase font-bold text-slate-400 block mb-1">Subject Line</label>
              <input
                type="text"
                required
                placeholder="Concise, natural subject line"
                value={newSubject}
                onChange={(e) => setNewSubject(e.target.value)}
                className="w-full px-3 py-2 rounded-xl bg-slate-900 border border-white/[0.08] text-xs text-slate-200 focus:outline-none focus:border-blue-500"
              />
            </div>

            <div>
              <label className="text-[0.7rem] uppercase font-bold text-slate-400 block mb-1">Email Body Content</label>
              <textarea
                rows={8}
                placeholder="Write message content or leave blank to auto-compose from roadmap context..."
                value={newContent}
                onChange={(e) => setNewContent(e.target.value)}
                className="w-full p-3 rounded-xl bg-slate-900 border border-white/[0.08] text-xs text-slate-200 font-mono leading-relaxed focus:outline-none focus:border-blue-500"
              />
            </div>

            <div className="flex justify-end gap-3 pt-2">
              <button
                type="button"
                onClick={() => setComposeMode(false)}
                className="px-4 py-2 rounded-xl text-xs font-semibold text-slate-400 hover:text-white"
              >
                Cancel
              </button>
              <button
                type="submit"
                disabled={actionLoading}
                className="px-5 py-2.5 rounded-xl text-xs font-bold text-white bg-blue-600 hover:bg-blue-500 flex items-center gap-1.5 shadow-lg shadow-blue-600/30"
              >
                {actionLoading ? <Loader2 size={14} className="animate-spin" /> : <Sparkles size={14} />} Create Draft
              </button>
            </div>
          </form>
        ) : (
          /* Split View: Left List, Right Editor */
          <div className="flex-1 flex flex-col md:flex-row overflow-hidden">
            {/* Left Drafts List */}
            <div className="w-full md:w-80 border-r border-white/[0.08] flex flex-col bg-[#080d1b]">
              {/* Filter Tabs */}
              <div className="flex border-b border-white/[0.06] p-2 gap-1 bg-slate-900/30">
                {[
                  { id: 'pending_approval', label: 'Pending Approval' },
                  { id: 'sent', label: 'Sent' },
                  { id: 'all', label: 'All' },
                ].map(t => (
                  <button
                    key={t.id}
                    onClick={() => setActiveTab(t.id)}
                    className={`flex-1 py-1.5 px-2 rounded-lg text-[0.7rem] font-bold transition-all
                      ${activeTab === t.id ? 'bg-blue-500/20 text-blue-300 border border-blue-500/30' : 'text-slate-400 hover:text-slate-200'}`}
                  >
                    {t.label}
                  </button>
                ))}
              </div>

              {/* Items List */}
              <div className="flex-1 overflow-y-auto p-2 space-y-1.5">
                {loading ? (
                  <div className="py-12 text-center text-slate-500 text-xs">
                    <Loader2 size={18} className="animate-spin mx-auto mb-2 opacity-50" /> Loading drafts...
                  </div>
                ) : drafts.length === 0 ? (
                  <div className="py-12 text-center text-slate-500 text-xs px-4">
                    <Clock size={20} className="mx-auto mb-2 opacity-40" />
                    No drafts in this view.
                  </div>
                ) : (
                  drafts.map((d) => {
                    const isSelected = selectedDraft?.id === d.id
                    const badge = getWorkflowBadge(d.workflow_type)
                    const isPending = d.status === 'pending_approval'

                    return (
                      <div
                        key={d.id}
                        onClick={() => setSelectedDraft(d)}
                        className={`p-3 rounded-xl border cursor-pointer transition-all text-left
                          ${isSelected
                            ? 'bg-blue-500/10 border-blue-500/40 shadow-sm'
                            : 'bg-white/[0.015] border-white/[0.05] hover:bg-white/[0.03] hover:border-white/10'}`}
                      >
                        <div className="flex items-center justify-between mb-1.5">
                          <span className={`text-[0.6rem] px-2 py-0.5 rounded-md border font-extrabold uppercase ${badge.color}`}>
                            {badge.label}
                          </span>
                          <span className="text-[0.62rem] text-slate-500">
                            {d.created_at ? new Date(d.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : ''}
                          </span>
                        </div>
                        <div className="text-xs font-bold text-slate-200 truncate">
                          {d.subject || '(Untitled Draft)'}
                        </div>
                        <div className="text-[0.68rem] text-slate-400 truncate mt-0.5">
                          To: {d.recipient}
                        </div>
                        {isPending && (
                          <div className="mt-2 flex items-center gap-1 text-[0.62rem] font-bold text-amber-400">
                            <span className="w-1.5 h-1.5 rounded-full bg-amber-400 animate-pulse" /> Review & Approval Required
                          </div>
                        )}
                      </div>
                    )
                  })
                )}
              </div>
            </div>

            {/* Right Draft Preview & Action Editor */}
            <div className="flex-1 flex flex-col bg-[#0b1328] overflow-hidden">
              {selectedDraft ? (
                <div className="flex-1 flex flex-col overflow-hidden p-6 space-y-4">
                  {/* Top Meta info */}
                  <div className="space-y-3 pb-3 border-b border-white/[0.06]">
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <div className="flex items-center gap-2">
                        <span className={`text-xs px-2.5 py-0.5 rounded-md border font-extrabold uppercase ${getWorkflowBadge(selectedDraft.workflow_type).color}`}>
                          {getWorkflowBadge(selectedDraft.workflow_type).label}
                        </span>
                        <span className="text-xs font-bold text-slate-400">
                          Status: <strong className={selectedDraft.status === 'sent' ? 'text-emerald-400' : 'text-amber-400'}>{selectedDraft.status?.replace('_', ' ')}</strong>
                        </span>
                      </div>
                      <div className="text-xs text-slate-500 font-mono">
                        Draft #{selectedDraft.id}
                      </div>
                    </div>

                    {/* Recipient */}
                    <div className="flex items-center gap-2 bg-white/[0.02] p-2 rounded-xl border border-white/[0.05]">
                      <span className="text-xs font-bold text-slate-400 w-16">To:</span>
                      <input
                        type="email"
                        value={selectedDraft.recipient || ''}
                        disabled={selectedDraft.status === 'sent'}
                        onChange={(e) => setSelectedDraft({ ...selectedDraft, recipient: e.target.value })}
                        className="flex-1 bg-transparent text-xs font-semibold text-slate-100 focus:outline-none"
                      />
                    </div>

                    {/* Subject */}
                    <div className="flex items-center gap-2 bg-white/[0.02] p-2 rounded-xl border border-white/[0.05]">
                      <span className="text-xs font-bold text-slate-400 w-16">Subject:</span>
                      <input
                        type="text"
                        value={selectedDraft.subject || ''}
                        disabled={selectedDraft.status === 'sent'}
                        onChange={(e) => setSelectedDraft({ ...selectedDraft, subject: e.target.value })}
                        className="flex-1 bg-transparent text-xs font-bold text-slate-100 focus:outline-none"
                      />
                    </div>
                  </div>

                  {/* Body Text Editor */}
                  <div className="flex-1 flex flex-col min-h-0">
                    <label className="text-[0.68rem] font-bold uppercase tracking-wider text-slate-400 mb-1 flex items-center justify-between">
                      <span>Message Content (Editable)</span>
                      <span className="text-slate-500 font-normal">What you see is what will be sent</span>
                    </label>
                    <textarea
                      value={selectedDraft.body_text || ''}
                      disabled={selectedDraft.status === 'sent'}
                      onChange={(e) => setSelectedDraft({ ...selectedDraft, body_text: e.target.value })}
                      className="flex-1 p-4 rounded-xl bg-slate-950/70 border border-white/[0.08] text-xs text-slate-200 font-mono leading-relaxed resize-none focus:outline-none focus:border-blue-500/50"
                    />
                  </div>

                  {/* Actions Footer */}
                  <div className="pt-3 border-t border-white/[0.06] flex flex-wrap items-center justify-between gap-3">
                    <div className="flex items-center gap-2">
                      {selectedDraft.status !== 'sent' && (
                        <>
                          <button
                            onClick={handleSaveDraftEdits}
                            disabled={actionLoading}
                            className="px-4 py-2 rounded-xl text-xs font-bold text-slate-300 hover:text-white bg-white/[0.04] hover:bg-white/[0.08] border border-white/[0.08] transition-all"
                          >
                            Save Edits
                          </button>
                          <button
                            onClick={handleDiscard}
                            disabled={actionLoading}
                            className="px-3 py-2 rounded-xl text-xs font-bold text-red-400 hover:text-red-300 bg-red-500/5 hover:bg-red-500/15 border border-red-500/20 transition-all flex items-center gap-1.5"
                          >
                            <Trash2 size={13} /> Discard
                          </button>
                        </>
                      )}
                    </div>

                    {selectedDraft.status !== 'sent' ? (
                      <button
                        onClick={handleApproveAndSend}
                        disabled={actionLoading}
                        className="px-6 py-2.5 rounded-xl text-xs font-bold text-white bg-gradient-to-r from-emerald-600 to-teal-600 hover:from-emerald-500 hover:to-teal-500 shadow-lg shadow-emerald-600/30 flex items-center gap-2 transition-all"
                      >
                        {actionLoading ? (
                          <>
                            <Loader2 size={14} className="animate-spin" /> Sending via Gmail...
                          </>
                        ) : (
                          <>
                            <Send size={14} /> Approve & Send Now
                          </>
                        )}
                      </button>
                    ) : (
                      <span className="text-xs font-bold text-emerald-400 flex items-center gap-1.5">
                        <CheckCircle2 size={15} /> Sent via Gmail (Msg ID: {selectedDraft.sent_message_id || 'sent'})
                      </span>
                    )}
                  </div>
                </div>
              ) : (
                <div className="flex-1 flex flex-col items-center justify-center text-slate-500 text-xs">
                  <Mail size={32} className="opacity-30 mb-2" />
                  Select an email draft from the left panel to preview or approve.
                </div>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
