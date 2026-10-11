import client from './client'

export const deepResearchApi = {
  /**
   * Run deep research synchronously (fallback).
   * @param {{ blueprint_id: number, focus?: string, force_refresh?: boolean }} payload
   */
  run: (payload) => client.post('/api/deep-research/start', payload),

  /**
   * Fetch cached deep research results for a blueprint.
   * @param {number} blueprintId
   * @param {string} [focus]
   */
  getResults: (blueprintId, focus = 'FULL_STARTUP_ANALYSIS') => 
    client.get(`/api/deep-research/${blueprintId}/results`, { params: { focus } }),

  /**
   * Stream deep research execution via fetch() + ReadableStream.
   * Uses POST with Authorization: Bearer <token> header.
   */
  stream: (payload, { onProgress, onComplete, onError }) => {
    const token = localStorage.getItem('access_token')
    const baseUrl = import.meta.env.VITE_API_URL || ''
    const ctrl = new AbortController()

    fetch(`${baseUrl}/api/deep-research/stream`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${token}`,
        'Accept': 'text/event-stream',
      },
      body: JSON.stringify(payload),
      signal: ctrl.signal,
    })
      .then(async (res) => {
        if (!res.ok) {
          const errText = await res.text().catch(() => '')
          let detail = `Server error ${res.status}`
          try {
            const parsed = JSON.parse(errText)
            if (parsed.detail) detail = parsed.detail
          } catch (e) {}
          onError(detail)
          return
        }

        const reader = res.body.getReader()
        const decoder = new TextDecoder()
        let buffer = ''

        while (true) {
          const { done, value } = await reader.read()
          if (done) break

          buffer += decoder.decode(value, { stream: true })
          const lines = buffer.split('\n\n')
          buffer = lines.pop()

          for (const line of lines) {
            const trimmed = line.trim()
            if (!trimmed.startsWith('data: ')) continue
            try {
              const eventData = JSON.parse(trimmed.slice(6))
              if (eventData.event === 'progress') {
                onProgress(eventData)
              } else if (eventData.event === 'complete') {
                let reportData = eventData.data
                if (typeof reportData === 'string') {
                  try { reportData = JSON.parse(reportData) } catch (e) {}
                }
                onComplete(reportData)
              } else if (eventData.event === 'error') {
                onError(eventData.error || 'Deep Research failed')
              }
            } catch (e) {
              console.warn('Deep Research SSE parse error:', e)
            }
          }
        }
      })
      .catch((err) => {
        if (err.name !== 'AbortError') onError(err.message || 'Network error')
      })

    return ctrl
  }
}
