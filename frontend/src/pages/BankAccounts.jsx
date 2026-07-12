import { useState, useEffect, useRef } from 'react'
import { bankAccountsAPI, pdfImportAPI, withFilePassword, apiErrMsg } from '../api/client'
import CategoryTrainer from '../components/CategoryTrainer'
import { CategorySelect, TxnBadges } from '../components/CategoryBits'
import toast from 'react-hot-toast'

const fmt  = (n) => `₹${Number(n||0).toLocaleString('en-IN',{maximumFractionDigits:0})}`
const fmtK = (n) => Number(n||0) >= 100000 ? `₹${(n/100000).toFixed(1)}L` : fmt(n)

/* ── Toggle Switch ───────────────────────────────── */
function Toggle({ checked, onChange }) {
  return (
    <div onClick={onChange} style={{
      width:40, height:22, borderRadius:11, cursor:'pointer', position:'relative',
      background: checked ? 'var(--green)' : 'var(--bg3)',
      border: `1.5px solid ${checked ? 'var(--green)' : 'var(--bd)'}`,
      transition:'background .2s, border-color .2s', flexShrink:0,
    }}>
      <div style={{
        position:'absolute', top:2, width:14, height:14, borderRadius:'50%',
        background:'#fff', transition:'left .2s',
        left: checked ? 22 : 2,
        boxShadow:'0 1px 3px rgba(0,0,0,.4)',
      }}/>
    </div>
  )
}

/* ── Shared field wrapper (must be top-level, not inside component) ── */
const FieldRow = ({ label, children }) => (
  <div style={{display:'flex',flexDirection:'column',gap:5}}>
    <label style={{fontSize:12,color:'var(--t2)',fontWeight:500}}>{label}</label>
    {children}
  </div>
)

/* ── Account Form Modal ──────────────────────────── */
function AccountModal({ acc, onClose, onSave }) {
  const [form, setForm] = useState(acc || {
    name:'', bank:'', purpose:'', balance:'0',
    monthly_inflow:'', monthly_outflow:'', is_emergency_fund: false
  })
  const [saving, setSaving] = useState(false)

  const submit = async (e) => {
    e.preventDefault(); setSaving(true)
    try {
      const data = {
        name: form.name, bank: form.bank, purpose: form.purpose,
        balance:         parseFloat(form.balance)||0,
        monthly_inflow:  parseFloat(form.monthly_inflow)||0,
        monthly_outflow: parseFloat(form.monthly_outflow)||0,
        is_emergency_fund: form.is_emergency_fund,
      }
      if (acc?.id) await bankAccountsAPI.update(acc.id, data)
      else         await bankAccountsAPI.create(data)
      toast.success(acc?.id ? 'Account updated!' : 'Account added!')
      onSave()
    } catch(e) { toast.error(e.response?.data?.detail || 'Failed to save') }
    finally { setSaving(false) }
  }
  return (
    <div className="modal-overlay" onClick={e=>e.target===e.currentTarget&&onClose()}>
      <div className="modal" style={{maxWidth:480}}>
        <h2 style={{fontFamily:'Syne',fontSize:18,fontWeight:700,marginBottom:20,color:'var(--t1)'}}>
          {acc?.id ? 'Edit' : 'Add'} Bank Account
        </h2>
        <form onSubmit={submit} style={{display:'flex',flexDirection:'column',gap:14}}>
          <div style={{display:'grid',gridTemplateColumns:'1fr 1fr',gap:12}}>
            <FieldRow label="Account Name">
              <input placeholder="Jupiter" value={form.name} onChange={e=>setForm(prev => ({...prev,name:e.target.value}))} required />
            </FieldRow>
            <FieldRow label="Bank">
              <input placeholder="Jupiter Bank" value={form.bank} onChange={e=>setForm(prev => ({...prev,bank:e.target.value}))} required />
            </FieldRow>
          </div>
          <FieldRow label="Purpose / Note">
            <input placeholder="Main salary account" value={form.purpose} onChange={e=>setForm(prev => ({...prev,purpose:e.target.value}))} />
          </FieldRow>
          <FieldRow label="Current Balance (₹)">
            <input type="number" step="0.01" placeholder="0" value={form.balance} onChange={e=>setForm(prev => ({...prev,balance:e.target.value}))} />
          </FieldRow>
          <div style={{display:'grid',gridTemplateColumns:'1fr 1fr',gap:12}}>
            <FieldRow label="Monthly Inflow (₹)">
              <input type="number" step="0.01" placeholder="0" value={form.monthly_inflow} onChange={e=>setForm(prev => ({...prev,monthly_inflow:e.target.value}))} />
            </FieldRow>
            <FieldRow label="Monthly Outflow (₹)">
              <input type="number" step="0.01" placeholder="0" value={form.monthly_outflow} onChange={e=>setForm(prev => ({...prev,monthly_outflow:e.target.value}))} />
            </FieldRow>
          </div>

          {/* Emergency Fund Toggle */}
          <div style={{
            display:'flex',alignItems:'center',justifyContent:'space-between',
            background:'var(--bg1)',border:'1.5px solid var(--bd)',borderRadius:12,padding:'12px 16px',
          }}>
            <div>
              <div style={{fontWeight:600,fontSize:13,color:'var(--t1)'}}>Emergency Fund Account</div>
              <div style={{fontSize:11,color:'var(--t2)',marginTop:2}}>Used to track 3-6 month expense coverage</div>
            </div>
            <Toggle checked={form.is_emergency_fund} onChange={()=>setForm(prev => ({...prev,is_emergency_fund:!prev.is_emergency_fund}))} />
          </div>

          <div style={{display:'flex',gap:10,marginTop:4}}>
            <button type="button" className="btn btn-secondary" style={{flex:1}} onClick={onClose}>Cancel</button>
            <button type="submit" className="btn btn-primary" style={{flex:1}} disabled={saving}>
              {saving ? 'Saving...' : 'Save'}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}

/* ── Statement Import Modal ──────────────────────── */
function ImportModal({ acc, onClose, onDone }) {
  const [file, setFile]       = useState(null)
  const [loading, setLoading] = useState(false)
  const [result, setResult]   = useState(null)
  const [trainItems, setTrainItems] = useState(null)
  const fileRef = useRef()

  const handleImport = async () => {
    if (!file) return toast.error('Select a file first')
    setLoading(true)
    try {
      const isPDF = file.name.toLowerCase().endsWith('.pdf')
      const res = await withFilePassword(pw => isPDF
        ? pdfImportAPI.bankStatement(acc.id, file, pw)
        : bankAccountsAPI.importStatement(acc.id, file, pw))
      setResult(res.data)
      toast.success(res.data.message)
      if (res.data.uncategorized?.length) setTrainItems(res.data.uncategorized)
    } catch(e) {
      toast.error(apiErrMsg(e, 'Import failed — check format'))
    } finally { setLoading(false) }
  }

  return (
    <div className="modal-overlay" onClick={e=>e.target===e.currentTarget&&onClose()}>
      <div className="modal" style={{maxWidth:520}}>
        <h2 style={{fontFamily:'Syne',fontSize:18,fontWeight:700,marginBottom:4,color:'var(--t1)'}}>
          Import Bank Statement
        </h2>
        <p style={{color:'var(--t2)',fontSize:13,marginBottom:20}}>{acc.name} — {acc.bank}</p>

        <div style={{background:'var(--bg1)',border:'1.5px solid var(--bd)',borderRadius:12,padding:'12px 16px',marginBottom:16}}>
          <div style={{fontSize:12,color:'var(--t2)',fontWeight:600,marginBottom:6}}>📋 How to export your statement:</div>
          <div style={{fontSize:12,color:'var(--t3)',lineHeight:1.8}}>
            • <strong style={{color:'var(--t2)'}}>Jupiter:</strong> App → Passbook → Download Statement → Excel<br/>
            • <strong style={{color:'var(--t2)'}}>DBS:</strong> NetBanking → Accounts → Download → Excel or CSV<br/>
            • <strong style={{color:'var(--t2)'}}>Equitas:</strong> NetBanking → Account Statement → Download<br/>
            • Any XLSX/CSV with Date + Description + Amount/Debit/Credit columns works
          </div>
        </div>

        <div style={{display:'flex',flexDirection:'column',gap:14}}>
          <div className="drop-zone" onClick={()=>fileRef.current.click()} style={file?{borderColor:'var(--green)',background:'rgba(0,212,170,0.05)'}:{}}>
            <input ref={fileRef} type="file" accept=".pdf,.xlsx,.xls,.csv" style={{display:'none'}}
              onChange={e=>{setFile(e.target.files[0]);setResult(null)}} />
            {file ? (
              <>
                <div style={{fontSize:28,marginBottom:6}}>✅</div>
                <div style={{color:'var(--green)',fontWeight:600,fontSize:14}}>{file.name}</div>
                <div style={{color:'var(--t3)',fontSize:12,marginTop:3}}>{(file.size/1024).toFixed(1)} KB</div>
              </>
            ) : (
              <>
                <div style={{fontSize:28,marginBottom:8}}>📂</div>
                <div style={{color:'var(--t2)',fontSize:13}}>Click to upload XLSX or CSV statement</div>
                <div style={{color:'var(--t3)',fontSize:11,marginTop:4}}>PDF or XLSX · DBS · Federal(Jupiter) · Equitas · Canara</div>
              </>
            )}
          </div>

          {result && (
            <div style={{background:'rgba(0,212,170,0.07)',border:'1.5px solid rgba(0,212,170,0.2)',borderRadius:12,padding:16}}>
              <div style={{color:'var(--green)',fontWeight:700,fontSize:14,marginBottom:10}}>✅ {result.message}</div>
              <div style={{display:'grid',gridTemplateColumns:'1fr 1fr',gap:8,marginBottom:10}}>
                {[
                  {label:'Total Credits', value:fmt(result.total_credits), color:'var(--green)'},
                  {label:'Total Debits',  value:fmt(result.total_debits),  color:'var(--red)'},
                  {label:'Transactions',  value:result.transactions,       color:'var(--t1)'},
                  {label:'Period',        value:result.period||'—',        color:'var(--t2)'},
                ].map((s,i)=>(
                  <div key={i} style={{background:'var(--bg2)',borderRadius:8,padding:'8px 12px'}}>
                    <div style={{fontSize:11,color:'var(--t3)'}}>{s.label}</div>
                    <div style={{fontFamily:'monospace',fontWeight:600,color:s.color,fontSize:13,marginTop:2}}>{s.value}</div>
                  </div>
                ))}
              </div>
              {result.top_categories && (
                <>
                  <div style={{fontSize:12,color:'var(--t2)',fontWeight:600,marginBottom:6}}>Top Spending Categories:</div>
                  {result.top_categories.map((c,i)=>(
                    <div key={i} style={{display:'flex',justifyContent:'space-between',fontSize:12,marginBottom:4}}>
                      <span style={{color:'var(--t2)'}}>{c.category}</span>
                      <span style={{fontFamily:'monospace',color:'var(--t1)'}}>{fmt(c.amount)}</span>
                    </div>
                  ))}
                </>
              )}
            </div>
          )}

          <div style={{display:'flex',gap:10}}>
            <button className="btn btn-secondary" style={{flex:1}} onClick={()=>{onDone();onClose()}}>
              {result ? 'Done' : 'Cancel'}
            </button>
            {!result && (
              <button className="btn btn-primary" style={{flex:1}} onClick={handleImport} disabled={!file||loading}>
                {loading ? '⏳ Parsing...' : '⬆️ Import Statement'}
              </button>
            )}
          </div>
        </div>
      </div>
      {trainItems && (
        <CategoryTrainer items={trainItems} onClose={()=>setTrainItems(null)} onSaved={onDone} />
      )}
    </div>
  )
}

/* ── Account Card ────────────────────────────────── */
function AccountCard({ acc, onEdit, onDelete, onImport }) {
  const coverageMonths = acc.emergency_months || 0
  const coveragePct    = Math.min(100, (coverageMonths / 6) * 100)
  const coverageColor  = coverageMonths >= 6 ? 'var(--green)' : coverageMonths >= 3 ? 'var(--gold)' : 'var(--red)'

  return (
    <div className="card fade-in" style={{padding:20,display:'flex',flexDirection:'column',gap:0}}>
      {/* Header */}
      <div style={{display:'flex',justifyContent:'space-between',alignItems:'flex-start',marginBottom:16}}>
        <div>
          <div style={{display:'flex',alignItems:'center',gap:8,marginBottom:4}}>
            <span style={{fontWeight:600,fontSize:15,color:'var(--t1)'}}>{acc.name}</span>
            {acc.is_emergency_fund && (
              <span className="tag tag-green" style={{fontSize:10}}>🛡 Emergency</span>
            )}
          </div>
          <div style={{fontSize:12,color:'var(--t2)'}}>{acc.bank}{acc.purpose ? ` · ${acc.purpose}` : ''}</div>
        </div>
        <div style={{display:'flex',gap:4}}>
          <button className="btn btn-ghost" style={{padding:'5px 8px',fontSize:13}} onClick={()=>onImport(acc)} title="Import statement">📥</button>
          <button className="btn btn-ghost" style={{padding:'5px 8px',fontSize:13}} onClick={()=>onEdit(acc)} title="Edit">✏️</button>
          <button className="btn btn-ghost" style={{padding:'5px 8px',fontSize:13,color:'var(--red)'}} onClick={()=>onDelete(acc.id)} title="Delete">🗑</button>
        </div>
      </div>

      {/* Balance */}
      <div style={{fontFamily:'JetBrains Mono',fontSize:26,fontWeight:700,color:'var(--t1)',marginBottom:16}}>{fmt(acc.balance)}</div>

      {/* Inflow / Outflow */}
      <div style={{display:'grid',gridTemplateColumns:'1fr 1fr',gap:10,marginBottom:acc.is_emergency_fund?14:0}}>
        <div style={{background:'var(--bg1)',borderRadius:10,padding:'10px 12px'}}>
          <div style={{fontSize:11,color:'var(--t3)',marginBottom:3}}>Monthly In</div>
          <div style={{fontFamily:'monospace',fontWeight:600,color:'var(--green)',fontSize:14}}>{fmt(acc.monthly_inflow)}</div>
        </div>
        <div style={{background:'var(--bg1)',borderRadius:10,padding:'10px 12px'}}>
          <div style={{fontSize:11,color:'var(--t3)',marginBottom:3}}>Monthly Out</div>
          <div style={{fontFamily:'monospace',fontWeight:600,color:'var(--red)',fontSize:14}}>{fmt(acc.monthly_outflow)}</div>
        </div>
      </div>

      {/* Emergency coverage bar */}
      {acc.is_emergency_fund && (
        <div>
          <div style={{display:'flex',justifyContent:'space-between',fontSize:11,marginBottom:5}}>
            <span style={{color:'var(--t3)'}}>Emergency Coverage</span>
            <span style={{color:coverageColor,fontWeight:600}}>{coverageMonths.toFixed(1)} / 6 months</span>
          </div>
          <div className="progress-track">
            <div className="progress-fill" style={{width:`${coveragePct}%`,background:coverageColor}}/>
          </div>
          {coverageMonths < 3 && (
            <div style={{fontSize:11,color:'var(--red)',marginTop:5}}>⚠ Below 3-month minimum — top up {fmt(Math.max(0,(3-coverageMonths)*100000))}</div>
          )}
        </div>
      )}
    </div>
  )
}

/* ── Transactions Panel ──────────────────────────── */
function TransactionsPanel({ accId }) {
  const [txns, setTxns] = useState([])
  const [loading, setLoading] = useState(true)

  useEffect(()=>{
    bankAccountsAPI.transactions(accId)
      .then(r=>setTxns(r.data))
      .catch(()=>{})
      .finally(()=>setLoading(false))
  },[accId])

  if (loading) return <div style={{color:'var(--t3)',fontSize:13,padding:20,textAlign:'center'}}>Loading...</div>
  if (!txns.length) return <div style={{color:'var(--t3)',fontSize:13,padding:20,textAlign:'center'}}>No transactions yet. Import a statement above.</div>

  return (
    <div style={{maxHeight:300,overflowY:'auto'}}>
      <table>
        <thead><tr>
          <th>Date</th><th>Description</th><th>Category</th>
          <th style={{textAlign:'right'}}>Credit</th>
          <th style={{textAlign:'right'}}>Debit</th>
        </tr></thead>
        <tbody>
          {txns.slice(0,50).map(t=>(
            <tr key={t.id}>
              <td style={{color:'var(--t3)',fontSize:12,whiteSpace:'nowrap'}}>
                {new Date(t.transaction_date).toLocaleDateString('en-IN',{day:'2-digit',month:'short'})}
              </td>
              <td style={{fontSize:12,maxWidth:200}}>
                <div style={{overflow:'hidden',textOverflow:'ellipsis',whiteSpace:'nowrap'}}>{t.description||'—'}</div>
              </td>
              <td style={{whiteSpace:'nowrap'}}>
                <CategorySelect source="bank" txn={t} onSaved={()=>{}} />
                <TxnBadges txn={t} />
              </td>
              <td style={{textAlign:'right',fontFamily:'monospace',color:'var(--green)',fontSize:12}}>
                {t.credit_amount>0 ? fmt(t.credit_amount) : '—'}
              </td>
              <td style={{textAlign:'right',fontFamily:'monospace',color:'var(--red)',fontSize:12}}>
                {t.debit_amount>0 ? fmt(t.debit_amount) : '—'}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

/* ── Main Page ───────────────────────────────────── */
export default function BankAccounts() {
  const [accounts, setAccounts] = useState([])
  const [summary,  setSummary]  = useState(null)
  const [modal,    setModal]    = useState(null)
  const [importAcc,setImportAcc]= useState(null)
  const [expanded, setExpanded] = useState(null)
  const [loading,  setLoading]  = useState(true)

  const load = async () => {
    setLoading(true)
    try {
      const [accs, sum] = await Promise.all([bankAccountsAPI.list(), bankAccountsAPI.summary()])
      setAccounts(accs.data); setSummary(sum.data)
    } catch { toast.error('Failed to load') }
    finally { setLoading(false) }
  }

  useEffect(()=>{ load() },[])

  const handleDelete = async (id) => {
    if (!confirm('Delete this account and all its transactions?')) return
    await bankAccountsAPI.delete(id)
    toast.success('Deleted')
    load()
  }

  const emOk = summary?.emergency_adequate
  const emMonths = summary?.emergency_months || 0

  return (
    <div className="page">
      {/* Page Header */}
      <div style={{display:'flex',justifyContent:'space-between',alignItems:'flex-start',marginBottom:24}}>
        <div>
          <h1 style={{fontFamily:'Syne',fontSize:24,fontWeight:700,color:'var(--t1)'}}>Bank Accounts</h1>
          <p style={{color:'var(--t2)',fontSize:13,marginTop:4}}>Upload monthly statements to track spending and balances</p>
        </div>
        <button className="btn btn-primary" onClick={()=>setModal({})}>+ Add Account</button>
      </div>

      {/* Summary Cards */}
      {summary && (
        <div className="grid-4" style={{marginBottom:28}}>
          <div className="stat-card">
            <div className="stat-label">Total Balance</div>
            <div className="stat-value">{fmt(summary.total_balance)}</div>
          </div>
          <div className="stat-card">
            <div className="stat-label">Emergency Fund</div>
            <div className="stat-value" style={{color: emOk?'var(--green)':'var(--red)'}}>{fmt(summary.emergency_balance)}</div>
            <div style={{fontSize:11,color:'var(--t3)',marginTop:4}}>{emMonths.toFixed(1)} months coverage</div>
          </div>
          <div className="stat-card">
            <div className="stat-label">Net Monthly Flow</div>
            <div className="stat-value" style={{color:(summary.net_monthly_flow||0)>=0?'var(--green)':'var(--red)'}}>
              {(summary.net_monthly_flow||0)>=0?'+':''}{fmt(summary.net_monthly_flow)}
            </div>
          </div>
          <div className="stat-card" style={{
            borderColor: emOk ? 'rgba(0,212,170,0.3)' : 'rgba(244,63,94,0.3)',
            background: emOk ? 'rgba(0,212,170,0.06)' : 'rgba(244,63,94,0.06)',
          }}>
            <div style={{fontSize:11,fontWeight:600,textTransform:'uppercase',letterSpacing:'0.06em',
              color:emOk?'var(--green)':'var(--red)',marginBottom:8}}>
              {emOk ? '🛡 Fund Adequate' : '⚠ Fund Low'}
            </div>
            <div style={{fontSize:12,color:'var(--t2)'}}>
              {emOk ? `${emMonths.toFixed(1)} months covered` : `Need ${(6-emMonths).toFixed(1)} more months`}
            </div>
            <div style={{marginTop:10}}>
              <div className="progress-track">
                <div className="progress-fill" style={{
                  width:`${Math.min(100,emMonths/6*100)}%`,
                  background:emOk?'var(--green)':'var(--red)',
                }}/>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Account Grid */}
      {loading ? (
        <div style={{display:'grid',gridTemplateColumns:'repeat(3,1fr)',gap:16}}>
          {[0,1,2].map(i=><div key={i} className="skeleton" style={{height:180,borderRadius:16}}/>)}
        </div>
      ) : accounts.length === 0 ? (
        <div className="card" style={{padding:56,textAlign:'center'}}>
          <div style={{fontSize:44,marginBottom:12}}>🏦</div>
          <div style={{color:'var(--t1)',fontSize:16,fontWeight:600,marginBottom:6}}>No bank accounts yet</div>
          <div style={{color:'var(--t2)',fontSize:13,marginBottom:20}}>Add Jupiter, DBS, and Equitas accounts to track balances</div>
          <button className="btn btn-primary" onClick={()=>setModal({})}>+ Add Account</button>
        </div>
      ) : (
        <div style={{display:'grid',gridTemplateColumns:'repeat(auto-fill,minmax(340px,1fr))',gap:16}}>
          {accounts.map(acc=>(
            <div key={acc.id}>
              <AccountCard acc={acc} onEdit={setModal} onDelete={handleDelete} onImport={setImportAcc}/>
              {/* Expandable transactions */}
              <div style={{marginTop:2}}>
                <button
                  onClick={()=>setExpanded(expanded===acc.id?null:acc.id)}
                  style={{
                    width:'100%',background:'var(--bg1)',border:'1.5px solid var(--bd)',
                    borderRadius:10,padding:'7px 16px',fontSize:12,fontWeight:500,
                    color:'var(--t2)',cursor:'pointer',display:'flex',alignItems:'center',
                    justifyContent:'space-between',
                  }}>
                  <span>Transaction History</span>
                  <span>{expanded===acc.id?'▲':'▼'}</span>
                </button>
                {expanded===acc.id && (
                  <div className="card" style={{marginTop:2,borderRadius:'0 0 12px 12px',overflow:'hidden'}}>
                    <TransactionsPanel accId={acc.id} />
                  </div>
                )}
              </div>
            </div>
          ))}
        </div>
      )}

      {modal    !== null && <AccountModal acc={modal?.id?modal:null} onClose={()=>setModal(null)} onSave={()=>{setModal(null);load()}}/>}
      {importAcc !== null && <ImportModal acc={importAcc} onClose={()=>setImportAcc(null)} onDone={()=>{load()}}/>}
    </div>
  )
}
