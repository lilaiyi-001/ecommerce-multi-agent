import { defineStore } from 'pinia'
import * as api from '../api/index.js'

const RECENT_KEY = 'ecommerce_recent_analyses'
const MAX_RECENT = 5

function loadRecent() {
  try { return JSON.parse(localStorage.getItem(RECENT_KEY) || '[]') }
  catch { return [] }
}
function saveRecent(entry) {
  const recent = loadRecent()
  recent.unshift({ ...entry, time: new Date().toLocaleString() })
  if (recent.length > MAX_RECENT) recent.length = MAX_RECENT
  localStorage.setItem(RECENT_KEY, JSON.stringify(recent))
}

export const useAnalysisStore = defineStore('analysis', {
  state: () => ({
    intent: null, selection: null, trend: null, competitor: null,
    profile: null, pricing: null, copy: null, inventory: null, promotion: null,
    loading: false, error: null, systemStatus: null, recentAnalyses: loadRecent(),
  }),
  getters: {
    productCount: (state) => state.selection?.total_products || 0,
  },
  actions: {
    async checkHealth() {
      try {
        const res = await api.getHealth()
        this.systemStatus = res.data?.status === 'healthy' ? 'ok' : 'error'
      } catch { this.systemStatus = 'offline' }
    },
    saveChatResult(userMessage, intent, orch) {
      this.intent = intent
      saveRecent({
        message: userMessage,
        category: intent?.parsed_result?.extracted_params?.category || '?',
        tasks: orch?.task_plan?.tasks?.length || 0,
        completed: orch?.final_report?.completed_tasks || 0,
      })
      this.recentAnalyses = loadRecent()
    },
    async chat(userMessage, sessionId) {
      const res = await api.chatWithAgent(userMessage, sessionId)
      const data = res.data
      this.saveChatResult(userMessage, data.intent_result, data.orchestrator_result)
      return data
    },
    async analyzeSelection(category, topN = 5) {
      const res = await api.analyzeSelection(category, topN)
      this.selection = res.data; return res.data
    },
    async analyzeTrend(productIds, category) {
      const res = await api.forecastTrend(productIds, category)
      this.trend = res.data; return res.data
    },
    async analyzeCompetitor(productId, category) {
      const res = await api.analyzeCompetitor(productId, category)
      this.competitor = res.data; return res.data
    },
    async analyzeProfile(category) {
      const res = await api.analyzeProfile(category)
      this.profile = res.data; return res.data
    },
    async analyzePricing(productId, product, category) {
      const res = await api.analyzePricing(productId, product, category)
      this.pricing = res.data; return res.data
    },
    async generateCopy(productId, product, pricingInfo, category) {
      const res = await api.generateCopy(productId, product, pricingInfo, category)
      this.copy = res.data; return res.data
    },
    async analyzeInventory(productId, product, category) {
      const res = await api.analyzeInventory(productId, product, category)
      this.inventory = res.data; return res.data
    },
    async createPromotionPlan(products) {
      const res = await api.createPromotionPlan(products)
      this.promotion = res.data; return res.data
    },
  },
})
