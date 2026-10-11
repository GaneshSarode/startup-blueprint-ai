import { useState } from 'react'
import { ChevronDown, ChevronUp } from 'lucide-react'

const CONFIDENCE_META = {
  CORRECT: {
    badge: { color:'#34d399', bg:'rgba(16,185,129,0.09)', border:'rgba(16,185,129,0.25)' },
    summary: 'Internal knowledge base was strongly relevant. Blueprint grounded in verified PDF corpus.',
    label: '✅ CORRECT',
  },
  AMBIGUOUS: {
    badge: { color:'#fbbf24', bg:'rgba(234,179,8,0.09)', border:'rgba(234,179,8,0.25)' },
    summary: 'Partial match in knowledge base. Web search used to supplement context.',
    label: '⚡ AMBIGUOUS',
  },
  INCORRECT: {
    badge: { color:'#f87171', bg:'rgba(239,68,68,0.09)', border:'rgba(239,68,68,0.25)' },
    summary: 'Knowledge base insufficient. Tavily web search used as primary source.',
    label: '❌ INCORRECT',
  },
}

const NODES = {
  CORRECT: [
    ['retrieve',       'ChromaDB retrieval across text, table & visual chunks.'],
    ['eval_each_doc',  'CrossEncoder scored chunks. Max logit ≥ −3.0 → CORRECT branch.'],
    ['rewrite_query',  'Gemini Flash expanded idea into 10-field structured brief.'],
    ['refine',         'Top-5 sentence-pair strips kept. Internal PDF knowledge sufficient.'],
    ['generate',       'IBM Granite 4.0 synthesised policy brief from refined PDF context.'],
    ['explore_search', 'Tavily fetched live results as bonus — not fed into blueprint.'],
  ],
  AMBIGUOUS: [
    ['retrieve',      'ChromaDB queried all 3 collections; merged by cosine distance.'],
    ['eval_each_doc', 'CrossEncoder scored chunks. Max logit between −6.5 and −3.0 → AMBIGUOUS.'],
    ['rewrite_query', 'Gemini Flash expanded idea for Tavily queries.'],
    ['web_search',    'Tavily searched live web to supplement weak retrieval.'],
    ['refine',        'PDF sentence strips + Tavily snippets merged into combined context.'],
    ['generate',      'IBM Granite 4.0 synthesised policy brief from combined sources.'],
  ],
  INCORRECT: [
    ['retrieve',       'ChromaDB queried all 3 collections.'],
    ['eval_each_doc',  'CrossEncoder scored chunks. Max logit < −6.5 → INCORRECT branch.'],
    ['rewrite_query',  'Gemini Flash rewrote query for web search.'],
    ['web_search',     'PDF corpus discarded. Tavily used as sole knowledge source.'],
    ['conversational', 'Groq generated a plain market snapshot. No full blueprint produced.'],
  ],
}

function ScoreBars({ logits }) {
  if (!logits?.length) return null
  const UPPER = -3.0, LOWER = -6.5
  return (
    <div>
      <div style={{ fontSize:'0.72rem', fontWeight:700, color:'#94a3b8', marginBottom:8 }}>CrossEncoder Raw Logits</div>
      {logits.slice(0, 8).map((l, i) => {
        const pct   = Math.max(0, Math.min(100, ((l + 10) / 10) * 100))
        const color = l >= UPPER ? '#10b981' : l >= LOWER ? '#f59e0b' : '#ef4444'
        return (
          <div key={i} style={{ display:'flex', alignItems:'center', gap:8, marginBottom:6 }}>
            <span style={{ fontFamily:'JetBrains Mono,monospace', fontSize:'0.7rem', color:'#64748b', width:44, flexShrink:0 }}>Doc {i+1}</span>
            <div className="score-track" style={{ flex:1 }}>
              <div className="score-fill" style={{ width:`${pct}%`, background:color }} />
            </div>
            <span style={{ fontFamily:'JetBrains Mono,monospace', fontSize:'0.7rem', color:'#64748b', width:44, textAlign:'right' }}>{l.toFixed(2)}</span>
          </div>
        )
      })}
      <div style={{ fontSize:'0.67rem', color:'#475569', marginTop:6 }}>
        <span style={{ color:'#10b981' }}>■</span> ≥ {UPPER}&nbsp;·&nbsp;
        <span style={{ color:'#f59e0b' }}>■</span> Ambiguous&nbsp;·&nbsp;
        <span style={{ color:'#ef4444' }}>■</span> &lt; {LOWER}
      </div>
    </div>
  )
}

export default function CRAGTrace({ cragResult }) {
  const [open, setOpen] = useState(false)
  if (!cragResult) return null

  const { confidence, action, raw_logits = [], sources = [], retrieval_queries = [], internal_context, external_context } = cragResult
  const meta  = CONFIDENCE_META[confidence] || CONFIDENCE_META.INCORRECT
  const nodes = NODES[confidence] || NODES.INCORRECT

  // Build a concise collapsed summary from action or fall back to meta.summary
  const collapsedSummary = (() => {
    if (!action) return meta.summary
    const stripped = action.replace(/^[\u2713✅⚡❌✓\s]+/, '').trim()
    if (stripped.length < 10) return meta.summary
    return stripped.length > 120 ? stripped.slice(0, 120) + '…' : stripped
  })()

  return (
    <div style={{
      marginBottom:20,
      borderRadius:16,
      border:'1px solid rgba(255,255,255,0.062)',
      background:'rgba(255,255,255,0.014)',
      overflow:'hidden'
    }}>
      {/* ── Collapsed header ── */}
      <button
        type="button"
        onClick={() => setOpen(!open)}
        aria-expanded={open}
        aria-controls="crag-detail"
        style={{
          width:'100%', display:'flex', alignItems:'center', justifyContent:'space-between',
          padding:'12px 20px', background:'none', border:'none', cursor:'pointer',
          textAlign:'left'
        }}
        className="hover:bg-white/[0.022] transition-colors"
      >
        <div style={{ display:'flex', alignItems:'center', gap:10, minWidth:0, flex:1 }}>
          {/* Confidence badge */}
          <span style={{
            fontSize:'0.7rem', fontWeight:700,
            padding:'2px 10px', borderRadius:99,
            color: meta.badge.color,
            background: meta.badge.bg,
            border: `1px solid ${meta.badge.border}`,
            flexShrink:0, whiteSpace:'nowrap'
          }}>
            {meta.label}
          </span>
          {/* Concise summary */}
          <span style={{ fontSize:'0.8rem', color:'#64748b', overflow:'hidden', textOverflow:'ellipsis', whiteSpace:'nowrap' }}>
            {collapsedSummary}
          </span>
        </div>
        <span style={{ color:'#64748b', flexShrink:0, marginLeft:12 }}>
          {open ? <ChevronUp size={15} /> : <ChevronDown size={15} />}
        </span>
      </button>

      {/* ── Expanded detail ── */}
      {open && (
        <div id="crag-detail" className="animate-fade-in" style={{ padding:'0 20px 20px' }}>

          {/* Decision banner */}
          <div style={{
            borderRadius:10, border:`1px solid ${meta.badge.border}`,
            background: meta.badge.bg,
            padding:'10px 14px', marginBottom:16,
            fontSize:'0.8rem', fontWeight:600,
            color: meta.badge.color,
            lineHeight:1.5
          }}>
            {meta.label} — {meta.summary}
          </div>

          {/* Pipeline trace */}
          <div style={{ marginBottom:16 }}>
            <div style={{ fontSize:'0.67rem', fontWeight:700, color:'#475569', textTransform:'uppercase', letterSpacing:'0.09em', marginBottom:10 }}>
              Pipeline Trace — Yan et al. 2024
            </div>
            {nodes.map(([name, desc], i) => (
              <div key={i}>
                <div style={{
                  display:'flex', alignItems:'flex-start', gap:10,
                  padding:'8px 12px', borderRadius:10,
                  border:'1px solid rgba(16,185,129,0.18)',
                  background:'rgba(16,185,129,0.022)',
                }}>
                  <span style={{ fontSize:'0.75rem', fontWeight:700, color:'#34d399', flexShrink:0, minWidth:0 }}>✅ {name}</span>
                  <span style={{ fontSize:'0.75rem', color:'#64748b', lineHeight:1.55 }}>{desc}</span>
                </div>
                {i < nodes.length - 1 && <div className="crag-connector" />}
              </div>
            ))}
          </div>

          {/* Logits + sources */}
          {(raw_logits.length > 0 || sources.length > 0) && (
            <div className="grid md:grid-cols-2 gap-5" style={{ marginBottom:14 }}>
              <ScoreBars logits={raw_logits} />
              {sources.length > 0 && (
                <div>
                  <div style={{ fontSize:'0.72rem', fontWeight:700, color:'#94a3b8', marginBottom:8 }}>Sources Used</div>
                  {sources.map((s, i) => (
                    <div key={i} style={{ display:'flex', alignItems:'center', gap:8, fontSize:'0.75rem', color:'#94a3b8', padding:'4px 0' }}>
                      <span>{s === 'tavily_web_search' ? '🌐' : '📄'}</span>
                      <code style={{ color:'#60a5fa', background:'rgba(59,130,246,0.08)', padding:'1px 6px', borderRadius:6, fontSize:'0.7rem' }}>{s}</code>
                    </div>
                  ))}
                  {retrieval_queries?.length > 0 && (
                    <>
                      <div style={{ fontSize:'0.72rem', fontWeight:700, color:'#94a3b8', marginTop:12, marginBottom:8 }}>Tavily Queries</div>
                      {retrieval_queries.slice(0, 3).map((q, i) => (
                        <div key={i} style={{
                          fontSize:'0.75rem', color:'#64748b', lineHeight:1.55,
                          background:'rgba(255,255,255,0.022)', border:'1px solid rgba(255,255,255,0.048)',
                          borderRadius:8, padding:'6px 10px', marginBottom:4
                        }}>{q}</div>
                      ))}
                    </>
                  )}
                </div>
              )}
            </div>
          )}

          {/* Contexts */}
          {(internal_context || external_context) && (
            <div className="grid md:grid-cols-2 gap-4">
              {internal_context && (
                <div>
                  <div style={{ fontSize:'0.67rem', fontWeight:700, color:'#475569', textTransform:'uppercase', letterSpacing:'0.09em', marginBottom:8 }}>📄 PDF Context (refined)</div>
                  <div style={{ fontSize:'0.75rem', color:'#64748b', background:'rgba(255,255,255,0.022)', border:'1px solid rgba(255,255,255,0.048)', borderRadius:10, padding:12, lineHeight:1.6, maxHeight:144, overflowY:'auto' }}>
                    {internal_context.slice(0, 600)}…
                  </div>
                </div>
              )}
              {external_context && (
                <div>
                  <div style={{ fontSize:'0.67rem', fontWeight:700, color:'#475569', textTransform:'uppercase', letterSpacing:'0.09em', marginBottom:8 }}>🌐 Web Context (Tavily)</div>
                  <div style={{ fontSize:'0.75rem', color:'#64748b', background:'rgba(255,255,255,0.022)', border:'1px solid rgba(255,255,255,0.048)', borderRadius:10, padding:12, lineHeight:1.6, maxHeight:144, overflowY:'auto' }}>
                    {external_context.slice(0, 600)}…
                  </div>
                </div>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  )
}
