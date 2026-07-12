import { useState } from 'react'
import { categoriesAPI } from '../api/client'
import toast from 'react-hot-toast'

const KNOWN_CATEGORIES = [
  'Food & Dining', 'Groceries', 'Shopping', 'Travel', 'Fuel', 'Entertainment',
  'Healthcare', 'Utilities', 'Education', 'Investment', 'Transfer', 'Salary',
  'ATM/Cash', 'Bill Payment', 'Finance Charges', 'Cashback / Refund', 'EMI',
  'Rent', 'Subscriptions', 'Other',
]

/**
 * Shown after an import when some transactions could not be categorized.
 * The user types (or picks) a category per merchant; saved rules are applied
 * to existing transactions immediately and remembered for every future import.
 */
export default function CategoryTrainer({ items, onClose, onSaved }) {
  const [rows, setRows] = useState(items.map(d => ({ pattern: d, category: '' })))
  const [saving, setSaving] = useState(false)
  const setRow = (i, key, val) => setRows(rs => rs.map((r, j) => j === i ? { ...r, [key]: val } : r))

  const save = async () => {
    const rules = rows
      .map(r => ({ pattern: r.pattern.trim(), category: r.category.trim() }))
      .filter(r => r.pattern && r.category)
    if (!rules.length) return toast.error('Type a category for at least one merchant (or press Skip)')
    setSaving(true)
    try {
      const res = await categoriesAPI.saveRules(rules)
      toast.success(res.data.message || 'Learned!')
      onSaved?.()
      onClose()
    } catch { toast.error('Failed to save category rules') }
    finally { setSaving(false) }
  }

  return (
    <div className="modal-overlay" onClick={e => e.target === e.currentTarget && onClose()}>
      <div className="modal" style={{maxWidth:560}}>
        <h2 style={{fontFamily:'Syne',fontSize:18,fontWeight:700,marginBottom:4,color:'var(--t1)'}}>
          🧠 Teach me these merchants
        </h2>
        <p style={{color:'var(--t2)',fontSize:13,marginBottom:16,lineHeight:1.5}}>
          I couldn't categorize {items.length} merchant{items.length !== 1 ? 's' : ''} from this statement.
          Assign categories once — I'll remember them for every future import
          (and retag matching past transactions too). Leave blank to skip.
        </p>

        <div style={{display:'flex',flexDirection:'column',gap:10,maxHeight:'50vh',overflowY:'auto',paddingRight:4}}>
          {rows.map((row, i) => (
            <div key={i} style={{display:'grid',gridTemplateColumns:'1fr 170px',gap:8,alignItems:'center',
              background:'var(--bg1)',border:'1.5px solid var(--bd)',borderRadius:10,padding:'8px 10px'}}>
              <input
                value={row.pattern}
                title="Any transaction containing this text gets the category"
                onChange={e => setRow(i, 'pattern', e.target.value)}
                style={{fontSize:'12px'}}
              />
              <input
                list="wealthos-known-categories"
                placeholder="Type category…"
                value={row.category}
                onChange={e => setRow(i, 'category', e.target.value)}
                style={{fontSize:'12px'}}
              />
            </div>
          ))}
        </div>
        <datalist id="wealthos-known-categories">
          {KNOWN_CATEGORIES.map(c => <option key={c} value={c} />)}
        </datalist>

        <div style={{fontSize:11,color:'var(--t3)',marginTop:10,lineHeight:1.5}}>
          Tip: shorten the match text to the merchant name (e.g. just <code style={{color:'var(--green)'}}>zomato</code>)
          so it matches all its future transactions.
        </div>

        <div style={{display:'flex',gap:10,marginTop:16}}>
          <button className="btn btn-secondary" style={{flex:1}} onClick={onClose}>Skip for now</button>
          <button className="btn btn-primary" style={{flex:1}} onClick={save} disabled={saving}>
            {saving ? 'Learning…' : '💾 Learn categories'}
          </button>
        </div>
      </div>
    </div>
  )
}
