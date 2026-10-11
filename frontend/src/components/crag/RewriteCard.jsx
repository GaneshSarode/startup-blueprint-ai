import { useState } from 'react'
import { ChevronDown, ChevronUp } from 'lucide-react'

const SECTIONS = [
  ['PROBLEM STATEMENT',  '🔍', 'Problem Statement'],
  ['TARGET USERS',       '👥', 'Target Users'],
  ['CORE SOLUTION',      '💡', 'Core Solution'],
  ['KEY FEATURES',       '⚡', 'Key Features'],
  ['TECHNOLOGIES',       '⚙️', 'Technologies'],
  ['INDUSTRY',           '🏭', 'Industry'],
  ['GEOGRAPHY',          '🗺️', 'Geography'],
  ['BUSINESS MODEL',     '💰', 'Business Model'],
  ['SEARCH CONTEXT',     '🔎', 'Search Context'],
]

function parse(text) {
  const out = {}
  let cur = null
  for (const line of text.split('\n')) {
    const s = line.trim()
    if (!s) continue
    let hit = false
    for (const [key] of SECTIONS) {
      if (s.toUpperCase().startsWith(key + ':') || s.toUpperCase() === key) {
        cur = key
        out[key] = s.includes(':') ? s.slice(s.indexOf(':') + 1).trim() : ''
        hit = true; break
      }
      if (s.toUpperCase().startsWith('KEYWORDS:') || s.toUpperCase().startsWith('RETRIEVAL QUERIES:')) {
        cur = null; hit = true; break
      }
    }
    if (!hit && cur) out[cur] = ((out[cur] || '') + '\n' + s).trim()
  }
  return out
}

function FeatureList({ val }) {
  const lines = val.split('\n').map(l => l.trim()).filter(l => l.replace(/^[-•]\s*/, '').length > 0)
  if (lines.length <= 1) {
    return <span className="text-sm text-slate-300 leading-relaxed">{val}</span>
  }
  return (
    <ul className="space-y-1 mt-0.5">
      {lines.map((l, i) => (
        <li key={i} className="flex items-start gap-2 text-sm text-slate-300 leading-relaxed">
          <span className="mt-1.5 w-1.5 h-1.5 rounded-full bg-blue-400/60 flex-shrink-0 inline-block" />
          <span>{l.replace(/^[-•]\s*/, '')}</span>
        </li>
      ))}
    </ul>
  )
}

function TagChips({ val }) {
  const items = val.split(/[,;/\n]/).map(t => t.trim()).filter(Boolean)
  if (items.length <= 1) {
    return <span className="text-sm text-slate-300 leading-relaxed">{val}</span>
  }
  return (
    <div className="flex flex-wrap gap-1.5 mt-0.5">
      {items.map((t, i) => (
        <span key={i} style={{
          display:'inline-flex', alignItems:'center',
          padding:'2px 10px', borderRadius:99,
          fontSize:'0.72rem', fontWeight:500,
          background:'rgba(255,255,255,0.045)',
          border:'1px solid rgba(255,255,255,0.07)',
          color:'#cbd5e1'
        }}>{t}</span>
      ))}
    </div>
  )
}

function InfoCard({ icon, label, val }) {
  return (
    <div style={{
      borderRadius:12, border:'1px solid rgba(255,255,255,0.055)',
      background:'rgba(255,255,255,0.022)', padding:'10px 12px',
      display:'flex', alignItems:'flex-start', gap:10
    }}>
      <span style={{ fontSize:'1rem', flexShrink:0, marginTop:2 }}>{icon}</span>
      <div style={{ minWidth:0 }}>
        <div style={{ fontSize:'0.65rem', fontWeight:700, color:'#475569', textTransform:'uppercase', letterSpacing:'0.09em', marginBottom:2 }}>{label}</div>
        <div style={{ fontSize:'0.875rem', color:'#e2e8f0', lineHeight:1.45 }}>{val}</div>
      </div>
    </div>
  )
}

function SearchContextBlock({ val }) {
  const [expanded, setExpanded] = useState(false)
  const preview = val.slice(0, 160)
  const hasMore = val.length > 160
  return (
    <div style={{ borderRadius:12, border:'1px solid rgba(255,255,255,0.04)', background:'rgba(255,255,255,0.016)', padding:'10px 12px' }}>
      <div style={{ fontSize:'0.75rem', color:'#94a3b8', lineHeight:1.6 }}>
        {expanded ? val : (hasMore ? preview + '…' : val)}
      </div>
      {hasMore && (
        <button
          onClick={() => setExpanded(!expanded)}
          style={{ marginTop:6, display:'flex', alignItems:'center', gap:4,
            fontSize:'0.7rem', color:'#60a5fa', background:'none', border:'none',
            cursor:'pointer', fontWeight:500, padding:0 }}
        >
          {expanded ? <><ChevronUp size={12} /> Show less</> : <><ChevronDown size={12} /> Show full context</>}
        </button>
      )}
    </div>
  )
}

export default function RewriteCard({ text }) {
  if (!text) return null
  const parsed = parse(text)
  const hasData = Object.keys(parsed).length > 0

  const ps   = parsed['PROBLEM STATEMENT']?.trim()
  const cs   = parsed['CORE SOLUTION']?.trim()
  const tu   = parsed['TARGET USERS']?.trim()
  const kf   = parsed['KEY FEATURES']?.trim()
  const tech = parsed['TECHNOLOGIES']?.trim()
  const ind  = parsed['INDUSTRY']?.trim()
  const geo  = parsed['GEOGRAPHY']?.trim()
  const bm   = parsed['BUSINESS MODEL']?.trim()
  const sc   = parsed['SEARCH CONTEXT']?.trim()

  return (
    <div className="rounded-2xl border border-amber-500/14 bg-gradient-to-br from-amber-500/[0.028] to-blue-500/[0.038] mb-5 overflow-hidden">

      {/* Panel header */}
      <div className="flex items-center justify-between px-5 py-3 border-b border-white/[0.048]">
        <div className="flex items-center gap-2">
          <span className="text-amber-400 text-sm">✨</span>
          <span className="text-[0.72rem] font-bold text-amber-400 uppercase tracking-wider">
            Gemini Flash — Structured Understanding
          </span>
        </div>
        <span style={{
          fontSize:'0.65rem', fontWeight:600, color:'#34d399',
          background:'rgba(16,185,129,0.09)', border:'1px solid rgba(16,185,129,0.2)',
          padding:'1px 8px', borderRadius:99
        }}>Parsed</span>
      </div>

      {hasData ? (
        <div className="p-5 space-y-4">

          {/* 1. Primary row: Problem Statement + Core Solution */}
          {(ps || cs) && (
            <div className="grid md:grid-cols-2 gap-3">
              {ps && (
                <div style={{ borderRadius:12, border:'1px solid rgba(59,130,246,0.18)', background:'rgba(59,130,246,0.038)', padding:16 }}>
                  <div className="flex items-center gap-1.5 mb-2">
                    <span className="text-sm">🔍</span>
                    <span style={{ fontSize:'0.67rem', fontWeight:700, color:'#60a5fa', textTransform:'uppercase', letterSpacing:'0.08em' }}>Problem Statement</span>
                  </div>
                  <p className="text-sm text-slate-200 leading-relaxed">{ps}</p>
                </div>
              )}
              {cs && (
                <div style={{ borderRadius:12, border:'1px solid rgba(139,92,246,0.18)', background:'rgba(139,92,246,0.038)', padding:16 }}>
                  <div className="flex items-center gap-1.5 mb-2">
                    <span className="text-sm">💡</span>
                    <span style={{ fontSize:'0.67rem', fontWeight:700, color:'#a78bfa', textTransform:'uppercase', letterSpacing:'0.08em' }}>Core Solution</span>
                  </div>
                  <p className="text-sm text-slate-200 leading-relaxed">{cs}</p>
                </div>
              )}
            </div>
          )}

          {/* 2. Secondary grid: Target Users + Key Features */}
          {(tu || kf) && (
            <div className="grid md:grid-cols-2 gap-3">
              {tu && (
                <div style={{ borderRadius:12, border:'1px solid rgba(255,255,255,0.055)', background:'rgba(255,255,255,0.018)', padding:14 }}>
                  <div className="flex items-center gap-1.5 mb-2">
                    <span className="text-sm">👥</span>
                    <span style={{ fontSize:'0.67rem', fontWeight:700, color:'#64748b', textTransform:'uppercase', letterSpacing:'0.08em' }}>Target Users</span>
                  </div>
                  <p className="text-sm text-slate-300 leading-relaxed">{tu}</p>
                </div>
              )}
              {kf && (
                <div style={{ borderRadius:12, border:'1px solid rgba(255,255,255,0.055)', background:'rgba(255,255,255,0.018)', padding:14 }}>
                  <div className="flex items-center gap-1.5 mb-2">
                    <span className="text-sm">⚡</span>
                    <span style={{ fontSize:'0.67rem', fontWeight:700, color:'#64748b', textTransform:'uppercase', letterSpacing:'0.08em' }}>Key Features</span>
                  </div>
                  <FeatureList val={kf} />
                </div>
              )}
            </div>
          )}

          {/* 3. Metadata: Technologies + Industry */}
          {(tech || ind) && (
            <div className="space-y-2">
              {tech && (
                <div>
                  <div className="flex items-center gap-1.5 mb-1.5">
                    <span className="text-sm">⚙️</span>
                    <span style={{ fontSize:'0.65rem', fontWeight:700, color:'#475569', textTransform:'uppercase', letterSpacing:'0.09em' }}>Technologies</span>
                  </div>
                  <TagChips val={tech} />
                </div>
              )}
              {ind && (
                <div>
                  <div className="flex items-center gap-1.5 mb-1.5">
                    <span className="text-sm">🏭</span>
                    <span style={{ fontSize:'0.65rem', fontWeight:700, color:'#475569', textTransform:'uppercase', letterSpacing:'0.09em' }}>Industry</span>
                  </div>
                  <TagChips val={ind} />
                </div>
              )}
            </div>
          )}

          {/* 4. Info cards: Geography + Business Model */}
          {(geo || bm) && (
            <div className="grid sm:grid-cols-2 gap-2.5">
              {geo && <InfoCard icon="🗺️" label="Geography" val={geo} />}
              {bm  && <InfoCard icon="💰" label="Business Model" val={bm} />}
            </div>
          )}

          {/* 5. Expandable Search Context */}
          {sc && (
            <div>
              <div className="flex items-center gap-1.5 mb-1.5">
                <span className="text-sm">🔎</span>
                <span style={{ fontSize:'0.65rem', fontWeight:700, color:'#475569', textTransform:'uppercase', letterSpacing:'0.09em' }}>Search Context</span>
              </div>
              <SearchContextBlock val={sc} />
            </div>
          )}

        </div>
      ) : (
        <div className="p-5">
          <pre className="text-xs text-slate-400 whitespace-pre-wrap leading-relaxed">{text.slice(0, 800)}</pre>
        </div>
      )}
    </div>
  )
}
