import axios from 'axios'
import { downloadBlob } from '../utils/helpers'

const api = axios.create({ baseURL: '/api', timeout: 30000 })

api.interceptors.request.use((config) => {
  const token = localStorage.getItem('auth_token')
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})
api.interceptors.response.use(
  (res) => res,
  (err) => {
    if (err.response?.status === 401) {
      localStorage.removeItem('auth_token')
      window.location.href = '/login'
    }
    return Promise.reject(err)
  }
)
export default api

/* ── Error helpers ─────────────────────────────────────────────── */
const detail = (e) => e?.response?.data?.detail
export const apiErrMsg = (e, fallback = 'Something went wrong') => {
  const d = detail(e)
  if (typeof d === 'string') return d
  return d?.message || fallback
}
const needsPassword = (e) => ['password_required', 'password_incorrect'].includes(detail(e)?.code)

/* Run an import; if the backend reports the file is password-protected,
   prompt the user and retry with the password (up to 3 attempts). */
export const withFilePassword = async (fn) => {
  let password
  for (let attempt = 0; attempt < 4; attempt++) {
    try {
      return await fn(password)
    } catch (e) {
      if (!needsPassword(e)) throw e
      const msg = detail(e)?.code === 'password_incorrect'
        ? '❌ Incorrect password. Try again:'
        : '🔒 This statement is password-protected.\nEnter the file password:'
      password = window.prompt(msg)
      if (!password) throw e
    }
  }
}

const fileForm = (file, password) => {
  const fd = new FormData()
  fd.append('file', file)
  if (password) fd.append('password', password)
  return fd
}
const MP = { headers: { 'Content-Type': 'multipart/form-data' } }

export const authAPI = {
  status: () => api.get('/auth/status'),
  setup:  (pin) => api.post('/auth/setup', { pin }),
  login:  (pin) => api.post('/auth/login', { pin }),
  changePin: (pin) => api.post('/auth/change-pin', { pin }),
}

export const dashboardAPI = {
  overview: () => api.get('/dashboard/overview'),
  history:  () => api.get('/dashboard/net-worth-history'),
  snapshot: () => api.post('/dashboard/snapshot'),
}

export const investmentsAPI = {
  list:    (asset_class) => api.get('/investments/', { params: asset_class ? { asset_class } : {} }),
  summary: () => api.get('/investments/summary'),
  create:  (data) => api.post('/investments/', data),
  update:  (id, data) => api.put(`/investments/${id}`, data),
  delete:  (id) => api.delete(`/investments/${id}`),
  refreshPrices: () => api.post('/investments/refresh-prices'),
  importXLSX: (broker, file, password) =>
    api.post(`/investments/import-xlsx?broker=${broker}`, fileForm(file, password), MP),
}

export const creditCardsAPI = {
  list:   () => api.get('/credit-cards/'),
  create: (data) => api.post('/credit-cards/', data),
  update: (id, data) => api.put(`/credit-cards/${id}`, data),
  delete: (id) => api.delete(`/credit-cards/${id}`),
  transactions:     (cardId, params) => api.get(`/credit-cards/${cardId}/transactions`, { params }),
  addTransaction:   (data) => api.post('/credit-cards/transactions', data),
  deleteTransaction:(id) => api.delete(`/credit-cards/transactions/${id}`),
  spendingSummary:  (params) => api.get('/credit-cards/spending-summary', { params }),
  importStatement:  (cardId, file, password) =>
    api.post(`/credit-cards/${cardId}/import-statement`, fileForm(file, password), MP),
}

export const bankAccountsAPI = {
  list:    () => api.get('/bank-accounts/'),
  summary: () => api.get('/bank-accounts/summary'),
  create:  (data) => api.post('/bank-accounts/', data),
  update:  (id, data) => api.put(`/bank-accounts/${id}`, data),
  delete:  (id) => api.delete(`/bank-accounts/${id}`),
  transactions: (id) => api.get(`/bank-accounts/${id}/transactions`),
  importStatement: (id, file, password) =>
    api.post(`/bank-accounts/${id}/import-statement`, fileForm(file, password), MP),
}

export const suggestionsAPI = { get: () => api.get('/suggestions/') }

export const categoriesAPI = {
  rules:      () => api.get('/categories/rules'),
  saveRules:  (rules) => api.post('/categories/rules/bulk', rules),
  deleteRule: (id) => api.delete(`/categories/rules/${id}`),
}

/* Exports go through axios (not window.open) so the bearer token is sent */
export const exportAPI = {
  excel: async () => {
    const res = await api.get('/export/excel', { responseType: 'blob' })
    downloadBlob(res.data, `wealthos_${new Date().toISOString().slice(0, 10)}.xlsx`)
  },
  backupDB: async () => {
    const res = await api.get('/export/backup-db', { responseType: 'blob' })
    downloadBlob(res.data, `wealthos_backup_${new Date().toISOString().slice(0, 10)}.db`)
  },
}

// CR1: universal auto-import. params: {kind, target_id} to force routing.
export const importAPI = {
  auto: (file, password, params = {}) => {
    const qs = new URLSearchParams(Object.entries(params).filter(([, v]) => v != null)).toString()
    return api.post(`/import/auto${qs ? '?' + qs : ''}`, fileForm(file, password), MP)
  },
}
export const needsTarget = (e) => e?.response?.data?.detail?.code === 'target_required'

export const insightsAPI = {
  spendTrend: () => api.get('/insights/spend-trend'),
  coverage:   () => api.get('/insights/coverage'),
  summary:    () => api.get('/insights/summary'),
  rematch:    () => api.post('/insights/rematch'),
}

export const transactionsAPI = {
  search: (q) => api.get('/transactions/search', { params: { q } }),
  setCategory: (source, id, category, learn = true, pattern = null) =>
    api.put(`/transactions/${source}/${id}/category`, { category, learn, pattern }),
}

export const pdfImportAPI = {
  bankStatement:     (accId, file, password)  => api.post(`/pdf-import/bank/${accId}`, fileForm(file, password), MP),
  creditCard:        (cardId, file, password) => api.post(`/pdf-import/credit-card/${cardId}`, fileForm(file, password), MP),
  creditCardPreview: (file, password)         => api.post('/pdf-import/credit-card-preview', fileForm(file, password), MP),
  alpaca:            (file, password)         => api.post('/pdf-import/investments/alpaca', fileForm(file, password), MP),
  aura:              (file, password)         => api.post('/pdf-import/investments/aura', fileForm(file, password), MP),
}
