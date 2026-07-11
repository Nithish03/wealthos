export const formatCurrency = (amount, compact = false) => {
  if (amount === null || amount === undefined) return '₹0'
  const abs = Math.abs(amount)
  const sign = amount < 0 ? '-' : ''
  if (compact) {
    if (abs >= 10000000) return `${sign}₹${(abs / 10000000).toFixed(2)}Cr`
    if (abs >= 100000) return `${sign}₹${(abs / 100000).toFixed(2)}L`
    if (abs >= 1000) return `${sign}₹${(abs / 1000).toFixed(1)}K`
  }
  return `${sign}₹${abs.toLocaleString('en-IN', { minimumFractionDigits: 0, maximumFractionDigits: 0 })}`
}

export const formatPct = (pct) => {
  if (pct === null || pct === undefined) return '0%'
  const sign = pct >= 0 ? '+' : ''
  return `${sign}${pct.toFixed(2)}%`
}

export const pnlColor = (val) => val >= 0 ? 'text-[#00ff87]' : 'text-red-400'
export const pnlBg = (val) => val >= 0 ? 'bg-[#00ff87]/10' : 'bg-red-400/10'

export const ASSET_CLASS_CONFIG = {
  stocks: { label: 'Indian Stocks', color: '#6366f1', icon: '📈' },
  mutual_funds: { label: 'Mutual Funds', color: '#8b5cf6', icon: '🏦' },
  us_stocks: { label: 'US Stocks', color: '#06b6d4', icon: '🌍' },
  crypto: { label: 'Crypto', color: '#f59e0b', icon: '₿' },
  gold_etf: { label: 'Gold ETF', color: '#ffd700', icon: '🥇' },
  silver_etf: { label: 'Silver ETF', color: '#94a3b8', icon: '🥈' },
  sgb: { label: 'Sovereign Gold Bond', color: '#d97706', icon: '🏅' },
  digital_gold: { label: 'Digital Gold', color: '#f59e0b', icon: '✨' },
  digital_silver: { label: 'Digital Silver', color: '#9ca3af', icon: '💎' },
}

export const CATEGORIES = ['Food', 'Shopping', 'Travel', 'Entertainment', 'Utilities', 'Health', 'Fuel', 'EMI', 'Other']

export const CATEGORY_COLORS = {
  Food: '#f97316', Shopping: '#8b5cf6', Travel: '#06b6d4', Entertainment: '#ec4899',
  Utilities: '#6366f1', Health: '#10b981', Fuel: '#f59e0b', EMI: '#ef4444', Other: '#64748b'
}

export const getMonthYear = (date) => {
  const d = new Date(date)
  return { month: d.getMonth() + 1, year: d.getFullYear() }
}

export const downloadBlob = (blob, filename) => {
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  a.click()
  URL.revokeObjectURL(url)
}
