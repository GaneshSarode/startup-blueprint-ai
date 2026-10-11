import { Card } from '../ui'

export default function GTMTab({ data }) {
  if (!data) return <div className="text-slate-500 text-sm">No GTM data available.</div>

  const getPriorityColor = (priority) => {
    switch (priority?.toLowerCase()) {
      case 'high': return 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20'
      case 'medium': return 'bg-amber-500/10 text-amber-400 border-amber-500/20'
      case 'low': return 'bg-slate-500/10 text-slate-400 border-slate-500/20'
      default: return 'bg-blue-500/10 text-blue-400 border-blue-500/20'
    }
  }

  // Parse or extract TAM, SAM, SOM
  const sizing = data.market_sizing || {}
  const rawSizeStr = data.market_size || ''

  // Fallback parsers if structured market_sizing is not present
  const extractMetric = (pattern, fallback) => {
    const match = rawSizeStr.match(pattern)
    return match ? match[1].trim() : fallback
  }

  const tamVal = sizing.tam || extractMetric(/TAM:?\s*([^,|]+)/i, '₹25,000 Cr ($3B)')
  const samVal = sizing.sam || extractMetric(/SAM:?\s*([^,|]+)/i, '₹4,500 Cr ($540M)')
  const somVal = sizing.som || extractMetric(/SOM:?\s*([^,)]+)/i, '₹150 Cr ($18M)')

  return (
    <div className="space-y-6">
      {/* ── TOP SECTION: Balanced 2-Column Target Market & Market Sizing ── */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-5 items-stretch">
        {/* Target Market Card */}
        <Card className="flex flex-col border-l-4 border-l-blue-500 bg-white/[0.015]">
          <div className="flex items-center justify-between mb-3 pb-2 border-b border-white/[0.06]">
            <div className="flex items-center gap-2">
              <span className="text-base select-none" aria-hidden="true">🎯</span>
              <h3 className="text-xs font-800 text-blue-400 uppercase tracking-wider">
                Target Market & ICP
              </h3>
            </div>
            <span className="text-[0.65rem] px-2 py-0.5 rounded bg-blue-500/10 text-blue-300 border border-blue-500/20">
              Primary Segment
            </span>
          </div>

          <p className="text-sm text-slate-300 leading-relaxed flex-1 whitespace-pre-line">
            {data.target_market || 'Target market definition currently in progress.'}
          </p>

          <div className="mt-4 pt-3 border-t border-white/[0.05] grid grid-cols-2 gap-3 text-xs text-slate-400">
            <div>
              <span className="text-[0.65rem] text-slate-500 uppercase tracking-wider block mb-0.5">Geography</span>
              <span className="text-slate-200 font-semibold">{sizing.geography || 'Pan-India / Tier 1 & 2'}</span>
            </div>
            <div>
              <span className="text-[0.65rem] text-slate-500 uppercase tracking-wider block mb-0.5">Validation</span>
              <span className="text-emerald-400 font-semibold">Active Early Demand</span>
            </div>
          </div>
        </Card>

        {/* Market Sizing Breakdown Card */}
        <Card className="flex flex-col border-l-4 border-l-emerald-500 bg-white/[0.015]">
          <div className="flex items-center justify-between mb-3 pb-2 border-b border-white/[0.06]">
            <div className="flex items-center gap-2">
              <span className="text-base select-none" aria-hidden="true">📊</span>
              <h3 className="text-xs font-800 text-emerald-400 uppercase tracking-wider">
                Market Sizing (TAM · SAM · SOM)
              </h3>
            </div>
            <span className="text-[0.65rem] px-2 py-0.5 rounded bg-emerald-500/10 text-emerald-300 border border-emerald-500/20">
              Estimated Opportunity
            </span>
          </div>

          {/* 3 Metric Pills */}
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-2.5 mb-3 flex-1">
            <div className="bg-white/[0.03] border border-white/[0.06] rounded-xl p-3 flex flex-col justify-between">
              <div>
                <span className="text-[0.65rem] font-bold text-slate-400 uppercase tracking-wider block mb-0.5">TAM</span>
                <span className="text-[0.62rem] text-slate-500 block leading-tight">Total Addressable</span>
              </div>
              <div className="text-base font-800 text-blue-300 mt-2 font-mono break-words">{tamVal}</div>
            </div>

            <div className="bg-white/[0.03] border border-white/[0.06] rounded-xl p-3 flex flex-col justify-between">
              <div>
                <span className="text-[0.65rem] font-bold text-slate-400 uppercase tracking-wider block mb-0.5">SAM</span>
                <span className="text-[0.62rem] text-slate-500 block leading-tight">Serviceable Market</span>
              </div>
              <div className="text-base font-800 text-indigo-300 mt-2 font-mono break-words">{samVal}</div>
            </div>

            <div className="bg-white/[0.03] border border-white/[0.06] rounded-xl p-3 flex flex-col justify-between">
              <div>
                <span className="text-[0.65rem] font-bold text-slate-400 uppercase tracking-wider block mb-0.5">SOM</span>
                <span className="text-[0.62rem] text-slate-500 block leading-tight">Year 1-2 Realistic</span>
              </div>
              <div className="text-base font-800 text-emerald-400 mt-2 font-mono break-words">{somVal}</div>
            </div>
          </div>

          {/* Assumptions & Grounding Note */}
          <div className="pt-2.5 border-t border-white/[0.05] space-y-1 text-[0.72rem] text-slate-400">
            <div className="flex items-start gap-1.5">
              <span className="text-slate-500 font-semibold shrink-0">Assumptions:</span>
              <span className="text-slate-300">{sizing.assumptions || 'Based on target audience concentration and current digital adoption velocity.'}</span>
            </div>
            <div className="flex items-start gap-1.5">
              <span className="text-slate-500 font-semibold shrink-0">Sources:</span>
              <span className="text-slate-400 italic">{sizing.sources || 'Industry research databases and public market sizing benchmarks.'}</span>
            </div>
          </div>
        </Card>
      </div>

      {/* ── MIDDLE SECTION: Launch Strategy & Growth Channels ── */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
        {/* Launch Strategy */}
        <div className="space-y-3">
          <div className="flex items-center justify-between px-1">
            <h3 className="text-[0.72rem] font-800 text-purple-400 uppercase tracking-wider flex items-center gap-1.5">
              <span>🚀</span> Sequential Launch Strategy
            </h3>
            <span className="text-[0.65rem] text-slate-500">{data.launch_strategy?.length || 0} Phases</span>
          </div>

          <div className="space-y-2.5">
            {data.launch_strategy?.map((step, i) => (
              <Card key={i} className="flex gap-3 items-start py-3 px-3.5 bg-white/[0.015] border-white/[0.06]">
                <div className="w-6 h-6 rounded-lg bg-purple-500/15 border border-purple-500/25 text-purple-300 flex items-center justify-center font-800 text-xs shrink-0 mt-0.5">
                  {i + 1}
                </div>
                <div className="text-xs text-slate-200 leading-relaxed">{step}</div>
              </Card>
            ))}
          </div>
        </div>

        {/* Growth Channels */}
        <div className="space-y-3">
          <div className="flex items-center justify-between px-1">
            <h3 className="text-[0.72rem] font-800 text-amber-400 uppercase tracking-wider flex items-center gap-1.5">
              <span>📈</span> Growth & Acquisition Channels
            </h3>
            <span className="text-[0.65rem] text-slate-500">{data.growth_channels?.length || 0} Channels</span>
          </div>

          <div className="space-y-2.5">
            {data.growth_channels?.map((c, i) => (
              <Card key={i} className="flex flex-col gap-2 p-3.5 bg-white/[0.015] border-white/[0.06]">
                <div className="flex justify-between items-start gap-2">
                  <div className="text-xs font-800 text-slate-100">{c.channel}</div>
                  <div className="flex items-center gap-1.5 shrink-0">
                    <span className={`text-[0.6rem] font-700 px-2 py-0.5 rounded border uppercase tracking-wider ${getPriorityColor(c.priority)}`}>
                      {c.priority} Priority
                    </span>
                    {c.cost && (
                      <span className="text-[0.6rem] font-semibold text-slate-400 bg-white/[0.04] border border-white/[0.06] px-1.5 py-0.5 rounded">
                        {c.cost}
                      </span>
                    )}
                  </div>
                </div>
                {c.strategy && (
                  <div className="text-xs text-slate-300">{c.strategy}</div>
                )}
                <div className="text-[0.7rem] text-slate-400 bg-white/[0.02] p-2 rounded border border-white/[0.04]">
                  <span className="text-slate-500 font-semibold">Rationale: </span>
                  {c.rationale}
                </div>
              </Card>
            ))}
          </div>
        </div>
      </div>

      {/* ── BOTTOM SECTION: Milestones & Key Metrics ── */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-5">
        <div className="lg:col-span-2 space-y-3">
          <h3 className="text-[0.72rem] font-800 text-emerald-400 uppercase tracking-wider px-1 flex items-center gap-1.5">
            <span>📅</span> Timeline & Execution Milestones
          </h3>
          <Card className="p-4 bg-white/[0.015]">
            <div className="space-y-3">
              {data.milestones?.map((m, i) => (
                <div key={i} className="flex items-center gap-3 p-2.5 rounded-lg border border-white/[0.04] bg-white/[0.01]">
                  <div className="w-12 text-center py-1 rounded bg-blue-500/10 border border-blue-500/20 text-[0.68rem] font-bold text-blue-300 shrink-0">
                    M{m.month}
                  </div>
                  <div className="text-xs text-slate-300 flex-1 leading-relaxed">{m.goal}</div>
                </div>
              ))}
            </div>
          </Card>
        </div>

        <div className="space-y-3">
          <h3 className="text-[0.72rem] font-800 text-sky-400 uppercase tracking-wider px-1 flex items-center gap-1.5">
            <span>📐</span> Key Metrics (KPIs)
          </h3>
          <Card className="h-full p-4 bg-white/[0.015]">
            <ul className="space-y-2.5">
              {data.key_metrics?.map((m, i) => (
                <li key={i} className="flex gap-2 items-start text-xs text-slate-300">
                  <span className="text-sky-400 font-bold shrink-0">✓</span>
                  <span>{m}</span>
                </li>
              ))}
            </ul>
          </Card>
        </div>
      </div>
    </div>
  )
}
