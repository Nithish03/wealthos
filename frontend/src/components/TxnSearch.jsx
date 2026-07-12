import { useState } from 'react'
import { transactionsAPI, apiErrMsg } from '../api/client'
import { CategorySelect, TxnBadges } from './CategoryBits'
import toast from 'react-hot-toast'

const fmt = (n) => `₹${Number(n || 0).toLocaleString('en-IN', { maximumFractionDigits: 0 })}`

/* CR11: search every transaction across all accounts & cards; fix categories inline. */
export default function TxnSearch() {
  const [q, setQ] = useState('')
  const [results, setResults] = useState(null)
  const [loading, setLoading] = useState(false)

  const search = async (e) => {
    e?.preventDefault()
    if (q.trim().length < 2) return toast.error('Type at least 2 characters')
    setLoading(true)
    try {
      const res = await transactionsAPI.search(q.trim())
      setResults(res.data)
    } catch (err) { toast.error(apiErrMsg(err, 'Search failed')) }
    finally { setLoading(false) }
  }

  return (
    <div className="card" style={{padding:16}}>
      <form onSubmit={search} style={{display:'flex',gap:8}}>
        <input placeholder='🔍 Search all transactions — merchant or amount (e.g. "zomato", 2400)'
          value={q} onChange={e => setQ(e.target.value)} />
        <button type="submit" className="btn btn-secondary" disabled={loading}>
          {loading ? '…' : 'Search'}
        </button>
        {results && <button type="button" className="btn btn-ghost" onClick={() => { setResults(null); setQ('') }}>✕</button>}
      </form>

      {results && (
        results.length === 0
          ? <div style={{color:'var(--t3)',fontSize:13,padding:'16px 4px'}}>No transactions match "{q}"</div>
          : (
            <div style={{maxHeight:320,overflowY:'auto',marginTop:12}}>
              <table style={{fontSize:12.5}}>
                <thead><tr><th>Date</th><th>Where</th><th>Description</th><th>Amount</th><th>Category</th></tr></thead>
                <tbody>
                  {results.map((t, i) => (
                    <tr key={`${t.source}-${t.id}`}>
                      <td style={{whiteSpace:'nowrap',color:'var(--t3)',fontSize:11}}>
                        {new Date(t.date).toLocaleDateString('en-IN', { day: '2-digit', month: 'short', year: '2-digit' })}
                      </td>
                      <td style={{fontSize:11,color:'var(--t2)',whiteSpace:'nowrap'}}>
                        {t.source === 'cc' ? '💳' : '🏦'} {t.where}
                      </td>
                      <td style={{maxWidth:220}}>
                        <div style={{overflow:'hidden',textOverflow:'ellipsis',whiteSpace:'nowrap'}}>
                          {t.description || '—'}<TxnBadges txn={t} />
                        </div>
                      </td>
                      <td style={{textAlign:'right',fontFamily:'monospace',whiteSpace:'nowrap',
                        color: t.credit > 0 ? 'var(--green)' : 'var(--t1)'}}>
                        {t.credit > 0 ? `+${fmt(t.credit)}` : fmt(t.debit)}
                      </td>
                      <td>
                        <CategorySelect source={t.source} txn={t}
                          onSaved={(cat) => setResults(rs => rs.map(r =>
                            r.source === t.source && r.id === t.id ? { ...r, category: cat } : r))} />
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )
      )}
    </div>
  )
}
