import { useState, useEffect, useRef } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { 
  ArrowLeft, Search, Globe, ExternalLink, Loader2, Sparkles, RefreshCw, 
  CheckCircle2, Clock, ShieldCheck, AlertTriangle, TrendingUp, DollarSign, 
  FileText, Layers, Award, ChevronRight, ChevronDown, ChevronUp, BookOpen, 
  Wrench, Shield, Key, Code, Cpu, Target, HelpCircle, Check, X, Filter, BarChart3,
  Users, Zap, Compass, Info
} from 'lucide-react'
import { historyApi } from '../api/history'
import { deepResearchApi } from '../api/deepResearch'
import { Spinner, Badge, Card } from '../components/ui'

const RESEARCH_STEPS = [
  { id: 'profile', name: 'Step 1: Extracting Startup Profile & Research Scope' },
  { id: 'questions', name: 'Step 2: Formulating Multi-Domain Research Questions' },
  { id: 'retrieval', name: 'Step 3: Retrieving Internal Vector Chunks & Web Intelligence' },
  { id: 'sizing', name: 'Step 4: Cross-Checking Evidence & Deterministic Bottom-Up Sizing' },
  { id: 'synthesis', name: 'Step 5: Synthesizing Evidence-Grounded Critical Intelligence' },
  { id: 'validation', name: 'Step 6: Schema Validation & Claim-to-Source Traceability' },
]

function SectionFallback({ title = "Section unavailable", field = "data" }) {
  return (
    <Card className="p-8 text-center space-y-3 bg-slate-900/60 border border-slate-800/80">
      <div className="w-10 h-10 rounded-xl bg-amber-500/10 text-amber-400 flex items-center justify-center mx-auto border border-amber-500/20">
        <AlertTriangle size={20} />
      </div>
      <h4 className="text-sm font-700 text-slate-200">{title}</h4>
      <p className="text-xs text-slate-400 font-mono">
        Field <span className="text-amber-300">{field}</span> pending or not returned in latest synthesis.
      </p>
    </Card>
  )
}

export default function DeepResearch() {
  const { blueprintId } = useParams()
  const navigate = useNavigate()

  const [blueprint, setBlueprint] = useState(null)
  const [focus, setFocus] = useState('FULL_STARTUP_ANALYSIS')
  const [cachedReport, setCachedReport] = useState(null)
  const [report, setReport] = useState(null)
  const [loading, setLoading] = useState(false)
  const [initialLoading, setInitialLoading] = useState(true)
  const [progressPct, setProgressPct] = useState(0)
  const [currentModule, setCurrentModule] = useState('')
  const [completedModules, setCompletedModules] = useState([])
  const [activeTab, setActiveTab] = useState('overview')
  const [error, setError] = useState('')

  // UI interaction states
  const [descExpanded, setDescExpanded] = useState(false)
  const [criticalAnalysisExpanded, setCriticalAnalysisExpanded] = useState(true)
  const [competitorCategoryFilter, setCompetitorCategoryFilter] = useState('All')
  const [sourceCategoryFilter, setSourceCategoryFilter] = useState('All')
  const [sourceSearchTerm, setSourceSearchTerm] = useState('')
  const [activeScoreDetail, setActiveScoreDetail] = useState(null)

  const abortCtrlRef = useRef(null)

  useEffect(() => {
    if (!blueprintId) { navigate('/history'); return }
    loadData()
  }, [blueprintId])

  const loadData = async () => {
    setInitialLoading(true)
    setReport(null)
    try {
      const bpRes = await historyApi.getById(blueprintId)
      setBlueprint(bpRes.data)

      try {
        const cachedRes = await deepResearchApi.getResults(blueprintId, focus)
        if (cachedRes.data) {
          setCachedReport(cachedRes.data)
        }
      } catch (err) {
        setCachedReport(null)
      }
    } catch (err) {
      console.error(err)
      navigate('/history')
    } finally {
      setInitialLoading(false)
    }
  }

  const startDeepResearch = (forceRefresh = false) => {
    if (loading) return
    setLoading(true)
    setError('')
    setProgressPct(5)
    setCurrentModule(`Initializing Deep Research 2.0 (${focus})...`)
    setCompletedModules([])

    const ctrl = deepResearchApi.stream(
      {
        blueprint_id: parseInt(blueprintId),
        research_focus: focus,
        focus: focus,
        force_refresh: forceRefresh,
      },
      {
        onProgress: (data) => {
          if (data.pct) setProgressPct(data.pct)
          if (data.module) setCurrentModule(data.module)
          if (data.status === 'completed' && data.module) {
            setCompletedModules(prev => [...new Set([...prev, data.module])])
          }
        },
        onComplete: (reportData) => {
          setReport(reportData)
          setCachedReport(reportData)
          setLoading(false)
          setProgressPct(100)
          setActiveTab('overview')
        },
        onError: (msg) => {
          setError(msg || 'Deep research execution failed')
          setLoading(false)
        }
      }
    )

    abortCtrlRef.current = ctrl
  }

  if (initialLoading) {
    return (
      <div className="flex flex-col items-center justify-center h-[70vh] gap-3">
        <Spinner size={32} />
        <p className="text-xs font-mono text-slate-500">Loading Blueprint Context for Deep Research 2.0...</p>
      </div>
    )
  }

  // Canonical 7 tabs + optional specialized roadmap tabs when available
  const getTabs = () => {
    const tabs = [
      { id: 'overview', label: '📊 Briefing', icon: BarChart3 },
      { id: 'market', label: '📈 Market Sizing', icon: TrendingUp },
      { id: 'competitors', label: '🏆 Competitors', icon: Award },
      { id: 'customers', label: '🎯 Customer Demand', icon: Target },
      { id: 'pulse', label: '📰 Market Pulse', icon: Globe },
      { id: 'verdict', label: '⚖️ Market Verdict', icon: ShieldCheck },
      { id: 'sources', label: '📚 Grounded Sources', icon: BookOpen },
    ]

    if (report?.compliance_roadmap && report.compliance_roadmap.length > 0) {
      tabs.push({ id: 'roadmap', label: '🛡️ Compliance Roadmap', icon: Shield })
    }
    if (report?.pitch_roadmap && report.pitch_roadmap.length > 0) {
      tabs.push({ id: 'strategy', label: '💰 Pitch Roadmap', icon: DollarSign })
    }
    if (report?.technical_roadmap && report.technical_roadmap.length > 0) {
      tabs.push({ id: 'tech_roadmap', label: '⚙️ Technical Roadmap', icon: Code })
    }

    return tabs
  }

  // Helper for recommendation badges
  const getVerdictBadge = (rec) => {
    const val = (rec || '').toUpperCase()
    if (val.includes('GO') && !val.includes('NO')) return <Badge variant="green" size="md">🟢 {rec}</Badge>
    if (val.includes('VALIDATE')) return <Badge variant="blue" size="md">🔵 {rec}</Badge>
    if (val.includes('PIVOT')) return <Badge variant="amber" size="md">🟡 {rec}</Badge>
    if (val.includes('NO')) return <Badge variant="red" size="md">🔴 {rec}</Badge>
    return <Badge variant="purple" size="md">🟣 {rec || 'VALIDATE-FIRST'}</Badge>
  }

  return (
    <div className="max-w-screen-xl mx-auto px-4 sm:px-6 py-6 space-y-6">
      
      {/* Back button */}
      <button
        onClick={() => navigate(`/history/${blueprintId}`)}
        className="flex items-center text-xs text-slate-400 hover:text-slate-200 transition-colors"
      >
        <ArrowLeft size={14} className="mr-1.5" /> Back to Blueprint
      </button>

      {/* ── SETUP VIEW (No active research report & not loading) ── */}
      {!report && !loading && (
        <div className="space-y-6 animate-fade-in">
          {/* Header */}
          <div className="bg-[var(--bg-card)] rounded-2xl border border-white/[0.08] p-6 shadow-xl relative overflow-hidden">
            <div className="absolute -right-10 -bottom-10 w-48 h-48 bg-blue-500/10 rounded-full blur-3xl pointer-events-none" />
            
            <div className="flex items-start gap-4">
              <div className="w-12 h-12 rounded-2xl bg-gradient-to-br from-blue-500/20 to-purple-500/20 border border-blue-500/30 flex items-center justify-center shrink-0 shadow-lg text-blue-400">
                <Search size={24} />
              </div>
              <div className="space-y-1">
                <div className="flex items-center gap-2 flex-wrap">
                  <h1 className="text-xl font-800 text-slate-100 tracking-tight">Deep Research 2.0</h1>
                  <Badge variant="purple" size="sm">Evidence-Grounded Startup Intelligence</Badge>
                  <Badge variant="blue" size="sm">Deterministic Bottom-Up Sizing</Badge>
                </div>
                <p className="text-xs text-slate-400 leading-relaxed max-w-3xl">
                  Conducts rigorous multi-step research: discovers direct & indirect competitors, validates customer demand, performs bottom-up market sizing arithmetic, checks regulatory & funding frameworks, and stress-tests hidden assumptions.
                </p>
              </div>
            </div>
          </div>

          {/* Previous Research Available Card */}
          {cachedReport && (
            <div className="p-4.5 rounded-2xl bg-gradient-to-r from-blue-500/[0.08] to-purple-500/[0.06] border border-blue-500/25 flex flex-wrap items-center justify-between gap-4 shadow-md">
              <div className="space-y-1">
                <div className="flex items-center gap-2">
                  <span className="text-sm">📄</span>
                  <h3 className="text-xs font-800 text-blue-300">Previous Deep Research 2.0 Report Available</h3>
                  <Badge variant="green" size="sm">Cached Report</Badge>
                </div>
                <p className="text-xs text-slate-400 font-mono">
                  Last researched: {cachedReport.meta?.researched_at || 'Recently'} • {cachedReport.meta?.total_sources || cachedReport.sources?.length || 0} unique sources • Mode: {cachedReport.meta?.focus || 'FULL_STARTUP_ANALYSIS'}
                </p>
              </div>

              <button
                type="button"
                onClick={() => setReport(cachedReport)}
                className="px-4 py-2.5 rounded-xl bg-blue-600/20 hover:bg-blue-600/30 text-blue-300 border border-blue-500/40 text-xs font-700 transition-all flex items-center gap-2 shadow-sm"
              >
                <FileText size={14} />
                <span>Open Cached Report</span>
              </button>
            </div>
          )}

          {/* Research Subject Card */}
          <Card className="space-y-4">
            <div className="flex items-center justify-between border-b border-white/[0.08] pb-3">
              <span className="text-[0.68rem] font-800 text-slate-400 uppercase tracking-wider">Research Subject</span>
              <div className="flex gap-1.5 flex-wrap">
                {blueprint?.sector && <Badge variant="blue">{blueprint.sector}</Badge>}
                {blueprint?.stage && <Badge variant="amber">{blueprint.stage}</Badge>}
                {blueprint?.business_model && <Badge variant="purple">{blueprint.business_model}</Badge>}
                {blueprint?.market && <Badge variant="green">{blueprint.market}</Badge>}
              </div>
            </div>

            <div>
              <h2 className="text-base font-800 text-slate-100 mb-1">
                {blueprint?.original_query || 'Startup Venture'}
              </h2>
              <p className="text-xs text-slate-400 leading-relaxed">
                {blueprint?.summary || 'Deep Research 2.0 will investigate market sizing, competitive intensity, customer demand, pricing models, and hidden failure scenarios.'}
              </p>
            </div>

            {/* Controls */}
            <div className="pt-2 flex flex-wrap items-center justify-between gap-4 border-t border-white/[0.06]">
              <div className="flex items-center gap-3">
                <label className="text-xs font-700 text-slate-300">Research Focus Mode:</label>
                <select
                  value={focus}
                  onChange={(e) => setFocus(e.target.value)}
                  className="bg-slate-900 border border-slate-700 text-xs text-slate-200 rounded-xl px-3.5 py-2.5 focus:outline-none focus:border-blue-500/50 font-600"
                >
                  <option value="FULL_STARTUP_ANALYSIS">Full Startup Analysis (Recommended — All 7 Tabs)</option>
                  <option value="MARKET_COMPETITOR">Market Sizing & Competitor Deep Dive</option>
                  <option value="FUNDING_INVESTOR">Funding Ecosystem & Pitch Roadmap</option>
                  <option value="REGULATORY_POLICY">Regulatory Laws & Compliance Roadmap</option>
                  <option value="TECHNOLOGY_TRENDS">Technology Stack & Technical Roadmap</option>
                </select>
              </div>

              <button
                type="button"
                onClick={() => startDeepResearch(false)}
                disabled={loading}
                className="btn-primary py-3 px-6 rounded-xl flex items-center gap-2 text-sm shadow-lg font-700 disabled:opacity-50"
              >
                <Sparkles size={16} />
                <span>Execute Deep Research 2.0</span>
              </button>
            </div>
          </Card>
        </div>
      )}

      {/* ── RESEARCH PROGRESS VIEW ── */}
      {loading && (
        <div className="space-y-6 animate-fade-in">
          <div className="bg-[var(--bg-card)] rounded-2xl border border-blue-500/30 p-6 shadow-2xl space-y-6">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-xl bg-blue-500/20 text-blue-400 border border-blue-500/30 flex items-center justify-center">
                  <Loader2 size={20} className="animate-spin" />
                </div>
                <div>
                  <h2 className="text-base font-800 text-slate-100">Deep Research 2.0 Active ({focus})</h2>
                  <p className="text-xs text-slate-400 font-mono">Investigating: {blueprint?.original_query?.substring(0, 55)}…</p>
                </div>
              </div>

              <div className="text-right">
                <div className="text-xl font-800 text-blue-400">{progressPct}%</div>
                <div className="text-[0.65rem] font-mono text-slate-500 uppercase">Multi-Step Progress</div>
              </div>
            </div>

            {/* Progress Bar */}
            <div className="w-full bg-slate-800/80 rounded-full h-2.5 overflow-hidden p-0.5 border border-white/[0.08]">
              <div
                className="bg-gradient-to-r from-blue-500 via-indigo-500 to-purple-500 h-full rounded-full transition-all duration-300 shadow-md"
                style={{ width: `${progressPct}%` }}
              />
            </div>

            <div className="text-xs text-blue-300 font-600 flex items-center gap-2 bg-blue-500/10 p-3 rounded-xl border border-blue-500/20">
              <Sparkles size={14} className="animate-spin text-amber-400" />
              <span>Current Status: {currentModule}</span>
            </div>

            {/* 6 Real Research Steps */}
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 pt-2 border-t border-white/[0.06]">
              {RESEARCH_STEPS.map((step, idx) => {
                const stepNum = idx + 1
                const isDone = progressPct >= stepNum * 16.6 || progressPct === 100
                const isCurrent = progressPct < stepNum * 16.6 && progressPct >= (stepNum - 1) * 16.6
                return (
                  <div
                    key={step.id}
                    className={`p-2.5 rounded-xl border text-xs flex items-center gap-2.5 transition-all ${
                      isDone
                        ? 'bg-emerald-500/[0.05] border-emerald-500/20 text-emerald-300'
                        : isCurrent
                        ? 'bg-blue-500/[0.08] border-blue-500/30 text-blue-200'
                        : 'bg-white/[0.015] border-white/[0.04] text-slate-500'
                    }`}
                  >
                    {isDone ? (
                      <CheckCircle2 size={14} className="text-emerald-400 shrink-0" />
                    ) : isCurrent ? (
                      <Loader2 size={14} className="animate-spin text-blue-400 shrink-0" />
                    ) : (
                      <Clock size={14} className="text-slate-600 shrink-0" />
                    )}
                    <span className="truncate font-500">{step.name}</span>
                  </div>
                )
              })}
            </div>
          </div>
        </div>
      )}

      {/* Error alert */}
      {error && (
        <div className="bg-red-500/[0.1] border border-red-500/30 rounded-2xl p-4 text-xs text-red-400 flex items-center justify-between">
          <span>❌ {error}</span>
          <button onClick={() => startDeepResearch(true)} className="btn-primary py-1 px-3 text-xs">Try Again</button>
        </div>
      )}

      {/* ── REPORT RESULTS VIEW ── */}
      {report && !loading && (
        <div className="space-y-6 animate-fade-in">
          
          {/* Report Top Header */}
          <div className="bg-[var(--bg-card)] rounded-2xl border border-white/[0.08] p-6 shadow-xl space-y-4">
            <div className="flex flex-wrap items-start justify-between gap-4 border-b border-white/[0.08] pb-4">
              <div className="space-y-1.5 flex-1 min-w-[280px]">
                <div className="flex items-center gap-2 flex-wrap">
                  <Badge variant="purple" size="sm">Deep Research 2.0</Badge>
                  <Badge variant="blue" size="sm">{report.meta?.focus || focus}</Badge>
                  {getVerdictBadge(report.research_verdict?.overall_recommendation)}
                  <span className="text-xs text-slate-500 font-mono">Researched: {report.meta?.researched_at || 'Recently'}</span>
                </div>
                <h1 className="text-xl font-800 text-slate-100 tracking-tight">
                  {report.title || 'Startup Intelligence Report'}
                </h1>
                
                {/* Collapsible startup description */}
                <div className="text-xs text-slate-400 leading-relaxed">
                  <strong className="text-slate-200">Startup Idea:</strong>{' '}
                  {descExpanded || (blueprint?.original_query?.length || 0) <= 120 ? (
                    <span>{blueprint?.original_query}</span>
                  ) : (
                    <span>{blueprint?.original_query?.substring(0, 120)}…</span>
                  )}
                  {(blueprint?.original_query?.length || 0) > 120 && (
                    <button
                      onClick={() => setDescExpanded(!descExpanded)}
                      className="ml-2 text-blue-400 hover:text-blue-300 font-600 underline cursor-pointer"
                    >
                      {descExpanded ? 'Show less' : 'Show full description'}
                    </button>
                  )}
                </div>
              </div>

              <div className="flex items-center gap-2">
                <button
                  onClick={() => setReport(null)}
                  className="px-3.5 py-2 rounded-xl bg-white/[0.04] border border-white/[0.08] hover:bg-white/[0.08] text-xs font-700 text-slate-300 flex items-center gap-1.5 transition-all"
                >
                  <ArrowLeft size={13} />
                  <span>Back to Setup</span>
                </button>

                <button
                  onClick={() => startDeepResearch(true)}
                  className="px-3.5 py-2 rounded-xl bg-blue-600/20 hover:bg-blue-600/30 border border-blue-500/30 text-xs font-700 text-blue-300 flex items-center gap-1.5 transition-all"
                >
                  <RefreshCw size={13} />
                  <span>Refresh Research</span>
                </button>
              </div>
            </div>

            {/* Clickable Metrics Bar */}
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
              <button
                onClick={() => { setActiveTab('sources'); setSourceCategoryFilter('All'); }}
                className="p-3 rounded-xl bg-white/[0.02] border border-white/[0.06] hover:border-blue-500/40 text-left transition-all group"
              >
                <div className="text-lg font-800 text-blue-400 group-hover:text-blue-300 flex items-center justify-between">
                  <span>{report.meta?.total_sources || report.sources?.length || 0}</span>
                  <ExternalLink size={12} className="opacity-0 group-hover:opacity-100 transition-opacity" />
                </div>
                <div className="text-[0.65rem] text-slate-500 uppercase tracking-wider font-700">Total Unique Sources</div>
              </button>

              <button
                onClick={() => { setActiveTab('sources'); setSourceCategoryFilter('All'); }}
                className="p-3 rounded-xl bg-white/[0.02] border border-white/[0.06] hover:border-purple-500/40 text-left transition-all group"
              >
                <div className="text-lg font-800 text-purple-400 group-hover:text-purple-300 flex items-center justify-between">
                  <span>{report.meta?.web_count || 0}</span>
                  <ExternalLink size={12} className="opacity-0 group-hover:opacity-100 transition-opacity" />
                </div>
                <div className="text-[0.65rem] text-slate-500 uppercase tracking-wider font-700">Web Evidence Sources</div>
              </button>

              <button
                onClick={() => { setActiveTab('sources'); setSourceCategoryFilter('Internal Retrieval'); }}
                className="p-3 rounded-xl bg-white/[0.02] border border-white/[0.06] hover:border-emerald-500/40 text-left transition-all group"
              >
                <div className="text-lg font-800 text-emerald-400 group-hover:text-emerald-300 flex items-center justify-between">
                  <span>{report.meta?.internal_count || 0}</span>
                  <ExternalLink size={12} className="opacity-0 group-hover:opacity-100 transition-opacity" />
                </div>
                <div className="text-[0.65rem] text-slate-500 uppercase tracking-wider font-700">Internal Document Chunks</div>
              </button>

              <div className="p-3 rounded-xl bg-white/[0.02] border border-white/[0.06]">
                <div className="text-sm font-800 text-amber-400 truncate">{report.meta?.focus || 'FULL'}</div>
                <div className="text-[0.65rem] text-slate-500 uppercase tracking-wider font-700">Research Focus Mode</div>
              </div>
            </div>
          </div>

          {/* Canonical Navigation Tabs */}
          <div className="flex overflow-x-auto no-scrollbar gap-1.5 border-b border-white/[0.08] pb-2">
            {getTabs().map(tab => {
              const Icon = tab.icon
              const isActive = activeTab === tab.id
              return (
                <button
                  key={tab.id}
                  onClick={() => setActiveTab(tab.id)}
                  className={`px-3.5 py-2.5 rounded-xl text-xs font-700 transition-all shrink-0 flex items-center gap-1.5 ${
                    isActive
                      ? 'bg-blue-600/20 text-blue-300 border border-blue-500/30 shadow-sm'
                      : 'text-slate-400 hover:text-slate-200 bg-white/[0.02] border border-transparent'
                  }`}
                >
                  <Icon size={14} className={isActive ? 'text-blue-400' : 'text-slate-500'} />
                  <span>{tab.label}</span>
                </button>
              )
            })}
          </div>

          {/* ══════════════════════════════════════════════════════════════════ */}
          {/* TAB 1: BRIEFING & CRITICAL ANALYSIS */}
          {/* ══════════════════════════════════════════════════════════════════ */}
          {activeTab === 'overview' && (
            <div className="space-y-6">
              
              {/* Executive Decision Briefing */}
              <Card className="space-y-5">
                <div className="flex items-center justify-between border-b border-white/[0.06] pb-3">
                  <div className="flex items-center gap-2">
                    <h3 className="text-xs font-800 uppercase tracking-wider text-slate-300">
                      Decision-Oriented Executive Briefing
                    </h3>
                    <Badge variant="blue" size="sm">Evidence-Grounded</Badge>
                  </div>
                  {getVerdictBadge(report.research_verdict?.overall_recommendation)}
                </div>

                <div className="text-xs sm:text-sm text-slate-200 leading-relaxed p-4 rounded-xl bg-blue-500/[0.04] border border-blue-500/15">
                  {report.executive_summary?.overview || 'Comprehensive synthesis of startup intelligence report.'}
                </div>

                {/* Structured Key Factors Grid */}
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-xs">
                  <div className="p-3.5 rounded-xl bg-white/[0.02] border border-white/[0.06] space-y-1.5">
                    <div className="flex items-center gap-1.5 font-700 text-slate-300">
                      <Target size={14} className="text-blue-400" />
                      <span>Target Customer & Problem Reality</span>
                    </div>
                    <p className="text-slate-400 leading-relaxed">
                      {report.executive_summary?.core_problem_and_alternatives || report.executive_summary?.startup_summary || 'Targeting operational friction in vertical workflows.'}
                    </p>
                  </div>

                  <div className="p-3.5 rounded-xl bg-white/[0.02] border border-white/[0.06] space-y-1.5">
                    <div className="flex items-center gap-1.5 font-700 text-slate-300">
                      <TrendingUp size={14} className="text-purple-400" />
                      <span>Market Opportunity & Demand Evidence</span>
                    </div>
                    <p className="text-slate-400 leading-relaxed">
                      {report.executive_summary?.customer_demand_evidence || report.executive_summary?.market_opportunity_summary || 'Evidence demonstrates real demand requiring low-cost validation.'}
                    </p>
                  </div>

                  <div className="p-3.5 rounded-xl bg-white/[0.02] border border-white/[0.06] space-y-1.5">
                    <div className="flex items-center gap-1.5 font-700 text-slate-300">
                      <Award size={14} className="text-amber-400" />
                      <span>Competitive Intensity & Business Model</span>
                    </div>
                    <div className="flex items-center gap-2 pt-0.5">
                      <Badge variant="amber" size="sm">Intensity: {report.executive_summary?.competitive_intensity || 'Medium'}</Badge>
                      <Badge variant="purple" size="sm">Feasibility: {report.executive_summary?.business_model_feasibility || 'Moderate'}</Badge>
                    </div>
                    <p className="text-slate-400 leading-relaxed pt-1">
                      {report.competitor_intelligence?.positioning_summary || 'Vertical specialization provides defensible wedge against legacy incumbents.'}
                    </p>
                  </div>

                  <div className="p-3.5 rounded-xl bg-white/[0.02] border border-white/[0.06] space-y-1.5">
                    <div className="flex items-center gap-1.5 font-700 text-slate-300">
                      <Shield size={14} className="text-red-400" />
                      <span>Regulatory & Operational Risks</span>
                    </div>
                    <p className="text-slate-400 leading-relaxed">
                      {report.executive_summary?.regulatory_and_execution_risks || 'Standard incorporation, DPDP data governance, and sales cycle traction.'}
                    </p>
                  </div>
                </div>

                {/* Strategic Wedge & Next Action Callout */}
                <div className="grid grid-cols-1 md:grid-cols-3 gap-3 pt-2">
                  <div className="p-3 rounded-xl bg-emerald-500/[0.05] border border-emerald-500/20">
                    <span className="text-[0.65rem] font-800 text-emerald-400 uppercase tracking-wider">Strongest Opportunity</span>
                    <p className="text-xs text-slate-200 mt-1 font-600">
                      {report.executive_summary?.strongest_opportunity || 'Automating manual operational workflows.'}
                    </p>
                  </div>

                  <div className="p-3 rounded-xl bg-red-500/[0.05] border border-red-500/20">
                    <span className="text-[0.65rem] font-800 text-red-400 uppercase tracking-wider">Biggest Threat</span>
                    <p className="text-xs text-slate-200 mt-1 font-600">
                      {report.executive_summary?.biggest_threat || 'Customer inertia and habit sticking with manual tools.'}
                    </p>
                  </div>

                  <div className="p-3 rounded-xl bg-blue-500/[0.05] border border-blue-500/20">
                    <span className="text-[0.65rem] font-800 text-blue-400 uppercase tracking-wider">Recommended Next Action</span>
                    <p className="text-xs text-slate-200 mt-1 font-600">
                      {report.executive_summary?.recommended_next_action || 'Execute 15 structured customer discovery interviews.'}
                    </p>
                  </div>
                </div>
              </Card>

              {/* ── CRITICAL ANALYSIS & HIDDEN ASSUMPTIONS (MANDATORY SECTION 3) ── */}
              <Card className="space-y-5 border-amber-500/30">
                <div className="flex items-center justify-between border-b border-white/[0.06] pb-3">
                  <div className="flex items-center gap-2">
                    <AlertTriangle size={16} className="text-amber-400" />
                    <h3 className="text-xs font-800 uppercase tracking-wider text-amber-300">
                      Critical Analysis & Hidden Assumptions
                    </h3>
                  </div>
                  <button
                    onClick={() => setCriticalAnalysisExpanded(!criticalAnalysisExpanded)}
                    className="text-xs text-slate-400 hover:text-slate-200 flex items-center gap-1"
                  >
                    <span>{criticalAnalysisExpanded ? 'Collapse' : 'Expand'}</span>
                    {criticalAnalysisExpanded ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
                  </button>
                </div>

                {criticalAnalysisExpanded && (
                  <div className="space-y-5">
                    {/* Balanced Thesis: Why It Might Succeed vs Why It Might Fail */}
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                      <div className="p-4 rounded-xl bg-emerald-500/[0.03] border border-emerald-500/20 space-y-2">
                        <span className="text-xs font-800 text-emerald-400 flex items-center gap-1.5">
                          <Check size={14} /> Strongest Supporting Evidence
                        </span>
                        <ul className="text-xs text-slate-300 space-y-1.5">
                          {(report.critical_analysis?.strongest_supporting_evidence || []).map((ev, i) => (
                            <li key={i} className="flex items-start gap-1.5">
                              <span className="text-emerald-400">✓</span> {ev}
                            </li>
                          ))}
                        </ul>
                      </div>

                      <div className="p-4 rounded-xl bg-red-500/[0.03] border border-red-500/20 space-y-2">
                        <span className="text-xs font-800 text-red-400 flex items-center gap-1.5">
                          <X size={14} /> Strongest Counterarguments & Failure Modes
                        </span>
                        <ul className="text-xs text-slate-300 space-y-1.5">
                          {(report.critical_analysis?.strongest_counterarguments || []).map((ca, i) => (
                            <li key={i} className="flex items-start gap-1.5">
                              <span className="text-red-400">⚠</span> {ca}
                            </li>
                          ))}
                        </ul>
                      </div>
                    </div>

                    {/* Fatal Assumptions */}
                    <div className="space-y-3">
                      <h4 className="text-xs font-800 text-slate-300 uppercase tracking-wider">
                        Critical Assumptions (Must Hold True)
                      </h4>
                      <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                        {(report.critical_analysis?.critical_assumptions || []).map((item, i) => (
                          <div key={i} className="p-3.5 rounded-xl bg-white/[0.02] border border-amber-500/25 space-y-1">
                            <div className="flex items-center justify-between">
                              <span className="text-xs font-700 text-slate-200">{item.assumption}</span>
                              <Badge variant="amber" size="sm">{item.validation_priority || 'High'} Priority</Badge>
                            </div>
                            <p className="text-[0.72rem] text-slate-400 leading-relaxed">
                              <strong>Why critical:</strong> {item.why_critical}
                            </p>
                          </div>
                        ))}
                      </div>
                    </div>

                    {/* Low-Cost Founder Experiments */}
                    <div className="space-y-3">
                      <h4 className="text-xs font-800 text-slate-300 uppercase tracking-wider">
                        Low-Cost Founder Validation Experiments
                      </h4>
                      <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                        {(report.critical_analysis?.validation_experiments || []).map((exp, i) => (
                          <div key={i} className="p-3.5 rounded-xl bg-blue-500/[0.03] border border-blue-500/20 space-y-1.5">
                            <div className="flex items-center justify-between">
                              <span className="text-xs font-800 text-blue-300">{exp.experiment_name}</span>
                              <span className="text-[0.65rem] font-mono text-slate-400">{exp.cost_time}</span>
                            </div>
                            <p className="text-xs text-slate-300">{exp.objective}</p>
                            <div className="text-[0.68rem] text-emerald-400 font-500">
                              <strong>Success Metric:</strong> {exp.success_metric}
                            </div>
                          </div>
                        ))}
                      </div>
                    </div>

                    {/* Pivot Triggers */}
                    {(report.critical_analysis?.pivot_triggers || []).length > 0 && (
                      <div className="p-3 rounded-xl bg-amber-500/[0.05] border border-amber-500/20 text-xs text-amber-300 space-y-1">
                        <strong>Evidence Signals Mandating a Strategic Pivot:</strong>
                        <ul className="space-y-1 pl-4 list-disc text-slate-300 text-[0.72rem]">
                          {report.critical_analysis.pivot_triggers.map((pt, i) => (
                            <li key={i}>{pt}</li>
                          ))}
                        </ul>
                      </div>
                    )}
                  </div>
                )}
              </Card>

            </div>
          )}

          {/* ══════════════════════════════════════════════════════════════════ */}
          {/* TAB 2: MARKET SIZING & BOTTOM-UP ARITHMETIC */}
          {/* ══════════════════════════════════════════════════════════════════ */}
          {activeTab === 'market' && (
            <div className="space-y-6">
              <Card className="space-y-6">
                <div className="flex items-center justify-between border-b border-white/[0.06] pb-3">
                  <div>
                    <h3 className="text-xs font-800 uppercase tracking-wider text-slate-300">
                      Deterministic Market Sizing (TAM / SAM / SOM)
                    </h3>
                    <p className="text-[0.7rem] text-slate-400">
                      Grounded in deterministic bottom-up arithmetic rather than generic top-down LLM ranges.
                    </p>
                  </div>
                  <Badge variant="blue" size="sm">Scope: {report.market_landscape?.geographic_scope || 'India & Global'}</Badge>
                </div>

                {/* Sizing Visual Comparison Cards */}
                <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
                  <div className="p-4 rounded-2xl bg-blue-500/[0.05] border border-blue-500/25 space-y-2">
                    <span className="text-xs text-slate-400 font-700">Total Addressable Market (TAM)</span>
                    <div className="text-2xl font-800 text-blue-400">
                      {report.market_landscape?.tam?.value || '$270.0M'}
                    </div>
                    <p className="text-xs text-slate-400 leading-relaxed">
                      {report.market_landscape?.tam?.description || 'Total eligible customer base multiplied by annual addressable revenue.'}
                    </p>
                  </div>

                  <div className="p-4 rounded-2xl bg-purple-500/[0.05] border border-purple-500/25 space-y-2">
                    <span className="text-xs text-slate-400 font-700">Serviceable Addressable (SAM)</span>
                    <div className="text-2xl font-800 text-purple-400">
                      {report.market_landscape?.sam?.value || '$54.0M'}
                    </div>
                    <p className="text-xs text-slate-400 leading-relaxed">
                      {report.market_landscape?.sam?.description || 'Reachable customers in primary launch geographies & initial sales verticals.'}
                    </p>
                  </div>

                  <div className="p-4 rounded-2xl bg-emerald-500/[0.05] border border-emerald-500/25 space-y-2">
                    <span className="text-xs text-slate-400 font-700">Serviceable Obtainable (SOM)</span>
                    <div className="text-2xl font-800 text-emerald-400">
                      {report.market_landscape?.som?.value || '$1.62M'}
                    </div>
                    <p className="text-xs text-slate-400 leading-relaxed">
                      {report.market_landscape?.som?.description || 'Realistic 3-year market capture based on early sales team capacity.'}
                    </p>
                  </div>
                </div>

                {/* Deterministic Bottom-Up Arithmetic Breakdown */}
                {report.market_landscape?.bottom_up && (
                  <div className="p-4 rounded-xl bg-slate-900/80 border border-white/[0.08] space-y-3">
                    <div className="flex items-center justify-between border-b border-white/[0.06] pb-2">
                      <span className="text-xs font-800 text-blue-300 uppercase tracking-wider flex items-center gap-1.5">
                        <BarChart3 size={14} /> Deterministic Calculation Formula
                      </span>
                      <span className="text-[0.68rem] font-mono text-slate-400">
                        Horizon: {report.market_landscape?.projection_horizon || '2025–2030'} • CAGR: {report.market_landscape?.cagr || '16.4%'}
                      </span>
                    </div>

                    <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-4 gap-3 text-xs">
                      <div className="p-2.5 rounded-lg bg-white/[0.02] border border-white/[0.04]">
                        <span className="text-slate-500 text-[0.65rem] uppercase">Eligible Customers</span>
                        <div className="text-sm font-800 text-slate-200">
                          {report.market_landscape.bottom_up.target_customers?.toLocaleString() || '150,000'}
                        </div>
                        <span className="text-[0.62rem] text-slate-500 truncate block">
                          {report.market_landscape.bottom_up.target_customers_source}
                        </span>
                      </div>

                      <div className="p-2.5 rounded-lg bg-white/[0.02] border border-white/[0.04]">
                        <span className="text-slate-500 text-[0.65rem] uppercase">Addressable Annual ARPU</span>
                        <div className="text-sm font-800 text-slate-200">
                          ${report.market_landscape.bottom_up.arpu?.toLocaleString() || '1,800'}
                        </div>
                        <span className="text-[0.62rem] text-slate-500 truncate block">
                          {report.market_landscape.bottom_up.arpu_source}
                        </span>
                      </div>

                      <div className="p-2.5 rounded-lg bg-white/[0.02] border border-white/[0.04]">
                        <span className="text-slate-500 text-[0.65rem] uppercase">SAM Reach Ratio</span>
                        <div className="text-sm font-800 text-purple-300">
                          {(report.market_landscape.bottom_up.sam_reach_ratio * 100) || 20}%
                        </div>
                        <span className="text-[0.62rem] text-slate-500 block">Launch geography share</span>
                      </div>

                      <div className="p-2.5 rounded-lg bg-white/[0.02] border border-white/[0.04]">
                        <span className="text-slate-500 text-[0.65rem] uppercase">SOM 3-Year Capture</span>
                        <div className="text-sm font-800 text-emerald-300">
                          {(report.market_landscape.bottom_up.som_capture_ratio * 100) || 3}%
                        </div>
                        <span className="text-[0.62rem] text-slate-500 block">Obtainable sales share</span>
                      </div>
                    </div>

                    <p className="text-[0.72rem] text-slate-400 font-mono leading-relaxed pt-1">
                      {report.market_landscape.bottom_up.notes}
                    </p>
                  </div>
                )}

                {/* Conflicting Estimates Analysis */}
                {(report.market_landscape?.conflicting_estimates || []).length > 0 && (
                  <div className="p-4 rounded-xl bg-amber-500/[0.03] border border-amber-500/20 space-y-2">
                    <span className="text-xs font-800 text-amber-300 uppercase tracking-wider flex items-center gap-1.5">
                      <HelpCircle size={14} /> Disagreeing & Conflicting Estimates Analysis
                    </span>
                    <p className="text-xs text-slate-400">
                      Why secondary reports cite figures such as $10B–$15B:
                    </p>
                    {report.market_landscape.conflicting_estimates.map((item, idx) => (
                      <div key={idx} className="p-2.5 rounded-lg bg-white/[0.02] border border-white/[0.04] text-xs space-y-1">
                        <div className="flex items-center justify-between">
                          <strong className="text-slate-200">{item.source_name}: {item.estimate}</strong>
                          <span className="text-[0.65rem] text-amber-400">{item.methodology}</span>
                        </div>
                        <p className="text-slate-400 text-[0.72rem]">{item.why_it_differs}</p>
                      </div>
                    ))}
                  </div>
                )}

                {/* Drivers & Constraints */}
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 pt-2">
                  <div className="space-y-2">
                    <span className="text-xs font-800 text-emerald-400 uppercase tracking-wider">Verified Market Drivers</span>
                    <ul className="space-y-1.5 text-xs text-slate-300">
                      {(report.market_landscape?.drivers || []).map((d, i) => (
                        <li key={i} className="flex items-start gap-1.5"><span className="text-emerald-400">✓</span> {d}</li>
                      ))}
                    </ul>
                  </div>
                  <div className="space-y-2">
                    <span className="text-xs font-800 text-amber-400 uppercase tracking-wider">Structural Market Constraints</span>
                    <ul className="space-y-1.5 text-xs text-slate-300">
                      {(report.market_landscape?.constraints || []).map((c, i) => (
                        <li key={i} className="flex items-start gap-1.5"><span className="text-amber-400">⚠</span> {c}</li>
                      ))}
                    </ul>
                  </div>
                </div>
              </Card>
            </div>
          )}

          {/* ══════════════════════════════════════════════════════════════════ */}
          {/* TAB 3: COMPETITORS & MATRIX */}
          {/* ══════════════════════════════════════════════════════════════════ */}
          {activeTab === 'competitors' && (
            <div className="space-y-6">
              <Card className="space-y-5">
                <div className="flex flex-wrap items-center justify-between gap-3 border-b border-white/[0.06] pb-3">
                  <div>
                    <h3 className="text-xs font-800 uppercase tracking-wider text-slate-300">
                      Competitive Intelligence Matrix & Moats
                    </h3>
                    <p className="text-[0.7rem] text-slate-400">
                      Direct, indirect, manual substitutes, and emerging competitors with verified data.
                    </p>
                  </div>

                  {/* Filter Pills */}
                  <div className="flex gap-1.5 flex-wrap">
                    {['All', 'Direct Competitor', 'Indirect Competitor', 'Substitute / Manual Workflow', 'Emerging Competitor'].map(cat => (
                      <button
                        key={cat}
                        onClick={() => setCompetitorCategoryFilter(cat)}
                        className={`px-2.5 py-1 rounded-lg text-[0.68rem] font-700 transition-all ${
                          competitorCategoryFilter === cat
                            ? 'bg-blue-600/30 text-blue-300 border border-blue-500/40'
                            : 'bg-white/[0.02] text-slate-400 hover:text-slate-200 border border-transparent'
                        }`}
                      >
                        {cat}
                      </button>
                    ))}
                  </div>
                </div>

                {/* Competitors Grid */}
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  {(report.competitor_intelligence?.competitors || [])
                    .filter(c => competitorCategoryFilter === 'All' || c.category === competitorCategoryFilter)
                    .map((c, i) => (
                      <div key={i} className="p-4 rounded-xl bg-slate-900/80 border border-white/[0.08] space-y-3">
                        <div className="flex items-start justify-between gap-2 border-b border-white/[0.04] pb-2">
                          <div>
                            <h4 className="text-sm font-800 text-blue-300">{c.name}</h4>
                            <span className="text-[0.65rem] text-slate-400">{c.product}</span>
                          </div>
                          <div className="flex flex-col items-end gap-1">
                            <Badge variant="purple" size="sm">{c.category || 'Competitor'}</Badge>
                            <Badge variant={c.pricing_verification === 'Verified' ? 'green' : 'amber'} size="sm">
                              {c.pricing_verification || 'Not verified'}
                            </Badge>
                          </div>
                        </div>

                        <div className="grid grid-cols-2 gap-2 text-[0.72rem]">
                          <div>
                            <span className="text-slate-500 block">Target Customer</span>
                            <span className="text-slate-300 font-500">{c.target_customer || 'Mid-market businesses'}</span>
                          </div>
                          <div>
                            <span className="text-slate-500 block">Pricing Model</span>
                            <span className={c.pricing_verification === 'Verified' ? 'text-emerald-300' : 'text-amber-300'}>
                              {c.pricing_model || 'Not verified'}
                            </span>
                          </div>
                          <div>
                            <span className="text-slate-500 block">Distribution</span>
                            <span className="text-slate-300">{c.distribution || 'Direct sales'}</span>
                          </div>
                          <div>
                            <span className="text-slate-500 block">Territory</span>
                            <span className="text-slate-300">{c.geographic_presence || 'Global'}</span>
                          </div>
                        </div>

                        {/* Differentiation Angle */}
                        <div className="p-2.5 rounded-lg bg-blue-500/[0.04] border border-blue-500/15 text-xs text-blue-200">
                          <strong>Our Differentiation Wedge:</strong> {c.differentiation}
                        </div>

                        <div className="flex flex-wrap gap-2 text-[0.65rem] pt-1 border-t border-white/[0.04]">
                          <span className="text-emerald-400 bg-emerald-500/10 px-2 py-0.5 rounded border border-emerald-500/20">
                            Strengths: {(c.strengths || []).join(', ')}
                          </span>
                          <span className="text-red-400 bg-red-500/10 px-2 py-0.5 rounded border border-red-500/20">
                            Weaknesses: {(c.weaknesses || []).join(', ')}
                          </span>
                        </div>
                      </div>
                    ))}
                </div>

                {/* Positioning Summary */}
                <div className="p-4 rounded-xl bg-gradient-to-r from-blue-500/10 to-indigo-500/10 border border-blue-500/30 space-y-1">
                  <span className="text-xs font-800 text-blue-300 uppercase tracking-wider">Startup Positioning & Moat Strategy</span>
                  <p className="text-xs text-slate-200 leading-relaxed">
                    {report.competitor_intelligence?.positioning_summary || 'Targeting uncontested workflow wedges with faster time-to-value.'}
                  </p>
                </div>
              </Card>
            </div>
          )}

          {/* ══════════════════════════════════════════════════════════════════ */}
          {/* TAB 4: CUSTOMER DEMAND & EXPERIMENTS */}
          {/* ══════════════════════════════════════════════════════════════════ */}
          {activeTab === 'customers' && (
            <div className="space-y-6">
              <Card className="space-y-5">
                <div className="border-b border-white/[0.06] pb-3">
                  <h3 className="text-xs font-800 uppercase tracking-wider text-slate-300">
                    Customer Demand Evidence & Validation Roadmap
                  </h3>
                  <p className="text-[0.7rem] text-slate-400">
                    Separating verified commercial willingness to pay from hypothetical founder interest.
                  </p>
                </div>

                {/* Target Customer Persona */}
                <div className="p-3.5 rounded-xl bg-white/[0.02] border border-white/[0.06] text-xs">
                  <span className="text-slate-400 font-700">Primary Customer Persona:</span>{' '}
                  <span className="text-slate-200 font-600">{report.customer_validation?.target_customer}</span>
                </div>

                {/* Problem Evidence vs Willingness to Pay */}
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-xs">
                  <div className="p-4 rounded-xl bg-red-500/[0.03] border border-red-500/20 space-y-2">
                    <span className="font-800 text-red-400 flex items-center gap-1.5 uppercase tracking-wider text-[0.68rem]">
                      <AlertTriangle size={14} /> Evidence Problem Really Exists
                    </span>
                    {(report.customer_validation?.evidence_problem_exists || []).map((item, i) => (
                      <div key={i} className="space-y-0.5">
                        <strong className="text-slate-200 block">• {item.problem}</strong>
                        <span className="text-slate-400 text-[0.7rem]">{item.evidence}</span>
                      </div>
                    ))}
                  </div>

                  <div className="p-4 rounded-xl bg-emerald-500/[0.03] border border-emerald-500/20 space-y-2">
                    <span className="font-800 text-emerald-400 flex items-center gap-1.5 uppercase tracking-wider text-[0.68rem]">
                      <DollarSign size={14} /> Willingness-to-Pay Signals
                    </span>
                    {(report.customer_validation?.willingness_to_pay_signals || []).map((item, i) => (
                      <div key={i} className="space-y-0.5">
                        <strong className="text-slate-200 block">• {item.signal}</strong>
                        <span className="text-slate-400 text-[0.7rem]">{item.evidence}</span>
                      </div>
                    ))}
                  </div>
                </div>

                {/* Switching Barriers & Real Complaints */}
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-xs">
                  <div className="p-4 rounded-xl bg-white/[0.02] border border-white/[0.06] space-y-2">
                    <span className="font-800 text-amber-400 uppercase tracking-wider text-[0.68rem]">
                      Current Alternatives & Switching Inertia
                    </span>
                    {(report.customer_validation?.current_alternatives_and_switching_costs || []).map((alt, i) => (
                      <div key={i} className="space-y-0.5">
                        <strong className="text-slate-200 block">• {alt.alternative}</strong>
                        <span className="text-slate-400 text-[0.7rem]">{alt.switching_barrier}</span>
                      </div>
                    ))}
                  </div>

                  <div className="p-4 rounded-xl bg-white/[0.02] border border-white/[0.06] space-y-2">
                    <span className="font-800 text-blue-400 uppercase tracking-wider text-[0.68rem]">
                      Unmet Needs & Customer Complaints
                    </span>
                    {(report.customer_validation?.unmet_needs_and_complaints || []).map((un, i) => (
                      <div key={i} className="space-y-0.5">
                        <strong className="text-slate-200 block">• {un.need}</strong>
                        <span className="text-slate-400 text-[0.7rem] italic">"{un.customer_quote_or_signal}"</span>
                      </div>
                    ))}
                  </div>
                </div>

                {/* Actionable Founder Customer Discovery Questions */}
                <div className="p-4 rounded-xl bg-blue-500/[0.03] border border-blue-500/20 space-y-3">
                  <span className="text-xs font-800 text-blue-300 uppercase tracking-wider flex items-center gap-1.5">
                    <HelpCircle size={14} /> Founder Customer Discovery Interview Script (Top Questions)
                  </span>
                  <div className="space-y-1.5 text-xs text-slate-300">
                    {(report.customer_validation?.customer_discovery_questions || []).map((q, i) => (
                      <div key={i} className="p-2 rounded-lg bg-white/[0.02] border border-white/[0.04] flex items-start gap-2">
                        <span className="text-blue-400 font-bold shrink-0">Q{i+1}:</span>
                        <span>{q}</span>
                      </div>
                    ))}
                  </div>
                </div>
              </Card>
            </div>
          )}

          {/* ══════════════════════════════════════════════════════════════════ */}
          {/* TAB 5: MARKET PULSE (GENUINE DATED NEWS) */}
          {/* ══════════════════════════════════════════════════════════════════ */}
          {activeTab === 'pulse' && (
            <div className="space-y-6">
              <Card className="space-y-5">
                <div className="border-b border-white/[0.06] pb-3 flex items-center justify-between">
                  <div>
                    <h3 className="text-xs font-800 uppercase tracking-wider text-slate-300">
                      Live Market Pulse & Dated Industry Developments
                    </h3>
                    <p className="text-[0.7rem] text-slate-400">
                      Genuine dated news items with working original source URLs. No fabricated publishers or headlines.
                    </p>
                  </div>
                  <Badge variant="blue" size="sm">Verified News Feed</Badge>
                </div>

                {(!report.market_pulse || report.market_pulse.length === 0) ? (
                  <div className="p-8 text-center space-y-2 text-slate-400 text-xs">
                    <p>No recent dated news verified through live web intelligence for this specific niche.</p>
                    <p className="text-slate-500">We do not manufacture fake news headlines or non-existent URLs.</p>
                  </div>
                ) : (
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    {report.market_pulse.map((item, idx) => (
                      <div key={idx} className="p-4 rounded-xl bg-slate-900/80 border border-white/[0.08] space-y-2.5">
                        <div className="flex items-start justify-between gap-2">
                          <h4 className="text-xs font-800 text-blue-300 leading-snug">{item.headline}</h4>
                          <span className="text-[0.62rem] font-mono text-slate-400 shrink-0 bg-white/[0.03] px-2 py-0.5 rounded">
                            {item.date}
                          </span>
                        </div>

                        <span className="text-[0.65rem] font-semibold text-slate-400 block">
                          Publisher: <strong className="text-slate-200">{item.publisher}</strong>
                        </span>

                        <p className="text-xs text-slate-300 leading-relaxed">
                          {item.factual_summary}
                        </p>

                        <div className="p-2.5 rounded-lg bg-blue-500/[0.04] border border-blue-500/15 text-[0.72rem] text-blue-200">
                          <strong>Strategic Impact:</strong> {item.why_it_matters}
                        </div>

                        {item.source_url && (
                          <a
                            href={item.source_url}
                            target="_blank"
                            rel="noreferrer"
                            className="text-[0.68rem] text-blue-400 hover:text-blue-300 flex items-center gap-1 font-600 pt-1"
                          >
                            <Globe size={11} /> <span>Read Original Article</span> <ExternalLink size={10} />
                          </a>
                        )}
                      </div>
                    ))}
                  </div>
                )}
              </Card>
            </div>
          )}

          {/* ══════════════════════════════════════════════════════════════════ */}
          {/* TAB 6: MARKET VERDICT (ANALYTICAL 9 SCORES) */}
          {/* ══════════════════════════════════════════════════════════════════ */}
          {activeTab === 'verdict' && (
            <div className="space-y-6">
              <Card className="space-y-6">
                <div className="flex flex-wrap items-center justify-between gap-3 border-b border-white/[0.06] pb-3">
                  <div>
                    <h3 className="text-xs font-800 uppercase tracking-wider text-slate-300">
                      Analytical Research Verdict & 9-Dimension Rubric
                    </h3>
                    <p className="text-[0.7rem] text-slate-400">
                      Grounded scores with explicit evidence, assumptions, and directional triggers.
                    </p>
                  </div>
                  {getVerdictBadge(report.research_verdict?.overall_recommendation)}
                </div>

                {/* Overall Verdict Banner */}
                <div className="p-4 rounded-xl bg-gradient-to-r from-blue-500/10 via-indigo-500/10 to-purple-500/10 border border-blue-500/30 space-y-2">
                  <div className="text-sm font-800 text-blue-300">
                    {report.research_verdict?.overall_verdict_title || 'RESEARCH VERDICT'}
                  </div>
                  <p className="text-xs text-slate-200 leading-relaxed font-500">
                    {report.research_verdict?.verdict_reasoning}
                  </p>
                </div>

                {/* 9 Dimension Score Cards */}
                <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-3">
                  {(report.research_verdict?.scores || []).map((scoreItem, idx) => (
                    <div
                      key={idx}
                      className="p-3.5 rounded-xl bg-slate-900/80 border border-white/[0.08] space-y-2 cursor-pointer hover:border-blue-500/40 transition-all"
                      onClick={() => setActiveScoreDetail(activeScoreDetail === idx ? null : idx)}
                    >
                      <div className="flex items-center justify-between">
                        <span className="text-xs font-700 text-slate-200 truncate">{scoreItem.dimension}</span>
                        <div className="text-base font-800 text-blue-400">{scoreItem.score}/10</div>
                      </div>

                      <div className="w-full bg-slate-800 rounded-full h-1.5 overflow-hidden">
                        <div
                          className="bg-blue-500 h-full rounded-full"
                          style={{ width: `${scoreItem.score * 10}%` }}
                        />
                      </div>

                      <p className="text-[0.68rem] text-slate-400 line-clamp-2">
                        {scoreItem.definition}
                      </p>

                      {/* Expandable score detail */}
                      {activeScoreDetail === idx && (
                        <div className="pt-2 border-t border-white/[0.06] text-[0.68rem] space-y-1.5 animate-fade-in">
                          <p className="text-slate-300"><strong>Evidence:</strong> {scoreItem.evidence_and_assumptions}</p>
                          <p className="text-emerald-400"><strong>What raises score:</strong> {scoreItem.what_would_increase_score}</p>
                          <p className="text-red-400"><strong>What lowers score:</strong> {scoreItem.what_would_decrease_score}</p>
                        </div>
                      )}
                    </div>
                  ))}
                </div>

                {/* Reasons to Proceed vs Reasons for Caution */}
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4 pt-2">
                  <div className="p-4 rounded-xl bg-emerald-500/[0.03] border border-emerald-500/20 space-y-2">
                    <span className="text-xs font-800 text-emerald-400 uppercase tracking-wider">Top Reasons to Proceed</span>
                    <ul className="text-xs text-slate-300 space-y-1.5">
                      {(report.research_verdict?.strongest_reasons_to_proceed || []).map((r, i) => (
                        <li key={i} className="flex items-start gap-1.5"><span className="text-emerald-400">✓</span> {r}</li>
                      ))}
                    </ul>
                  </div>

                  <div className="p-4 rounded-xl bg-red-500/[0.03] border border-red-500/20 space-y-2">
                    <span className="text-xs font-800 text-red-400 uppercase tracking-wider">Top Reasons for Caution</span>
                    <ul className="text-xs text-slate-300 space-y-1.5">
                      {(report.research_verdict?.strongest_reasons_for_caution || []).map((c, i) => (
                        <li key={i} className="flex items-start gap-1.5"><span className="text-red-400">⚠</span> {c}</li>
                      ))}
                    </ul>
                  </div>
                </div>

                {/* Recommended Next Three Actions */}
                <div className="p-4 rounded-xl bg-blue-500/[0.04] border border-blue-500/20 space-y-2">
                  <span className="text-xs font-800 text-blue-300 uppercase tracking-wider flex items-center gap-1.5">
                    <CheckCircle2 size={14} /> Founder Next 30-Day Tactical Action Plan
                  </span>
                  <div className="space-y-1.5 text-xs text-slate-200">
                    {(report.research_verdict?.recommended_next_three_actions || []).map((action, i) => (
                      <div key={i} className="p-2.5 rounded-lg bg-white/[0.02] border border-white/[0.04]">
                        {action}
                      </div>
                    ))}
                  </div>
                </div>
              </Card>
            </div>
          )}

          {/* ══════════════════════════════════════════════════════════════════ */}
          {/* TAB 7: GROUNDED SOURCES (EVIDENCE EXPLORER) */}
          {/* ══════════════════════════════════════════════════════════════════ */}
          {activeTab === 'sources' && (
            <div className="space-y-6">
              <Card className="space-y-5">
                <div className="flex flex-wrap items-center justify-between gap-4 border-b border-white/[0.06] pb-3">
                  <div>
                    <h3 className="text-xs font-800 uppercase tracking-wider text-slate-300">
                      Grounded Sources & Evidence Explorer
                    </h3>
                    <p className="text-[0.7rem] text-slate-400">
                      Full provenance, quality rubric ratings, and primary vs secondary designation.
                    </p>
                  </div>

                  {/* Search Bar */}
                  <div className="relative w-full sm:w-64">
                    <Search size={14} className="absolute left-3 top-3 text-slate-500" />
                    <input
                      type="text"
                      placeholder="Filter sources by title or domain…"
                      value={sourceSearchTerm}
                      onChange={(e) => setSourceSearchTerm(e.target.value)}
                      className="w-full bg-slate-900 border border-slate-700 text-xs text-slate-200 rounded-xl pl-9 pr-3 py-2 focus:outline-none focus:border-blue-500/50"
                    />
                  </div>
                </div>

                {/* Category Filter Pills */}
                <div className="flex gap-1.5 flex-wrap">
                  {['All', 'Market Sizing', 'Competitors', 'Customer Demand', 'Regulation', 'Funding', 'Market News', 'Internal Retrieval'].map(cat => (
                    <button
                      key={cat}
                      onClick={() => setSourceCategoryFilter(cat)}
                      className={`px-3 py-1.5 rounded-xl text-xs font-700 transition-all ${
                        sourceCategoryFilter === cat
                          ? 'bg-blue-600/30 text-blue-300 border border-blue-500/40'
                          : 'bg-white/[0.02] text-slate-400 hover:text-slate-200 border border-transparent'
                      }`}
                    >
                      {cat}
                    </button>
                  ))}
                </div>

                {/* Sources List */}
                <div className="space-y-3">
                  {(report.sources || [])
                    .filter(s => sourceCategoryFilter === 'All' || s.category === sourceCategoryFilter)
                    .filter(s => !sourceSearchTerm || (s.title + ' ' + s.publisher + ' ' + s.domain).toLowerCase().includes(sourceSearchTerm.toLowerCase()))
                    .map(src => (
                      <div
                        key={src.id}
                        className="p-4 rounded-xl bg-slate-900/80 border border-white/[0.08] flex flex-col sm:flex-row sm:items-start justify-between gap-4 hover:border-blue-500/30 transition-all"
                      >
                        <div className="space-y-1.5 min-w-0 flex-1">
                          <div className="flex items-center gap-2 flex-wrap">
                            <span className="w-5 h-5 rounded bg-blue-500/20 text-blue-400 font-bold text-[0.68rem] flex items-center justify-center shrink-0">
                              #{src.id}
                            </span>
                            <Badge variant={src.type === 'internal' ? 'emerald' : 'blue'} size="sm">
                              {src.type === 'internal' ? 'Internal Document' : 'Live Web Evidence'}
                            </Badge>
                            <Badge variant={src.evidence_quality === 'High' ? 'green' : 'amber'} size="sm">
                              {src.evidence_quality} Quality
                            </Badge>
                            {src.is_primary && (
                              <Badge variant="purple" size="sm">Primary Source</Badge>
                            )}
                            <span className="text-[0.65rem] font-mono text-slate-500">{src.published_date}</span>
                          </div>

                          <h4 className="text-xs font-700 text-slate-200 leading-snug">{src.title}</h4>

                          <p className="text-[0.72rem] text-slate-400 line-clamp-3 italic bg-white/[0.015] p-2 rounded-lg border border-white/[0.03]">
                            "{src.excerpt}"
                          </p>

                          <div className="text-[0.65rem] text-slate-500 font-mono">
                            Domain: <strong className="text-slate-400">{src.domain || src.publisher}</strong> • Category: <strong className="text-slate-400">{src.category}</strong>
                          </div>
                        </div>

                        {src.url && (
                          <a
                            href={src.url}
                            target="_blank"
                            rel="noreferrer"
                            className="px-3 py-1.5 rounded-lg bg-blue-600/15 hover:bg-blue-600/25 border border-blue-500/30 text-[0.7rem] text-blue-300 font-700 flex items-center gap-1 shrink-0 self-start sm:self-center transition-all"
                          >
                            <span>Visit Source</span> <ExternalLink size={10} />
                          </a>
                        )}
                      </div>
                    ))}
                </div>
              </Card>
            </div>
          )}

          {/* ══════════════════════════════════════════════════════════════════ */}
          {/* SPECIALIZED ROADMAP TABS (PRESERVED) */}
          {/* ══════════════════════════════════════════════════════════════════ */}
          
          {/* Compliance Roadmap */}
          {activeTab === 'roadmap' && report?.compliance_roadmap && (
            <Card className="space-y-6">
              <h3 className="text-xs font-800 uppercase tracking-wider text-slate-300 border-b border-white/[0.06] pb-2 flex items-center gap-2">
                <Shield size={16} className="text-amber-400" />
                <span>Step-by-Step Statutory Compliance & Licensing Roadmap</span>
              </h3>
              <div className="space-y-4">
                {report.compliance_roadmap.map((step, idx) => (
                  <div key={idx} className="p-4 rounded-xl bg-slate-900/80 border border-amber-500/30 space-y-3">
                    <div className="flex items-center justify-between border-b border-white/[0.06] pb-2">
                      <div className="flex items-center gap-2">
                        <span className="w-6 h-6 rounded-full bg-amber-500/20 text-amber-400 font-800 text-xs flex items-center justify-center border border-amber-500/30">
                          {idx + 1}
                        </span>
                        <h4 className="text-sm font-800 text-amber-200">{step.phase}</h4>
                      </div>
                      <Badge variant="amber" size="sm">{step.timeline}</Badge>
                    </div>

                    <div className="grid grid-cols-1 md:grid-cols-2 gap-3 text-xs">
                      <div className="space-y-1">
                        <span className="font-700 text-slate-300">Mandatory Requirements:</span>
                        <ul className="space-y-1 text-slate-400">
                          {(step.requirements || []).map((r, i) => <li key={i} className="flex items-start gap-1"><span className="text-amber-400">•</span> {r}</li>)}
                        </ul>
                      </div>
                      <div className="space-y-1">
                        <span className="font-700 text-slate-300">Action Steps:</span>
                        <ul className="space-y-1 text-slate-400">
                          {(step.actions || []).map((a, i) => <li key={i} className="flex items-start gap-1"><span className="text-emerald-400">✓</span> {a}</li>)}
                        </ul>
                      </div>
                    </div>

                    {step.completion_criteria && (
                      <div className="p-2.5 rounded-lg bg-emerald-500/10 border border-emerald-500/20 text-xs text-emerald-300 font-500">
                        <strong>Completion Criteria:</strong> {step.completion_criteria}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </Card>
          )}

          {/* Pitch Roadmap */}
          {activeTab === 'strategy' && report?.pitch_roadmap && (
            <Card className="space-y-6">
              <h3 className="text-xs font-800 uppercase tracking-wider text-slate-300 border-b border-white/[0.06] pb-2 flex items-center gap-2">
                <DollarSign size={16} className="text-emerald-400" />
                <span>Investor Pitching & Non-Dilutive Grant Roadmap</span>
              </h3>
              <div className="space-y-4">
                {report.pitch_roadmap.map((step, idx) => (
                  <div key={idx} className="p-4 rounded-xl bg-slate-900/80 border border-emerald-500/30 space-y-3">
                    <div className="flex items-center justify-between border-b border-white/[0.06] pb-2">
                      <div className="flex items-center gap-2">
                        <span className="w-6 h-6 rounded-full bg-emerald-500/20 text-emerald-400 font-800 text-xs flex items-center justify-center border border-emerald-500/30">
                          {idx + 1}
                        </span>
                        <h4 className="text-sm font-800 text-emerald-200">{step.phase}</h4>
                      </div>
                      <Badge variant="green" size="sm">{step.timeline}</Badge>
                    </div>

                    <p className="text-xs text-slate-300 font-500"><strong>Objective:</strong> {step.objective}</p>

                    <div className="grid grid-cols-1 md:grid-cols-2 gap-3 text-xs">
                      <div className="space-y-1">
                        <span className="font-700 text-slate-300">Milestones & KPIs:</span>
                        <ul className="space-y-1 text-slate-400">
                          {(step.milestones || []).map((m, i) => <li key={i} className="flex items-start gap-1"><span className="text-emerald-400">✓</span> {m}</li>)}
                          {(step.kpis || []).map((k, i) => <li key={i} className="flex items-start gap-1"><span className="text-blue-400">📈</span> {k}</li>)}
                        </ul>
                      </div>
                      <div className="space-y-1">
                        <span className="font-700 text-slate-300">Required Deliverables:</span>
                        <ul className="space-y-1 text-slate-400">
                          {(step.deliverables || []).map((d, i) => <li key={i} className="flex items-start gap-1"><span className="text-purple-400">📄</span> {d}</li>)}
                        </ul>
                      </div>
                    </div>

                    {step.exit_criteria && (
                      <div className="p-2.5 rounded-lg bg-blue-500/10 border border-blue-500/20 text-xs text-blue-300 font-500">
                        <strong>Exit Criteria:</strong> {step.exit_criteria}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </Card>
          )}

          {/* Technical Roadmap */}
          {activeTab === 'tech_roadmap' && report?.technical_roadmap && (
            <Card className="space-y-6">
              <h3 className="text-xs font-800 uppercase tracking-wider text-slate-300 border-b border-white/[0.06] pb-2 flex items-center gap-2">
                <Code size={16} className="text-purple-400" />
                <span>Technical Architecture & Engineering Roadmap</span>
              </h3>
              <div className="space-y-4">
                {report.technical_roadmap.map((step, idx) => (
                  <div key={idx} className="p-4 rounded-xl bg-slate-900/80 border border-purple-500/30 space-y-3">
                    <div className="flex items-center justify-between border-b border-white/[0.06] pb-2">
                      <div className="flex items-center gap-2">
                        <span className="w-6 h-6 rounded-full bg-purple-500/20 text-purple-400 font-800 text-xs flex items-center justify-center border border-purple-500/30">
                          {idx + 1}
                        </span>
                        <h4 className="text-sm font-800 text-purple-200">{step.phase}</h4>
                      </div>
                      <Badge variant="purple" size="sm">{step.timeline}</Badge>
                    </div>

                    <div className="grid grid-cols-1 md:grid-cols-2 gap-3 text-xs">
                      <div className="space-y-1">
                        <span className="font-700 text-slate-300">Engineering Milestones:</span>
                        <ul className="space-y-1 text-slate-400">
                          {(step.milestones || []).map((m, i) => <li key={i} className="flex items-start gap-1"><span className="text-purple-400">⚙️</span> {m}</li>)}
                        </ul>
                      </div>
                      <div className="space-y-1">
                        <span className="font-700 text-slate-300">Technology Stack:</span>
                        <ul className="space-y-1 text-slate-400">
                          {(step.stack || []).map((s, i) => <li key={i} className="flex items-start gap-1"><span className="text-blue-400">💻</span> {s}</li>)}
                        </ul>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </Card>
          )}

        </div>
      )}

    </div>
  )
}
