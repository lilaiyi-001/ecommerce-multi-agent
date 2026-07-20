import axios from 'axios'

const TOKEN_KEY = 'ecommerce_token'

export function getToken() {
  return localStorage.getItem(TOKEN_KEY)
}

export function setToken(token) {
  localStorage.setItem(TOKEN_KEY, token)
}

export function clearToken() {
  localStorage.removeItem(TOKEN_KEY)
}

export function isAuthenticated() {
  return !!getToken()
}

const api = axios.create({
  baseURL: '/api/v1',
  timeout: 30000,
  headers: { 'Content-Type': 'application/json' },
})

api.interceptors.request.use(
  (config) => {
    const token = getToken()
    if (token) {
      config.headers.Authorization = `Bearer ${token}`
    }
    return config
  },
  (error) => Promise.reject(error)
)

api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response && error.response.status === 401) {
      clearToken()
      if (window.location.pathname !== '/login') {
        window.location.href = '/login'
      }
    }
    return Promise.reject(error)
  }
)

export function getHealth() {
  return axios.get('/health')
}

export function getCategoryStats() {
  return api.get('/categories')
}

export function getProducts(category = '') {
  const params = category ? { category } : {}
  return api.get('/products', { params })
}

export function generateReport(productIds, activityType, sessionId) {
  return api.post('/reports/generate', {
    product_ids: productIds,
    activity_type: activityType,
    session_id: sessionId || 'sess_' + Date.now(),
  }, { timeout: 120000 })
}

export function getReportHistory(skip = 0, limit = 20) {
  return api.get('/reports/history', { params: { skip, limit } })
}

export function getReportDetail(reportId) {
  return api.get(`/reports/${reportId}`)
}

export function chatFollowup(reportId, userMessage, conversationHistory) {
  return api.post(`/reports/${reportId}/chat`, {
    user_message: userMessage,
    conversation_history: conversationHistory || [],
  })
}

export default api