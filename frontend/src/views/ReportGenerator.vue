<script setup>
import { ref, computed, onMounted, watch, nextTick } from 'vue'
import { getProducts, generateReport, getReportHistory, getReportDetail, chatFollowup } from '../api/index.js'

// === Session ID（持久化） ===
const SESSION_KEY = 'ecommerce_session_id'
function getSessionId() {
  let sid = localStorage.getItem(SESSION_KEY)
  if (!sid) {
    sid = 'sess_' + Date.now() + '_' + Math.random().toString(36).slice(2, 8)
    localStorage.setItem(SESSION_KEY, sid)
  }
  return sid
}

// === 聊天历史持久化 ===
function getChatKey(reportId) { return 'chat_history_' + reportId }
function loadChatHistory(reportId) {
  try { return JSON.parse(localStorage.getItem(getChatKey(reportId)) || '[]') }
  catch { return [] }
}
function saveChatHistory(reportId, history) {
  try { localStorage.setItem(getChatKey(reportId), JSON.stringify(history)) }
  catch { /* quota exceeded, ignore */ }
}

// === 状态 ===
const products = ref([])
const selectedIds = ref([])
const activityType = ref('daily')
const categoryFilter = ref('')
const searchQuery = ref('')
const loading = ref(false)
const generating = ref(false)
const currentReport = ref(null)
const historyReports = ref([])
const viewingReportId = ref(null)
const viewingReport = ref(null)
const error = ref('')

// 聊天状态
const chatMessages = ref([])
const chatInput = ref('')
const chatLoading = ref(false)
const chatContainer = ref(null)

const ACTIVITY_OPTIONS = [
  { value: 'double11', label: '双11大促' },
  { value: '618', label: '618大促' },
  { value: 'new_product', label: '新品发布' },
  { value: 'clearance', label: '清仓促销' },
  { value: 'daily', label: '日常促销' },
]

const CATEGORIES = ['', '食品', '服饰', '家居', '数码', '园艺', '宠物用品', '文具', '箱包']

// === 计算属性 ===
const filteredProducts = computed(() => {
  let list = products.value
  if (categoryFilter.value) list = list.filter(p => p.category === categoryFilter.value)
  if (searchQuery.value) {
    const q = searchQuery.value.toLowerCase()
    list = list.filter(p => p.title.toLowerCase().includes(q) || String(p.product_id).includes(q))
  }
  return list
})

const canGenerate = computed(() => selectedIds.value.length >= 1 && !generating.value)

// === 方法 ===
async function loadProducts() {
  loading.value = true
  try {
    const res = await getProducts(categoryFilter.value)
    products.value = res.data.products || []
  } catch (e) {
    error.value = '加载产品列表失败: ' + (e.response?.data?.detail || e.message)
  } finally { loading.value = false }
}

async function loadHistory() {
  try {
    const res = await getReportHistory(0, 50)
    historyReports.value = res.data.reports || []
  } catch (e) { /* silent */ }
}

function toggleProduct(id) {
  const sid = String(id)
  const idx = selectedIds.value.indexOf(sid)
  if (idx >= 0) selectedIds.value.splice(idx, 1)
  else selectedIds.value.push(sid)
}

function selectAll() { selectedIds.value = filteredProducts.value.map(p => String(p.product_id)) }
function clearSelection() { selectedIds.value = [] }

async function doGenerate() {
  if (!canGenerate.value) return
  generating.value = true; error.value = ''; currentReport.value = null
  try {
    const res = await generateReport(selectedIds.value, activityType.value, getSessionId())
    currentReport.value = res.data
    // 为新报告加载聊天历史
    chatMessages.value = loadChatHistory(res.data.report_id)
    await loadHistory()
  } catch (e) {
    error.value = '报告生成失败: ' + (e.response?.data?.detail || e.message)
  } finally { generating.value = false }
}

async function viewReport(reportId) {
  viewingReportId.value = reportId
  try {
    const res = await getReportDetail(reportId)
    viewingReport.value = res.data
    chatMessages.value = loadChatHistory(reportId)
    await nextTick(); scrollChatBottom()
  } catch (e) { viewingReport.value = null }
}

function closeViewer() {
  viewingReportId.value = null; viewingReport.value = null; chatMessages.value = []
}

// === 聊天方法 ===
async function sendChatMessage() {
  const msg = chatInput.value.trim()
  if (!msg || chatLoading.value) return
  const reportId = currentReport.value?.report_id || viewingReport.value?.id
  if (!reportId) return

  chatInput.value = ''
  chatMessages.value.push({ role: 'user', content: msg })
  chatLoading.value = true
  await nextTick(); scrollChatBottom()

  try {
    const res = await chatFollowup(reportId, msg, chatMessages.value.slice(0, -1))
    // 后端返回了完整的 conversation_history
    if (res.data.conversation_history) {
      chatMessages.value = res.data.conversation_history
    } else {
      chatMessages.value.push({ role: 'assistant', content: res.data.reply })
    }
    saveChatHistory(reportId, chatMessages.value)
  } catch (e) {
    chatMessages.value.push({ role: 'assistant', content: '抱歉，追问失败: ' + (e.response?.data?.detail || e.message) })
    saveChatHistory(reportId, chatMessages.value)
  } finally {
    chatLoading.value = false
    await nextTick(); scrollChatBottom()
  }
}

function handleChatKeydown(e) {
  if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); sendChatMessage() }
}

function scrollChatBottom() {
  if (chatContainer.value) chatContainer.value.scrollTop = chatContainer.value.scrollHeight
}

function formatTime(iso) {
  if (!iso) return ''
  return new Date(iso).toLocaleString('zh-CN')
}

function activityLabel(type) {
  const opt = ACTIVITY_OPTIONS.find(o => o.value === type)
  return opt ? opt.label : type
}

onMounted(() => { loadProducts(); loadHistory() })
watch(categoryFilter, () => { loadProducts() })
</script>

<template>
  <div class="report-page">
    <div class="page-header">
      <h2>📊 生成分析报告</h2>
      <p>选择商品 + 活动类型，多智能体自动协作产出完整分析报告</p>
    </div>

    <div class="layout">
      <!-- 左侧：选择面板 -->
      <div class="left-panel">
        <div class="card section">
          <h3>🎯 活动类型</h3>
          <div class="activity-options">
            <label v-for="opt in ACTIVITY_OPTIONS" :key="opt.value" class="radio-label" :class="{ active: activityType === opt.value }">
              <input type="radio" v-model="activityType" :value="opt.value" />{{ opt.label }}
            </label>
          </div>
        </div>

        <div class="card section">
          <div class="section-header"><h3>📦 选择商品</h3><span class="count">{{ selectedIds.length }} / {{ products.length }} 已选</span></div>
          <div class="filters">
            <input type="text" v-model="searchQuery" placeholder="搜索商品名称或ID..." class="search-input" />
            <select v-model="categoryFilter" class="category-select">
              <option v-for="c in CATEGORIES" :key="c" :value="c">{{ c || '全部类目' }}</option>
            </select>
          </div>
          <div class="batch-actions">
            <button class="btn-sm" @click="selectAll">全选当前</button>
            <button class="btn-sm btn-outline" @click="clearSelection">清空</button>
          </div>
          <div class="product-list" v-if="!loading">
            <div v-if="filteredProducts.length === 0" class="empty">暂无商品数据</div>
            <label v-for="p in filteredProducts" :key="p.product_id" class="product-item" :class="{ selected: selectedIds.includes(String(p.product_id)) }">
              <input type="checkbox" :checked="selectedIds.includes(String(p.product_id))" @change="toggleProduct(p.product_id)" />
              <span class="product-title">{{ p.title }}</span>
              <span class="product-meta"><span class="price">¥{{ p.price }}</span><span class="category-tag">{{ p.category }}</span></span>
            </label>
          </div>
          <div v-else class="loading-text">加载中...</div>
        </div>

        <button class="btn-generate" :disabled="!canGenerate" @click="doGenerate">
          {{ generating ? '⏳ 智能体协作中...' : 🚀 生成报告（ 个商品） }}
        </button>
        <div v-if="error" class="error-msg">{{ error }}</div>
      </div>

      <!-- 右侧：报告 & 聊天 & 历史 -->
      <div class="right-panel">
        <!-- 当前生成的报告 -->
        <template v-if="currentReport">
          <div class="card report-card">
            <div class="report-header"><h3>📋 分析报告</h3><span class="report-time">{{ formatTime(currentReport.created_at) }}</span></div>
            <div class="report-meta">
              <span class="tag">{{ currentReport.activity_label || activityLabel(currentReport.activity_type) }}</span>
              <span class="tag">{{ currentReport.category }}</span>
              <span class="tag">{{ currentReport.product_count }} 个商品</span>
            </div>
            <div class="report-summary">{{ currentReport.summary || '无摘要' }}</div>
            <details class="report-details"><summary>查看详细结果</summary><pre class="detail-json">{{ JSON.stringify(currentReport.report_content, null, 2) }}</pre></details>
          </div>

          <!-- 追问聊天区域 -->
          <div class="card chat-card">
            <h3>💬 追问分析</h3>
            <div ref="chatContainer" class="chat-messages">
              <div v-if="chatMessages.length === 0" class="chat-hint">出报告后可以在这里追问，比如"帮我调低价格""推荐哪个最值得推"</div>
              <div v-for="(msg, i) in chatMessages" :key="i" :class="['chat-bubble', msg.role]">
                <div class="chat-role">{{ msg.role === 'user' ? '👤 你' : '🤖 AI' }}</div>
                <div class="chat-content">{{ msg.content }}</div>
              </div>
              <div v-if="chatLoading" class="chat-bubble assistant"><div class="chat-role">🤖 AI</div><div class="chat-content typing">思考中...</div></div>
            </div>
            <div class="chat-input-row">
              <textarea v-model="chatInput" @keydown="handleChatKeydown" placeholder="追问更多分析..." class="chat-textarea" rows="2"></textarea>
              <button class="btn-chat-send" :disabled="!chatInput.trim() || chatLoading" @click="sendChatMessage">发送</button>
            </div>
          </div>
        </template>

        <!-- 查看历史报告详情 -->
        <template v-if="viewingReport && !currentReport">
          <div class="card report-card">
            <div class="report-header"><h3>📋 历史报告</h3><button class="btn-sm btn-outline" @click="closeViewer">✕ 关闭</button></div>
            <div class="report-meta">
              <span class="tag">{{ activityLabel(viewingReport.activity_type) }}</span>
              <span class="tag">{{ viewingReport.category }}</span>
              <span class="tag">{{ viewingReport.product_ids?.length || 0 }} 个商品</span>
              <span class="tag">{{ formatTime(viewingReport.created_at) }}</span>
            </div>
            <div class="report-summary">{{ viewingReport.summary || '无摘要' }}</div>
            <details class="report-details"><summary>查看详细结果</summary><pre class="detail-json">{{ JSON.stringify(viewingReport.report_content, null, 2) }}</pre></details>
          </div>

          <div class="card chat-card">
            <h3>💬 追问分析</h3>
            <div ref="chatContainer" class="chat-messages">
              <div v-if="chatMessages.length === 0" class="chat-hint">点击历史报告后可在此追问</div>
              <div v-for="(msg, i) in chatMessages" :key="i" :class="['chat-bubble', msg.role]">
                <div class="chat-role">{{ msg.role === 'user' ? '👤 你' : '🤖 AI' }}</div>
                <div class="chat-content">{{ msg.content }}</div>
              </div>
              <div v-if="chatLoading" class="chat-bubble assistant"><div class="chat-role">🤖 AI</div><div class="chat-content typing">思考中...</div></div>
            </div>
            <div class="chat-input-row">
              <textarea v-model="chatInput" @keydown="handleChatKeydown" placeholder="追问更多分析..." class="chat-textarea" rows="2"></textarea>
              <button class="btn-chat-send" :disabled="!chatInput.trim() || chatLoading" @click="sendChatMessage">发送</button>
            </div>
          </div>
        </template>

        <!-- 历史列表（无报告时） -->
        <div class="card history-card" v-if="!currentReport && !viewingReport">
          <h3>📜 历史报告</h3>
          <div v-if="historyReports.length === 0" class="empty">暂无历史报告，选择商品后点击"生成报告"开始</div>
          <div v-for="r in historyReports" :key="r.id" class="history-item" @click="viewReport(r.id)" :class="{ active: viewingReportId === r.id }">
            <div class="history-main">
              <span class="history-activity">{{ activityLabel(r.activity_type) }}</span>
              <span class="history-category">{{ r.category || '综合' }}</span>
              <span class="history-count">{{ r.product_count }} 商品</span>
            </div>
            <div class="history-time">{{ formatTime(r.created_at) }}</div>
          </div>
        </div>

        <div v-if="!currentReport && !viewingReport && historyReports.length === 0" class="card placeholder">
          <div class="placeholder-icon">🤖</div>
          <div class="placeholder-text">左侧选择商品和活动类型，点击"生成报告"</div>
          <div class="placeholder-sub">系统将自动调度 7 个智能体协作分析</div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.report-page { max-width: 1400px; margin: 0 auto; }
.page-header { margin-bottom: 20px; }
.page-header h2 { font-size: 22px; font-weight: 700; color: #1a1a2e; margin: 0; }
.page-header p { color: #888; font-size: 13px; margin-top: 4px; }

.layout { display: grid; grid-template-columns: 420px 1fr; gap: 20px; align-items: start; }

.card { background: #fff; border-radius: 10px; padding: 20px; border: 1px solid #e8e8e8; margin-bottom: 16px; }
.section h3, .card h3 { font-size: 15px; font-weight: 600; color: #333; margin: 0 0 12px 0; }

.activity-options { display: flex; flex-wrap: wrap; gap: 8px; }
.radio-label { padding: 8px 16px; border: 1px solid #ddd; border-radius: 20px; font-size: 13px; cursor: pointer; transition: all 0.2s; display: flex; align-items: center; gap: 4px; }
.radio-label input { display: none; }
.radio-label.active { background: #4fc3f7; color: #fff; border-color: #4fc3f7; font-weight: 600; }
.radio-label:hover:not(.active) { border-color: #4fc3f7; color: #4fc3f7; }

.filters { display: flex; gap: 8px; margin-bottom: 10px; }
.search-input { flex: 1; padding: 8px 12px; border: 1px solid #ddd; border-radius: 6px; font-size: 13px; }
.category-select { padding: 8px; border: 1px solid #ddd; border-radius: 6px; font-size: 13px; min-width: 100px; }

.section-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px; }
.section-header h3 { margin: 0; }
.count { font-size: 12px; color: #888; }
.batch-actions { display: flex; gap: 8px; margin-bottom: 10px; }
.btn-sm { padding: 4px 12px; font-size: 12px; border: 1px solid #4fc3f7; background: #4fc3f7; color: #fff; border-radius: 4px; cursor: pointer; }
.btn-sm.btn-outline { background: #fff; color: #4fc3f7; }
.product-list { max-height: 400px; overflow-y: auto; border: 1px solid #eee; border-radius: 6px; }
.product-item { display: flex; align-items: center; gap: 10px; padding: 10px 12px; border-bottom: 1px solid #f5f5f5; cursor: pointer; transition: background 0.15s; font-size: 13px; }
.product-item:hover { background: #f8faff; }
.product-item.selected { background: #e3f2fd; }
.product-item input[type="checkbox"] { width: 16px; height: 16px; cursor: pointer; }
.product-title { flex: 1; color: #333; font-weight: 500; }
.product-meta { display: flex; gap: 8px; align-items: center; }
.price { color: #e53935; font-weight: 600; }
.category-tag { background: #f0f4ff; color: #3f51b5; padding: 1px 8px; border-radius: 10px; font-size: 11px; }

.btn-generate { width: 100%; padding: 14px; font-size: 16px; font-weight: 700; background: linear-gradient(135deg, #4fc3f7, #29b6f6); color: #fff; border: none; border-radius: 10px; cursor: pointer; transition: all 0.2s; margin-top: 16px; }
.btn-generate:hover:not(:disabled) { transform: translateY(-1px); box-shadow: 0 4px 12px rgba(79,195,247,0.4); }
.btn-generate:disabled { opacity: 0.5; cursor: not-allowed; }

.error-msg { margin-top: 10px; padding: 10px; background: #fff0f0; border: 1px solid #ffcdd2; border-radius: 6px; color: #c62828; font-size: 13px; }

.report-card { border-left: 4px solid #4fc3f7; }
.report-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px; }
.report-time { font-size: 12px; color: #888; }
.report-meta { display: flex; gap: 8px; flex-wrap: wrap; margin-bottom: 12px; }
.tag { background: #f0f4ff; color: #3f51b5; padding: 3px 10px; border-radius: 12px; font-size: 12px; }
.report-summary { font-size: 14px; line-height: 1.7; color: #333; white-space: pre-wrap; }
.report-details { margin-top: 16px; }
.report-details summary { cursor: pointer; color: #4fc3f7; font-size: 13px; font-weight: 500; }
.detail-json { margin-top: 10px; padding: 16px; background: #1a1a2e; color: #e0e0e0; border-radius: 8px; font-size: 11px; max-height: 400px; overflow: auto; white-space: pre-wrap; word-break: break-all; }

/* === 聊天区域 === */
.chat-card { border-top: 3px solid #4fc3f7; }
.chat-messages { max-height: 350px; overflow-y: auto; margin-bottom: 12px; padding: 8px 0; }
.chat-hint { text-align: center; color: #aaa; font-size: 13px; padding: 20px; }
.chat-bubble { margin-bottom: 12px; }
.chat-bubble.user .chat-content { background: #4fc3f7; color: #fff; margin-left: 40px; border-radius: 8px 8px 0 8px; }
.chat-bubble.assistant .chat-content { background: #f5f5f5; color: #333; margin-right: 40px; border-radius: 8px 8px 8px 0; }
.chat-role { font-size: 11px; color: #999; margin-bottom: 2px; padding: 0 4px; }
.chat-content { padding: 10px 14px; font-size: 13px; line-height: 1.6; white-space: pre-wrap; word-break: break-word; }
.chat-content.typing { color: #999; font-style: italic; }
.chat-input-row { display: flex; gap: 8px; align-items: flex-end; }
.chat-textarea { flex: 1; padding: 10px 12px; border: 1px solid #ddd; border-radius: 8px; font-size: 13px; resize: none; font-family: inherit; }
.chat-textarea:focus { outline: none; border-color: #4fc3f7; }
.btn-chat-send { padding: 10px 20px; background: #4fc3f7; color: #fff; border: none; border-radius: 8px; font-size: 13px; font-weight: 600; cursor: pointer; white-space: nowrap; }
.btn-chat-send:disabled { opacity: 0.4; cursor: not-allowed; }

.history-item { display: flex; justify-content: space-between; align-items: center; padding: 12px 14px; border-bottom: 1px solid #f0f0f0; cursor: pointer; transition: background 0.15s; border-radius: 6px; }
.history-item:hover { background: #f8faff; }
.history-item.active { background: #e3f2fd; }
.history-main { display: flex; gap: 12px; align-items: center; }
.history-activity { font-weight: 600; color: #333; font-size: 14px; }
.history-category { color: #888; font-size: 13px; }
.history-count { color: #888; font-size: 12px; }
.history-time { color: #aaa; font-size: 12px; }

.placeholder { text-align: center; padding: 60px 20px; }
.placeholder-icon { font-size: 48px; margin-bottom: 12px; }
.placeholder-text { font-size: 15px; color: #555; margin-bottom: 8px; }
.placeholder-sub { font-size: 13px; color: #aaa; }
.empty { text-align: center; padding: 30px; color: #aaa; font-size: 13px; }
.loading-text { text-align: center; padding: 30px; color: #aaa; font-size: 13px; }

@media (max-width: 768px) { .layout { grid-template-columns: 1fr; } }
</style>


