import client from './client'

export const blueprintApi = {
  getById: (id) => client.get(`/api/blueprint/${id}`),
  getNews:  (q) => client.get('/api/blueprint/news/feed', { params: { q } }),
  retrySection: (payload) => client.post('/api/blueprint/retry-section', payload),
  retrySectionById: (id, payload) => client.post(`/api/blueprint/${id}/retry-section`, payload),
}

/**
 * generateBlueprint — SSE streaming blueprint generation.
 *
 * Uses fetch() + ReadableStream because EventSource doesn't support POST.
 * Calls onProgress(event) for each SSE frame, onComplete(blueprint) when done,
 * onError(message) on failure.
 *
 * Returns an AbortController so the caller can cancel mid-stream.
 */
export function generateBlueprint(
  payload,
  { onProgress, onStage, onSection, onSectionStarted, onComplete, onError }
) {
  const token = localStorage.getItem('access_token')
  const baseUrl = import.meta.env.VITE_API_URL || ''
  const ctrl = new AbortController()
  let hasCompleted = false
  let hasErrored = false

  fetch(`${baseUrl}/api/blueprint/generate`, {
    method:  'POST',
    headers: {
      'Content-Type':  'application/json',
      Authorization:   `Bearer ${token}`,
    },
    body:   JSON.stringify(payload),
    signal: ctrl.signal,
  })
    .then(async (res) => {
      if (!res.ok) {
        const err = await res.json().catch(() => ({}))
        if (!hasErrored) {
          hasErrored = true
          onError?.(err.detail || `Server error ${res.status}`)
        }
        return
      }

      const reader  = res.body.getReader()
      const decoder = new TextDecoder()
      let   buffer  = ''

      while (true) {
        const { done, value } = await reader.read()
        if (done) break

        buffer += decoder.decode(value, { stream: true })
        const lines = buffer.split('\n\n')
        buffer = lines.pop()   // keep incomplete last chunk

        for (const line of lines) {
          const trimmed = line.trim()
          if (!trimmed.startsWith('data: ')) continue
          try {
            const event = JSON.parse(trimmed.slice(6))
            const eventType = event.event

            if (eventType === 'progress') {
              onProgress?.(event)
            } else if (eventType === 'stage_started' || eventType === 'stage_completed') {
              onStage?.(event)
              onProgress?.({
                step: event.message || event.stage,
                node: event.stage,
                progress: event.progress,
                data: event.data,
              })
            } else if (eventType === 'section_started') {
              onSectionStarted?.(event.section)
              onProgress?.({
                step: event.message || `Generating ${event.section}...`,
                node: `generate_${event.section}`,
                progress: event.progress,
                section: event.section,
              })
            } else if (eventType === 'section_completed') {
              onSection?.(event.section, event.data)
              onProgress?.({
                step: event.message || `Completed ${event.section}`,
                node: `generate_${event.section}`,
                progress: event.progress,
                section: event.section,
                data: event.data,
              })
            } else if (eventType === 'complete' || eventType === 'generation_completed') {
              if (!hasCompleted) {
                hasCompleted = true
                let dataPayload = event.data
                if (typeof dataPayload === 'string') {
                  try { dataPayload = JSON.parse(dataPayload) } catch (e) {}
                }
                onComplete?.(dataPayload)
              }
            } else if (eventType === 'error' || eventType === 'generation_failed') {
              if (!hasErrored) {
                hasErrored = true
                onError?.(event.error || event.message || 'Generation failed')
              }
            }
          } catch (e) {
            console.warn('SSE parse error:', e)
          }
        }
      }
    })
    .catch((err) => {
      if (err.name !== 'AbortError' && !hasErrored) {
        hasErrored = true
        onError?.(err.message || 'Network error')
      }
    })

  return ctrl   // caller can call ctrl.abort() to cancel
}