import { Card } from '../ui'

export default function RisksTab({ data }) {
  if (!data || !data.risks || data.risks.length === 0) {
    return <div className="text-slate-500 text-sm">No risk data available.</div>
  }

  const getSeverityBadge = (level = '') => {
    const l = String(level).toUpperCase()
    if (l.includes('HIGH')) {
      return {
        badge: 'bg-rose-500/10 text-rose-400 border-rose-500/20',
        border: 'border-l-rose-500',
        dot: 'bg-rose-400',
      }
    } else if (l.includes('LOW')) {
      return {
        badge: 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20',
        border: 'border-l-emerald-500',
        dot: 'bg-emerald-400',
      }
    }
    return {
      badge: 'bg-amber-500/10 text-amber-400 border-amber-500/20',
      border: 'border-l-amber-500',
      dot: 'bg-amber-400',
    }
  }

  const getProbabilityBadge = (prob = '') => {
    const p = String(prob).toUpperCase()
    if (p.includes('HIGH')) {
      return 'bg-purple-500/10 text-purple-300 border-purple-500/20'
    } else if (p.includes('LOW')) {
      return 'bg-slate-500/10 text-slate-300 border-slate-500/20'
    }
    return 'bg-blue-500/10 text-blue-300 border-blue-500/20'
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between pb-2 border-b border-white/[0.06] px-1">
        <h3 className="text-xs font-800 text-slate-200 uppercase tracking-wider flex items-center gap-1.5">
          <span>⚠️</span> Enterprise Risk Matrix & Mitigation Controls
        </h3>
        <span className="text-[0.65rem] text-slate-500 font-mono">
          {data.risks.length} Risk Factors
        </span>
      </div>

      <div className="grid grid-cols-1 gap-4">
        {data.risks.map((risk, i) => {
          const sevStyle = getSeverityBadge(risk.severity)
          const probBadge = getProbabilityBadge(risk.probability)

          return (
            <Card
              key={i}
              className={`flex flex-col md:flex-row md:items-start gap-5 p-4.5 border-l-4 ${sevStyle.border} bg-white/[0.015]`}
            >
              {/* Left Column: Category & Enums */}
              <div className="md:w-56 shrink-0 space-y-2.5">
                <div>
                  <span className="text-[0.62rem] text-slate-500 uppercase tracking-wider block mb-0.5 font-bold">Category</span>
                  <h4 className="text-sm font-800 text-slate-100 flex items-center gap-1.5">
                    <span className={`w-2 h-2 rounded-full ${sevStyle.dot}`} />
                    {risk.category || 'Operational'}
                  </h4>
                </div>

                <div className="flex flex-wrap md:flex-col gap-2 pt-1">
                  <div className="flex items-center gap-2">
                    <span className="text-[0.62rem] text-slate-500 uppercase tracking-wider w-16">Severity:</span>
                    <span className={`inline-block px-2 py-0.5 rounded text-[0.65rem] font-bold border uppercase tracking-wider ${sevStyle.badge}`}>
                      {risk.severity || 'MEDIUM'}
                    </span>
                  </div>

                  <div className="flex items-center gap-2">
                    <span className="text-[0.62rem] text-slate-500 uppercase tracking-wider w-16">Likelihood:</span>
                    <span className={`inline-block px-2 py-0.5 rounded text-[0.65rem] font-bold border uppercase tracking-wider ${probBadge}`}>
                      {risk.probability || 'MEDIUM'}
                    </span>
                  </div>
                </div>
              </div>

              {/* Right Column: Description, Impact, Mitigation & Monitoring Indicator */}
              <div className="flex-1 space-y-3">
                {/* Risk statement */}
                <div>
                  <div className="text-[0.62rem] text-slate-500 uppercase tracking-wider mb-1 font-bold">
                    Risk Statement
                  </div>
                  <p className="text-xs text-slate-200 leading-relaxed bg-white/[0.02] p-3 rounded-lg border border-white/[0.04]">
                    {risk.risk || risk.description}
                  </p>
                </div>

                {/* Impact */}
                {risk.impact && (
                  <div className="text-[0.72rem] text-slate-400">
                    <span className="text-slate-500 font-semibold uppercase text-[0.62rem] block mb-0.5">Potential Impact:</span>
                    <span className="text-slate-300 leading-relaxed">{risk.impact}</span>
                  </div>
                )}

                {/* Mitigation */}
                <div>
                  <div className="text-[0.65rem] text-blue-400 font-bold uppercase tracking-wider mb-1 flex items-center gap-1">
                    <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"></path></svg>
                    Actionable Mitigation Strategy
                  </div>
                  <p className="text-xs text-blue-200/90 leading-relaxed bg-blue-500/[0.04] p-3 rounded-lg border border-blue-500/20">
                    {risk.mitigation}
                  </p>
                </div>

                {/* Monitoring Indicator */}
                {risk.monitoring_indicator && (
                  <div className="pt-2 border-t border-white/[0.04] flex items-center gap-2 text-[0.7rem] text-slate-400">
                    <span className="text-amber-400/80 font-bold">KPI Trigger:</span>
                    <span className="text-slate-300 font-mono text-[0.68rem]">{risk.monitoring_indicator}</span>
                  </div>
                )}
              </div>
            </Card>
          )
        })}
      </div>
    </div>
  )
}
