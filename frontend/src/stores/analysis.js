import { defineStore } from 'pinia'
import { getHealth, getCategoryStats } from '../api/index.js'

const RECENT_KEY = 'ecommerce_recent_analyses'
const MAX_RECENT = 5

function loadRecent() {
  try { return JSON.parse(localStorage.getItem(RECENT_KEY) || '[]') }
  catch { return [] }
}

export const useAnalysisStore = defineStore('analysis', {
  state: () => ({
    systemStatus: null,
    recentAnalyses: loadRecent(),
    categoryStats: [],
  }),
  getters: {
    productCount: (state) => {
      if (!state.categoryStats.length) return 0
      return state.categoryStats.reduce((sum, c) => sum + (c.product_count || 0), 0)
    },
  },
  actions: {
    async checkHealth() {
      try {
        const res = await getHealth()
        this.systemStatus = res.data?.status === 'healthy' ? 'ok' : 'error'
      } catch { this.systemStatus = 'offline' }
    },
    async fetchCategoryStats() {
      try {
        const res = await getCategoryStats()
        this.categoryStats = res.data?.categories || []
      } catch { this.categoryStats = [] }
    },
    refreshRecent() {
      this.recentAnalyses = loadRecent()
    },
  },
})
