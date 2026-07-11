import axios from 'axios'

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
  importXLSX: (broker, file) => {
    const fd = new FormData()
    fd.append('file', file)
    return api.post(`/investments/import-xlsx?broker=${broker}`, fd,
      { headers: { 'Content-Type': 'multipart/form-data' } })
  },
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
  importStatement:  (cardId, file) => {
    const fd = new FormData()
    fd.append('file', file)
    return api.post(`/credit-cards/${cardId}/import-statement`, fd,
      { headers: { 'Content-Type': 'multipart/form-data' } })
  },
}

export const bankAccountsAPI = {
  list:    () => api.get('/bank-accounts/'),
  summary: () => api.get('/bank-accounts/summary'),
  create:  (data) => api.post('/bank-accounts/', data),
  update:  (id, data) => api.put(`/bank-accounts/${id}`, data),
  delete:  (id) => api.delete(`/bank-accounts/${id}`),
  transactions: (id) => api.get(`/bank-accounts/${id}/transactions`),
  importStatement: (id, file) => {
    const fd = new FormData()
    fd.append('file', file)
    return api.post(`/bank-accounts/${id}/import-statement`, fd,
      { headers: { 'Content-Type': 'multipart/form-data' } })
  },
}

export const suggestionsAPI = { get: () => api.get('/suggestions/') }

export const exportAPI = {
  excel:    () => window.open('/api/export/excel', '_blank'),
  backupDB: () => window.open('/api/export/backup-db', '_blank'),
}

export const pdfImportAPI = {
  bankStatement:   (accId, file)  => { const fd=new FormData(); fd.append('file',file); return api.post(`/pdf-import/bank/${accId}`, fd, {headers:{'Content-Type':'multipart/form-data'}}) },
  creditCard:      (cardId, file) => { const fd=new FormData(); fd.append('file',file); return api.post(`/pdf-import/credit-card/${cardId}`, fd, {headers:{'Content-Type':'multipart/form-data'}}) },
  creditCardPreview: (file)       => { const fd=new FormData(); fd.append('file',file); return api.post('/pdf-import/credit-card-preview', fd, {headers:{'Content-Type':'multipart/form-data'}}) },
  alpaca:          (file)         => { const fd=new FormData(); fd.append('file',file); return api.post('/pdf-import/investments/alpaca', fd, {headers:{'Content-Type':'multipart/form-data'}}) },
  aura:            (file)         => { const fd=new FormData(); fd.append('file',file); return api.post('/pdf-import/investments/aura', fd, {headers:{'Content-Type':'multipart/form-data'}}) },
}
