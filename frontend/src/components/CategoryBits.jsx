import toast from 'react-hot-toast'
import { transactionsAPI } from '../api/client'

export const ALL_CATS = [
  'Food & Dining', 'Groceries', 'Shopping', 'Travel', 'Fuel', 'Entertainment',
  'Healthcare', 'Utilities', 'Education', 'Investment', 'Transfer', 'Salary',
  'ATM/Cash', 'ATM', 'Bill Payment', 'Finance Charges', 'Cashback / Refund',
  'EMI', 'Rent', 'Subscriptions', 'Other',
]

/* Inline category editor: changing it also teaches a rule from the txn
   description so future imports categorize it automatically (CR11). */
export function CategorySelect({ source, txn, onSaved }) {
  const value = txn.category || 'Other'
  const change = async (e) => {
    const category = e.target.value
    try {
      const res = await transactionsAPI.setCategory(source, txn.id, category, true, txn.description)
      toast.success(res.data.message)
      onSaved?.(category)
    } catch { toast.error('Failed to update category') }
  }
  return (
    <select value={ALL_CATS.includes(value) ? value : 'Other'} onChange={change}
      className="cat-select" onClick={e => e.stopPropagation()}>
      {ALL_CATS.map(c => <option key={c} value={c}>{c}</option>)}
    </select>
  )
}

export function TxnBadges({ txn }) {
  return (
    <>
      {txn.is_self_transfer && <span className="tag tag-blue" style={{fontSize:9,marginLeft:4}} title="Matched transfer between your own accounts — excluded from spend">↔ self</span>}
      {txn.is_reimbursement && <span className="tag tag-green" style={{fontSize:9,marginLeft:4}} title="Matched reimbursement — excluded from spend">↩ reimb</span>}
    </>
  )
}
