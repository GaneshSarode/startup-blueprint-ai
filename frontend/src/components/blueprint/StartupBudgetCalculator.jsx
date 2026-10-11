import { useEffect, useMemo, useState } from 'react'
import { Calculator, Gauge, Wallet, TrendingUp } from 'lucide-react'

const formatINR = (amount) => new Intl.NumberFormat('en-IN', {
  style: 'currency',
  currency: 'INR',
  maximumFractionDigits: 0,
}).format(amount)

const nonNegativeNumber = (value) => Math.max(0, Number(value) || 0)

function NumberField({ id, label, hint, value, onChange }) {
  return (
    <label htmlFor={id} className="block space-y-1.5">
      <span className="block text-xs font-semibold text-slate-300">{label}</span>
      <input
        id={id}
        type="number"
        inputMode="decimal"
        min="0"
        step="1000"
        value={value}
        onChange={(event) => onChange(event.target.value)}
        className="block input-base px-3 py-2.5 tabular-nums"
        aria-describedby={`${id}-hint`}
      />
      <span id={`${id}-hint`} className="block text-[0.68rem] text-slate-500">{hint}</span>
    </label>
  )
}

function Metric({ icon: Icon, label, value, note, accent = 'text-blue-300' }) {
  return (
    <div className="rounded-xl border border-white/[0.07] bg-white/[0.025] p-4">
      <div className="flex items-center gap-2 text-[0.68rem] font-bold uppercase tracking-wider text-slate-500">
        <Icon size={15} className={accent} aria-hidden="true" />
        <span>{label}</span>
      </div>
      <div className={`mt-2 text-lg font-extrabold tabular-nums ${accent}`}>{value}</div>
      <p className="mt-1 text-[0.68rem] leading-5 text-slate-500">{note}</p>
    </div>
  )
}

/**
 * A client-side estimator that complements the AI-generated phase budget.
 * It does not persist inputs or send financial values to the backend.
 */
export default function StartupBudgetCalculator({ suggestedMonthlyCost = 0 }) {
  const [monthlyCosts, setMonthlyCosts] = useState(String(Math.round(nonNegativeNumber(suggestedMonthlyCost))))
  const [monthlyCostsEdited, setMonthlyCostsEdited] = useState(false)
  const [setupCosts, setSetupCosts] = useState('0')
  const [availableFunding, setAvailableFunding] = useState('0')
  const [monthlyRevenue, setMonthlyRevenue] = useState('0')

  useEffect(() => {
    if (!monthlyCostsEdited) {
      setMonthlyCosts(String(Math.round(nonNegativeNumber(suggestedMonthlyCost))))
    }
  }, [suggestedMonthlyCost, monthlyCostsEdited])

  const metrics = useMemo(() => {
    const costs = nonNegativeNumber(monthlyCosts)
    const setup = nonNegativeNumber(setupCosts)
    const funding = nonNegativeNumber(availableFunding)
    const revenue = nonNegativeNumber(monthlyRevenue)
    const netBurn = costs - revenue
    const cashAfterSetup = Math.max(0, funding - setup)
    const runwayMonths = netBurn > 0 ? cashAfterSetup / netBurn : null
    const sixMonthNeed = setup + (6 * Math.max(0, netBurn))

    return {
      monthlyCosts: costs,
      netBurn,
      runwayMonths,
      fundingGap: Math.max(0, sixMonthNeed - funding),
      breakEvenRevenue: costs,
    }
  }, [monthlyCosts, setupCosts, availableFunding, monthlyRevenue])

  const reset = () => {
    setMonthlyCosts(String(Math.round(nonNegativeNumber(suggestedMonthlyCost))))
    setMonthlyCostsEdited(false)
    setSetupCosts('0')
    setAvailableFunding('0')
    setMonthlyRevenue('0')
  }

  const hasMonthlySurplus = metrics.netBurn < 0

  return (
    <section className="glass-card space-y-5 p-5 sm:p-6" aria-labelledby="startup-budget-calculator-title">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="flex items-start gap-3">
          <div className="rounded-xl border border-emerald-400/20 bg-emerald-400/10 p-2.5 text-emerald-300">
            <Calculator size={20} aria-hidden="true" />
          </div>
          <div>
            <h3 id="startup-budget-calculator-title" className="text-sm font-extrabold text-slate-100">
              Runway &amp; Funding Calculator
            </h3>
            <p className="mt-1 max-w-2xl text-xs leading-5 text-slate-400">
              Adjust the estimates to see how funding, setup costs, and monthly revenue affect your cash runway.
            </p>
          </div>
        </div>
        <button type="button" onClick={reset} className="btn-secondary px-3 py-2 text-xs">
          Reset estimates
        </button>
      </div>

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <NumberField
          id="startup-monthly-costs"
          label="Monthly operating costs (₹)"
          hint="Starts from the 12-month plan average; edit it to suit your business."
          value={monthlyCosts}
          onChange={(value) => { setMonthlyCosts(value); setMonthlyCostsEdited(true) }}
        />
        <NumberField
          id="startup-setup-costs"
          label="One-time setup costs (₹)"
          hint="Equipment, registration, deposits, and other initial expenses."
          value={setupCosts}
          onChange={setSetupCosts}
        />
        <NumberField
          id="startup-available-funding"
          label="Available funding (₹)"
          hint="Cash already available to the startup, excluding unconfirmed funding."
          value={availableFunding}
          onChange={setAvailableFunding}
        />
        <NumberField
          id="startup-monthly-revenue"
          label="Expected monthly revenue (₹)"
          hint="Use a conservative estimate, not your best-case forecast."
          value={monthlyRevenue}
          onChange={setMonthlyRevenue}
        />
      </div>

      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-4" aria-live="polite">
        <Metric
          icon={Gauge}
          label="Estimated runway"
          value={metrics.runwayMonths === null ? 'Not burning cash' : `${metrics.runwayMonths.toFixed(1)} months`}
          note={metrics.runwayMonths === null
            ? 'Revenue covers or exceeds monthly operating costs.'
            : 'Available funding after setup costs divided by net monthly burn.'}
          accent="text-emerald-300"
        />
        <Metric
          icon={Wallet}
          label={hasMonthlySurplus ? 'Monthly surplus' : 'Monthly net burn'}
          value={formatINR(Math.abs(metrics.netBurn))}
          note={hasMonthlySurplus ? 'Expected revenue exceeds monthly operating costs.' : 'Monthly operating costs minus expected revenue.'}
          accent={hasMonthlySurplus ? 'text-emerald-300' : 'text-amber-300'}
        />
        <Metric
          icon={TrendingUp}
          label="Six-month funding gap"
          value={formatINR(metrics.fundingGap)}
          note="Estimated setup and six months of positive net burn, less available funding."
          accent="text-violet-300"
        />
        <Metric
          icon={Calculator}
          label="Break-even revenue"
          value={formatINR(metrics.breakEvenRevenue)}
          note="Monthly revenue needed to cover recurring operating costs."
          accent="text-blue-300"
        />
      </div>

      <p className="text-[0.68rem] leading-5 text-slate-500">
        Planning estimate only. The calculation excludes taxes, debt repayments, working-capital timing, and unexpected costs; actual runway may differ.
      </p>
    </section>
  )
}
