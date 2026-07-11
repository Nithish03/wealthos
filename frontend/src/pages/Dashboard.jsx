import { useState, useEffect } from 'react'
import { dashboardAPI, investmentsAPI } from '../api/client'
import { TrendingUp, TrendingDown, AlertTriangle, Wallet, CreditCard, Building2, BarChart3, RefreshCw } from 'lucide-react'
import { AreaChart, Area, XAxis, YAxis, Tooltip, ResponsiveContainer, PieChart, Pie, Cell, Legend } from 'recharts'
import toast from 'react-hot-toast'

const ASSET_COLORS = {
  indian_stocks: '#00d4aa', mutual_funds: '#3b82f6', us_stocks: '#a855f7',
  crypto: '#f59e0b', gold_etf: '#fbbf24', silver_etf: '#94a3b8',
  sgb: '#f97316', digital_gold: '#eab308', digital_silver: '#cbd5e1',
  liquid_funds: '#06b6d4', bonds: '#8b5cf6', real_estate: '#ef4444',
}
const ASSET_LABELS = {
  indian_stocks: 'Indian Stocks', mutual_funds: 'Mutual Funds', us_stocks: 'US Stocks',
  crypto: 'Crypto', gold_etf: 'Gold ETF', silver_etf: 'Silver ETF',
  sgb: 'SGB', digital_gold: 'Digital Gold', digital_silver: 'Digital Silver',
  liquid_funds: 'Liquid Funds', bonds: 'Bonds', real_estate: 'Real Estate',
}
const assetLabel = (key) => ASSET_LABELS[key] || key.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase())

function fmt(n) { return `₹${Number(n || 0).toLocaleString('en-IN', { maximumFractionDigits: 0 })}` }

function StatCard({ label, value, sub, trend, color = 'text-text-primary', icon: Icon }) {
  return (
    <div className="stat-card animate-slide-up">
      <div className="flex items-center justify-between mb-2">
        <span className="text-xs font-medium text-text-secondary uppercase tracking-wider">{label}</span>
        {Icon && <Icon size={15} className="text-text-muted" />}
      </div>
      <div className={`font-mono text-2xl font-semibold ${color}`}>{value}</div>
      {sub && <div className={`text-xs mt-1 font-mono ${trend === 'up' ? 'text-accent-green' : trend === 'down' ? 'text-accent-red' : 'text-text-secondary'}`}>
        {trend === 'up' ? '▲' : trend === 'down' ? '▼' : ''} {sub}
      </div>}
    </div>
  )
}

function AlertBanner({ alerts }) {
  if (!alerts?.length) return null
  return (
    <div className="space-y-2">
      {alerts.map((alert, i) => (
        <div key={i} className={`flex items-center gap-3 px-4 py-3 rounded-xl border text-sm ${
          alert.type === 'danger'
            ? 'bg-accent-red/10 border-accent-red/30 text-accent-red'
            : 'bg-accent-gold/10 border-accent-gold/30 text-accent-gold'
        }`}>
          <span>{alert.icon}</span>
          <span>{alert.message}</span>
        </div>
      ))}
    </div>
  )
}

const CustomTooltip = ({ active, payload, label }) => {
  if (!active || !payload?.length) return null
  return (
    <div className="card p-3 text-xs space-y-1">
      <div className="font-medium text-text-secondary mb-2">{label}</div>
      {payload.map((p, i) => (
        <div key={i} className="flex justify-between gap-4">
          <span style={{ color: p.color }}>{p.name}</span>
          <span className="font-mono font-medium">{fmt(p.value)}</span>
        </div>
      ))}
    </div>
  )
}

export default function Dashboard() {
  const [overview, setOverview] = useState(null)
  const [history, setHistory] = useState([])
  const [allocation, setAllocation] = useState([])
  const [loading, setLoading] = useState(true)

  const loadData = async () => {
    try {
      setLoading(true)
      const [ov, hist, alloc] = await Promise.all([
        dashboardAPI.overview(),
        dashboardAPI.history(),
        investmentsAPI.summary(),
      ])
      setOverview(ov.data)
      setHistory(hist.data)
      setAllocation(alloc.data.allocation || [])
    } catch (err) {
      toast.error('Failed to load dashboard')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { loadData() }, [])

  if (loading) return (
    <div className="p-4 md:p-8 space-y-4">
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        {[...Array(4)].map((_, i) => <div key={i} className="skeleton h-28 rounded-2xl" />)}
      </div>
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div className="skeleton md:col-span-2 h-64 rounded-2xl" />
        <div className="skeleton h-64 rounded-2xl" />
      </div>
    </div>
  )

  const pnlPositive = (overview?.total_pnl || 0) >= 0

  return (
    <div className="p-4 md:p-8 space-y-6 animate-fade-in">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="font-display text-2xl font-bold text-text-primary">Dashboard</h1>
          <p className="text-text-secondary text-sm mt-1">Your financial overview</p>
        </div>
        <button onClick={loadData} className="btn-secondary flex items-center gap-2">
          <RefreshCw size={14} />
          Refresh
        </button>
      </div>

      {/* Alerts */}
      {overview?.alerts?.length > 0 && <AlertBanner alerts={overview.alerts} />}

      {/* Stats Grid */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard
          label="Net Worth"
          value={fmt(overview?.net_worth)}
          sub={`${fmt(overview?.total_assets)} assets`}
          icon={Wallet}
          color="gradient-text"
        />
        <StatCard
          label="Portfolio Value"
          value={fmt(overview?.investment_value)}
          sub={`${pnlPositive ? '+' : ''}${fmt(overview?.total_pnl)} (${overview?.pnl_percent?.toFixed(1)}%)`}
          trend={pnlPositive ? 'up' : 'down'}
          icon={TrendingUp}
        />
        <StatCard
          label="Bank Balance"
          value={fmt(overview?.bank_balance)}
          icon={Building2}
        />
        <StatCard
          label="Monthly CC Spend"
          value={fmt(overview?.monthly_spend)}
          sub={`${overview?.spend_salary_percent?.toFixed(0)}% of salary`}
          trend={overview?.spend_salary_percent > 40 ? 'down' : 'up'}
          icon={CreditCard}
          color={overview?.spend_salary_percent > 40 ? 'text-accent-red' : 'text-text-primary'}
        />
      </div>

      {/* Assets vs Liabilities */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div className="card p-4">
          <div className="text-xs text-text-secondary uppercase tracking-wider mb-3">Balance Sheet</div>
          <div className="space-y-3">
            <div className="flex justify-between items-center">
              <span className="text-sm text-text-secondary">Total Assets</span>
              <span className="font-mono text-sm text-accent-green font-medium">{fmt(overview?.total_assets)}</span>
            </div>
            <div className="flex justify-between items-center">
              <span className="text-sm text-text-secondary">Total Liabilities</span>
              <span className="font-mono text-sm text-accent-red font-medium">{fmt(overview?.total_liabilities)}</span>
            </div>
            <div className="h-px bg-bg-border" />
            <div className="flex justify-between items-center">
              <span className="text-sm font-medium text-text-primary">Net Worth</span>
              <span className={`font-mono text-sm font-bold ${(overview?.net_worth || 0) >= 0 ? 'text-accent-green' : 'text-accent-red'}`}>
                {fmt(overview?.net_worth)}
              </span>
            </div>
          </div>

          <div className="mt-4 space-y-2">
            <div className="text-xs text-text-secondary">Salary Info</div>
            <div className="flex justify-between text-xs">
              <span className="text-text-muted">Monthly In-hand</span>
              <span className="font-mono text-text-secondary">{fmt(overview?.monthly_salary)}</span>
            </div>
            <div className="flex justify-between text-xs">
              <span className="text-text-muted">Annual CTC</span>
              <span className="font-mono text-text-secondary">{fmt(overview?.annual_ctc)}</span>
            </div>
          </div>
        </div>

        {/* Spending Meter */}
        <div className="card p-4">
          <div className="text-xs text-text-secondary uppercase tracking-wider mb-3">Monthly Spend Meter</div>
          <div className="flex flex-col items-center justify-center h-32">
            <SpendMeter percent={overview?.spend_salary_percent || 0} />
          </div>
          <div className="text-center mt-2">
            <div className="font-mono text-lg font-semibold">{overview?.spend_salary_percent?.toFixed(1)}%</div>
            <div className="text-xs text-text-secondary">of monthly salary spent</div>
          </div>
        </div>

        {/* Quick Stats */}
        <div className="card p-4 space-y-3">
          <div className="text-xs text-text-secondary uppercase tracking-wider">Portfolio P&L</div>
          <div className={`font-mono text-2xl font-bold ${pnlPositive ? 'text-accent-green' : 'text-accent-red'}`}>
            {pnlPositive ? '+' : ''}{fmt(overview?.total_pnl)}
          </div>
          <div className="text-sm text-text-secondary">{overview?.pnl_percent?.toFixed(2)}% overall returns</div>
          <div className="h-px bg-bg-border" />
          <div className="text-xs text-text-secondary uppercase tracking-wider">Total Invested</div>
          <div className="font-mono text-lg font-semibold">{fmt(overview?.total_invested)}</div>
        </div>
      </div>

      {/* Charts Row */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {/* Net Worth Chart */}
        <div className="md:col-span-2 card p-5">
          <div className="flex justify-between items-center mb-4">
            <div className="text-sm font-medium text-text-primary">Net Worth Over Time</div>
            <div className="text-xs text-text-muted">{history.length} snapshots</div>
          </div>
          {history.length === 0 ? (
            <div className="h-48 flex items-center justify-center text-text-muted text-sm">
              <div className="text-center">
                <BarChart3 size={32} className="mx-auto mb-2 opacity-30" />
                <div>No history yet. Save a snapshot to start tracking.</div>
              </div>
            </div>
          ) : (
            <ResponsiveContainer width="100%" height={200}>
              <AreaChart data={history}>
                <defs>
                  <linearGradient id="nwGrad" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#00d4aa" stopOpacity={0.2} />
                    <stop offset="95%" stopColor="#00d4aa" stopOpacity={0} />
                  </linearGradient>
                  <linearGradient id="assetsGrad" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#3b82f6" stopOpacity={0.1} />
                    <stop offset="95%" stopColor="#3b82f6" stopOpacity={0} />
                  </linearGradient>
                </defs>
                <XAxis dataKey="date" tick={{ fill: '#7a8aaa', fontSize: 11 }} tickLine={false} axisLine={false} />
                <YAxis tick={{ fill: '#7a8aaa', fontSize: 11 }} tickLine={false} axisLine={false}
                  tickFormatter={v => `₹${(v/100000).toFixed(0)}L`} />
                <Tooltip content={<CustomTooltip />} />
                <Area type="monotone" dataKey="net_worth" name="Net Worth" stroke="#00d4aa" fill="url(#nwGrad)" strokeWidth={2} dot={false} />
                <Area type="monotone" dataKey="assets" name="Total Assets" stroke="#3b82f6" fill="url(#assetsGrad)" strokeWidth={1.5} strokeDasharray="4 2" dot={false} />
              </AreaChart>
            </ResponsiveContainer>
          )}
        </div>

        {/* Allocation Donut */}
        <div className="card p-5">
          <div className="text-sm font-medium text-text-primary mb-4">Portfolio Allocation</div>
          {allocation.length === 0 ? (
            <div className="h-48 flex items-center justify-center text-text-muted text-sm">
              <div className="text-center">
                <div className="text-2xl mb-2">📊</div>
                <div>No investments yet</div>
              </div>
            </div>
          ) : (
            <>
              <ResponsiveContainer width="100%" height={160}>
                <PieChart>
                  <Pie data={allocation} dataKey="current" nameKey="asset_class" cx="50%" cy="50%"
                    innerRadius={45} outerRadius={70} paddingAngle={2}>
                    {allocation.map((entry, i) => (
                      <Cell key={i} fill={ASSET_COLORS[entry.asset_class] || '#6b7280'} />
                    ))}
                  </Pie>
                  <Tooltip
                    formatter={(v) => [fmt(v), '']}
                    contentStyle={{ background: '#141927', border: '1px solid #1e2a40', borderRadius: '12px', color: '#e2e8f0' }}
                    labelStyle={{ color: '#94a3b8' }}
                    itemStyle={{ color: '#e2e8f0' }}
                  />
                </PieChart>
              </ResponsiveContainer>
              <div className="space-y-1.5 mt-2">
                {allocation.slice(0, 6).map((a, i) => (
                  <div key={i} className="flex items-center justify-between text-xs">
                    <div className="flex items-center gap-2">
                      <div className="w-2 h-2 rounded-full flex-shrink-0" style={{ background: ASSET_COLORS[a.asset_class] || '#6b7280' }} />
                      <span style={{ color: '#94a3b8' }}>{assetLabel(a.asset_class)}</span>
                    </div>
                    <span style={{ fontFamily: 'monospace', color: '#e2e8f0' }}>{a.percent?.toFixed(1)}%</span>
                  </div>
                ))}
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  )
}

function SpendMeter({ percent }) {
  const clamp = Math.min(100, Math.max(0, percent))
  const angle = (clamp / 100) * 180
  const color = clamp >= 80 ? '#f43f5e' : clamp >= 40 ? '#f59e0b' : '#00d4aa'

  const polarToCartesian = (cx, cy, r, angleDeg) => {
    const rad = (angleDeg - 180) * Math.PI / 180
    return { x: cx + r * Math.cos(rad), y: cy + r * Math.sin(rad) }
  }

  const describeArc = (cx, cy, r, startAngle, endAngle) => {
    const start = polarToCartesian(cx, cy, r, endAngle)
    const end = polarToCartesian(cx, cy, r, startAngle)
    const largeArc = endAngle - startAngle <= 180 ? '0' : '1'
    return `M ${start.x} ${start.y} A ${r} ${r} 0 ${largeArc} 0 ${end.x} ${end.y}`
  }

  const needle = polarToCartesian(60, 60, 40, angle)

  return (
    <svg viewBox="0 0 120 70" width="120" height="70">
      <path d={describeArc(60, 60, 48, 0, 180)} fill="none" stroke="#1e2a40" strokeWidth="8" strokeLinecap="round" />
      <path d={describeArc(60, 60, 48, 0, angle)} fill="none" stroke={color} strokeWidth="8" strokeLinecap="round" />
      <line x1="60" y1="60" x2={needle.x} y2={needle.y} stroke={color} strokeWidth="2.5" strokeLinecap="round" />
      <circle cx="60" cy="60" r="4" fill={color} />
      <text x="15" y="68" fill="#3d4d6a" fontSize="8">0%</text>
      <text x="96" y="68" fill="#3d4d6a" fontSize="8">100%</text>
    </svg>
  )
}
