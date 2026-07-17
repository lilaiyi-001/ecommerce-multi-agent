<script setup>
import { ref } from 'vue'
import { useAnalysisStore } from '../stores/analysis.js'
const store = useAnalysisStore()
const loading = ref(false); const productId = ref(1); const category = ref('数码'); const error = ref('')
async function run() {
  loading.value = true; error.value = ''
  const p = store.selection?.ranking?.find(r => r.product_id === productId.value)
  try { await store.generateCopy(productId.value, p || { title: '商品'+productId.value, price: 99 }, store.pricing, category.value) }
  catch (e) { error.value = e.response?.data?.detail || e.message }
  finally { loading.value = false }
}
</script>
<template>
  <div>
    <h2 style="font-size:20px;font-weight:700;color:#1a1a2e;margin-bottom:16px">营销文案</h2>
    <div class="card" style="margin-bottom:16px;display:flex;gap:12px;align-items:center;padding:16px 20px;flex-wrap:wrap">
      <input v-model.number="productId" type="number" placeholder="商品ID" style="padding:8px 12px;border:1px solid #ddd;border-radius:6px;width:100px" />
      <input v-model="category" placeholder="类目" style="padding:8px 12px;border:1px solid #ddd;border-radius:6px;width:120px" />
      <button class="btn btn-primary" :disabled="loading" @click="run">{{ loading ? '生成中...' : '生成文案' }}</button>
    </div>
    <div v-if="error" style="color:#d32f2f;margin-bottom:16px">{{ error }}</div>
    <div v-if="store.copy" class="card">
      <pre style="font-size:13px;line-height:1.8;white-space:pre-wrap">{{ store.copy.for_display }}</pre>
    </div>
  </div>
</template>
