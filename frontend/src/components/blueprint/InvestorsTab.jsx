import { Card } from '../ui'

export default function InvestorsTab({ data }) {
  if (!data) return <div className="text-slate-500 text-sm">No funding data available.</div>

  const roadmap = data.funding_roadmap || []
  const schemes = data.government_schemes || []
  const investorTypes = data.investor_types || data.investor_landscape || []
  const incubators = data.incubators || data.relevant_incubators || []
  const pitchTips = data.pitch_tips || []

  const getTypeBadge = (type = '') => {
    const t = type.toLowerCase()
    if (t.includes('grant')) {
      return 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20'
    } else if (t.includes('debt') || t.includes('guarantee') || t.includes('credit')) {
      return 'bg-blue-500/10 text-blue-400 border-blue-500/20'
    } else if (t.includes('loan')) {
      return 'bg-purple-500/10 text-purple-400 border-purple-500/20'
    } else if (t.includes('tax')) {
      return 'bg-amber-500/10 text-amber-400 border-amber-500/20'
    } else if (t.includes('equity')) {
      return 'bg-violet-500/10 text-violet-400 border-violet-500/20'
    }
    return 'bg-slate-500/10 text-slate-300 border-slate-500/20'
  }

  return (
    <div className="space-y-6">
      {/* ── 1. Funding Roadmap ── */}
      <div>
        <div className="flex items-center justify-between mb-3 border-b border-white/[0.06] pb-2 px-1">
          <h3 className="text-xs font-800 text-blue-400 uppercase tracking-wider flex items-center gap-1.5">
            <span>🗺️</span> Capital Roadmap
          </h3>
          <span className="text-[0.65rem] text-slate-500">Phased Capital Strategy</span>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {roadmap.map((road, i) => (
            <Card key={i} className="flex flex-col relative overflow-hidden group bg-white/[0.015] border-white/[0.07] p-4">
              <div className="absolute top-1 right-2 pointer-events-none select-none text-4xl font-900 text-blue-500/[0.07] group-hover:text-blue-500/[0.12] transition-colors">
                {i + 1}
              </div>
              <div className="flex justify-between items-start mb-2 relative z-10">
                <h4 className="text-sm font-800 text-blue-300">{road.stage}</h4>
                <span className="text-[0.65rem] font-bold bg-blue-500/10 text-blue-400 px-2 py-0.5 rounded border border-blue-500/20">
                  {road.timeline}
                </span>
              </div>
              <div className="text-xs text-slate-400 mb-3 relative z-10 flex-1">
                <span className="text-slate-500 font-semibold block text-[0.65rem] uppercase tracking-wider mb-0.5">Recommended Source</span>
                <span className="text-slate-300">{road.source}</span>
              </div>
              <div className="mt-auto pt-3 border-t border-white/[0.05] relative z-10 flex justify-between items-end">
                <div>
                  <div className="text-[0.62rem] text-slate-500 uppercase tracking-wider">Target Capital</div>
                  <div className="text-sm font-800 text-emerald-400 font-mono">{road.amount}</div>
                </div>
                <span className="text-[0.6rem] text-slate-500">Milestone-linked</span>
              </div>
            </Card>
          ))}
        </div>
      </div>

      {/* ── 2. Government Schemes & Financial Subsidies ── */}
      {schemes.length > 0 && (
        <div className="space-y-3">
          <div className="flex items-center justify-between px-1">
            <h3 className="text-[0.72rem] font-800 text-emerald-400 uppercase tracking-wider flex items-center gap-1.5">
              <span>🏛️</span> Official Government Schemes & Subsidies
            </h3>
            <span className="text-[0.65rem] text-emerald-400/80 bg-emerald-500/10 border border-emerald-500/20 px-2 py-0.5 rounded-full font-semibold">
              Authoritative Grounding
            </span>
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            {schemes.map((scheme, i) => (
              <Card key={i} className="flex flex-col border-l-4 border-l-emerald-500 bg-white/[0.015] p-4.5 space-y-3">
                <div className="flex justify-between items-start gap-3">
                  <div>
                    <h4 className="text-sm font-800 text-slate-100">{scheme.name}</h4>
                    {scheme.administering_agency && (
                      <div className="text-[0.68rem] text-slate-400 mt-0.5">
                        Agency: <span className="text-slate-300 font-medium">{scheme.administering_agency}</span>
                      </div>
                    )}
                  </div>
                  <div className="flex flex-col items-end gap-1 shrink-0">
                    {scheme.amount && (
                      <span className="text-xs text-emerald-400 font-800 bg-emerald-500/10 px-2.5 py-0.5 rounded border border-emerald-500/20 font-mono">
                        {scheme.amount}
                      </span>
                    )}
                    {scheme.type && (
                      <span className={`text-[0.6rem] font-bold px-2 py-0.2 rounded border uppercase tracking-wider ${getTypeBadge(scheme.type)}`}>
                        {scheme.type}
                      </span>
                    )}
                  </div>
                </div>

                {scheme.benefit && (
                  <div className="bg-white/[0.02] p-2.5 rounded-lg border border-white/[0.04]">
                    <div className="text-[0.62rem] text-slate-500 uppercase tracking-wider mb-0.5 font-bold">Key Benefit</div>
                    <div className="text-xs text-slate-300 leading-relaxed">{scheme.benefit}</div>
                  </div>
                )}

                <div className="space-y-2 text-xs text-slate-300">
                  {scheme.eligibility && (
                    <div>
                      <span className="text-[0.62rem] text-slate-500 uppercase tracking-wider block mb-0.5 font-bold">Eligibility Criteria</span>
                      <p className="text-slate-400 leading-relaxed text-[0.73rem] bg-white/[0.01] p-2 rounded border border-white/[0.03]">
                        {scheme.eligibility}
                      </p>
                    </div>
                  )}

                  {scheme.application_steps && (
                    <div>
                      <span className="text-[0.62rem] text-slate-500 uppercase tracking-wider block mb-0.5 font-bold">Application Pathway</span>
                      <p className="text-slate-400 text-[0.72rem] leading-relaxed">
                        {scheme.application_steps}
                      </p>
                    </div>
                  )}

                  {scheme.conditions && (
                    <div className="text-[0.7rem] text-slate-500 italic">
                      <span className="font-semibold text-slate-400 not-italic">Conditions: </span>
                      {scheme.conditions}
                    </div>
                  )}
                </div>

                <div className="mt-auto pt-3 border-t border-white/[0.05] flex items-center justify-between text-[0.7rem]">
                  <span className="text-slate-500">
                    Source: <span className="text-slate-400">{scheme.source || 'Official Guidelines'}</span>
                  </span>
                  {scheme.official_url && (
                    <a
                      href={scheme.official_url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-emerald-400 hover:text-emerald-300 inline-flex items-center gap-1 font-semibold hover:underline"
                    >
                      <span>Official Portal</span>
                      <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5"><path d="M18 13v6a2 2 0 01-2 2H5a2 2 0 01-2-2V8a2 2 0 012-2h6"></path><polyline points="15 3 21 3 21 9"></polyline><line x1="10" y1="14" x2="21" y2="3"></line></svg>
                    </a>
                  )}
                </div>
              </Card>
            ))}
          </div>
        </div>
      )}

      {/* ── 3. Private Investors, Incubators & Pitch Tips ── */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
        {/* Investor Landscape */}
        <div className="space-y-3">
          <div className="flex items-center justify-between px-1">
            <h3 className="text-[0.72rem] font-800 text-purple-400 uppercase tracking-wider flex items-center gap-1.5">
              <span>💼</span> Relevant Investor Networks
            </h3>
            <span className="text-[0.65rem] text-slate-500">{investorTypes.length} Categories</span>
          </div>

          <div className="space-y-3">
            {investorTypes.length > 0 ? (
              investorTypes.map((inv, i) => (
                <Card key={i} className="p-3.5 bg-white/[0.015] border-white/[0.06]">
                  <div className="flex justify-between items-center mb-2">
                    <div className="text-xs font-800 text-slate-200">{inv.type}</div>
                    <div className="text-[0.62rem] text-purple-300 bg-purple-500/10 border border-purple-500/20 px-2 py-0.5 rounded font-semibold">
                      {inv.stage}
                    </div>
                  </div>
                  {inv.focus && (
                    <div className="text-[0.72rem] text-slate-400 mb-2">
                      Focus: <span className="text-slate-300">{inv.focus}</span>
                    </div>
                  )}
                  <div className="text-[0.62rem] text-slate-500 uppercase tracking-wider mb-1 font-bold">Notable Examples</div>
                  <div className="flex flex-wrap gap-1.5">
                    {(Array.isArray(inv.examples) ? inv.examples : [inv.examples].filter(Boolean)).map((ex, j) => (
                      <span key={j} className="text-[0.68rem] bg-purple-500/10 border border-purple-500/20 text-purple-300 px-2 py-0.5 rounded">
                        {ex}
                      </span>
                    ))}
                  </div>
                </Card>
              ))
            ) : (
              <div className="text-xs text-slate-500 italic p-4 border border-white/[0.04] rounded-xl bg-white/[0.01]">
                Investor landscape recommendations unavailable.
              </div>
            )}
          </div>
        </div>

        {/* Incubators & Pitch Tips */}
        <div className="space-y-5">
          {/* Incubators */}
          <div className="space-y-3">
            <div className="flex items-center justify-between px-1">
              <h3 className="text-[0.72rem] font-800 text-amber-400 uppercase tracking-wider flex items-center gap-1.5">
                <span>🌱</span> Recommended Incubators & Accelerators
              </h3>
              <span className="text-[0.65rem] text-slate-500">{incubators.length} Partners</span>
            </div>

            <div className="space-y-2">
              {incubators.length > 0 ? (
                incubators.map((inc, i) => (
                  <Card key={i} className="p-3 flex justify-between items-center bg-white/[0.015] border-white/[0.06]">
                    <div>
                      <div className="text-xs font-700 text-slate-200">{inc.name}</div>
                      <div className="text-[0.68rem] text-slate-400">{inc.focus}</div>
                    </div>
                    <div className="text-[0.62rem] text-amber-400 border border-amber-500/20 bg-amber-500/10 px-2 py-0.5 rounded font-mono shrink-0 ml-2">
                      {inc.location}
                    </div>
                  </Card>
                ))
              ) : (
                <div className="text-xs text-slate-500 italic p-3 border border-white/[0.04] rounded-lg bg-white/[0.01]">
                  No incubator matches listed.
                </div>
              )}
            </div>
          </div>

          {/* Pitch Tips */}
          <Card className="border-l-4 border-l-blue-500 p-4 bg-white/[0.015]">
            <h3 className="text-[0.72rem] font-800 text-blue-400 uppercase tracking-wider mb-2.5 flex items-center gap-1.5">
              <span>💡</span> Pitch & Due Diligence Advisory
            </h3>
            {pitchTips.length > 0 ? (
              <ul className="space-y-2">
                {pitchTips.map((tip, i) => (
                  <li key={i} className="text-xs text-slate-300 flex gap-2 items-start leading-relaxed">
                    <span className="text-blue-400 mt-0.5 shrink-0">✦</span>
                    <span>{tip}</span>
                  </li>
                ))}
              </ul>
            ) : (
              <div className="text-xs text-slate-500 italic">No pitch tips available.</div>
            )}
          </Card>
        </div>
      </div>

      {/* ── 4. Regulatory & Eligibility Disclaimer ── */}
      <div className="p-3.5 rounded-xl border border-white/[0.05] bg-white/[0.01] text-[0.68rem] text-slate-500 leading-relaxed flex items-start gap-2">
        <span className="text-amber-400 shrink-0 text-sm">ℹ️</span>
        <span>
          <strong>Funding Disclaimer:</strong> Government grants (SISFS, CGSS, MSME) and institutional investment amounts represent official statutory limits and benchmarks. Disbursement is subject to formal application, eligibility verification, incubator selection committee evaluation, and investor due diligence. No capital amounts are guaranteed.
        </span>
      </div>
    </div>
  )
}
