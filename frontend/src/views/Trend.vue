<script setup>
import { ref, computed } from 'vue'
import VChart from 'vue-echarts'
import { use } from 'echarts/core'
import { LineChart } from 'echarts/charts'
import { TitleComponent, TooltipComponent, GridComponent, LegendComponent } from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'
import { useAnalysisStore } from '../stores/analysis.js'

use([LineChart, TitleComponent, TooltipComponent, GridComponent, LegendComponent, CanvasRenderer])

const store = useAnalysisStore()
const loading = ref(false)
const category = ref('数码')
const topN = ref(5)
const error = ref('')
const result = ref(null)

async function runAnalysis() {
  loading.value = true; error.value = ''
  try {
    const sel = await store.analyzeSelection(category.value, topN.value)
    const ids = (sel.ranking || []).map(r => r.product_id).slice(0, 5)
    result.value = await store.analyzeTrend(ids, category.value)
  } catch (e) { error.value = e.response?.data?.detail || e.message }
  finally { loading.value = false }
}

const lineOption = computed(() => {
  const forecasts = result.value?.forecasts || []
  if (!forecasts.length) return {}
  const days = forecasts[0]?.forecast_7d?.daily?.map(d => `第${d.day}天`) || []
  return {
    tooltip: { trigger: 'axis' },
    legend: { data: forecasts.map(f => f.title?.slice(0, 10)), bottom: 0 },
    grid: { left: '3%', right: '4%', bottom: '12%', containLabel: true },
    xAxis: { type: 'category', data: days, boundaryGap: false },
    yAxis: { type: 'value', name: '预测销量(件)' },
    series: forecasts.map((f, i) => ({
      name: f.title?.slice(0, 10),
      type: 'line',
      data: (f.forecast_7d?.daily || []).map(d => d.value),
      smooth: true,
      symbol: 'circle',
      symbolSize: 6,
    })),
  }
})
</script>

<template>
  <div>
    <h2 style="font-size:20px;font-weight:700;color:#1a1a2e;margin-bottom:16px">趋势预测</h2>
    <div class="card" style="margin-bottom:16px;display:flex;gap:12px;align-items:center;padding:16px 20px;flex-wrap:wrap">
      <input v-model="category" placeholder="类目" style="padding:8px 12px;border:1px solid #ddd;border-radius:6px;width:120px" />
      <input v-model.number="topN" type="number" min="1" max="20" style="padding:8px 12px;border:1px solid #ddd;border-radius:6px;width:80px" />
      <button class="btn btn-primary" :disabled="loading" @click="runAnalysis">{{ loading ? '预测中...' : '开始预测' }}</button>
    </div>

    <div v-if="error" style="color:#d32f2f;margin-bottom:16px">{{ error }}</div>

    <div v-if="result" class="card">
      <div class="card-title">7天销量预测</div>
      <v-chart v-if="lineOption.series" :option="lineOption" style="height:400px" autoresize />
      <div v-for="f in result.forecasts" :key="f.product_id" style="padding:8px 12px;border-bottom:1px solid #f0f0f0;font-size:13px">
        <span style="font-weight:600">{{ f.title?.slice(0,20) }}</span>
        <span style="margin-left:12px;color:#888">历史日均{{ f.historical_avg }}件</span>
        <span :style="{marginLeft:12,color:f.trend_direction==='上升'?'#4caf50':f.trend_direction==='下降'?'#f44336':'#888'}">{{ f.trend_direction }}</span>
        <span style="margin-left:12px">7日均{{ f.forecast_7d?.avg_daily }} | 30天共{{ f.forecast_30d_total }}</span>
      </div>
    </div>
  </div>
</template>
