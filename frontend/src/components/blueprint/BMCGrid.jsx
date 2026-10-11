import { Card } from '../ui'

export default function BMCGrid({ data }) {
  if (!data) return <div className="text-slate-500 text-sm">No BMC data available.</div>

  const blocks = [
    { key: 'key_partners', title: 'Key Partners', icon: '🤝', color: 'text-sky-400', border: 'border-sky-500/20' },
    { key: 'key_activities', title: 'Key Activities', icon: '⚡', color: 'text-indigo-400', border: 'border-indigo-500/20' },
    { key: 'key_resources', title: 'Key Resources', icon: '🧱', color: 'text-indigo-400', border: 'border-indigo-500/20' },
    { key: 'value_propositions', title: 'Value Propositions', icon: '💎', color: 'text-blue-400', border: 'border-blue-500/30', accent: true },
    { key: 'customer_relationships', title: 'Customer Relationships', icon: '❤️', color: 'text-violet-400', border: 'border-violet-500/20' },
    { key: 'channels', title: 'Channels', icon: '📣', color: 'text-violet-400', border: 'border-violet-500/20' },
    { key: 'customer_segments', title: 'Customer Segments', icon: '🎯', color: 'text-purple-400', border: 'border-purple-500/20' },
    { key: 'cost_structure', title: 'Cost Structure', icon: '💸', color: 'text-rose-400', border: 'border-rose-500/20' },
    { key: 'revenue_streams', title: 'Revenue Streams', icon: '💰', color: 'text-emerald-400', border: 'border-emerald-500/30', accentGreen: true },
  ]

  const getItems = (key) => {
    const val = data[key]
    if (Array.isArray(val)) return val
    if (typeof val === 'string' && val.trim()) return [val]
    return []
  }

  const CanvasCard = ({ blockKey, className = '' }) => {
    const meta = blocks.find((b) => b.key === blockKey) || { title: blockKey, icon: '📌', color: 'text-blue-400', border: 'border-white/10' }
    const items = getItems(blockKey)

    return (
      <Card
        className={`flex flex-col p-4 transition-all duration-200 hover:border-white/20 ${
          meta.accent
            ? 'bg-gradient-to-b from-blue-500/[0.07] to-transparent border-blue-500/25 ring-1 ring-blue-500/10'
            : meta.accentGreen
            ? 'bg-gradient-to-b from-emerald-500/[0.07] to-transparent border-emerald-500/25 ring-1 ring-emerald-500/10'
            : 'bg-white/[0.015] border-white/[0.07]'
        } ${className}`}
      >
        <div className="flex items-center justify-between pb-2.5 mb-2.5 border-b border-white/[0.06]">
          <div className="flex items-center gap-2">
            <span className="text-sm select-none" aria-hidden="true">{meta.icon}</span>
            <h3 className={`text-[0.72rem] font-800 tracking-wider uppercase ${meta.color}`}>
              {meta.title}
            </h3>
          </div>
          {items.length > 0 && (
            <span className="text-[0.65rem] font-bold px-1.5 py-0.5 rounded-full bg-white/[0.05] text-slate-400 border border-white/[0.05]">
              {items.length}
            </span>
          )}
        </div>

        {items.length > 0 ? (
          <ul className="space-y-2 flex-1">
            {items.map((item, i) => (
              <li key={i} className="text-xs text-slate-300 leading-relaxed flex items-start gap-2">
                <span className="w-1.5 h-1.5 rounded-full bg-blue-400/60 mt-1.5 flex-shrink-0" />
                <span className="break-words">{item}</span>
              </li>
            ))}
          </ul>
        ) : (
          <div className="text-xs text-slate-500 italic py-2">No items listed.</div>
        )}
      </Card>
    )
  }

  return (
    <div className="space-y-3.5">
      {/* ── TOP SECTION: 5-column standard Business Model Canvas layout ── */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-5 gap-3.5 items-stretch">
        {/* 1. Key Partners (Spans full top height) */}
        <div className="flex flex-col">
          <CanvasCard blockKey="key_partners" className="h-full" />
        </div>

        {/* 2. Key Activities (top) & Key Resources (bottom) */}
        <div className="flex flex-col gap-3.5">
          <CanvasCard blockKey="key_activities" className="flex-1" />
          <CanvasCard blockKey="key_resources" className="flex-1" />
        </div>

        {/* 3. Value Propositions (Center anchor, spans full top height) */}
        <div className="flex flex-col">
          <CanvasCard blockKey="value_propositions" className="h-full shadow-lg shadow-blue-500/[0.02]" />
        </div>

        {/* 4. Customer Relationships (top) & Channels (bottom) */}
        <div className="flex flex-col gap-3.5">
          <CanvasCard blockKey="customer_relationships" className="flex-1" />
          <CanvasCard blockKey="channels" className="flex-1" />
        </div>

        {/* 5. Customer Segments (Spans full top height) */}
        <div className="flex flex-col">
          <CanvasCard blockKey="customer_segments" className="h-full" />
        </div>
      </div>

      {/* ── BOTTOM SECTION: 2-column Cost Structure & Revenue Streams ── */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-3.5 items-stretch">
        <CanvasCard blockKey="cost_structure" />
        <CanvasCard blockKey="revenue_streams" className="shadow-lg shadow-emerald-500/[0.02]" />
      </div>
    </div>
  )
}
