import { Card } from '../ui'

export default function CompetitorsTab({ data }) {
  if (!data) return <div className="text-slate-500 text-sm">No competitors data available.</div>

  const competitors = data.competitors || []
  const differentiators = data.our_differentiators || data.differentiators || []
  const marketGaps = data.market_gaps || data.gaps || []
  const strategy = data.competitive_strategy || data.strategy || ''

  // Normalize market share percentage string cleanly
  const formatMarketShare = (share) => {
    if (!share) return null
    const s = String(share).trim()
    if (!s || s.toLowerCase() === 'n/a' || s.toLowerCase() === 'unknown' || s.toLowerCase() === 'none') {
      return null
    }
    const numericPart = s.replace(/%+/g, '').trim()
    if (!isNaN(parseFloat(numericPart))) {
      return `${numericPart}% Est. Share`
    }
    return s.endsWith('%') ? `${s} Share` : s
  }

  return (
    <div className="space-y-6">
      {/* ── 1. Competitors Grid ── */}
      <div>
        <div className="flex items-center justify-between mb-3 border-b border-white/[0.06] pb-2 px-1">
          <h3 className="text-xs font-800 text-slate-200 uppercase tracking-wider flex items-center gap-1.5">
            <span>⚔️</span> Competitive Landscape & Alternatives
          </h3>
          <span className="text-[0.65rem] text-slate-500 font-mono">
            {competitors.length} Evaluated {competitors.length === 1 ? 'Player' : 'Players'}
          </span>
        </div>

        {competitors.length > 0 ? (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {competitors.map((comp, i) => {
              const marketShareLabel = formatMarketShare(comp.market_share)

              return (
                <Card
                  key={i}
                  className="flex flex-col border-t-2 border-t-slate-700 hover:border-t-blue-500 transition-all duration-200 bg-white/[0.015] p-4 space-y-3"
                >
                  {/* Top: Name, Type, and Share */}
                  <div className="flex justify-between items-start gap-2">
                    <div>
                      <h4 className="text-sm font-800 text-slate-100">{comp.name}</h4>
                      {comp.type && (
                        <span className="text-[0.62rem] text-slate-400 font-medium block mt-0.5">
                          {comp.type} Competitor
                        </span>
                      )}
                    </div>
                    {marketShareLabel && (
                      <span className="text-[0.65rem] font-bold bg-blue-500/10 text-blue-300 border border-blue-500/20 px-2 py-0.5 rounded font-mono shrink-0">
                        {marketShareLabel}
                      </span>
                    )}
                  </div>

                  {/* Target Customer & Core Offering */}
                  {(comp.target_customer || comp.core_offering || comp.core_features) && (
                    <div className="space-y-1 text-xs">
                      {comp.target_customer && (
                        <div className="text-[0.7rem] text-slate-400">
                          <span className="text-slate-500 font-semibold">Target: </span>
                          {comp.target_customer}
                        </div>
                      )}
                      {(comp.core_features || comp.core_offering) && (
                        <div className="text-[0.7rem] text-slate-300 leading-snug">
                          <span className="text-slate-500 font-semibold">Core: </span>
                          {comp.core_features || comp.core_offering}
                        </div>
                      )}
                    </div>
                  )}

                  {/* Strengths & Weaknesses */}
                  <div className="space-y-2 flex-1 pt-1">
                    {comp.strength && (
                      <div>
                        <div className="text-[0.62rem] text-emerald-400/80 uppercase tracking-wider font-bold mb-0.5 flex items-center gap-1">
                          <span>✓</span> Strengths
                        </div>
                        <div className="text-xs text-slate-300 leading-relaxed bg-emerald-500/[0.03] p-2 rounded border border-emerald-500/10">
                          {comp.strength}
                        </div>
                      </div>
                    )}

                    {comp.weakness && (
                      <div>
                        <div className="text-[0.62rem] text-rose-400/80 uppercase tracking-wider font-bold mb-0.5 flex items-center gap-1">
                          <span>✗</span> Limitations / Gaps
                        </div>
                        <div className="text-xs text-rose-200/85 leading-relaxed bg-rose-500/[0.04] p-2 rounded border border-rose-500/10">
                          {comp.weakness}
                        </div>
                      </div>
                    )}

                    {comp.differentiator && (
                      <div className="text-[0.7rem] text-blue-300/90 bg-blue-500/[0.04] p-2 rounded border border-blue-500/15">
                        <span className="text-blue-400 font-bold">Our Edge: </span>
                        {comp.differentiator}
                      </div>
                    )}
                  </div>

                  {/* Footer: Pricing, Funding, Source */}
                  <div className="mt-auto pt-2.5 border-t border-white/[0.05] flex items-center justify-between text-[0.68rem] text-slate-400">
                    <div>
                      {comp.pricing && (
                        <span className="text-slate-500">
                          Pricing: <span className="text-slate-300 font-medium">{comp.pricing}</span>
                        </span>
                      )}
                    </div>
                    {comp.funding && (
                      <div className="font-semibold text-emerald-400">
                        {comp.funding}
                      </div>
                    )}
                  </div>
                  {comp.source && (
                    <div className="text-[0.62rem] text-slate-500 italic text-right">
                      Source: {comp.source}
                    </div>
                  )}
                </Card>
              )
            })}
          </div>
        ) : (
          <div className="text-center p-8 rounded-xl border border-white/[0.05] bg-white/[0.01] space-y-2">
            <div className="text-sm font-semibold text-slate-400">No Direct Competitors Documented</div>
            <p className="text-xs text-slate-500 max-w-md mx-auto">
              Sufficient evidence was not found in the verified knowledge base or web search. Prompt the AI Mentor to explore niche emerging alternatives.
            </p>
          </div>
        )}
      </div>

      {/* ── 2. Differentiators & Market Gaps ── */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
        {/* Differentiators */}
        <Card className="border-l-4 border-l-blue-500 p-4 bg-white/[0.015] space-y-3">
          <div className="flex items-center justify-between pb-2 border-b border-white/[0.06]">
            <h3 className="text-[0.72rem] font-800 text-blue-400 uppercase tracking-wider flex items-center gap-1.5">
              <span>💎</span> Our Value Differentiators
            </h3>
            <span className="text-[0.65rem] text-blue-400 bg-blue-500/10 px-2 py-0.5 rounded font-mono">
              Competitive Moats
            </span>
          </div>

          {differentiators.length > 0 ? (
            <ul className="space-y-2.5">
              {differentiators.map((diff, i) => (
                <li key={i} className="flex gap-2.5 items-start text-xs text-slate-200 leading-relaxed">
                  <span className="text-blue-400 font-bold shrink-0 mt-0.5">✦</span>
                  <span>{diff}</span>
                </li>
              ))}
            </ul>
          ) : (
            <div className="text-xs text-slate-500 italic py-2">No unique differentiators specified.</div>
          )}
        </Card>

        {/* Market Gaps */}
        <Card className="border-l-4 border-l-amber-500 p-4 bg-white/[0.015] space-y-3">
          <div className="flex items-center justify-between pb-2 border-b border-white/[0.06]">
            <h3 className="text-[0.72rem] font-800 text-amber-400 uppercase tracking-wider flex items-center gap-1.5">
              <span>🎯</span> Exploitable Market Gaps
            </h3>
            <span className="text-[0.65rem] text-amber-400 bg-amber-500/10 px-2 py-0.5 rounded font-mono">
              White Space
            </span>
          </div>

          {marketGaps.length > 0 ? (
            <ul className="space-y-2.5">
              {marketGaps.map((gap, i) => (
                <li key={i} className="flex gap-2.5 items-start text-xs text-slate-200 leading-relaxed">
                  <span className="text-amber-400 font-bold shrink-0 mt-0.5">◎</span>
                  <span>{gap}</span>
                </li>
              ))}
            </ul>
          ) : (
            <div className="text-xs text-slate-500 italic py-2">No market gaps listed.</div>
          )}
        </Card>
      </div>

      {/* ── 3. Strategic Positioning ── */}
      {strategy && (
        <Card className="p-4 bg-gradient-to-br from-white/[0.02] to-blue-500/[0.03] border border-blue-500/20">
          <h3 className="text-xs font-800 text-blue-300 uppercase tracking-wider mb-2 flex items-center gap-2">
            <span>🛡️</span> Strategic Market Positioning
          </h3>
          <p className="text-xs text-slate-300 leading-relaxed whitespace-pre-wrap">
            {strategy}
          </p>
        </Card>
      )}
    </div>
  )
}
