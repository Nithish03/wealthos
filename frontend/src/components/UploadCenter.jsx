import { useState, useRef } from 'react'
import { importAPI, withFilePassword, apiErrMsg, needsTarget } from '../api/client'
import CategoryTrainer from './CategoryTrainer'
import toast from 'react-hot-toast'

/* CR1 + CR2: one drop zone for EVERYTHING — bank PDFs, CC PDFs, broker
   XLS/XLSX, CSVs; multiple files at once. The backend detects what each file
   is and where it belongs; when ambiguous, a picker appears inline. */
export default function UploadCenter({ onRefresh }) {
  const [rows, setRows] = useState([])
  const [busy, setBusy] = useState(false)
  const [trainItems, setTrainItems] = useState(null)
  const fileRef = useRef()

  const setRow = (i, patch) => setRows(rs => rs.map((r, j) => j === i ? { ...r, ...patch } : r))

  const importOne = async (i, file, params = {}) => {
    try {
      setRow(i, { status: 'working', msg: 'Importing…' })
      const res = await withFilePassword(pw => importAPI.auto(file, pw, params))
      const d = res.data
      setRow(i, {
        status: 'ok',
        msg: `${d.message}${d.created_target ? ` → created "${d.target}"` : d.target ? ` → ${d.target}` : ''}`,
        uncat: d.uncategorized || [],
      })
      return d
    } catch (e) {
      if (needsTarget(e)) {
        const det = e.response.data.detail
        setRow(i, { status: 'pick', msg: det.message, options: det.options, kind: det.kind, file })
        return null
      }
      setRow(i, { status: 'error', msg: apiErrMsg(e, 'Import failed') })
      return null
    }
  }

  const handleFiles = async (list) => {
    const files = Array.from(list || [])
    if (!files.length) return
    setBusy(true)
    setRows(files.map(f => ({ name: f.name, status: 'pending', msg: 'Queued' })))
    const uncat = new Set()
    for (let i = 0; i < files.length; i++) {
      const d = await importOne(i, files[i])
      d?.uncategorized?.forEach(u => uncat.add(u))
    }
    setBusy(false)
    onRefresh?.()
    if (uncat.size) setTrainItems([...uncat])
  }

  const retryWithTarget = async (i, targetId) => {
    const r = rows[i]
    const d = await importOne(i, r.file, { kind: r.kind, target_id: targetId })
    if (d) {
      onRefresh?.()
      if (d.uncategorized?.length) setTrainItems(d.uncategorized)
    }
  }

  const ICONS = { pending: '⏳', working: '⚙️', ok: '✅', error: '❌', pick: '❓' }

  return (
    <div className="card" style={{padding:16}}>
      <div
        className="drop-zone"
        style={{padding:'18px 16px'}}
        onClick={() => !busy && fileRef.current.click()}
        onDragOver={e => e.preventDefault()}
        onDrop={e => { e.preventDefault(); if (!busy) handleFiles(e.dataTransfer.files) }}
      >
        <input ref={fileRef} type="file" multiple accept=".pdf,.xlsx,.xls,.csv" style={{display:'none'}}
          onChange={e => { handleFiles(e.target.files); e.target.value = '' }} />
        <div style={{fontSize:24,marginBottom:4}}>📥</div>
        <div style={{color:'var(--t1)',fontSize:14,fontWeight:600}}>
          Drop statements here — any bank, card or broker file
        </div>
        <div style={{color:'var(--t3)',fontSize:11,marginTop:4}}>
          Multiple files at once · PDF / XLSX / XLS / CSV · passwords handled · duplicates auto-skipped
        </div>
      </div>

      {rows.length > 0 && (
        <div style={{display:'flex',flexDirection:'column',gap:6,marginTop:12}}>
          {rows.map((r, i) => (
            <div key={i} style={{background:'var(--bg1)',border:'1.5px solid var(--bd)',borderRadius:10,
              padding:'8px 12px',fontSize:12}}>
              <div style={{display:'flex',gap:8,alignItems:'baseline'}}>
                <span>{ICONS[r.status]}</span>
                <span style={{color:'var(--t1)',fontWeight:600,whiteSpace:'nowrap',overflow:'hidden',
                  textOverflow:'ellipsis',maxWidth:180}}>{r.name}</span>
                <span style={{color: r.status === 'error' ? 'var(--red)' : 'var(--t2)',flex:1}}>{r.msg}</span>
              </div>
              {r.status === 'pick' && (
                <div style={{display:'flex',gap:8,marginTop:8,alignItems:'center'}}>
                  <select style={{flex:1}} defaultValue="" onChange={e => e.target.value && retryWithTarget(i, Number(e.target.value))}>
                    <option value="" disabled>Choose {r.kind === 'bank' ? 'account' : 'card'}…</option>
                    {r.options.map(o => <option key={o.id} value={o.id}>{o.name}</option>)}
                  </select>
                </div>
              )}
            </div>
          ))}
        </div>
      )}

      {trainItems && (
        <CategoryTrainer items={trainItems} onClose={() => setTrainItems(null)} onSaved={onRefresh} />
      )}
    </div>
  )
}
