import { useCallback, useRef } from 'react'
import { useBlueprintStore } from '../store/blueprintStore'
import { generateBlueprint as generateBlueprintApi } from '../api/blueprint'
import { historyApi } from '../api/history'

/**
 * useBlueprint — custom hook wrapping blueprintStore + generateBlueprint SSE call.
 *
 * Returns { current, generating, progress, currentStep, error, generate, cancel, reset }
 */
export function useBlueprint() {
  const {
    current, generating, progress, currentStep, currentNode, error,
    partialSections, runningSections, cragResult, timings,
    setGenerating, setProgress, setError, setBlueprint, setAbortCtrl, reset,
    setSectionStarted, setPartialSection, setCragResult,
  } = useBlueprintStore()

  const abortRef = useRef(null)

  const fetchGeneratedBlueprint = async (data) => {
    const blueprintId = data?.blueprint_id || data?.id
    if (!blueprintId) {
      setBlueprint(data)
      return
    }

    let attempts = 0
    const maxAttempts = 3
    const delayMs = 400

    while (attempts < maxAttempts) {
      attempts++
      try {
        const res = await historyApi.getById(blueprintId)
        if (res?.data) {
          const fetched = res.data
          const merged = {
            ...data,
            ...fetched,
            blueprint_id: blueprintId,
            blueprint: {
              bmc: fetched.bmc_data || data?.blueprint?.bmc || {},
              budget: fetched.budget_data || data?.blueprint?.budget || {},
              gtm: fetched.gtm_data || data?.blueprint?.gtm || {},
              investors: fetched.investor_data || data?.blueprint?.investors || {},
              competitors: fetched.competitor_data || data?.blueprint?.competitors || {},
              risks: fetched.risk_data || data?.blueprint?.risks || {},
              crag_trace: data?.blueprint?.crag_trace || {},
            },
            crag_result: data?.crag_result || {
              confidence: fetched.confidence,
              summary: fetched.summary,
              sources: fetched.sources || [],
              raw_logits: fetched.raw_logits || [],
              rewritten_query: fetched.rewritten_query || '',
              keywords: fetched.keywords || [],
              explore_results: fetched.explore_results || [],
              internal_context: fetched.internal_context || '',
              external_context: fetched.external_context || '',
            }
          }
          setBlueprint(merged)
          return
        }
      } catch (err) {
        console.warn(`Fetch blueprint attempt ${attempts} failed:`, err)
      }
      if (attempts < maxAttempts) {
        await new Promise((r) => setTimeout(r, delayMs))
      }
    }

    if (data) {
      setBlueprint(data)
    } else {
      setError("Failed to load newly created blueprint")
    }
  }

  const generate = useCallback((payload) => {
    reset()
    setGenerating(true)

    const ctrl = generateBlueprintApi(payload, {
      onStage: (event) => {
        if (event.data?.crag_result) {
          setCragResult(event.data.crag_result)
        }
      },
      onSectionStarted: (section) => {
        setSectionStarted(section)
      },
      onSection: (section, data) => {
        setPartialSection(section, data)
      },
      onProgress: ({ step, node, progress: p, data }) => {
        setProgress(p, step, node)
        if (data?.crag_result) {
          setCragResult(data.crag_result)
        }
      },
      onComplete: (data) => fetchGeneratedBlueprint(data),
      onError: (msg) => setError(msg),
    })

    abortRef.current = ctrl
    setAbortCtrl(ctrl)
    return ctrl
  }, [reset, setGenerating, setProgress, setBlueprint, setError, setAbortCtrl, setSectionStarted, setPartialSection, setCragResult])

  const cancel = useCallback(() => {
    abortRef.current?.abort()
    reset()
  }, [reset])

  return {
    current,
    generating,
    progress,
    currentStep,
    currentNode,
    error,
    partialSections,
    runningSections,
    cragResult,
    timings,
    generate,
    cancel,
    reset,
  }
}
