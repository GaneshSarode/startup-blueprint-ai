import { Card } from '../ui'
import StartupBudgetCalculator from './StartupBudgetCalculator'
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, PieChart, Pie, Cell } from 'recharts'

export default function BudgetTab({ data }) {
  if (!data) return <div className="text-slate-500 text-sm">No budget data available.</div>

  const formatLakhs = (val) => val ? `₹${(val / 100000).toFixed(1)}L` : '—'
  const formatCompact = (val) => val ? `₹${(val / 100000).toFixed(1)}L` : '0'

  const chartData = data.phases?.map(p => ({
    name: p.name,
    total: p.total || 0
  })) || []

  const estimatedAnnualCost = Number(data.total_12_months) || chartData.reduce((sum, phase) => sum + phase.total, 0)
  const suggestedMonthlyCost = estimatedAnnualCost / 12
  const pieColors = ['#3b82f6', '#8b5cf6', '#10b981']

  const renderCustomizedLabel = ({ cx, cy, midAngle, innerRadius, outerRadius, percent, index }) => {
    const radius = innerRadius + (outerRadius - innerRadius) * 0.5;
    const x = cx + radius * Math.cos(-midAngle * Math.PI / 180);
    const y = cy + radius * Math.sin(-midAngle * Math.PI / 180);
    return (
      <text x={x} y={y} fill="white" textAnchor="middle" dominantBaseline="central" className="text-[0.6rem] font-bold">
        {`${(percent * 100).toFixed(0)}%`}
      </text>
    );
  };

  return (
    <div className="space-y-8">
      
      {/* Top Level KPIs */}
      <div className="flex items-center gap-4 border-l-4 border-l-emerald-500 bg-white/[0.02] p-4 rounded-r-xl">
        <div>
          <div className="text-[0.65rem] text-slate-500 font-700 uppercase mb-1">Phase-wise Budget Estimate</div>
          <div className="text-xl font-800 text-slate-200">Total (12 Months): <span className="text-emerald-400">{formatLakhs(data.total_12_months)}</span></div>
          {data.funding_suggestion && (
            <div className="text-xs text-slate-400 mt-1">Suggested Source: <span className="text-blue-300 font-600">{data.funding_suggestion}</span></div>
          )}
        </div>
      </div>

      {/* Charts Section */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        
        {/* Bar Chart */}
        <Card className="h-64 flex flex-col">
          <h3 className="text-[0.7rem] font-800 text-slate-300 uppercase tracking-wider mb-4">Phase-wise Budget Allocation</h3>
          <div className="flex-1 w-full min-h-0">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={chartData} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#ffffff10" vertical={false} />
                <XAxis dataKey="name" stroke="#ffffff40" tick={{fontSize: 10}} axisLine={false} tickLine={false} />
                <YAxis stroke="#ffffff40" tickFormatter={formatCompact} tick={{fontSize: 10}} axisLine={false} tickLine={false} />
                <Tooltip cursor={{fill: '#ffffff05'}} contentStyle={{backgroundColor: '#0f172a', border: '1px solid #1e293b', borderRadius: '8px'}} formatter={(val) => formatLakhs(val)} />
                <Bar dataKey="total" radius={[4, 4, 0, 0]}>
                  {chartData.map((entry, index) => (
                    <Cell key={`cell-${index}`} fill={pieColors[index % pieColors.length]} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        </Card>

        {/* Donut Chart */}
        <Card className="h-64 flex flex-col items-center justify-center relative">
          <h3 className="text-[0.7rem] font-800 text-slate-300 uppercase tracking-wider absolute top-4 left-4 w-full text-left">Budget Split</h3>
          <div className="w-full h-full">
            <ResponsiveContainer width="100%" height="100%">
              <PieChart>
                <Pie
                  data={chartData}
                  cx="50%"
                  cy="50%"
                  innerRadius={60}
                  outerRadius={80}
                  paddingAngle={5}
                  dataKey="total"
                  labelLine={false}
                  label={renderCustomizedLabel}
                >
                  {chartData.map((entry, index) => (
                    <Cell key={`cell-${index}`} fill={pieColors[index % pieColors.length]} />
                  ))}
                </Pie>
                <Tooltip contentStyle={{backgroundColor: '#0f172a', border: '1px solid #1e293b', borderRadius: '8px'}} formatter={(val) => formatLakhs(val)} />
              </PieChart>
            </ResponsiveContainer>
          </div>
          <div className="absolute flex gap-4 bottom-4">
            {chartData.map((entry, index) => (
              <div key={index} className="flex items-center gap-1.5">
                <div className="w-2 h-2 rounded-full" style={{backgroundColor: pieColors[index % pieColors.length]}}></div>
                <div className="text-[0.6rem] text-slate-400 font-600">{entry.name}</div>
              </div>
            ))}
          </div>
        </Card>
      </div>

      {/* Detailed Breakdown */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {data.phases?.map((phase, i) => (
          <Card key={i} className="flex flex-col border-t-2" style={{borderTopColor: pieColors[i % pieColors.length]}}>
            <h4 className="text-sm font-800 text-slate-200 mb-0.5">{phase.name}</h4>
            <p className="text-[0.65rem] text-slate-500 font-700 uppercase tracking-wider mb-4">{phase.duration}</p>
            
            <div className="flex-1 space-y-3 mb-4">
              {phase.items?.map((exp, j) => (
                <div key={j} className="flex justify-between items-center gap-4 text-xs">
                  <div className="text-slate-300 truncate" title={exp.item}>• {exp.item}</div>
                  <div className="text-blue-300 font-600 shrink-0">{exp.amount.toLocaleString('en-IN', {style: 'currency', currency: 'INR', maximumFractionDigits: 0})}</div>
                </div>
              ))}
            </div>

            <div className="pt-3 border-t border-white/[0.05] flex justify-between items-end">
              <div className="text-[0.6rem] text-emerald-500 uppercase font-700 tracking-wider">Phase Total</div>
              <div className="text-lg font-800 text-emerald-400">{formatLakhs(phase.total)}</div>
            </div>
          </Card>
        ))}
      </div>

      {/* Interactive cash-flow planning tool */}
      <StartupBudgetCalculator suggestedMonthlyCost={suggestedMonthlyCost} />
    </div>
  )
}
