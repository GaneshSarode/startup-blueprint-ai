import { useState } from 'react'
import BMCGrid from './BMCGrid'
import BudgetTab from './BudgetTab'
import GTMTab from './GTMTab'
import InvestorsTab from './InvestorsTab'
import CompetitorsTab from './CompetitorsTab'
import RisksTab from './RisksTab'
import CRAGPipelineTab from './CRAGPipelineTab'
import { blueprintApi } from '../../api/blueprint'
import { useBlueprintStore } from '../../store/blueprintStore'

export default function BlueprintTabs({ 
  bmc, budget, gtm, 
  investors, competitors, risks, 
  cragResult = {}, blueprintId,
  blueprint = {},
  isGenerating = false,
  partialSections = {},
  runningSections = {},
}) {
  const [activeTab, setActiveTab] = useState('bmc')
  const [retryingSection, setRetryingSection] = useState(null)
  const [retryErrors, setRetryErrors] = useState({})
  const updateBlueprintSection = useBlueprintStore((s) => s.updateBlueprintSection)

  const bmcData = (bmc && Object.keys(bmc).length > 0) ? bmc : (partialSections.bmc || blueprint.bmc || blueprint.bmc_data || {})
  const budgetData = (budget && Object.keys(budget).length > 0) ? budget : (partialSections.budget || blueprint.budget || blueprint.budget_data || {})
  const gtmData = (gtm && Object.keys(gtm).length > 0) ? gtm : (partialSections.gtm || blueprint.gtm || blueprint.gtm_data || {})
  const investorsData = (investors && Object.keys(investors).length > 0) ? investors : (partialSections.investors || blueprint.investors || blueprint.funding || blueprint.investor_data || blueprint.funding_data || {})
  const competitorsData = (competitors && Object.keys(competitors).length > 0) ? competitors : (partialSections.competitors || blueprint.competitors || blueprint.competitor_data || {})
  const risksData = (risks && Object.keys(risks).length > 0) ? risks : (partialSections.risks || blueprint.risks || blueprint.risk_data || {})

  const failedSections = blueprint.failed_sections || []

  const isBmcEmpty = !bmcData || Object.values(bmcData).every(v => !v || (Array.isArray(v) && v.length === 0))
  const isBudgetEmpty = !budgetData || !budgetData.phases || budgetData.phases.length === 0
  const isGtmEmpty = !gtmData || (!gtmData.target_market && (!gtmData.launch_strategy || gtmData.launch_strategy.length === 0))
  const isInvestorsEmpty = !investorsData || ((!investorsData.funding_roadmap || investorsData.funding_roadmap.length === 0) && (!investorsData.government_schemes || investorsData.government_schemes.length === 0))
  const isCompetitorsEmpty = !competitorsData || ((!competitorsData.competitors || competitorsData.competitors.length === 0) && (!competitorsData.our_differentiators || competitorsData.our_differentiators.length === 0))
  const isRisksEmpty = !risksData || !risksData.risks || risksData.risks.length === 0

  const handleRetrySection = async (sectionId) => {
    try {
      setRetryingSection(sectionId)
      setRetryErrors((prev) => ({ ...prev, [sectionId]: null }))
      
      const res = await blueprintApi.retrySection({
        blueprint_id: blueprintId || blueprint?.id,
        section: sectionId,
        idea: blueprint?.idea || blueprint?.description || '',
        sector: blueprint?.sector || '',
        stage: blueprint?.stage || '',
        model_type: blueprint?.model_type || '',
        target_city: blueprint?.target_city || '',
      })

      if (res?.data?.success && res?.data?.data) {
        updateBlueprintSection(sectionId, res.data.data)
      } else {
        throw new Error(res?.data?.error || `Retry failed for ${sectionId}`)
      }
    } catch (err) {
      console.error(`Error retrying section ${sectionId}:`, err)
      setRetryErrors((prev) => ({
        ...prev,
        [sectionId]: err.response?.data?.detail || err.message || 'Retry failed'
      }))
    } finally {
      setRetryingSection(null)
    }
  }

  const renderSection = (id, label, component, isEmpty) => {
    if (retryingSection === id) {
      return (
        <div className="p-10 text-center bg-blue-500/[0.03] border border-blue-500/20 rounded-2xl space-y-4">
          <div className="inline-flex items-center justify-center w-12 h-12 rounded-full bg-blue-500/10 text-blue-400 mb-1">
            <svg className="animate-spin h-6 w-6 text-blue-400" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z"></path>
            </svg>
          </div>
          <div className="text-blue-300 font-bold text-base">Retrying {label} Generation…</div>
          <p className="text-xs text-slate-400 max-w-md mx-auto">
            Regenerating strictly validated {label} with grounded CRAG context. The section will render automatically once finished.
          </p>
        </div>
      )
    }

    if (isGenerating && isEmpty && !failedSections.includes(id)) {
      return (
        <div className="p-10 text-center bg-blue-500/[0.03] border border-blue-500/20 rounded-2xl space-y-4">
          <div className="inline-flex items-center justify-center w-12 h-12 rounded-full bg-blue-500/10 text-blue-400 mb-1">
            <svg className="animate-spin h-6 w-6 text-blue-400" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z"></path>
            </svg>
          </div>
          <div className="text-blue-300 font-bold text-base">Synthesizing {label}…</div>
          <p className="text-xs text-slate-400 max-w-md mx-auto">
            Generating grounded analysis using IBM Watsonx GPT-OSS-120B and retrieved CRAG policy context. This tab will update automatically as soon as generation finishes.
          </p>
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-blue-500/10 text-blue-400 text-[0.72rem] font-medium">
            <span className="w-2 h-2 rounded-full bg-blue-400 animate-ping" />
            Parallel section generator active
          </div>
        </div>
      )
    }

    if (failedSections.includes(id) || isEmpty) {
      return (
        <div className="p-8 text-center bg-red-500/[0.03] border border-red-500/20 rounded-xl space-y-3">
          <div className="text-amber-400 font-semibold text-sm">Data unavailable — {label} generation failed</div>
          <p className="text-xs text-slate-400 max-w-md mx-auto">
            The AI model was unable to complete this section or returned an invalid schema. You can retry generating only this section without regenerating the entire blueprint.
          </p>
          {retryErrors[id] && (
            <div className="text-xs text-rose-400 bg-rose-500/10 border border-rose-500/20 rounded-lg p-2 max-w-md mx-auto">
              {retryErrors[id]}
            </div>
          )}
          <div className="pt-2">
            <button
              onClick={() => handleRetrySection(id)}
              disabled={retryingSection === id}
              className="px-4 py-2 text-xs font-semibold rounded-lg bg-blue-600 hover:bg-blue-500 text-white transition-colors inline-flex items-center gap-2 cursor-pointer shadow-lg shadow-blue-500/20"
            >
              <svg className={`w-3.5 h-3.5 ${retryingSection === id ? 'animate-spin' : ''}`} fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
              </svg>
              <span>Retry Generating {label}</span>
            </button>
          </div>
        </div>
      )
    }
    return component
  }

  const cragData = {
    ...(blueprint?.crag_trace || {}),
    ...(cragResult || {}),
  }

  const tabs = [
    { id: 'bmc', label: 'Business Model', isEmpty: isBmcEmpty, component: renderSection('bmc', 'Business Model', <BMCGrid data={bmcData} />, isBmcEmpty) },
    { id: 'budget', label: 'Budget', isEmpty: isBudgetEmpty, component: renderSection('budget', 'Budget', <BudgetTab data={budgetData} />, isBudgetEmpty) },
    { id: 'gtm', label: 'GTM Strategy', isEmpty: isGtmEmpty, component: renderSection('gtm', 'GTM Strategy', <GTMTab data={gtmData} />, isGtmEmpty) },
    { id: 'investors', label: 'Funding', isEmpty: isInvestorsEmpty, component: renderSection('investors', 'Funding', <InvestorsTab data={investorsData} />, isInvestorsEmpty) },
    { id: 'competitors', label: 'Competitors', isEmpty: isCompetitorsEmpty, component: renderSection('competitors', 'Competitors', <CompetitorsTab data={competitorsData} />, isCompetitorsEmpty) },
    { id: 'risks', label: 'Risks', isEmpty: isRisksEmpty, component: renderSection('risks', 'Risks', <RisksTab data={risksData} />, isRisksEmpty) },
    { id: 'crag', label: 'CRAG Trace', isEmpty: false, component: <CRAGPipelineTab data={cragData} /> },
  ]

  return (
    <div className="mt-6 rounded-2xl border border-white/[0.08] overflow-hidden bg-[var(--bg-card)]">
      {/* Tab Navigation */}
      <div className="flex overflow-x-auto no-scrollbar border-b border-white/[0.08] bg-white/[0.015]">
        {tabs.map((t) => {
          const isDone = !t.isEmpty && !failedSections.includes(t.id)
          const isRunning = isGenerating && t.isEmpty && !failedSections.includes(t.id)

          return (
            <button
              key={t.id}
              onClick={() => setActiveTab(t.id)}
              className={`px-5 py-3.5 text-sm font-700 whitespace-nowrap transition-colors border-b-2 flex items-center gap-1.5
                ${activeTab === t.id
                  ? 'text-blue-400 border-blue-500 bg-blue-500/[0.035]'
                  : 'text-slate-500 border-transparent hover:text-slate-300 hover:bg-white/[0.02]'}`}
            >
              <span>{t.label}</span>
              {isGenerating && isDone && (
                <span className="text-[0.65rem] text-emerald-400 bg-emerald-500/10 border border-emerald-500/20 rounded-full px-1.5 py-0.2">
                  ✓
                </span>
              )}
              {isRunning && (
                <span className="w-2 h-2 rounded-full bg-blue-400 animate-pulse" />
              )}
              {failedSections.includes(t.id) && (
                <span className="ml-1.5 px-1.5 py-0.5 text-[0.6rem] bg-red-500/20 text-red-400 rounded-full font-normal">
                  failed
                </span>
              )}
            </button>
          )
        })}
      </div>

      {/* Tab Content */}
      <div className="p-6">
        {tabs.find((t) => t.id === activeTab)?.component}
      </div>
    </div>
  )
}

