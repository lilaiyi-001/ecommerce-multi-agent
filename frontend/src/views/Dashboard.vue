<script setup>
import { ref, onMounted, computed } from 'vue'
import { useRouter } from 'vue-router'
import { useAnalysisStore } from '../stores/analysis.js'

const store = useAnalysisStore()
const router = useRouter()

const categories = ['食品', '服饰', '家居', '数码', '园艺', '宠物用品', '文具', '箱包']

const statCards = computed(() => [
  { label: '系统状态', value: store.systemStatus === 'ok' ? '正常' : store.systemStatus === 'offline' ? '离线' : '异常', color: store.systemStatus === 'ok' ? '#4caf50' : '#f44336' },
  { label: '分析类目', value: store.recentAnalyses.length ? [...new Set(store.recentAnalyses.map(r => r.category))].length : 0, color: '#2196f3' },
  { label: '今日分析', value: store.recentAnalyses.filter(r => {
    const d = new Date(r.time)
    const t = new Date()
    return d.toDateString() === t.toDateString()
  }).length, color: '#ff9800' },
  { label: '商品总数', value: store.productCount, color: '#9c27b0' },
])

function goChat(cat) {
  router.push('/chat')
  setTimeout(() => {
    const input = document.querySelector('textarea')
    if (input) {
      const nativeInputValueSetter = Object.getOwnPropertyDescriptor(window.HTMLTextAreaElement.prototype, 'value').set
      nativeInputValueSetter.call(input, `分析${cat}类目，推荐3个爆款`)
      input.dispatchEvent(new Event('input', { bubbles: true }))
    }
  }, 100)
}

onMounted(() => {
  store.checkHealth()
})
</script>

<template>
  <div>
    <div style="margin-bottom:24px">
      <h2 style="font-size:22px;font-weight:700;color:#1a1a2e">电商选品运营多智能体系统</h2>
      <p style="color:#666;margin-top:6px">基于 10 个专业智能体协作，自动化完成选品分析的完整流程</p>
    </div>

    <!-- Stat Cards -->
    <div class="grid-4" style="margin-bottom:24px">
      <div v-for="card in statCards" :key="card.label" class="card stat-card">
        <div class="card-title">{{ card.label }}</div>
        <div class="stat-value" :style="{ color: card.color }">{{ card.value }}</div>
      </div>
    </div>

    <!-- Recent Analyses -->
    <div class="card" style="margin-bottom:24px">
      <div class="card-title" style="margin-bottom:12px">最近分析记录</div>
      <div v-if="store.recentAnalyses.length === 0" style="text-align:center;padding:20px;color:#888">
        暂无记录，去 <router-link to="/chat" style="color:#2196f3">智能对话</router-link> 开始分析
      </div>
      <div v-else style="display:flex;flex-direction:column;gap:8px">
        <div v-for="(r, i) in store.recentAnalyses" :key="i"
          style="display:flex;align-items:center;gap:12px;padding:8px 12px;background:#f9f9f9;border-radius:6px;font-size:13px">
          <span style="flex:1;color:#333">{{ r.message }}</span>
          <span class="tag tag-info">{{ r.category }}</span>
          <span style="color:#888;font-size:12px">{{ r.completed }}/{{ r.tasks }} 完成</span>
          <span style="color:#aaa;font-size:11px">{{ r.time }}</span>
        </div>
      </div>
    </div>

    <!-- Category Quick Entry -->
    <div class="card">
      <div class="card-title" style="margin-bottom:12px">快捷类目入口</div>
      <div class="grid-4">
        <button v-for="cat in categories" :key="cat" class="cat-btn" @click="goChat(cat)">
          {{ cat }}
        </button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.grid-4 {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 16px;
}
.stat-card {
  text-align: center;
  padding: 20px 16px;
}
.stat-card .stat-value {
  font-size: 28px;
  font-weight: 700;
  margin-top: 8px;
}
.cat-btn {
  background: #f0f4ff;
  border: 1px solid #c5d3f0;
  color: #3f51b5;
  padding: 14px;
  border-radius: 8px;
  font-size: 14px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.2s;
}
.cat-btn:hover {
  background: #e3ecff;
  border-color: #3f51b5;
  transform: translateY(-2px);
}
@media (max-width: 768px) {
  .grid-4 { grid-template-columns: repeat(2, 1fr); }
}
</style>
