import { useState, useEffect, useRef } from 'react'
import { investmentsAPI, pdfImportAPI } from '../api/client'
import { PieChart, Pie, Cell, Tooltip, ResponsiveContainer } from 'recharts'
import toast from 'react-hot-toast'

const ASSET_CLASSES = [
  { value:'indian_stocks',  label:'Indian Stocks',       icon:'📈', broker:'groww_stocks' },
  { value:'mutual_funds',   label:'Mutual Funds',        icon:'🏦', broker:'groww_mf'     },
  { value:'us_stocks',      label:'US Stocks',           icon:'🇺🇸', broker:'indmoney'     },
  { value:'crypto',         label:'Crypto',              icon:'🪙', broker:'coinswitch'   },
  { value:'gold_etf',       label:'Gold ETF',            icon:'🥇', broker:'groww_stocks' },
  { value:'silver_etf',     label:'Silver ETF',          icon:'🥈', broker:'groww_stocks' },
  { value:'sgb',            label:'Sovereign Gold Bond', icon:'🏛', broker:'groww_stocks' },
  { value:'digital_gold',   label:'Digital Gold',        icon:'✨', broker:null           },
  { value:'digital_silver', label:'Digital Silver',      icon:'💎', broker:null           },
]
const PDF_BROKERS = {
  alpaca: { label:'Alpaca — US Stocks (PDF)', tip:'Download Monthly Statement PDF from alpaca.markets' },
  aura:   { label:'Aura — Digital Gold/Silver (PDF)', tip:'Download Statement PDF from Aura app' },
}
const BROKER_INFO = {
  groww_stocks: { label:'Groww — Stocks', file:'Stocks_Holdings_Statement_*.xlsx',     tip:'Groww → Portfolio → Stocks → Download Statement' },
  groww_mf:     { label:'Groww — MF',     file:'Mutual_Funds_*.xlsx',                  tip:'Groww → Portfolio → Mutual Funds → Download Statement' },
  indmoney:     { label:'INDMoney — US',  file:'*.xlsx or *.csv',                      tip:'INDMoney → Portfolio → US Stocks → Export' },
  coinswitch:   { label:'CoinSwitch',     file:'*.xlsx or *.csv',                      tip:'CoinSwitch → Portfolio → Export' },
}
const COLORS = ['#00d4aa','#3b82f6','#a855f7','#f59e0b','#fbbf24','#f97316','#10b981','#ec4899','#94a3b8']
const fmt = (n) => `₹${Number(n||0).toLocaleString('en-IN',{maximumFractionDigits:0})}`
const acLabel = (v) => ASSET_CLASSES.find(a=>a.value===v)?.label || v
const acIcon  = (v) => ASSET_CLASSES.find(a=>a.value===v)?.icon  || '📊'

/* ── Field wrapper ───────────────────────────────── */
const Field = ({label, children}) => (
  <div style={{display:'flex',flexDirection:'column',gap:5}}>
    <label>{label}</label>
    {children}
  </div>
)

/* ── Add/Edit Modal ──────────────────────────────── */
function InvestmentModal({ inv, onClose, onSave }) {
  const [form, setForm] = useState(inv || {
    name:'', asset_class:'indian_stocks', platform:'Groww',
    invested_amount:'', current_value:'', units:'', symbol:'', notes:''
  })
  const [saving, setSaving] = useState(false)

  const submit = async (e) => {
    e.preventDefault(); setSaving(true)
    try {
      const data = {
        ...form,
        invested_amount: parseFloat(form.invested_amount)||0,
        current_value:   parseFloat(form.current_value)||0,
        units:           parseFloat(form.units)||0,
      }
      if (inv?.id) await investmentsAPI.update(inv.id, data)
      else         await investmentsAPI.create(data)
      toast.success(inv?.id ? 'Investment updated!' : 'Investment added!')
      onSave()
    } catch(e) { toast.error(e.response?.data?.detail||'Failed') }
    finally { setSaving(false) }
  }

  const selAC = ASSET_CLASSES.find(a=>a.value===form.asset_class)

  return (
    <div className="modal-overlay" onClick={e=>e.target===e.currentTarget&&onClose()}>
      <div className="modal" style={{maxWidth:500}}>
        <h2 style={{fontFamily:'Syne',fontSize:18,fontWeight:700,marginBottom:20,color:'var(--t1)'}}>
          {inv?.id ? 'Edit' : 'Add'} Investment
        </h2>
        <form onSubmit={submit} style={{display:'flex',flexDirection:'column',gap:14}}>
          <Field label="Asset Class">
            <select value={form.asset_class} onChange={e=>{
              const ac = ASSET_CLASSES.find(a=>a.value===e.target.value)
              setForm(prev => ({...prev, asset_class:e.target.value, platform: ac?.value==='us_stocks'?'INDMoney':ac?.value==='crypto'?'CoinSwitch':'Groww'}))
            }}>
              {ASSET_CLASSES.map(a=><option key={a.value} value={a.value}>{a.icon} {a.label}</option>)}
            </select>
          </Field>
          <div style={{display:'grid',gridTemplateColumns:'1fr 1fr',gap:12}}>
            <Field label="Name / Scheme">
              <input placeholder="e.g. Reliance Industries" value={form.name}
                onChange={e=>setForm(prev => ({...prev,name:e.target.value}))} required />
            </Field>
            <Field label="Platform">
              <input value={form.platform} onChange={e=>setForm(prev => ({...prev,platform:e.target.value}))} />
            </Field>
          </div>
          <div style={{display:'grid',gridTemplateColumns:'1fr 1fr',gap:12}}>
            <Field label="Invested Amount (₹)">
              <input type="number" step="0.01" placeholder="0" value={form.invested_amount}
                onChange={e=>setForm(prev => ({...prev,invested_amount:e.target.value}))} />
            </Field>
            <Field label="Current Value (₹)">
              <input type="number" step="0.01" placeholder="0" value={form.current_value}
                onChange={e=>setForm(prev => ({...prev,current_value:e.target.value}))} />
            </Field>
          </div>
          <div style={{display:'grid',gridTemplateColumns:'1fr 1fr',gap:12}}>
            <Field label="Units / Qty">
              <input type="number" step="0.001" placeholder="0" value={form.units}
                onChange={e=>setForm(prev => ({...prev,units:e.target.value}))} />
            </Field>
            <Field label={<span>Yahoo Symbol <span style={{color:'var(--t3)',fontSize:10,textTransform:'none',letterSpacing:0}}>(for live prices)</span></span>}>
              <input placeholder="e.g. RELIANCE.NS or AAPL" value={form.symbol}
                onChange={e=>setForm(prev => ({...prev,symbol:e.target.value}))} />
            </Field>
          </div>
          <Field label="Notes">
            <textarea rows={2} style={{resize:'none'}} value={form.notes}
              onChange={e=>setForm(prev => ({...prev,notes:e.target.value}))} />
          </Field>
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

/* ── Import Modal ────────────────────────────────── */
function ImportModal({ onClose, onDone }) {
  const [broker, setBroker] = useState('groww_stocks')
  const [file,   setFile]   = useState(null)
  const [loading,setLoading]= useState(false)
  const [result, setResult] = useState(null)
  const fileRef = useRef()

  const info = BROKER_INFO[broker] || {}

  const handleImport = async () => {
    if (!file) return toast.error('Select a file first')
    setLoading(true)
    try {
      const res = await investmentsAPI.importXLSX(broker, file)
      setResult(res.data)
      toast.success(res.data.message)
      onDone()   // auto-refresh parent list
    } catch(e) {
      toast.error(e.response?.data?.detail || 'Import failed')
    } finally { setLoading(false) }
  }

  return (
    <div className="modal-overlay" onClick={e=>e.target===e.currentTarget&&onClose()}>
      <div className="modal" style={{maxWidth:500}}>
        <h2 style={{fontFamily:'Syne',fontSize:18,fontWeight:700,marginBottom:4,color:'var(--t1)'}}>Import Portfolio</h2>
        <p style={{color:'var(--t2)',fontSize:13,marginBottom:20}}>Import directly from your broker XLSX export</p>

        <div style={{display:'flex',flexDirection:'column',gap:14}}>
          <Field label="Broker / File Type">
            <select value={broker} onChange={e=>{setBroker(e.target.value);setFile(null);setResult(null)}}>
              {Object.entries(BROKER_INFO).map(([k,v])=><option key={k} value={k}>{v.label}</option>)}
            </select>
          </Field>

          <div style={{background:'var(--bg1)',border:'1.5px solid var(--bd)',borderRadius:10,padding:'10px 14px'}}>
            <div style={{fontSize:12,color:'var(--t2)',marginBottom:3}}>
              📁 Expected: <code style={{color:'var(--green)',fontSize:11}}>{info.file}</code>
            </div>
            <div style={{fontSize:12,color:'var(--t3)'}}>{info.tip}</div>
          </div>

          <div className="drop-zone" onClick={()=>fileRef.current.click()} style={file?{borderColor:'var(--green)',background:'rgba(0,212,170,0.04)'}:{}}>
            <input ref={fileRef} type="file" accept=".xlsx,.xls,.csv" style={{display:'none'}}
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
                <div style={{color:'var(--t2)',fontSize:13}}>Click to choose file</div>
                <div style={{color:'var(--t3)',fontSize:11,marginTop:4}}>XLSX, XLS, or CSV</div>
              </>
            )}
          </div>

          {result && (
            <div style={{background:'rgba(0,212,170,0.07)',border:'1.5px solid rgba(0,212,170,0.2)',borderRadius:12,padding:14}}>
              <div style={{color:'var(--green)',fontWeight:700,marginBottom:6}}>✅ {result.message}</div>
              <div style={{fontSize:12,color:'var(--t2)'}}>
                Imported: <strong style={{color:'var(--t1)'}}>{result.imported}</strong>
                {result.skipped>0 && <span> · Skipped: {result.skipped}</span>}
              </div>
            </div>
          )}

          <div style={{display:'flex',gap:10}}>
            <button className="btn btn-secondary" style={{flex:1}} onClick={onClose}>
              {result ? 'Close' : 'Cancel'}
            </button>
            {!result && (
              <button className="btn btn-primary" style={{flex:1}} onClick={handleImport} disabled={!file||loading}>
                {loading ? '⏳ Importing...' : '⬆️ Import'}
              </button>
            )}
            {result && (
              <button className="btn btn-secondary" style={{flex:1}} onClick={()=>{setFile(null);setResult(null)}}>
                Import Another
              </button>
            )}
          </div>
        </div>

        <div style={{marginTop:8,borderTop:'1px solid var(--bd)',paddingTop:12}}>
          <div style={{fontSize:12,color:'var(--t3)',marginBottom:8}}>📄 Also import from PDF:</div>
          <div style={{display:'flex',gap:8,flexWrap:'wrap'}}>
            {Object.entries(PDF_BROKERS).map(([k,v])=>(
              <label key={k} style={{flex:1,minWidth:180,cursor:'pointer'}}>
                <input type="file" accept=".pdf" style={{display:'none'}} onChange={async e=>{
                  const f=e.target.files[0]; if(!f) return
                  try {
                    const res = await (k==='alpaca' ? pdfImportAPI.alpaca(f) : pdfImportAPI.aura(f))
                    toast.success(res.data.message); onDone()
                  } catch(err) { toast.error(err.response?.data?.detail||'Import failed') }
                  e.target.value=''
                }}/>
                <div style={{background:'var(--bg1)',border:'1.5px solid var(--bd)',borderRadius:10,
                  padding:'8px 12px',fontSize:12,color:'var(--t2)',textAlign:'center',
                  transition:'border-color .15s'}}
                  onMouseEnter={e=>e.currentTarget.style.borderColor='var(--green)'}
                  onMouseLeave={e=>e.currentTarget.style.borderColor='var(--bd)'}>
                  ⬆️ {v.label}
                </div>
              </label>
            ))}
          </div>
        </div>
      </div>
    </div>
  )
}

/* ── Main Page ───────────────────────────────────── */
export default function Investments() {
  const [investments, setInvestments] = useState([])
  const [summary,     setSummary]     = useState(null)
  const [loading,     setLoading]     = useState(true)
  const [modal,       setModal]       = useState(null)
  const [showImport,  setShowImport]  = useState(false)
  const [filter,      setFilter]      = useState('all')
  const [refreshing,  setRefreshing]  = useState(false)

  const load = async () => {
    setLoading(true)
    try {
      const [inv, sum] = await Promise.all([investmentsAPI.list(), investmentsAPI.summary()])
      setInvestments(inv.data); setSummary(sum.data)
    } catch { toast.error('Failed to load investments') }
    finally { setLoading(false) }
  }

  useEffect(()=>{ load() },[])

  const handleDelete = async (id) => {
    if (!confirm('Delete this investment?')) return
    await investmentsAPI.delete(id)
    toast.success('Deleted')
    load()
  }

  const handleRefresh = async () => {
    setRefreshing(true)
    try {
      const res = await investmentsAPI.refreshPrices()
      const d = res.data
      if (d.updated > 0) { toast.success(`Updated ${d.updated} prices via Yahoo Finance`); load() }
      else toast.error('No prices updated — set Yahoo symbols on investments first')
    } catch { toast.error('Price refresh failed') }
    finally { setRefreshing(false) }
  }

  const filtered = filter === 'all' ? investments : investments.filter(i=>i.asset_class===filter)
  const activeClasses = [...new Set(investments.map(i=>i.asset_class))]

  return (
    <div style={{padding:32,minHeight:'100vh'}}>
      {/* Header */}
      <div style={{display:'flex',justifyContent:'space-between',alignItems:'flex-start',marginBottom:24,flexWrap:'wrap',gap:12}}>
        <div>
          <h1 style={{fontFamily:'Syne',fontSize:24,fontWeight:700,color:'var(--t1)'}}>Investment Portfolio</h1>
          <p style={{color:'var(--t2)',fontSize:13,marginTop:4}}>
            {investments.length > 0 ? `${investments.length} holdings across ${activeClasses.length} categories` : 'Import from Groww XLSX or add manually'}
          </p>
        </div>
        <div style={{display:'flex',gap:8,flexWrap:'wrap'}}>
          <button className="btn btn-secondary" onClick={handleRefresh} disabled={refreshing}>
            ⚡ {refreshing ? 'Updating...' : 'Live Prices'}
          </button>
          <button className="btn btn-secondary" onClick={()=>setShowImport(true)}>
            ⬆️ Import XLSX
          </button>
          <button className="btn btn-primary" onClick={()=>setModal({})}>
            + Add Manual
          </button>
        </div>
      </div>

      {/* Info banner */}
      <div style={{background:'rgba(59,130,246,0.07)',border:'1.5px solid rgba(59,130,246,0.18)',borderRadius:12,padding:'10px 16px',marginBottom:20,fontSize:12,color:'var(--blue)',lineHeight:1.6}}>
        💡 <strong>Live Prices:</strong> Set a Yahoo Finance symbol on any investment (e.g. <code>RELIANCE.NS</code>, <code>NIFTYBEES.NS</code>, <code>AAPL</code>) then click Live Prices to auto-update.
        Groww stock imports auto-fill known symbols.
      </div>

      {/* Summary stats */}
      {summary && (
        <div style={{display:'grid',gridTemplateColumns:'repeat(4,1fr)',gap:16,marginBottom:24}}>
          {[
            { label:'Total Invested',  value:fmt(summary.total_invested) },
            { label:'Current Value',   value:fmt(summary.total_current) },
            { label:'Total P&L',       value:`${summary.total_pnl>=0?'+':''}${fmt(summary.total_pnl)}`,    color:summary.total_pnl>=0?'var(--green)':'var(--red)' },
            { label:'Overall Returns', value:`${summary.pnl_percent>=0?'+':''}${Number(summary.pnl_percent||0).toFixed(2)}%`, color:summary.pnl_percent>=0?'var(--green)':'var(--red)' },
          ].map((s,i)=>(
            <div key={i} className="stat-card">
              <div className="stat-label">{s.label}</div>
              <div className="stat-value" style={s.color?{color:s.color}:{}}>{s.value}</div>
            </div>
          ))}
        </div>
      )}

      {/* Content area */}
      <div style={{display:'grid',gridTemplateColumns:'1fr 220px',gap:16,alignItems:'start'}}>
        <div>
          {/* Filter pills */}
          <div style={{display:'flex',gap:6,flexWrap:'wrap',marginBottom:14}}>
            {[{value:'all',label:'All',icon:''},...ASSET_CLASSES].map(ac=>(
              <button key={ac.value}
                className={`filter-pill${filter===ac.value?' active':''}`}
                onClick={()=>setFilter(ac.value)}>
                {ac.icon} {ac.label}
              </button>
            ))}
          </div>

          {/* Table */}
          <div className="card" style={{overflow:'hidden'}}>
            {loading ? (
              <div style={{padding:40,textAlign:'center',color:'var(--t3)'}}>Loading...</div>
            ) : filtered.length === 0 ? (
              <div style={{padding:52,textAlign:'center'}}>
                <div style={{fontSize:40,marginBottom:12}}>📊</div>
                <div style={{color:'var(--t1)',fontSize:15,fontWeight:600,marginBottom:6}}>
                  {filter==='all' ? 'No investments yet' : `No ${acLabel(filter)} holdings`}
                </div>
                <div style={{color:'var(--t2)',fontSize:13,marginBottom:20}}>
                  {filter==='all' ? 'Click "Import XLSX" to import from Groww, or add manually' : 'Switch filter to All or import from Groww'}
                </div>
                {filter==='all' && <button className="btn btn-primary" onClick={()=>setShowImport(true)}>⬆️ Import XLSX</button>}
              </div>
            ) : (
              <div style={{overflowX:'auto'}}>
                <table>
                  <thead>
                    <tr>
                      <th>Name</th>
                      <th>Type</th>
                      <th style={{textAlign:'right'}}>Invested</th>
                      <th style={{textAlign:'right'}}>Current</th>
                      <th style={{textAlign:'right'}}>P&L</th>
                      <th style={{textAlign:'right'}}>Return %</th>
                      <th style={{textAlign:'right'}}>Updated</th>
                      <th style={{width:60}}></th>
                    </tr>
                  </thead>
                  <tbody>
                    {filtered.map(inv=>(
                      <tr key={inv.id} className="fade-in">
                        <td>
                          <div style={{fontWeight:500,color:'var(--t1)'}}>{inv.name}</div>
                          {inv.symbol && <div style={{fontSize:11,color:'var(--t3)',fontFamily:'monospace'}}>{inv.symbol}</div>}
                          {inv.notes  && <div style={{fontSize:10,color:'var(--t3)'}}>{inv.notes.substring(0,45)}{inv.notes.length>45?'…':''}</div>}
                        </td>
                        <td style={{fontSize:12,color:'var(--t2)',whiteSpace:'nowrap'}}>
                          {acIcon(inv.asset_class)} {acLabel(inv.asset_class)}
                        </td>
                        <td style={{textAlign:'right',fontFamily:'monospace',color:'var(--t2)'}}>{fmt(inv.invested_amount)}</td>
                        <td style={{textAlign:'right',fontFamily:'monospace',fontWeight:600,color:'var(--t1)'}}>{fmt(inv.current_value)}</td>
                        <td style={{textAlign:'right',fontFamily:'monospace',fontWeight:600,color:inv.pnl>=0?'var(--green)':'var(--red)'}}>
                          {inv.pnl>=0?'+':''}{fmt(inv.pnl)}
                        </td>
                        <td style={{textAlign:'right',fontFamily:'monospace',fontSize:13,color:inv.pnl_percent>=0?'var(--green)':'var(--red)',whiteSpace:'nowrap'}}>
                          {inv.pnl_percent>=0?'▲':'▼'} {Math.abs(Number(inv.pnl_percent||0)).toFixed(2)}%
                        </td>
                        <td style={{textAlign:'right',fontSize:11,color:'var(--t3)',whiteSpace:'nowrap'}}>
                          {inv.last_updated ? new Date(inv.last_updated).toLocaleDateString('en-IN',{day:'2-digit',month:'short',year:'2-digit'}) : '—'}
                        </td>
                        <td>
                          <div style={{display:'flex',gap:2,justifyContent:'flex-end'}}>
                            <button className="btn btn-ghost" style={{padding:'4px 7px'}} onClick={()=>setModal(inv)}>✏️</button>
                            <button className="btn btn-ghost" style={{padding:'4px 7px',color:'var(--red)'}} onClick={()=>handleDelete(inv.id)}>🗑</button>
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </div>

        {/* Allocation pie */}
        <div className="card" style={{padding:16}}>
          <div style={{fontSize:11,fontWeight:600,color:'var(--t2)',textTransform:'uppercase',letterSpacing:'0.06em',marginBottom:12}}>Allocation</div>
          {summary?.allocation?.length > 0 ? (
            <>
              <ResponsiveContainer width="100%" height={150}>
                <PieChart>
                  <Pie data={summary.allocation} dataKey="current" innerRadius={40} outerRadius={65} paddingAngle={2}>
                    {summary.allocation.map((_,i)=><Cell key={i} fill={COLORS[i%COLORS.length]}/>)}
                  </Pie>
                  <Tooltip
                    formatter={v=>fmt(v)}
                    contentStyle={{background:'#141927',border:'1px solid #1e2d42',borderRadius:10,fontSize:12}}
                  />
                </PieChart>
              </ResponsiveContainer>
              <div style={{display:'flex',flexDirection:'column',gap:5,marginTop:6}}>
                {summary.allocation.map((a,i)=>(
                  <div key={i} style={{display:'flex',alignItems:'center',justifyContent:'space-between',fontSize:12}}>
                    <div style={{display:'flex',alignItems:'center',gap:6}}>
                      <div style={{width:8,height:8,borderRadius:'50%',background:COLORS[i%COLORS.length],flexShrink:0}}/>
                      <span style={{color:'var(--t2)'}}>{acLabel(a.asset_class)}</span>
                    </div>
                    <span style={{fontFamily:'monospace',color:'var(--t1)',fontSize:11}}>{Number(a.percent||0).toFixed(1)}%</span>
                  </div>
                ))}
              </div>
            </>
          ) : (
            <div style={{height:150,display:'flex',alignItems:'center',justifyContent:'center',color:'var(--t3)',fontSize:13,textAlign:'center',lineHeight:1.6}}>
              Import or add<br/>investments to<br/>see allocation
            </div>
          )}
        </div>
      </div>

      {modal !== null && (
        <InvestmentModal inv={modal?.id?modal:null} onClose={()=>setModal(null)} onSave={()=>{setModal(null);load()}} />
      )}
      {showImport && (
        <ImportModal onClose={()=>setShowImport(false)} onDone={()=>{ load(); setShowImport(false) }} />
      )}
    </div>
  )
}
