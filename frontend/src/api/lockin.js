import client from './client'

export const lockinApi = {
  // Sync roadmap and completion state with backend
  syncRoadmap: (blueprintId, roadmap, completedTasks) =>
    client.post('/api/lock-in/sync', {
      blueprint_id: Number(blueprintId),
      roadmap,
      completed_tasks: completedTasks,
    }),

  // Get full agent status, metrics, Gmail status, and activity
  getStatus: (blueprintId) =>
    client.get(`/api/lock-in/status/${blueprintId}`),

  // Google OAuth URL
  getConnectUrl: (blueprintId) =>
    client.get(`/api/lock-in/gmail/connect?blueprint_id=${blueprintId}`),

  // Send verified test email
  sendTestEmail: () =>
    client.post('/api/lock-in/gmail/test'),

  // Disconnect Gmail
  disconnectGmail: () =>
    client.post('/api/lock-in/gmail/disconnect'),

  // Preferences
  getPreferences: (blueprintId) =>
    client.get(`/api/lock-in/${blueprintId}/preferences`),

  updatePreferences: (blueprintId, prefs) =>
    client.put(`/api/lock-in/${blueprintId}/preferences`, prefs),

  // Persistent Partner Context
  getPartnerContext: (blueprintId) =>
    client.get(`/api/lock-in/${blueprintId}/partner-context`),

  updatePartnerContext: (blueprintId, context) =>
    client.put(`/api/lock-in/${blueprintId}/partner-context`, context),

  // Email Workspace & Outbound Drafts
  getDrafts: (blueprintId, status) => {
    const q = status ? `?status=${status}` : ''
    return client.get(`/api/lock-in/${blueprintId}/drafts${q}`)
  },

  createDraft: (blueprintId, draftData) =>
    client.post(`/api/lock-in/${blueprintId}/drafts`, draftData),

  updateDraft: (blueprintId, draftId, updates) =>
    client.put(`/api/lock-in/${blueprintId}/drafts/${draftId}`, updates),

  sendDraft: (blueprintId, draftId) =>
    client.post(`/api/lock-in/${blueprintId}/drafts/${draftId}/send`),

  discardDraft: (blueprintId, draftId) =>
    client.post(`/api/lock-in/${blueprintId}/drafts/${draftId}/discard`),

  // Proactive Briefing & Weekly Review
  getBriefing: (blueprintId) =>
    client.get(`/api/lock-in/${blueprintId}/briefing`),

  getWeeklyReview: (blueprintId) =>
    client.get(`/api/lock-in/${blueprintId}/weekly-review`),

  // Activity & Notification Logs
  getActivity: (blueprintId) =>
    client.get(`/api/lock-in/${blueprintId}/activity`),

  // HITL Recommendations
  getRecommendations: (blueprintId) =>
    client.get(`/api/lock-in/${blueprintId}/recommendations`),

  approveRecommendation: (blueprintId, actionId) =>
    client.post(`/api/lock-in/${blueprintId}/recommendations/${actionId}/approve`),

  rejectRecommendation: (blueprintId, actionId) =>
    client.post(`/api/lock-in/${blueprintId}/recommendations/${actionId}/reject`),

  // Manual Trigger (for testing / demo)
  runAgentNow: (blueprintId, notificationType = 'daily') =>
    client.post(`/api/lock-in/${blueprintId}/run-agent-now?notification_type=${notificationType}`),
}
