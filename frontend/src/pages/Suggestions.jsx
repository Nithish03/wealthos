import { useState, useEffect } from 'react'
import { suggestionsAPI } from '../api/client'
import { RefreshCw, TrendingUp, Shield, CreditCard, PieChart, Target, BookOpen, Trophy } from 'lucide-react'
import { RadialBarChart, RadialBar, ResponsiveContainer } from 'recharts'
import toast from 'react-hot-toast'

function fmt(n) { return `₹${Number(n||0).toLocaleString('en-IN',{maximumFractionDigits:0})}` }

const CATEGORY_ICONS = {
  savings: '💰', investment: '📈', allocation: '⚖️', credit: '💳',
  emergency: '🏦', tax: '📋', milestones: '🏆',
}

const PRIORITY_STYLES = {
  high: 'border-accent-red/30 bg-accent-red/5',
  medium: 'border-accent-gold/30 bg-accent-gold/5',
  low: 'border-accent-green/30 bg-accent-green/5',
  info: 'border-accent-blue/30 bg-accent-blue/5',
}

const PRIORITY_LABELS = {
  high: { text: 'High Priority', color: 'text-accent-red bg-accent-red/10 border-accent-red/20' },
  medium: { text: 'Medium', color: 'text-accent-gold bg-accent-gold/10 border-accent-gold/20' },
  low: { text: 'On Track', color: 'text-accent-green bg-accent-green/10 border-accent-green/20' },
  info: { text: 'Info', color: 'text-accent-blue bg-accent-blue/10 border-accent-blue/20' },
}

function SuggestionCard({ s }) {
  const [open, setOpen] = useState(true)
  const pStyle = PRIORITY_STYLES[s.priority] || PRIORITY_STYLES.info
  const pLabel = PRIORITY_LABELS[s.priority] || PRIORITY_LABELS.info

  return (
    <div className={`card border ${pStyle} overflow-hidden`}>
      <button className="w-full text-left p-4 flex items-start justify-between gap-3" onClick={() => setOpen(!open)}>
        <div className="flex items-center gap-3">
          <span className="text-xl">{CATEGORY_ICONS[s.category] || '💡'}</span>
          <div>
            <div className="font-medium text-text-primary text-sm">{s.title}</div>
            {s.action && !open && <div className="text-xs text-text-muted mt-0.5 truncate max-w-xs">{s.action}</div>}
          </div>
        </div>
        <span className={`flex-shrink-0 text-xs px-2 py-0.5 rounded-full border font-medium ${pLabel.color}`}>
          {pLabel.text}
        </span>
      </button>

      {open && (
        <div className="px-4 pb-4 space-y-2">
          {/* SIP Breakdown */}
          {s.sip_breakdown && (
            <div className="grid grid-cols-2 gap-2 mb-3">
              {Object.entries(s.sip_breakdown).map(([k, v]) => (
                <div key={k} className="flex justify-between items-center bg-bg-secondary rounded-xl px-3 py-2">
                  <span className="text-xs text-text-secondary">{k}</span>
                  <span className="font-mono text-xs font-semibold text-accent-green">{fmt(v)}/mo</span>
                </div>
              ))}
            </div>
          )}

          {/* Allocation table */}
          {s.allocation_data && (
            <div className="space-y-1.5 mb-3">
              {s.allocation_data.map((a, i) => (
                <div key={i} className="flex items-center gap-3">
                  <span className="text-xs text-text-secondary w-28 flex-shrink-0">{a.label}</span>
                  <div className="flex-1 h-1.5 bg-bg-border rounded-full overflow-hidden">
                    <div className="h-full rounded-full bg-accent-blue" style={{ width: `${Math.min(100, a.actual_pct * 2)}%` }} />
                  </div>
                  <span className={`text-xs font-mono w-12 text-right ${a.status === 'over' ? 'text-accent-gold' : a.status === 'under' ? 'text-accent-red' : 'text-accent-green'}`}>
                    {a.actual_pct}%
                  </span>
                  <span className="text-xs text-text-muted w-12 text-right">rec: {a.recommended_pct}%</span>
                </div>
              ))}
            </div>
          )}

          {/* Milestones */}
          {s.milestones && (
            <div className="grid grid-cols-2 gap-2 mb-3">
              {s.milestones.map((m, i) => (
                <div key={i} className={`rounded-xl p-3 border ${m.months === 0 ? 'border-accent-green/30 bg-accent-green/5' : 'border-bg-border bg-bg-secondary'}`}>
                  <div className="text-xs font-bold text-text-primary">{m.label}</div>
                  {m.months === 0 ? (
                    <div className="text-xs text-accent-green mt-1">✅ Already reached!</div>
                  ) : (
                    <>
                      <div className="font-mono text-lg font-bold text-accent-gold mt-1">{m.years}y</div>
                      <div className="text-xs text-text-muted">{m.months} months</div>
                    </>
                  )}
                </div>
              ))}
            </div>
          )}

          {/* Details */}
          <ul className="space-y-1.5">
            {s.details?.map((d, i) => (
              <li key={i} className="flex items-start gap-2 text-sm text-text-secondary">
                <span className="text-text-muted mt-0.5 flex-shrink-0">•</span>
                <span>{d}</span>
              </li>
            ))}
          </ul>

          {s.action && (
            <div className="mt-3 pt-3 border-t border-bg-border/50">
              <div className="text-xs font-medium text-accent-green">💡 Action: {s.action}</div>
            </div>
          )}
        </div>
      )}
    </div>
  )
}

function HealthScore({ score, grade, breakdown }) {
  const color = score >= 80 ? '#00d4aa' : score >= 60 ? '#f59e0b' : score >= 40 ? '#f97316' : '#f43f5e'
  const data = [{ value: score, fill: color }, { value: 100 - score, fill: '#1e2a40' }]

  return (
    <div className="card p-5">
      <div className="text-sm font-medium text-text-primary mb-4">Financial Health Score</div>
      <div className="flex items-center gap-6">
        <div className="relative w-24 h-24 flex-shrink-0">
          <ResponsiveContainer width={96} height={96}>
            <RadialBarChart cx={48} cy={48} innerRadius={28} outerRadius={44} data={data} startAngle={90} endAngle={-270}>
              <RadialBar dataKey="value" cornerRadius={4} />
            </RadialBarChart>
          </ResponsiveContainer>
          <div className="absolute inset-0 flex flex-col items-center justify-center">
            <span className="font-mono text-xl font-bold" style={{ color }}>{score}</span>
            <span className="font-display text-sm font-bold" style={{ color }}>{grade}</span>
          </div>
        </div>
        <div className="flex-1 space-y-2">
          {breakdown?.map((b, i) => (
            <div key={i} className="flex items-center gap-2">
              <div className={`w-2 h-2 rounded-full flex-shrink-0 ${b.status === 'good' ? 'bg-accent-green' : b.status === 'partial' ? 'bg-accent-gold' : 'bg-accent-red'}`} />
              <span className="text-xs text-text-secondary flex-1">{b.label}</span>
              <span className="text-xs font-mono text-text-muted">{b.score}/{b.max}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}

export default function Suggestions() {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)

  const load = async () => {
    setLoading(true)
    try {
      const res = await suggestionsAPI.get()
      setData(res.data)
    } catch { toast.error('Failed to load suggestions') }
    finally { setLoading(false) }
  }

  useEffect(() => { load() }, [])

  if (loading) return (
    <div className="p-8 grid grid-cols-2 gap-4">
      {[...Array(4)].map((_,i) => <div key={i} className="skeleton h-40 rounded-2xl" />)}
    </div>
  )

  return (
    <div className="p-8 space-y-6 animate-fade-in">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="font-display text-2xl font-bold">AI Insights & Suggestions</h1>
          <p className="text-text-secondary text-sm mt-1">Personalized based on ₹13.95L CTC new salary</p>
        </div>
        <button onClick={load} className="btn-secondary flex items-center gap-2">
          <RefreshCw size={14} />Refresh
        </button>
      </div>

      {/* Salary Info Banner */}
      {data?.salary && (
        <div className="card p-4 border-accent-green/20 bg-accent-green/5">
          <div className="flex items-center gap-4 flex-wrap">
            <div className="text-sm font-medium text-accent-green">🎯 New Salary Context</div>
            <div className="flex gap-6 text-xs flex-wrap">
              <span className="text-text-secondary">CTC: <span className="font-mono text-text-primary font-medium">{fmt(data.salary.annual_ctc)}/yr</span></span>
              <span className="text-text-secondary">Fixed: <span className="font-mono text-text-primary font-medium">{fmt(data.salary.fixed_ctc)}/yr</span></span>
              <span className="text-text-secondary">Monthly Gross: <span className="font-mono text-text-primary font-medium">{fmt(data.salary.monthly_inhand)}/mo</span></span>
              <span className="text-text-secondary">Bonus: <span className="font-mono text-accent-gold font-medium">{fmt(data.salary.performance_bonus)} (July)</span></span>
            </div>
          </div>
        </div>
      )}

      <div className="grid grid-cols-3 gap-6">
        {/* Left: suggestions */}
        <div className="col-span-2 space-y-4">
          {data?.suggestions?.map((s, i) => <SuggestionCard key={i} s={s} />)}
        </div>

        {/* Right: health score + quick stats */}
        <div className="space-y-4">
          {data?.financial_health_score && (
            <HealthScore
              score={data.financial_health_score.score}
              grade={data.financial_health_score.grade}
              breakdown={data.financial_health_score.breakdown}
            />
          )}

          <div className="card p-4 space-y-3">
            <div className="text-sm font-medium text-text-primary">Quick Allocation Guide</div>
            <div className="text-xs text-text-secondary mb-2">For age 26, moderate-aggressive risk</div>
            {[
              { label: 'Equity (Stocks + MF)', pct: 60, color: 'bg-accent-green' },
              { label: 'Debt / Bonds', pct: 20, color: 'bg-accent-blue' },
              { label: 'Gold / Silver', pct: 10, color: 'bg-accent-gold' },
              { label: 'Crypto', pct: 5, color: 'bg-accent-purple' },
              { label: 'Cash Reserve', pct: 5, color: 'bg-text-secondary' },
            ].map((item, i) => (
              <div key={i}>
                <div className="flex justify-between text-xs mb-1">
                  <span className="text-text-secondary">{item.label}</span>
                  <span className="font-mono text-text-primary">{item.pct}%</span>
                </div>
                <div className="h-1 bg-bg-border rounded-full overflow-hidden">
                  <div className={`h-full ${item.color} rounded-full`} style={{ width: `${item.pct * 1.6}%` }} />
                </div>
              </div>
            ))}
          </div>

          <div className="card p-4">
            <div className="text-sm font-medium text-text-primary mb-3">Key Rules</div>
            <ul className="space-y-2 text-xs text-text-secondary">
              <li className="flex gap-2"><span className="text-accent-green flex-shrink-0">✓</span>Save 30-40% of in-hand salary</li>
              <li className="flex gap-2"><span className="text-accent-green flex-shrink-0">✓</span>Keep 6 months in emergency fund</li>
              <li className="flex gap-2"><span className="text-accent-green flex-shrink-0">✓</span>CC spend &lt; 40% of monthly salary</li>
              <li className="flex gap-2"><span className="text-accent-green flex-shrink-0">✓</span>Pay full CC due every month</li>
              <li className="flex gap-2"><span className="text-accent-green flex-shrink-0">✓</span>Max out 80C (₹1.5L) every FY</li>
              <li className="flex gap-2"><span className="text-accent-gold flex-shrink-0">→</span>Review portfolio every 3 months</li>
            </ul>
          </div>
        </div>
      </div>
    </div>
  )
}
