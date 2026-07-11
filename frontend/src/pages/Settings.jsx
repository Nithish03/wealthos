import { useState } from 'react'
import { authAPI, exportAPI, dashboardAPI } from '../api/client'
import toast from 'react-hot-toast'

const FieldRow = ({ label, children }) => (
  <div style={{display:'flex',flexDirection:'column',gap:5}}>
    <label style={{fontSize:12,color:'var(--t2)',fontWeight:500}}>{label}</label>
    {children}
  </div>
)

export default function Settings() {
  const [pin, setPin] = useState({ newPin: '', confirm: '' })
  const [saving, setSaving] = useState(false)

  const changePin = async () => {
    if (pin.newPin.length < 4) return toast.error('New PIN must be at least 4 digits')
    if (pin.newPin !== pin.confirm) return toast.error('PINs do not match')
    setSaving(true)
    try {
      const res = await authAPI.changePin(pin.newPin)
      localStorage.setItem('auth_token', res.data.access_token)
      toast.success('PIN changed!')
      setPin({ newPin: '', confirm: '' })
    } catch (e) { toast.error(e.response?.data?.detail || 'Failed to change PIN') }
    finally { setSaving(false) }
  }

  const takeSnapshot = async () => {
    try {
      const res = await dashboardAPI.snapshot()
      toast.success(`Snapshot saved! Net worth: ₹${res.data.net_worth?.toLocaleString('en-IN')}`)
    } catch { toast.error('Snapshot failed') }
  }

  return (
    <div style={{padding:32,minHeight:'100vh',maxWidth:640}}>
      <div style={{marginBottom:24}}>
        <h1 style={{fontFamily:'Syne',fontSize:24,fontWeight:700,color:'var(--t1)'}}>Settings</h1>
        <p style={{color:'var(--t2)',fontSize:13,marginTop:4}}>PIN, backups and snapshots</p>
      </div>

      {/* Change PIN */}
      <div className="card" style={{padding:20,marginBottom:16}}>
        <div style={{fontWeight:600,fontSize:15,color:'var(--t1)',marginBottom:14}}>🔐 Change PIN</div>
        <div style={{display:'grid',gridTemplateColumns:'1fr 1fr',gap:12,marginBottom:14}}>
          <FieldRow label="New PIN">
            <input type="password" inputMode="numeric" placeholder="Min. 4 digits" value={pin.newPin}
              onChange={e=>setPin(p => ({...p, newPin: e.target.value}))} />
          </FieldRow>
          <FieldRow label="Confirm PIN">
            <input type="password" inputMode="numeric" placeholder="Repeat PIN" value={pin.confirm}
              onChange={e=>setPin(p => ({...p, confirm: e.target.value}))} />
          </FieldRow>
        </div>
        <button className="btn btn-primary" onClick={changePin} disabled={saving}>
          {saving ? 'Changing...' : 'Change PIN'}
        </button>
      </div>

      {/* Export & Backup */}
      <div className="card" style={{padding:20,marginBottom:16}}>
        <div style={{fontWeight:600,fontSize:15,color:'var(--t1)',marginBottom:14}}>📤 Export & Backup</div>
        <div style={{display:'flex',flexDirection:'column',gap:10}}>
          {[
            { title:'Export to Excel', sub:'Investments, cards, accounts and net worth history',
              action:()=>exportAPI.excel().then(()=>toast.success('Exported!')).catch(()=>toast.error('Export failed')), label:'Export' },
            { title:'Backup Database', sub:'Download the SQLite .db file for safekeeping',
              action:()=>exportAPI.backupDB().then(()=>toast.success('Backup downloaded!')).catch(()=>toast.error('Backup failed')), label:'Download' },
            { title:'Manual Snapshot', sub:"Save today's net worth to history",                  action:takeSnapshot,             label:'Snapshot Now' },
          ].map((row,i)=>(
            <div key={i} style={{display:'flex',alignItems:'center',justifyContent:'space-between',
              background:'var(--bg1)',border:'1.5px solid var(--bd)',borderRadius:12,padding:'12px 16px'}}>
              <div>
                <div style={{fontSize:13,fontWeight:600,color:'var(--t1)'}}>{row.title}</div>
                <div style={{fontSize:11,color:'var(--t3)',marginTop:2}}>{row.sub}</div>
              </div>
              <button className="btn btn-secondary" style={{fontSize:12,padding:'7px 14px'}} onClick={row.action}>{row.label}</button>
            </div>
          ))}
        </div>
      </div>

      <div style={{textAlign:'center',color:'var(--t3)',fontSize:11,paddingBottom:16}}>
        WealthOS v1.0 · All data stored locally · No cloud, no tracking
      </div>
    </div>
  )
}
