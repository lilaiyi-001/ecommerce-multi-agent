<script setup>
import { ref } from 'vue'
import { useAnalysisStore } from '../stores/analysis.js'

const store = useAnalysisStore()
const loading = ref(false)
const productId = ref(1)
const category = ref('数码')
const error = ref('')

async function run() {
  loading.value = true; error.value = ''
  try { await store.analyzeCompetitor(productId.value, category.value) }
  catch (e) { error.value = e.response?.data?.detail || e.message }
  finally { loading.value = false }
}
</script>

<template>
  <div>
    <h2 style="font-size:20px;font-weight:700;color:#1a1a2e;margin-bottom:16px">竞品分析</h2>
    <div class="card" style="margin-bottom:16px;display:flex;gap:12px;align-items:center;padding:16px 20px;flex-wrap:wrap">
      <input v-model.number="productId" type="number" placeholder="商品ID" style="padding:8px 12px;border:1px solid #ddd;border-radius:6px;width:100px" />
      <input v-model="category" placeholder="类目" style="padding:8px 12px;border:1px solid #ddd;border-radius:6px;width:120px" />
      <button class="btn btn-primary" :disabled="loading" @click="run">{{ loading ? '分析中...' : '竞品分析' }}</button>
    </div>
    <div v-if="error" style="color:#d32f2f;margin-bottom:16px">{{ error }}</div>
    <div v-if="store.competitor" class="card">
      <div class="card-title">{{ store.competitor.target_product_title }}</div>
      <div style="margin:12px 0;font-size:14px">
        竞争力评分: <b :style="{color:store.competitor.competition_assessment?.overall_score>=60?'#4caf50':'#f44336'}">{{ store.competitor.competition_assessment?.overall_score }}/100</b>
      </div>
      <div style="color:#555;font-size:13px">{{ store.competitor.competition_assessment?.verdict }}</div>
      <div v-if="store.competitor.competitors?.length" style="margin-top:12px">
        <div class="card-title" style="font-size:14px">竞品列表</div>
        <div v-for="c in store.competitor.competitors" :key="c.product_id" style="padding:6px 0;border-bottom:1px solid #f0f0f0;font-size:13px;display:flex;gap:16px">
          <span>{{ c.title?.slice(0,20) }}</span>
          <span style="color:#888">¥{{ c.price }}</span>
          <span style="color:#888">评分{{ c.rating_rate }}</span>
        </div>
      </div>
    </div>
  </div>
</template>
