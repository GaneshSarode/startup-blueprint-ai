import { useState, useEffect } from 'react'
import { X, Bell, Clock, Globe, Shield, CheckCircle2, Loader2 } from 'lucide-react'
import { lockinApi } from '../../api/lockin'

export default function NotificationSettingsModal({ isOpen, onClose, blueprintId, currentPreferences, onUpdated }) {
  const [prefs, setPrefs] = useState({
    email_enabled: true,
    daily_reminder_enabled: true,
    deadline_alert_enabled: true,
    weekly_report_enabled: true,
    recovery_enabled: true,
    reminder_time: '09:00',
    timezone: Intl.DateTimeFormat().resolvedOptions().timeZone || 'Asia/Kolkata',
    automation_mode: 'approve_before_sending',
    is_paused: false,
    daily_send_limit: 5,
    trusted_contacts: [],
  })
  const [saving, setSaving] = useState(false)
  const [savedSuccess, setSavedSuccess] = useState(false)
  const [error, setError] = useState('')
  const [newTrustedEmail, setNewTrustedEmail] = useState('')
  const [newTrustedName, setNewTrustedName] = useState('')

  useEffect(() => {
    if (currentPreferences) {
      setPrefs(prev => ({
        ...prev,
        ...currentPreferences,
        timezone: currentPreferences.timezone || Intl.DateTimeFormat().resolvedOptions().timeZone || 'Asia/Kolkata',
        automation_mode: currentPreferences.automation_mode || 'approve_before_sending',
        is_paused: currentPreferences.is_paused || false,
        daily_send_limit: currentPreferences.daily_send_limit || 5,
        trusted_contacts: currentPreferences.trusted_contacts || [],
      }))
    }
  }, [currentPreferences, isOpen])

  if (!isOpen) return null

  const handleSave = async () => {
    setSaving(true)
    setError('')
    try {
      const { data } = await lockinApi.updatePreferences(blueprintId, prefs)
      setSavedSuccess(true)
      if (onUpdated) onUpdated(data)
      setTimeout(() => {
        setSavedSuccess(false)
        onClose()
      }, 800)
    } catch (e) {
      setError(e.response?.data?.detail || 'Failed to save preferences.')
    } finally {
      setSaving(false)
    }
  }

  const toggle = (key) => {
    setPrefs(p => ({ ...p, [key]: !p[key] }))
  }

  const handleAddTrustedContact = (e) => {
    e.preventDefault()
    if (!newTrustedEmail.trim()) return
    const current = prefs.trusted_contacts || []
    setPrefs(p => ({
      ...p,
      trusted_contacts: [...current, { name: newTrustedName.trim() || 'Contact', email: newTrustedEmail.trim() }]
    }))
    setNewTrustedEmail('')
    setNewTrustedName('')
  }

  const handleRemoveTrustedContact = (emailToRemove) => {
    setPrefs(p => ({
      ...p,
      trusted_contacts: (p.trusted_contacts || []).filter(c => c.email !== emailToRemove)
    }))
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/75 backdrop-blur-sm animate-fadeIn">
      <div className="relative w-full max-w-lg rounded-2xl border border-white/[0.08] bg-[#0f172a] shadow-2xl overflow-hidden">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-white/[0.08] bg-slate-900/50">
          <div className="flex items-center gap-2.5">
            <div className="w-8 h-8 rounded-xl bg-blue-500/15 border border-blue-500/30 flex items-center justify-center text-blue-400">
              <Bell size={16} />
            </div>
            <div>
              <h3 className="text-base font-800 text-slate-100">Automation & Notification Controls</h3>
              <p className="text-xs text-slate-400">Configure business partner autonomy, dispatch time, and trusted contacts</p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="text-slate-400 hover:text-slate-200 p-1 rounded-lg hover:bg-white/[0.05] transition-colors"
          >
            <X size={18} />
          </button>
        </div>

        {/* Form Body */}
        <div className="p-6 space-y-4 max-h-[70vh] overflow-y-auto">
          {error && (
            <div className="p-3 rounded-xl bg-red-500/10 border border-red-500/25 text-xs text-red-400">
              {error}
            </div>
          )}

          {/* Emergency Stop / Pause Switch */}
          <div className="rounded-xl border border-red-500/25 bg-red-500/[0.04] p-3.5 flex items-center justify-between">
            <div>
              <div className="text-xs font-800 text-red-300 uppercase tracking-wide flex items-center gap-1.5">
                <Shield size={14} /> Emergency Pause Control
              </div>
              <div className="text-[0.7rem] text-slate-400 mt-0.5">
                Immediately halts all scheduled evaluations and automated email dispatches
              </div>
            </div>
            <button
              type="button"
              onClick={() => toggle('is_paused')}
              className={`px-3 py-1.5 rounded-lg text-xs font-bold border transition-all
                ${prefs.is_paused ? 'bg-red-500 text-white border-red-600' : 'bg-white/[0.05] text-slate-300 border-white/10 hover:bg-white/[0.08]'}`}
            >
              {prefs.is_paused ? 'PAUSED' : 'Active'}
            </button>
          </div>

          {/* Autonomy Mode Selector */}
          <div className="rounded-xl border border-white/[0.06] bg-white/[0.02] p-3.5 space-y-2">
            <div className="text-xs font-800 text-slate-200 uppercase tracking-wide">
              Automation Mode
            </div>
            <select
              value={prefs.automation_mode}
              onChange={(e) => setPrefs(p => ({ ...p, automation_mode: e.target.value }))}
              className="w-full px-3 py-2 rounded-lg bg-slate-900 border border-white/[0.1] text-xs text-slate-100 font-semibold focus:outline-none focus:border-blue-500"
            >
              <option value="approve_before_sending">Approve Before Sending (Default & Recommended)</option>
              <option value="draft_only">Draft Only (Agent creates drafts, never sends)</option>
              <option value="trusted_automation">Trusted Automation (Auto-send to trusted contacts only)</option>
            </select>
            <p className="text-[0.67rem] text-slate-400 leading-relaxed">
              {prefs.automation_mode === 'approve_before_sending' && '• Every outbound email is queued in the Email Workspace for your explicit review and one-click send.'}
              {prefs.automation_mode === 'draft_only' && '• The agent drafts emails but will never transmit messages through Gmail.'}
              {prefs.automation_mode === 'trusted_automation' && '• Automated dispatch is permitted ONLY for verified recipients in your Trusted Contacts list below.'}
            </p>
          </div>

          {/* Timezone Info */}
          <div className="rounded-xl border border-white/[0.06] bg-white/[0.02] p-3.5 flex items-center justify-between">
            <div className="flex items-center gap-2.5">
              <Globe size={16} className="text-blue-400" />
              <div>
                <div className="text-xs font-700 text-slate-300">Detected Timezone</div>
                <div className="text-[0.7rem] text-slate-500">{prefs.timezone}</div>
              </div>
            </div>
            <span className="text-[0.65rem] px-2 py-0.5 rounded-full bg-blue-500/10 text-blue-300 border border-blue-500/20 font-mono">
              Auto-Synced
            </span>
          </div>

          {/* Daily Reminder Time */}
          <div className="rounded-xl border border-white/[0.06] bg-white/[0.02] p-3.5 flex items-center justify-between">
            <div className="flex items-center gap-2.5">
              <Clock size={16} className="text-purple-400" />
              <div>
                <div className="text-xs font-700 text-slate-300">Daily Mission Dispatch Time</div>
                <div className="text-[0.7rem] text-slate-500">Scheduled briefing delivery hour</div>
              </div>
            </div>
            <input
              type="time"
              value={prefs.reminder_time || '09:00'}
              onChange={(e) => setPrefs(p => ({ ...p, reminder_time: e.target.value }))}
              className="bg-slate-800 border border-white/10 text-slate-200 text-xs font-bold rounded-lg px-2.5 py-1.5 focus:border-blue-500 outline-none"
            />
          </div>

          {/* Trusted Contacts Section (for Trusted Automation mode) */}
          {prefs.automation_mode === 'trusted_automation' && (
            <div className="rounded-xl border border-amber-500/25 bg-amber-500/[0.03] p-3.5 space-y-3">
              <div className="flex items-center justify-between">
                <span className="text-xs font-800 text-amber-300 uppercase tracking-wide">
                  Trusted Contacts List
                </span>
                <span className="text-[0.65rem] text-slate-400">
                  Limit: {prefs.daily_send_limit || 5} / day
                </span>
              </div>

              <div className="flex gap-2">
                <input
                  type="text"
                  placeholder="Name"
                  value={newTrustedName}
                  onChange={(e) => setNewTrustedName(e.target.value)}
                  className="w-1/3 px-2.5 py-1.5 rounded-lg bg-slate-900 border border-white/10 text-xs text-slate-200"
                />
                <input
                  type="email"
                  placeholder="email@example.com"
                  value={newTrustedEmail}
                  onChange={(e) => setNewTrustedEmail(e.target.value)}
                  className="flex-1 px-2.5 py-1.5 rounded-lg bg-slate-900 border border-white/10 text-xs text-slate-200"
                />
                <button
                  type="button"
                  onClick={handleAddTrustedContact}
                  className="px-3 py-1.5 rounded-lg text-xs font-bold text-amber-950 bg-amber-400 hover:bg-amber-300"
                >
                  Add
                </button>
              </div>

              <div className="space-y-1.5 max-h-28 overflow-y-auto">
                {(prefs.trusted_contacts || []).length === 0 ? (
                  <p className="text-[0.7rem] text-slate-500 italic">No trusted contacts configured yet.</p>
                ) : (
                  prefs.trusted_contacts.map((c, idx) => (
                    <div key={idx} className="flex items-center justify-between p-2 rounded-lg bg-white/[0.02] border border-white/[0.05] text-xs">
                      <span className="text-slate-200">{c.name} <span className="text-slate-500 font-mono">({c.email})</span></span>
                      <button
                        type="button"
                        onClick={() => handleRemoveTrustedContact(c.email)}
                        className="text-slate-500 hover:text-red-400"
                      >
                        ✕
                      </button>
                    </div>
                  ))
                )}
              </div>
            </div>
          )}

          {/* Notification Channel Toggles */}
          <div className="space-y-2 pt-2">
            {/* Daily Accountability */}
            <div
              onClick={() => toggle('daily_reminder_enabled')}
              className="flex items-center justify-between p-3 rounded-xl border border-white/[0.05] bg-white/[0.015] hover:bg-white/[0.03] cursor-pointer transition-colors"
            >
              <div>
                <div className="text-xs font-700 text-slate-200">Daily Proactive Briefing</div>
                <div className="text-[0.7rem] text-slate-400">Personalized daily priority tasks grounded in roadmap context</div>
              </div>
              <div className={`w-11 h-6 rounded-full transition-colors relative flex items-center px-0.5 ${prefs.daily_reminder_enabled ? 'bg-blue-600' : 'bg-slate-700'}`}>
                <div className={`w-5 h-5 rounded-full bg-white transition-transform ${prefs.daily_reminder_enabled ? 'translate-x-5' : 'translate-x-0'}`} />
              </div>
            </div>

            {/* Deadline Alerts */}
            <div
              onClick={() => toggle('deadline_alert_enabled')}
              className="flex items-center justify-between p-3 rounded-xl border border-white/[0.05] bg-white/[0.015] hover:bg-white/[0.03] cursor-pointer transition-colors"
            >
              <div>
                <div className="text-xs font-700 text-slate-200">Milestone & Deadline Alerts</div>
                <div className="text-[0.7rem] text-slate-400">Proactive warnings before critical weekly milestone deadlines</div>
              </div>
              <div className={`w-11 h-6 rounded-full transition-colors relative flex items-center px-0.5 ${prefs.deadline_alert_enabled ? 'bg-blue-600' : 'bg-slate-700'}`}>
                <div className={`w-5 h-5 rounded-full bg-white transition-transform ${prefs.deadline_alert_enabled ? 'translate-x-5' : 'translate-x-0'}`} />
              </div>
            </div>

            {/* Weekly Progress Report */}
            <div
              onClick={() => toggle('weekly_report_enabled')}
              className="flex items-center justify-between p-3 rounded-xl border border-white/[0.05] bg-white/[0.015] hover:bg-white/[0.03] cursor-pointer transition-colors"
            >
              <div>
                <div className="text-xs font-700 text-slate-200">Weekly Business Partner Reviews</div>
                <div className="text-[0.7rem] text-slate-400">Planned vs completed breakdown with verified progress scores</div>
              </div>
              <div className={`w-11 h-6 rounded-full transition-colors relative flex items-center px-0.5 ${prefs.weekly_report_enabled ? 'bg-blue-600' : 'bg-slate-700'}`}>
                <div className={`w-5 h-5 rounded-full bg-white transition-transform ${prefs.weekly_report_enabled ? 'translate-x-5' : 'translate-x-0'}`} />
              </div>
            </div>

            {/* Recovery Recommendations */}
            <div
              onClick={() => toggle('recovery_enabled')}
              className="flex items-center justify-between p-3 rounded-xl border border-white/[0.05] bg-white/[0.015] hover:bg-white/[0.03] cursor-pointer transition-colors"
            >
              <div>
                <div className="text-xs font-700 text-slate-200">AI Recovery Recommendations (HITL)</div>
                <div className="text-[0.7rem] text-slate-400">Proposes schedule recovery plans if falling behind (requires your approval)</div>
              </div>
              <div className={`w-11 h-6 rounded-full transition-colors relative flex items-center px-0.5 ${prefs.recovery_enabled ? 'bg-blue-600' : 'bg-slate-700'}`}>
                <div className={`w-5 h-5 rounded-full bg-white transition-transform ${prefs.recovery_enabled ? 'translate-x-5' : 'translate-x-0'}`} />
              </div>
            </div>
          </div>
        </div>

        {/* Footer Actions */}
        <div className="flex items-center justify-end gap-2.5 px-6 py-4 border-t border-white/[0.08] bg-slate-900/60">
          <button
            onClick={onClose}
            className="px-4 py-2 rounded-xl text-xs font-700 text-slate-400 hover:text-slate-200 hover:bg-white/[0.05] transition-colors"
          >
            Cancel
          </button>
          <button
            onClick={handleSave}
            disabled={saving}
            className="px-5 py-2 rounded-xl text-xs font-800 text-white bg-gradient-to-r from-blue-600 to-indigo-600 hover:from-blue-500 hover:to-indigo-500 shadow-lg shadow-blue-600/25 flex items-center gap-1.5 transition-all"
          >
            {saving ? (
              <>
                <Loader2 size={14} className="animate-spin" /> Saving...
              </>
            ) : savedSuccess ? (
              <>
                <CheckCircle2 size={14} className="text-emerald-400" /> Saved!
              </>
            ) : (
              'Save Preferences'
            )}
          </button>
        </div>
      </div>
    </div>
  )
}
