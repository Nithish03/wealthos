import { useState, useEffect, useRef } from 'react'
import { creditCardsAPI, pdfImportAPI, withFilePassword, apiErrMsg } from '../api/client'
import CategoryTrainer from '../components/CategoryTrainer'
import { AlertTriangle } from 'lucide-react'
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell } from 'recharts'
import toast from 'react-hot-toast'

const CATEGORIES = ['Food & Dining','Groceries','Shopping','Travel','Fuel','Entertainment','Healthcare','Utilities','Education','ATM/Cash','Other']
const CAT_COLORS  = {'Food & Dining':'#f59e0b','Groceries':'#84cc16','Shopping':'#a855f7','Travel':'#3b82f6','Fuel':'#f97316','Entertainment':'#ec4899','Healthcare':'#10b981','Utilities':'#6b7280','Education':'#06b6d4','ATM/Cash':'#94a3b8','Other':'#64748b'}
const fmt = (n) => `₹${Number(n||0).toLocaleString('en-IN',{maximumFractionDigits:0})}`
/* ── Shared field wrapper (top-level to prevent focus loss) ── */
const FieldRow = ({ label, children }) => (
  <div style={{display:'flex',flexDirection:'column',gap:5}}>
    <label style={{fontSize:12,color:'var(--t2)',fontWeight:500}}>{label}</label>
    {children}
  </div>
)

/* ─── Card Form Modal ─────────────────────────────── */
/* ─── Card Form Modal (supports pre-fill from parsed statement) ─────── */
function CardModal({ card, prefill, onClose, onSave }) {
  const [form, setForm] = useState(card || prefill || {
    name:'', bank:'', credit_limit:'', current_balance:'0',
    statement_day:'5', due_day:'25', minimum_due:'0', total_due:'0',
    available_credit:'0', card_number_masked:''
  })
  const [saving, setSaving] = useState(false)
  const isPrefilled = !!prefill && !card?.id

  const submit = async (e) => {
    e.preventDefault(); setSaving(true)
    try {
      const d = {
        ...form,
        credit_limit:    parseFloat(form.credit_limit)||0,
        current_balance: parseFloat(form.total_due||form.current_balance)||0,
        total_due:       parseFloat(form.total_due)||0,
        minimum_due:     parseFloat(form.minimum_due)||0,
        available_credit: parseFloat(form.available_credit)||0,
        statement_day:   parseInt(form.statement_day)||5,
        due_day:         parseInt(form.due_day)||25,
      }
      if (card?.id) {
        await creditCardsAPI.update(card.id, d)
        toast.success('Updated!')
        onSave(card.id)
      } else {
        const res = await creditCardsAPI.create(d)
        toast.success('Card added!')
        onSave(res.data?.id)
      }
    } catch(e) { toast.error(e.response?.data?.detail||'Failed') }
    finally { setSaving(false) }
  }

  return (
    <div className="modal-overlay" onClick={e=>e.target===e.currentTarget&&onClose()}>
      <div className="modal" style={{maxWidth:500}}>
        <h2 style={{fontFamily:'Syne',fontSize:18,fontWeight:700,marginBottom:4,color:'var(--t1)'}}>
          {card?.id?'Edit':'Add'} Credit Card
        </h2>
        {isPrefilled && (
          <div style={{background:'rgba(0,212,170,0.08)',border:'1px solid rgba(0,212,170,0.25)',
            borderRadius:10,padding:'10px 14px',marginBottom:16,fontSize:12,color:'var(--green)'}}>
            ✅ Auto-filled from your statement — review and confirm
          </div>
        )}
        <form onSubmit={submit} style={{display:'flex',flexDirection:'column',gap:14}}>
          <div style={{display:'grid',gridTemplateColumns:'1fr 1fr',gap:12}}>
            <FieldRow label="Card Name"><input placeholder="Swiggy HDFC" value={form.name} onChange={e=>setForm(prev => ({...prev,name:e.target.value}))} required/></FieldRow>
            <FieldRow label="Bank"><input placeholder="HDFC Bank" value={form.bank} onChange={e=>setForm(prev => ({...prev,bank:e.target.value}))} required/></FieldRow>
          </div>
          {form.card_number_masked && (
            <FieldRow label="Card Number"><input value={form.card_number_masked} readOnly style={{opacity:0.7}}/></FieldRow>
          )}
          <div style={{display:'grid',gridTemplateColumns:'1fr 1fr',gap:12}}>
            <FieldRow label="Credit Limit (₹)"><input type="number" step="0.01" placeholder="0" value={form.credit_limit} onChange={e=>setForm(prev => ({...prev,credit_limit:e.target.value}))}/></FieldRow>
            <FieldRow label="Available Credit (₹)"><input type="number" step="0.01" placeholder="0" value={form.available_credit} onChange={e=>setForm(prev => ({...prev,available_credit:e.target.value}))}/></FieldRow>
          </div>
          <div style={{display:'grid',gridTemplateColumns:'1fr 1fr',gap:12}}>
            <FieldRow label="Total Due (₹)"><input type="number" step="0.01" placeholder="0" value={form.total_due} onChange={e=>setForm(prev => ({...prev,total_due:e.target.value}))}/></FieldRow>
            <FieldRow label="Minimum Due (₹)"><input type="number" step="0.01" placeholder="0" value={form.minimum_due} onChange={e=>setForm(prev => ({...prev,minimum_due:e.target.value}))}/></FieldRow>
          </div>
          <div style={{display:'grid',gridTemplateColumns:'1fr 1fr',gap:12}}>
            <FieldRow label="Statement Day"><input type="number" min="1" max="31" value={form.statement_day} onChange={e=>setForm(prev => ({...prev,statement_day:e.target.value}))}/></FieldRow>
            <FieldRow label="Due Day"><input type="number" min="1" max="31" value={form.due_day} onChange={e=>setForm(prev => ({...prev,due_day:e.target.value}))}/></FieldRow>
          </div>
          <div style={{display:'flex',gap:10,marginTop:4}}>
            <button type="button" className="btn btn-secondary" style={{flex:1}} onClick={onClose}>Cancel</button>
            <button type="submit" className="btn btn-primary" style={{flex:1}} disabled={saving}>{saving?'Saving...':'Save Card'}</button>
          </div>
        </form>
      </div>
    </div>
  )
}

/* ─── Add from Statement (parse-first flow) ─────────────────────────── */
function AddFromStatementModal({ onClose, onCardCreated }) {
  const [step, setStep] = useState('upload')   // upload → preview → confirm
  const [file, setFile] = useState(null)
  const [loading, setLoading] = useState(false)
  const [parsed, setParsed] = useState(null)
  const [pdfPassword, setPdfPassword] = useState(null)
  const fileRef = useRef()

  const handleParse = async () => {
    if (!file) return toast.error('Select a PDF file')
    setLoading(true)
    try {
      let usedPassword = null
      const res = await withFilePassword(pw => {
        usedPassword = pw
        return pdfImportAPI.creditCardPreview(file, pw)
      })
      setPdfPassword(usedPassword)
      setParsed(res.data)
      setStep('preview')
    } catch(e) {
      toast.error(apiErrMsg(e, 'Could not parse PDF — try manual entry'))
    } finally { setLoading(false) }
  }

  if (step === 'upload') return (
    <div className="modal-overlay" onClick={e=>e.target===e.currentTarget&&onClose()}>
      <div className="modal" style={{maxWidth:460}}>
        <h2 style={{fontFamily:'Syne',fontSize:18,fontWeight:700,marginBottom:4,color:'var(--t1)'}}>
          Add Card from Statement
        </h2>
        <p style={{color:'var(--t2)',fontSize:13,marginBottom:20}}>
          Upload your credit card statement PDF to auto-fill card details
        </p>
        <div className="drop-zone" onClick={()=>fileRef.current.click()}
          style={file?{borderColor:'var(--green)',background:'rgba(0,212,170,0.05)'}:{}}>
          <input ref={fileRef} type="file" accept=".pdf" style={{display:'none'}}
            onChange={e=>setFile(e.target.files[0])}/>
          {file ? (
            <>
              <div style={{fontSize:28,marginBottom:6}}>📄</div>
              <div style={{color:'var(--green)',fontWeight:600,fontSize:14}}>{file.name}</div>
              <div style={{color:'var(--t3)',fontSize:12,marginTop:3}}>{(file.size/1024).toFixed(1)} KB</div>
            </>
          ) : (
            <>
              <div style={{fontSize:32,marginBottom:8}}>📂</div>
              <div style={{color:'var(--t2)',fontSize:13,fontWeight:500}}>Click to upload CC statement PDF</div>
              <div style={{color:'var(--t3)',fontSize:11,marginTop:5}}>Supports HDFC · Axis · CSB/Jupiter</div>
            </>
          )}
        </div>
        <div style={{display:'flex',gap:10,marginTop:16}}>
          <button className="btn btn-secondary" style={{flex:1}} onClick={onClose}>Cancel</button>
          <button className="btn btn-primary" style={{flex:1}} onClick={handleParse} disabled={!file||loading}>
            {loading ? '⏳ Parsing...' : '🔍 Parse Statement'}
          </button>
        </div>
      </div>
    </div>
  )

  if (step === 'preview' && parsed) {
    const fmtV = (n) => n > 0 ? `₹${Number(n).toLocaleString('en-IN',{maximumFractionDigits:0})}` : '—'
    return (
      <CardModal
        prefill={{
          name: `${parsed.bank} Card`,
          bank: parsed.bank,
          card_number_masked: parsed.card_number || '',
          credit_limit: String(parsed.credit_limit || ''),
          available_credit: String(parsed.available_credit || ''),
          total_due: String(parsed.total_due || ''),
          minimum_due: String(parsed.minimum_due || ''),
          current_balance: String(parsed.total_due || '0'),
          statement_day: '1',
          due_day: parsed.payment_due_date ? new Date(parsed.payment_due_date).getDate() : '25',
        }}
        _parsedFile={file}
        _parsed={parsed}
        onClose={onClose}
        onSave={async (newCardId) => {
          onCardCreated(newCardId, file, pdfPassword)
          onClose()
        }}
      />
    )
  }

  return null
}

/* ─── Manual Transaction Modal ────────────────────── */
function TxnModal({ cardId, onClose, onSave }) {
  const now = new Date(); now.setMinutes(now.getMinutes()-now.getTimezoneOffset())
  const [form, setForm] = useState({ amount:'', category:'Food & Dining', description:'', transaction_date: now.toISOString().slice(0,16) })
  const submit = async (e) => {
    e.preventDefault()
    try {
      await creditCardsAPI.addTransaction({
        card_id: cardId, amount: parseFloat(form.amount),
        category: form.category, description: form.description,
        transaction_date: new Date(form.transaction_date).toISOString()
      })
      toast.success('Transaction added!')
      onSave()
    } catch(e) { toast.error(e.response?.data?.detail||'Failed') }
  }
  return (
    <div className="modal-overlay" onClick={e=>e.target===e.currentTarget&&onClose()}>
      <div className="modal" style={{maxWidth:400}}>
        <h2 style={{fontFamily:'Syne',fontSize:17,fontWeight:700,marginBottom:18,color:'var(--t1)'}}>Add Transaction</h2>
        <form onSubmit={submit} style={{display:'flex',flexDirection:'column',gap:14}}>
          <FieldRow label="Amount (₹)"><input type="number" step="0.01" placeholder="500" value={form.amount} onChange={e=>setForm(prev => ({...prev,amount:e.target.value}))} required/></FieldRow>
          <FieldRow label="Category">
            <select value={form.category} onChange={e=>setForm(prev => ({...prev,category:e.target.value}))}>
              {CATEGORIES.map(c=><option key={c}>{c}</option>)}
            </select>
          </FieldRow>
          <FieldRow label="Description"><input placeholder="Zomato order" value={form.description} onChange={e=>setForm(prev => ({...prev,description:e.target.value}))}/></FieldRow>
          <FieldRow label="Date"><input type="datetime-local" value={form.transaction_date} onChange={e=>setForm(prev => ({...prev,transaction_date:e.target.value}))}/></FieldRow>
          <div style={{display:'flex',gap:10}}>
            <button type="button" className="btn btn-secondary" style={{flex:1}} onClick={onClose}>Cancel</button>
            <button type="submit" className="btn btn-primary" style={{flex:1}}>Add</button>
          </div>
        </form>
      </div>
    </div>
  )
}

/* ─── Statement Import Modal ─────────────────────── */
function ImportModal({ card, onClose, onDone }) {
  const [file, setFile] = useState(null)
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState(null)
  const [trainItems, setTrainItems] = useState(null)
  const fileRef = useRef()

  const handleImport = async () => {
    if (!file) return toast.error('Select a file')
    setLoading(true)
    try {
      const isPDF = file.name.toLowerCase().endsWith('.pdf')
      const res = await withFilePassword(pw => isPDF
        ? pdfImportAPI.creditCard(card.id, file, pw)
        : creditCardsAPI.importStatement(card.id, file, pw))
      setResult(res.data)
      toast.success(res.data.message)
      if (res.data.uncategorized?.length) setTrainItems(res.data.uncategorized)
      onDone()  // auto-refresh parent
    } catch(e) {
      toast.error(apiErrMsg(e, 'Import failed — check the file format'))
    } finally { setLoading(false) }
  }

  return (
    <div className="modal-overlay" onClick={e=>e.target===e.currentTarget&&onClose()}>
      <div className="modal" style={{maxWidth:520}}>
        <h2 style={{fontFamily:'Syne',fontSize:18,fontWeight:700,marginBottom:4}}>Import Statement</h2>
        <p style={{color:'var(--t2)',fontSize:13,marginBottom:20}}>
          {card.name} — {card.bank}
        </p>

        <div style={{background:'var(--bg1)',border:'1px solid var(--border)',borderRadius:10,padding:'12px 16px',marginBottom:16}}>
          <div style={{fontSize:12,color:'var(--t2)',fontWeight:600,marginBottom:6}}>📋 How to get your statement:</div>
          <div style={{fontSize:12,color:'var(--t3)',lineHeight:1.7}}>
            • <strong>HDFC:</strong> NetBanking → Cards → Credit Card → Statement → Download Excel<br/>
            • <strong>Axis:</strong> NetBanking → Cards → Statement Download → Excel/CSV<br/>
            • <strong>CSB:</strong> NetBanking → Credit Cards → Statement → Download<br/>
            • Any XLSX or CSV with Date + Description + Amount columns will work
          </div>
        </div>

        <div style={{display:'grid',gap:14}}>
          <div
            onClick={()=>fileRef.current.click()}
            style={{
              border:`2px dashed ${file?'var(--green)':'var(--border)'}`,
              borderRadius:10, padding:24, textAlign:'center', cursor:'pointer',
              background: file?'rgba(0,212,170,0.05)':'var(--bg1)', transition:'all .2s'
            }}
          >
            <input ref={fileRef} type="file" accept=".pdf,.xlsx,.xls,.csv" style={{display:'none'}}
              onChange={e=>{setFile(e.target.files[0]);setResult(null)}}/>
            {file ? (
              <>
                <div style={{color:'var(--green)',fontWeight:600,fontSize:14}}>✓ {file.name}</div>
                <div style={{color:'var(--t3)',fontSize:12,marginTop:4}}>{(file.size/1024).toFixed(1)} KB</div>
              </>
            ) : (
              <>
                <div style={{fontSize:28,marginBottom:8}}>📂</div>
                <div style={{color:'var(--t2)',fontSize:13}}>Click to upload XLSX or CSV statement</div>
              </>
            )}
          </div>

          {result && (
            <div style={{background:'rgba(0,212,170,0.07)',border:'1px solid rgba(0,212,170,0.2)',borderRadius:12,padding:16}}>
              <div style={{color:'var(--green)',fontWeight:700,marginBottom:10}}>✅ {result.message}</div>
              {result.category_breakdown && (
                <>
                  <div style={{fontSize:12,color:'var(--t2)',marginBottom:8,fontWeight:600}}>Category Breakdown:</div>
                  {Object.entries(result.category_breakdown).map(([cat,amt])=>(
                    <div key={cat} style={{display:'flex',justifyContent:'space-between',fontSize:12,marginBottom:4}}>
                      <span style={{color:'var(--t2)'}}>{cat}</span>
                      <span style={{fontFamily:'monospace',color:'var(--t1)'}}>{fmt(amt)}</span>
                    </div>
                  ))}
                </>
              )}
              {result.sample && (
                <>
                  <div style={{fontSize:12,color:'var(--t2)',margin:'10px 0 6px',fontWeight:600}}>Sample transactions:</div>
                  {result.sample.map((t,i)=>(
                    <div key={i} style={{fontSize:11,color:'var(--t3)',marginBottom:3}}>
                      {t.date} · {t.desc} · <span style={{color:'var(--t2)'}}>{fmt(t.amount)}</span> · <span style={{color:CAT_COLORS[t.category]||'#64748b'}}>{t.category}</span>
                    </div>
                  ))}
                </>
              )}
            </div>
          )}

          <div style={{display:'flex',gap:10}}>
            <button className="btn btn-secondary" style={{flex:1}} onClick={()=>{onDone();onClose()}}>
              {result?'Done':'Cancel'}
            </button>
            {!result && (
              <button className="btn btn-primary" style={{flex:1}} onClick={handleImport} disabled={!file||loading}>
                {loading?'⏳ Parsing...':'⬆️ Import Statement'}
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

/* ─── Single Card Row ─────────────────────────────── */
function CardPanel({ card, onEdit, onDelete, onReload }) {
  const [open, setOpen] = useState(false)
  const [txns, setTxns] = useState([])
  const [txnModal, setTxnModal] = useState(false)
  const [importModal, setImportModal] = useState(false)
  const util = card.utilization_percent || 0

  const loadTxns = async () => {
    const res = await creditCardsAPI.transactions(card.id)
    setTxns(res.data)
  }
  useEffect(()=>{ if(open) loadTxns() },[open])

  const deleteTxn = async (id) => {
    await creditCardsAPI.deleteTransaction(id)
    toast.success('Deleted')
    loadTxns(); onReload()
  }

  const utilColor = util>=80?'var(--red)':util>=40?'var(--gold)':'var(--green)'

  return (
    <div className="card" style={{overflow:'hidden',marginBottom:12}}>
      {/* Card Header */}
      <div style={{padding:16}}>
        <div style={{display:'flex',justifyContent:'space-between',alignItems:'flex-start',marginBottom:14}}>
          <div>
            <div style={{display:'flex',alignItems:'center',gap:8,marginBottom:3}}>
              <span style={{fontWeight:600,fontSize:15}}>{card.name}</span>
              {card.alert_80 && <span className="tag-red">⚠ High Util</span>}
            </div>
            <div style={{fontSize:12,color:'var(--t2)'}}>{card.bank} · Statement: {card.statement_day}th · Due: {card.due_day}th</div>
          </div>
          <div style={{display:'flex',gap:6,alignItems:'center'}}>
            <button style={{background:'none',border:'none',cursor:'pointer',padding:5,color:'var(--t2)',fontSize:12}}
              onClick={()=>setImportModal(true)} title="Import statement">📥 Import</button>
            <button style={{background:'none',border:'none',cursor:'pointer',padding:5,color:'var(--t2)'}}
              onClick={()=>onEdit(card)} title="Edit">✏️</button>
            <button style={{background:'none',border:'none',cursor:'pointer',padding:5,color:'var(--red)'}}
              onClick={()=>onDelete(card.id)} title="Delete">🗑</button>
            <button style={{background:'none',border:'none',cursor:'pointer',padding:5,color:'var(--t2)',fontSize:18,lineHeight:1}}
              onClick={()=>setOpen(!open)}>{open?'▲':'▼'}</button>
          </div>
        </div>

        {/* Stats row */}
        <div className="grid-4" style={{gap:12,marginBottom:12}}>
          {[
            {label:'Total Due',    value:fmt(card.total_due),        color:'var(--red)'},
            {label:'Limit',        value:fmt(card.credit_limit),     color:'var(--t2)'},
            {label:'Minimum Due',  value:fmt(card.minimum_due),      color:'var(--gold)'},
            {label:'Available',    value:fmt(card.available_credit || Math.max(0, card.credit_limit - card.total_due)), color:'var(--green)'},
          ].map((s,i)=>(
            <div key={i}>
              <div style={{fontSize:11,color:'var(--t3)',marginBottom:3}}>{s.label}</div>
              <div style={{fontFamily:'monospace',fontWeight:600,fontSize:14,color:s.color}}>{s.value}</div>
            </div>
          ))}
        </div>

        {/* Utilization bar */}
        <div>
          <div style={{display:'flex',justifyContent:'space-between',fontSize:11,marginBottom:4}}>
            <span style={{color:'var(--t3)'}}>Utilization</span>
            <span style={{color:utilColor,fontWeight:600}}>{util.toFixed(1)}%</span>
          </div>
          <div className="progress-bar">
            <div className="progress-fill" style={{width:`${Math.min(100,util)}%`,background:utilColor}}/>
          </div>
        </div>
      </div>

      {/* Transactions */}
      {open && (
        <div style={{borderTop:'1px solid var(--border)'}}>
          <div style={{display:'flex',justifyContent:'space-between',alignItems:'center',padding:'10px 16px',background:'rgba(13,19,32,0.6)'}}>
            <span style={{fontSize:12,fontWeight:600,color:'var(--t2)',textTransform:'uppercase',letterSpacing:'0.06em'}}>
              Transactions ({txns.length})
            </span>
            <button className="btn btn-primary" style={{padding:'5px 12px',fontSize:12}}
              onClick={()=>setTxnModal(true)}>+ Add</button>
          </div>

          {txns.length === 0 ? (
            <div style={{textAlign:'center',padding:'24px 16px',color:'var(--t3)',fontSize:13}}>
              No transactions yet. Import a statement or add manually.
            </div>
          ) : (
            <div style={{maxHeight:280,overflowY:'auto'}}>
              <table style={{width:'100%',fontSize:13}}>
                <thead>
                  <tr>
                    <th>Date</th>
                    <th>Description</th>
                    <th>Category</th>
                    <th style={{textAlign:'right'}}>Amount</th>
                    <th/>
                  </tr>
                </thead>
                <tbody>
                  {txns.map(t=>(
                    <tr key={t.id}>
                      <td style={{color:'var(--t3)',fontSize:12,whiteSpace:'nowrap'}}>
                        {new Date(t.transaction_date).toLocaleDateString('en-IN',{day:'2-digit',month:'short'})}
                      </td>
                      <td style={{maxWidth:200}}>
                        <div style={{overflow:'hidden',textOverflow:'ellipsis',whiteSpace:'nowrap',fontSize:13}}>{t.description||'—'}</div>
                      </td>
                      <td>
                        <span style={{
                          display:'inline-block',padding:'2px 8px',borderRadius:20,fontSize:11,fontWeight:600,
                          background:`${CAT_COLORS[t.category]||'#64748b'}22`,
                          color:CAT_COLORS[t.category]||'#64748b',
                        }}>{t.category}</span>
                      </td>
                      <td style={{textAlign:'right',fontFamily:'monospace',fontWeight:600}}>{fmt(t.amount)}</td>
                      <td>
                        <button style={{background:'none',border:'none',cursor:'pointer',color:'var(--red)',padding:4,fontSize:12}}
                          onClick={()=>deleteTxn(t.id)}>✕</button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {txnModal   && <TxnModal cardId={card.id} onClose={()=>setTxnModal(false)} onSave={()=>{setTxnModal(false);loadTxns();onReload()}}/>}
      {importModal && <ImportModal card={card} onClose={()=>setImportModal(false)} onDone={()=>{loadTxns();onReload()}}/>}
    </div>
  )
}

/* ─── Main Page ───────────────────────────────────── */
export default function CreditCards() {
  const [cards, setCards] = useState([])
  const [spending, setSpending] = useState(null)
  const [modal, setModal] = useState(null)
  const [fromStatement, setFromStatement] = useState(false)
  const [trainItems, setTrainItems] = useState(null)
  const [loading, setLoading] = useState(true)

  const load = async () => {
    setLoading(true)
    try {
      const [c, s] = await Promise.all([creditCardsAPI.list(), creditCardsAPI.spendingSummary()])
      setCards(c.data); setSpending(s.data)
    } catch { toast.error('Failed to load') }
    finally { setLoading(false) }
  }

  useEffect(()=>{ load() },[])

  const handleDelete = async (id) => {
    if (!confirm('Delete card and all its transactions?')) return
    await creditCardsAPI.delete(id)
    toast.success('Card deleted')
    load()
  }

  const catData = Object.entries(spending?.by_category||{})
    .map(([name,value])=>({name,value}))
    .sort((a,b)=>b.value-a.value)

  return (
    <div className="page">
      <div style={{display:'flex',alignItems:'flex-start',justifyContent:'space-between',marginBottom:24}}>
        <div>
          <h1 style={{fontFamily:'Syne',fontSize:24,fontWeight:700}}>Credit Cards</h1>
          <p style={{color:'var(--t2)',fontSize:13,marginTop:4}}>Track spending. Import bank statements directly.</p>
        </div>
        <div style={{display:'flex',gap:8}}>
          <button className="btn btn-secondary" style={{display:'flex',alignItems:'center',gap:6}}
            onClick={()=>setFromStatement(true)}>
            📄 Add from Statement
          </button>
          <button className="btn btn-primary" style={{display:'flex',alignItems:'center',gap:6}}
            onClick={()=>setModal({})}>
            + Add Card
          </button>
        </div>
      </div>

      {/* Alerts */}
      {spending?.alerts?.length > 0 && (
        <div style={{display:'flex',flexDirection:'column',gap:8,marginBottom:20}}>
          {spending.alerts.map((a,i)=>(
            <div key={i} className={`alert alert-${a.type==='danger'?'danger':'warn'}`}>
              <AlertTriangle size={15}/>{a.message}
            </div>
          ))}
        </div>
      )}

      {/* Summary row */}
      {spending && (
        <div className="grid-3" style={{marginBottom:24}}>
          <div className="stat-card">
            <div style={{fontSize:11,fontWeight:600,color:'var(--t2)',textTransform:'uppercase',letterSpacing:'0.06em',marginBottom:6}}>This Month's Spend</div>
            <div style={{fontFamily:'monospace',fontSize:22,fontWeight:700}}>{fmt(spending.total_spend)}</div>
          </div>
          <div className="stat-card">
            <div style={{fontSize:11,fontWeight:600,color:'var(--t2)',textTransform:'uppercase',letterSpacing:'0.06em',marginBottom:6}}>% of Salary</div>
            <div style={{fontFamily:'monospace',fontSize:22,fontWeight:700,color:spending.salary_percent>=40?'var(--red)':'var(--green)'}}>
              {spending.salary_percent?.toFixed(1)}%
            </div>
            <div style={{marginTop:8}}>
              <div className="progress-bar">
                <div className="progress-fill" style={{
                  width:`${Math.min(100,spending.salary_percent)}%`,
                  background:spending.salary_percent>=80?'var(--red)':spending.salary_percent>=40?'var(--gold)':'var(--green)'
                }}/>
              </div>
            </div>
          </div>
          <div className="card" style={{padding:16}}>
            <div style={{fontSize:11,fontWeight:600,color:'var(--t2)',textTransform:'uppercase',letterSpacing:'0.06em',marginBottom:10}}>Spend by Category</div>
            {catData.length > 0 ? (
              <ResponsiveContainer width="100%" height={70}>
                <BarChart data={catData} layout="vertical" margin={{left:0,right:0,top:0,bottom:0}}>
                  <XAxis type="number" hide/>
                  <YAxis type="category" dataKey="name" width={95} tick={{fill:'#7a8aaa',fontSize:10}} tickLine={false} axisLine={false}/>
                  <Tooltip formatter={v=>fmt(v)} contentStyle={{background:'#141927',border:'1px solid #1e2a40',borderRadius:8,fontSize:11}}/>
                  <Bar dataKey="value" radius={[0,4,4,0]}>
                    {catData.map((e,i)=><Cell key={i} fill={CAT_COLORS[e.name]||'#64748b'}/>)}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            ) : <div style={{color:'var(--t3)',fontSize:12,textAlign:'center',paddingTop:20}}>No transactions this month</div>}
          </div>
        </div>
      )}

      {/* Cards */}
      {loading ? (
        <div style={{color:'var(--t3)',textAlign:'center',padding:40}}>Loading...</div>
      ) : cards.length === 0 ? (
        <div className="card" style={{padding:48,textAlign:'center'}}>
          <div style={{fontSize:40,marginBottom:12}}>💳</div>
          <div style={{color:'var(--t2)',fontSize:15,fontWeight:500,marginBottom:6}}>No credit cards added yet</div>
          <div style={{color:'var(--t3)',fontSize:13,marginBottom:20}}>Add your 4 cards — CSB, Swiggy HDFC, Axis Neo, Axis MyZone</div>
          <button className="btn btn-primary" onClick={()=>setModal({})}>+ Add Card</button>
        </div>
      ) : (
        cards.map(card=>(
          <CardPanel key={card.id} card={card}
            onEdit={c=>setModal(c)} onDelete={handleDelete} onReload={load}/>
        ))
      )}

      {modal !== null && (
        <CardModal card={modal?.id?modal:null} onClose={()=>setModal(null)} onSave={()=>{setModal(null);load()}}/>
      )}
      {fromStatement && (
        <AddFromStatementModal
          onClose={()=>setFromStatement(false)}
          onCardCreated={(newCardId, file, pdfPassword) => {
            load()
            // Also import transactions into the new card
            if (newCardId && file) {
              pdfImportAPI.creditCard(newCardId, file, pdfPassword)
                .then((res)=>{
                  toast.success('Transactions imported!')
                  if (res.data.uncategorized?.length) setTrainItems(res.data.uncategorized)
                  load()
                })
                .catch(()=>{})
            }
          }}
        />
      )}
      {trainItems && (
        <CategoryTrainer items={trainItems} onClose={()=>setTrainItems(null)} onSaved={load} />
      )}
    </div>
  )
}
