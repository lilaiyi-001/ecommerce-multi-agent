<script setup>
import { ref, computed } from 'vue'
import VChart from 'vue-echarts'
import { use } from 'echarts/core'
import { BarChart, PieChart } from 'echarts/charts'
import { TitleComponent, TooltipComponent, GridComponent, LegendComponent } from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'
import { useAnalysisStore } from '../stores/analysis.js'

use([BarChart, PieChart, TitleComponent, TooltipComponent, GridComponent, LegendComponent, CanvasRenderer])

const store = useAnalysisStore()
const loading = ref(false)
const category = ref('数码')
const topN = ref(10)
const error = ref('')

async function runAnalysis() {
  loading.value = true; error.value = ''
  try { await store.analyzeSelection(category.value, topN.value) }
  catch (e) { error.value = e.response?.data?.detail || e.message }
  finally { loading.value = false }
}

const barOption = computed(() => {
  const ranking = store.selection?.ranking || []
  return {
    tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
    grid: { left: '3%', right: '10%', bottom: '3%', containLabel: true },
    xAxis: { type: 'value', name: '爆款指数' },
    yAxis: { type: 'category', data: ranking.map(r => r.title?.slice(0, 12)).reverse(), inverse: true },
    series: [{
      type: 'bar', data: ranking.map(r => r.explosive_index).reverse(),
      itemStyle: { color: '#4fc3f7', borderRadius: [0, 4, 4, 0] },
      label: { show: true, position: 'right', fontSize: 12 },
    }],
  }
})

const pieOption = computed(() => {
  const bands = store.selection?.price_distribution?.bands || []
  return {
    tooltip: { trigger: 'item' },
    legend: { bottom: 0 },
    series: [{
      type: 'pie', radius: ['40%', '70%'], center: ['50%', '45%'],
      data: bands.map(b => ({ name: `${b.range}元`, value: b.count })),
      label: { formatter: '{b}\n{d}%' },
    }],
  }
})
</script>

<template>
  <div>
    <h2 style="font-size:20px;font-weight:700;color:#1a1a2e;margin-bottom:16px">选品分析</h2>
    <div class="card" style="margin-bottom:16px;display:flex;gap:12px;align-items:center;padding:16px 20px;flex-wrap:wrap">
      <input v-model="category" placeholder="类目，如数码" style="padding:8px 12px;border:1px solid #ddd;border-radius:6px;width:120px" />
      <input v-model.number="topN" type="number" min="1" max="50" style="padding:8px 12px;border:1px solid #ddd;border-radius:6px;width:80px" />
      <button class="btn btn-primary" :disabled="loading" @click="runAnalysis">{{ loading ? '分析中...' : '开始分析' }}</button>
    </div>

    <div v-if="error" style="color:#d32f2f;margin-bottom:16px">{{ error }}</div>

    <div v-if="store.selection">
      <div class="grid-3" style="margin-bottom:16px">
        <div class="card"><div class="card-title">商品总数</div><div class="stat-value">{{ store.selection.total_products }}</div></div>
        <div class="card" v-if="store.selection.price_distribution">
          <div class="card-title">价格区间</div>
          <div class="stat-value">¥{{ store.selection.price_distribution.min }} - ¥{{ store.selection.price_distribution.max }}</div>
          <div class="stat-label">中位数: ¥{{ store.selection.price_distribution.median }}</div>
        </div>
        <div class="card"><div class="card-title">推荐TOP</div><div class="stat-value">{{ store.selection.ranking?.length || 0 }}</div></div>
      </div>

      <!-- Charts -->
      <div class="grid-2" style="margin-bottom:16px">
        <div class="card">
          <div class="card-title">爆款指数排行</div>
          <v-chart :option="barOption" style="height:400px" autoresize />
        </div>
        <div class="card">
          <div class="card-title">价格带分布</div>
          <v-chart v-if="pieOption.series[0].data.length" :option="pieOption" style="height:400px" autoresize />
          <div v-else style="text-align:center;padding:40px;color:#888">暂无价格分布数据</div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.grid-2 { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }
@media (max-width: 768px) { .grid-2 { grid-template-columns: 1fr; } }
</style>
