import { useState } from 'react'
import { Card } from '../ui'

export default function CRAGPipelineTab({ data }) {
  const [showRaw, setShowRaw] = useState(false)
  const [expandedDocs, setExpandedDocs] = useState({})

  if (!data) return <div className="text-slate-500 text-sm">No CRAG trace data available.</div>

  const confidence = data.confidence || 'CORRECT'
  const action = data.action || data.decision || 'Blueprint grounded in verified official Indian startup context.'
  const sources = data.sources || []
  const retrievedDocs = data.retrieved_documents || []
  const maxLogit = data.max_logit || (data.raw_logits ? Math.max(...data.raw_logits) : null)
  const exploreResults = data.explore_results || []
  const summary = data.summary || data.granite_summary || ''
  const verifiedContext = data.verified_context || []
  const inferences = data.inferences || []
  const recommendations = data.recommendations || []
  const sourceUsage = data.source_usage || []

  // Sanitize path if any raw filesystem path leaked
  const cleanDocName = (name = '') => {
    if (!name) return 'Official Document'
    const clean = name.replace(/\\/g, '/').split('/').pop()
    return clean || name
  }

  const toggleDoc = (idx) => {
    setExpandedDocs((prev) => ({ ...prev, [idx]: !prev[idx] }))
  }

  const getConfidenceBadge = (conf = '') => {
    const c = String(conf).toUpperCase()
    if (c === 'CORRECT') return 'bg-emerald-500/15 text-emerald-400 border-emerald-500/30'
    if (c === 'AMBIGUOUS') return 'bg-amber-500/15 text-amber-400 border-amber-500/30'
    return 'bg-rose-500/15 text-rose-400 border-rose-500/30'
  }

  // Clean unescaped newlines in summary text
  const formattedSummary = typeof summary === 'string'
    ? summary.replace(/\\n/g, '\n').replace(/\\"/g, '"')
    : ''

  return (
    <div className="space-y-6">
      {/* ── 1. CRAG Routing & Decision Banner ── */}
      <Card className="p-5 border-l-4 border-l-blue-500 bg-white/[0.015]">
        <div className="flex flex-wrap items-center justify-between gap-3 mb-3 pb-3 border-b border-white/[0.06]">
          <div className="flex items-center gap-2.5">
            <span className="text-xl select-none" aria-hidden="true">🧠</span>
            <div>
              <h3 className="text-sm font-800 text-slate-100 flex items-center gap-2">
                Corrective RAG (CRAG) Decision Engine
              </h3>
              <div className="text-[0.68rem] text-slate-400 mt-0.5">
                Evaluation Model: CrossEncoder / MS-MARCO MiniLM
              </div>
            </div>
          </div>

          <div className="flex items-center gap-2">
            <span className={`text-xs font-800 px-3 py-1 rounded-full border uppercase tracking-wider ${getConfidenceBadge(confidence)}`}>
              Decision: {confidence}
            </span>
            {maxLogit !== null && (
              <span className="text-xs font-mono font-bold text-slate-300 bg-white/[0.04] border border-white/[0.06] px-2.5 py-1 rounded-full">
                Logit: {Number(maxLogit).toFixed(2)}
              </span>
            )}
            {data.used_web_fallback && (
              <span className="text-xs font-bold text-amber-400 bg-amber-500/10 border border-amber-500/20 px-2.5 py-1 rounded-full">
                🌐 Web Fallback Active
              </span>
            )}
          </div>
        </div>

        <p className="text-xs text-slate-300 leading-relaxed">
          {action}
        </p>
      </Card>

      {/* ── 2. IBM Granite Policy Summary ── */}
      {formattedSummary && (
        <Card className="p-5 bg-white/[0.015] border-l-4 border-l-indigo-500 space-y-3">
          <div className="flex items-center justify-between pb-2 border-b border-white/[0.06]">
            <h4 className="text-xs font-800 text-indigo-300 uppercase tracking-wider flex items-center gap-1.5">
              <span>📜</span> Synthesized Policy Brief
            </h4>
            <span className="text-[0.65rem] text-indigo-400 bg-indigo-500/10 border border-indigo-500/20 px-2 py-0.5 rounded font-mono">
              IBM Granite 4.0
            </span>
          </div>
          <div className="text-xs text-slate-300 leading-relaxed whitespace-pre-line max-h-72 overflow-y-auto pr-2 custom-scrollbar">
            {formattedSummary}
          </div>
        </Card>
      )}

      {/* ── 3. Retrieved Source Documents & Excerpts ── */}
      <div className="space-y-3">
        <div className="flex items-center justify-between px-1">
          <h4 className="text-xs font-800 text-slate-200 uppercase tracking-wider flex items-center gap-1.5">
            <span>📚</span> Retrieved Official Documents & Chunks
          </h4>
          <span className="text-[0.65rem] text-slate-500 font-mono">
            {retrievedDocs.length || sources.length} Sources
          </span>
        </div>

        {retrievedDocs.length > 0 ? (
          <div className="grid grid-cols-1 gap-3">
            {retrievedDocs.map((doc, i) => {
              const isExpanded = Boolean(expandedDocs[i])
              const title = cleanDocName(doc.source)

              return (
                <Card key={i} className="p-4 bg-white/[0.015] border-white/[0.06] space-y-2.5">
                  <div className="flex items-center justify-between gap-2">
                    <div className="flex items-center gap-2">
                      <span className="text-sm select-none">📄</span>
                      <span className="text-xs font-bold text-slate-200 break-all">{title}</span>
                      {doc.collection && (
                        <span className="text-[0.62rem] text-blue-300 bg-blue-500/10 border border-blue-500/20 px-1.5 py-0.2 rounded font-mono">
                          {doc.collection}
                        </span>
                      )}
                    </div>
                    {doc.score !== null && doc.score !== undefined && (
                      <span className="text-[0.68rem] font-mono text-emerald-400 bg-emerald-500/10 border border-emerald-500/20 px-2 py-0.5 rounded shrink-0">
                        Score: {doc.score}
                      </span>
                    )}
                  </div>

                  {/* Chunk preview */}
                  <div className="text-xs text-slate-400 bg-white/[0.02] p-3 rounded-lg border border-white/[0.04] leading-relaxed">
                    {isExpanded ? (
                      <div className="whitespace-pre-wrap">{doc.full_text || doc.excerpt}</div>
                    ) : (
                      <div>{doc.excerpt}</div>
                    )}
                  </div>

                  <div className="flex justify-end">
                    <button
                      onClick={() => toggleDoc(i)}
                      className="text-[0.68rem] text-blue-400 hover:text-blue-300 font-semibold"
                    >
                      {isExpanded ? 'Collapse excerpt ▲' : 'Expand full chunk ▼'}
                    </button>
                  </div>
                </Card>
              )
            })}
          </div>
        ) : sources.length > 0 ? (
          <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-3">
            {sources.map((s, i) => (
              <Card key={i} className="p-3 bg-white/[0.015] border-white/[0.06] flex items-center gap-2">
                <span className="text-sm">📌</span>
                <span className="text-xs text-slate-300 font-medium truncate">{cleanDocName(s)}</span>
              </Card>
            ))}
          </div>
        ) : (
          <div className="text-xs text-slate-500 italic p-4 border border-white/[0.04] rounded-xl bg-white/[0.01]">
            No internal policy documents retrieved.
          </div>
        )}
      </div>

      {/* ── 4. Section Grounding & Verified Claims Mapping ── */}
      {(sourceUsage.length > 0 || verifiedContext.length > 0) && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
          {sourceUsage.length > 0 && (
            <Card className="p-4 bg-white/[0.015] border-l-4 border-l-blue-500 space-y-3">
              <h4 className="text-[0.72rem] font-800 text-blue-400 uppercase tracking-wider flex items-center gap-1.5">
                <span>🔗</span> Evidence-to-Section Attribution
              </h4>
              <div className="space-y-2">
                {sourceUsage.map((u, i) => (
                  <div key={i} className="p-2.5 rounded bg-white/[0.02] border border-white/[0.04] text-xs">
                    <div className="text-slate-200 font-medium mb-1">{u.claim}</div>
                    <div className="text-[0.68rem] text-slate-400 flex items-center justify-between">
                      <span>Source: <strong className="text-slate-300">{u.source}</strong></span>
                      {u.section && (
                        <span className="text-blue-300 bg-blue-500/10 px-1.5 py-0.2 rounded font-mono text-[0.62rem]">
                          {u.section}
                        </span>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            </Card>
          )}

          {verifiedContext.length > 0 && (
            <Card className="p-4 bg-white/[0.015] border-l-4 border-l-emerald-500 space-y-3">
              <h4 className="text-[0.72rem] font-800 text-emerald-400 uppercase tracking-wider flex items-center gap-1.5">
                <span>✓</span> Verified Factual Context Points
              </h4>
              <ul className="space-y-2">
                {verifiedContext.map((v, i) => (
                  <li key={i} className="text-xs text-slate-300 flex items-start gap-2 leading-relaxed">
                    <span className="text-emerald-400 font-bold shrink-0 mt-0.5">•</span>
                    <span>{v}</span>
                  </li>
                ))}
              </ul>
            </Card>
          )}
        </div>
      )}

      {/* ── 5. Supplementary Web Context (Tavily) ── */}
      {exploreResults.length > 0 && (
        <Card className="p-4 bg-white/[0.015] space-y-3">
          <div className="flex items-center justify-between pb-2 border-b border-white/[0.06]">
            <h4 className="text-xs font-800 text-slate-200 uppercase tracking-wider flex items-center gap-1.5">
              <span>🌐</span> Supplementary Live Web Research (Tavily)
            </h4>
            <span className="text-[0.65rem] text-slate-400 font-mono">
              {exploreResults.length} Queries Verified
            </span>
          </div>

          <div className="space-y-2">
            {exploreResults.map((r, i) => (
              <div key={i} className="p-2.5 rounded bg-white/[0.02] border border-white/[0.04] text-xs space-y-1">
                <div className="flex justify-between items-center">
                  <a
                    href={r.url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-blue-400 hover:underline font-semibold"
                  >
                    {r.title || r.url}
                  </a>
                  {r.score && <span className="text-[0.65rem] text-slate-500 font-mono">{r.score}</span>}
                </div>
                {r.content && <p className="text-[0.72rem] text-slate-400 leading-relaxed">{r.content}</p>}
              </div>
            ))}
          </div>
        </Card>
      )}

      {/* ── 6. Collapsible Developer Raw View ── */}
      <div className="pt-2">
        <button
          onClick={() => setShowRaw(!showRaw)}
          className="text-xs font-semibold text-slate-400 hover:text-slate-200 flex items-center gap-1.5 py-1 px-2 rounded hover:bg-white/[0.03] transition-colors"
        >
          <span>{showRaw ? '▼' : '▶'}</span>
          <span>Developer Debug & Raw State Payload</span>
        </button>

        {showRaw && (
          <div className="mt-3 bg-slate-950/80 p-4 rounded-xl border border-white/[0.08] font-mono text-[0.72rem] text-slate-300 max-h-96 overflow-y-auto custom-scrollbar">
            <pre className="whitespace-pre-wrap break-words">
              {JSON.stringify(data, null, 2)}
            </pre>
          </div>
        )}
      </div>
    </div>
  )
}
