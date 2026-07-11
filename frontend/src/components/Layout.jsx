import { Outlet, NavLink, useNavigate } from 'react-router-dom'
import { LayoutDashboard, TrendingUp, CreditCard, Building2, Lightbulb, Download, LogOut, Database, RefreshCw, Settings as SettingsIcon } from 'lucide-react'
import { exportAPI, dashboardAPI } from '../api/client'
import toast from 'react-hot-toast'

const navItems = [
  { to: '/', icon: LayoutDashboard, label: 'Dashboard', end: true },
  { to: '/investments', icon: TrendingUp, label: 'Portfolio' },
  { to: '/credit-cards', icon: CreditCard, label: 'Credit Cards' },
  { to: '/bank-accounts', icon: Building2, label: 'Bank Accounts' },
  { to: '/suggestions', icon: Lightbulb, label: 'AI Insights' },
  { to: '/settings', icon: SettingsIcon, label: 'Settings' },
]

export default function Layout() {
  const navigate = useNavigate()

  const handleLogout = () => {
    localStorage.removeItem('auth_token')
    navigate('/login')
  }

  const handleSnapshot = async () => {
    try {
      const res = await dashboardAPI.snapshot()
      toast.success(`Snapshot saved! Net Worth: ₹${res.data.net_worth?.toLocaleString('en-IN')}`)
    } catch {
      toast.error('Failed to save snapshot')
    }
  }

  return (
    <div className="flex h-screen overflow-hidden bg-bg-primary">
      <aside className="w-64 flex-shrink-0 bg-bg-secondary border-r border-bg-border flex flex-col">
        <div className="p-6 border-b border-bg-border">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-xl bg-accent-green/10 border border-accent-green/30 flex items-center justify-center">
              <span className="text-lg">₹</span>
            </div>
            <div>
              <div className="font-display font-bold text-lg text-text-primary leading-none">WealthOS</div>
              <div className="text-xs text-text-secondary mt-0.5">Personal Finance</div>
            </div>
          </div>
        </div>

        <nav className="flex-1 p-4 space-y-1">
          {navItems.map(({ to, icon: Icon, label, end }) => (
            <NavLink key={to} to={to} end={end}
              className={({ isActive }) =>
                `flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm font-medium transition-all duration-150 ${
                  isActive
                    ? 'bg-accent-green/10 text-accent-green border border-accent-green/20'
                    : 'text-text-secondary hover:text-text-primary hover:bg-bg-hover'
                }`
              }>
              <Icon size={17} />{label}
            </NavLink>
          ))}
        </nav>

        <div className="p-4 border-t border-bg-border space-y-1">
          <button onClick={handleSnapshot} className="flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm text-text-secondary hover:text-text-primary hover:bg-bg-hover transition-all w-full">
            <RefreshCw size={16} />Save Snapshot
          </button>
          <button onClick={() => exportAPI.excel().catch(() => toast.error('Export failed'))} className="flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm text-text-secondary hover:text-text-primary hover:bg-bg-hover transition-all w-full">
            <Download size={16} />Export Excel
          </button>
          <button onClick={() => exportAPI.backupDB().catch(() => toast.error('Backup failed'))} className="flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm text-text-secondary hover:text-text-primary hover:bg-bg-hover transition-all w-full">
            <Database size={16} />Backup DB
          </button>
          <button onClick={handleLogout} className="flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm text-accent-red/70 hover:text-accent-red hover:bg-accent-red/10 transition-all w-full">
            <LogOut size={16} />Lock App
          </button>
        </div>
      </aside>

      <main className="flex-1 overflow-y-auto">
        <Outlet />
      </main>
    </div>
  )
}
