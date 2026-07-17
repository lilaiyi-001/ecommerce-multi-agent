import axios from 'axios'

const TOKEN_KEY = 'ecommerce_token'

// Token 工具函数
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

// 请求拦截器：自动注入 Authorization header
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

// 响应拦截器：401 时清 token，触发登录跳转
api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response && error.response.status === 401) {
      clearToken()
      // 如果不在登录页，跳转到登录页
      if (window.location.pathname !== '/login') {
        window.location.href = '/login'
      }
    }
    return Promise.reject(error)
  }
)

export function recognizeIntent(userMessage, sessionId) {
  return api.post('/intent/recognize', {
    user_message: userMessage,
    session_id: sessionId || 'sess_' + Date.now(),
    turn_number: 1,
  })
}

export function chatWithAgent(userMessage, sessionId) {
  return api.post('/chat', {
    user_message: userMessage,
    session_id: sessionId || 'sess_' + Date.now(),
    turn_number: 1,
  })
}

export function analyzeSelection(category, topN) {
  return api.post('/selection/analyze', { category, top_n: topN || 5 })
}

export function forecastTrend(productIds, category) {
  return api.post('/trend/forecast', { product_ids: productIds || [], category })
}

export function analyzeCompetitor(productId, category) {
  return api.post('/competitor/analyze', {
    target_product_id: productId,
    category: category || "electronics",
  })
}

export function analyzeProfile(category) {
  return api.post('/profile/analyze', { category })
}

export function analyzePricing(productId, product, category) {
  return api.post('/pricing/analyze', {
    product_id: productId,
    product: { ...product, category: category || product.category },
  })
}

export function generateCopy(productId, product, pricingInfo, category) {
  return api.post('/copy/generate', {
    product_id: productId,
    product: { ...product, category: category || product.category },
    pricing_info: pricingInfo || {},
  })
}

export function analyzeInventory(productId, product, category) {
  return api.post('/inventory/analyze', {
    product_id: productId,
    product: { ...product, category: category || product.category },
  })
}

export function createPromotionPlan(products) {
  return api.post('/promotion/plan', { recommended_products: products || [] })
}

export default api
// Add raw GET for health check
export function getHealth() {
  return axios.get('/health')
}
