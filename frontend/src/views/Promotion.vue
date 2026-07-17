<script setup>
import { ref } from 'vue'
import { useAnalysisStore } from '../stores/analysis.js'
const store = useAnalysisStore()
const loading = ref(false); const error = ref('')
async function run() {
  loading.value = true; error.value = ''
  const products = store.selection?.ranking || []
  try { await store.createPromotionPlan(products.slice(0, 5)) }
  catch (e) { error.value = e.response?.data?.detail || e.message }
  finally { loading.value = false }
}
</script>
<template>
  <div>
    <h2 style="font-size:20px;font-weight:700;color:#1a1a2e;margin-bottom:16px">活动策划</h2>
    <div class="card" style="margin-bottom:16px;padding:16px 20px">
      <p style="color:#888;font-size:13px;margin-bottom:12px">基于当前选品结果（需先在选品分析页执行分析），自动生成促销方案</p>
      <button class="btn btn-primary" :disabled="loading" @click="run">{{ loading ? '生成中...' : '生成活动方案' }}</button>
    </div>
    <div v-if="error" style="color:#d32f2f;margin-bottom:16px">{{ error }}</div>
    <div v-if="store.promotion" class="card">
      <pre style="font-size:13px;line-height:1.8;white-space:pre-wrap">{{ store.promotion.for_display }}</pre>
    </div>
  </div>
</template>
