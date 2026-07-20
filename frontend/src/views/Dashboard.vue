<script setup>
import { ref, onMounted, computed } from 'vue'
import { useRouter } from 'vue-router'
import VChart from 'vue-echarts'
import { use } from 'echarts/core'
import { PieChart } from 'echarts/charts'
import { TitleComponent, TooltipComponent, LegendComponent } from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'
import { useAnalysisStore } from '../stores/analysis.js'

use([PieChart, TitleComponent, TooltipComponent, LegendComponent, CanvasRenderer])

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

const ringOption = computed(() => {
  const data = store.categoryStats.length
    ? store.categoryStats.map(c => ({ name: c.name, value: c.product_count }))
    : categories.map(c => ({ name: c, value: 5 }))
  return {
    tooltip: { trigger: 'item', formatter: '{b}: {c} 件 ({d}%)' },
    legend: { bottom: 0, textStyle: { fontSize: 12 } },
    series: [{
      type: 'pie',
      radius: ['45%', '75%'],
      center: ['50%', '42%'],
      data,
      label: { formatter: '{b}\n{d}%', fontSize: 11 },
      itemStyle: { borderRadius: 4, borderColor: '#fff', borderWidth: 2 },
      emphasis: { label: { fontSize: 16, fontWeight: 'bold' } },
    }],
  }
})

function goReport() {
  router.push('/report')
}

onMounted(() => {
  store.checkHealth()
  store.fetchCategoryStats()
})
</script>

<template>
  <div>
    <div style="margin-bottom:24px">
      <h2 style="font-size:22px;font-weight:700;color:#1a1a2e">电商选品运营多智能体系统</h2>
      <p style="color:#666;margin-top:6px">基于多个专业智能体协作，自动化完成选品分析的完整流程</p>
    </div>

    <div class="grid-4" style="margin-bottom:24px">
      <div v-for="card in statCards" :key="card.label" class="card stat-card">
        <div class="card-title">{{ card.label }}</div>
        <div class="stat-value" :style="{ color: card.color }">{{ card.value }}</div>
      </div>
    </div>

    <div class="grid-2" style="margin-bottom:24px">
      <div class="card">
        <div class="card-title">类目商品分布</div>
        <v-chart :option="ringOption" style="height:320px" autoresize />
      </div>
      <div class="card">
        <div class="card-title" style="margin-bottom:12px">最近分析记录</div>
        <div v-if="store.recentAnalyses.length === 0" style="text-align:center;padding:20px;color:#888">
          暂无记录，去 <router-link to="/report" style="color:#2196f3">生成报告</router-link> 开始分析
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
    </div>

    <div class="card">
      <div class="card-title" style="margin-bottom:12px">快捷入口</div>
      <div style="text-align:center;padding:20px">
        <button class="cat-btn primary" @click="goReport" style="font-size:16px;padding:16px 48px">
          📊 立即生成分析报告
        </button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.grid-2 { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }
.grid-4 { display: grid; grid-template-columns: repeat(4, 1fr); gap: 16px; }
.stat-card { text-align: center; padding: 20px 16px; }
.stat-card .stat-value { font-size: 28px; font-weight: 700; margin-top: 8px; }
.cat-btn.primary {
  background: linear-gradient(135deg, #4fc3f7, #29b6f6);
  border: none;
  color: #fff;
  border-radius: 10px;
  font-weight: 700;
  cursor: pointer;
  transition: all 0.2s;
}
.cat-btn.primary:hover { transform: translateY(-2px); box-shadow: 0 4px 12px rgba(79,195,247,0.4); }
@media (max-width: 768px) {
  .grid-2 { grid-template-columns: 1fr; }
  .grid-4 { grid-template-columns: repeat(2, 1fr); }
}
</style>
