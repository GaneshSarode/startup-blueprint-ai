import { create } from 'zustand'

export const useBlueprintStore = create((set) => ({
  // Current blueprint output
  current:          null,
  // Generation state
  generating:       false,
  generationId:     null,
  progress:         0,
  currentStep:      '',
  currentNode:      '',
  error:            null,
  // Abort controller for cancellation
  abortCtrl:        null,
  // Incremental streaming partial results
  partialSections:  {},
  runningSections:  {},
  cragResult:       null,
  timings:          null,

  setGenerating:     (generating) => set({ generating }),
  setGenerationId:   (generationId) => set({ generationId }),
  setProgress:       (progress, step, node) => set({ progress, currentStep: step, currentNode: node }),
  setSectionStarted: (section) => set((s) => ({
    runningSections: { ...s.runningSections, [section]: true },
  })),
  setPartialSection: (section, data) => set((s) => ({
    partialSections: { ...s.partialSections, [section]: data },
    runningSections: { ...s.runningSections, [section]: false },
  })),
  setCragResult:     (cragResult) => set((s) => ({
    cragResult: { ...(s.cragResult || {}), ...cragResult },
  })),
  setError:          (error) => set({ error, generating: false }),
  setBlueprint:      (blueprint) => set({
    current: blueprint,
    generating: false,
    progress: 100,
    error: null,
    timings: blueprint?.timings || null,
  }),
  setAbortCtrl:      (ctrl) => set({ abortCtrl: ctrl }),
  updateBlueprintSection: (section, data) => set((s) => {
    if (!s.current) return s
    const updated = JSON.parse(JSON.stringify(s.current))
    if (updated.blueprint) {
      updated.blueprint[section] = data
      if (Array.isArray(updated.blueprint.failed_sections)) {
        updated.blueprint.failed_sections = updated.blueprint.failed_sections.filter((sec) => sec !== section)
      }
    } else {
      updated[section] = data
      if (Array.isArray(updated.failed_sections)) {
        updated.failed_sections = updated.failed_sections.filter((sec) => sec !== section)
      }
    }
    return { current: updated }
  }),

  reset: () => set({
    generating: false,
    generationId: null,
    progress: 0,
    currentStep: '',
    currentNode: '',
    error: null,
    partialSections: {},
    runningSections: {},
    cragResult: null,
    timings: null,
  }),

  abort: () => set((s) => {
    s.abortCtrl?.abort()
    return {
      generating: false,
      progress: 0,
      currentStep: '',
      error: 'Generation cancelled',
      runningSections: {},
    }
  }),
}))