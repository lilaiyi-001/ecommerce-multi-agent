<script setup>
import { ref, computed, onMounted, watch, nextTick } from 'vue'
import VChart from 'vue-echarts'
import { use } from 'echarts/core'
import { PieChart } from 'echarts/charts'
import { TitleComponent, TooltipComponent, LegendComponent } from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'
import { useAnalysisStore } from '../stores/analysis.js'
import { getProducts, generateReport, getReportHistory, getReportDetail, chatFollowup, exportReportMd, exportReportPdf } from '../api/index.js'
import { marked } from 'marked'

marked.setOptions({ breaks: true, gfm: true })
use([PieChart, TitleComponent, TooltipComponent, LegendComponent, CanvasRenderer])

const store = useAnalysisStore()
const categories = ['食品', '服饰', '家居', '数码', '园艺', '宠物用品', '文具', '箱包']

const SESSION_KEY = 'ecommerce_session_id'
function getSessionId() {
  let sid = localStorage.getItem(SESSION_KEY)
  if (!sid) { sid = 'sess_' + Date.now() + '_' + Math.random().toString(36).slice(2,8); localStorage.setItem(SESSION_KEY, sid) }
  return sid
}
function getChatKey(reportId) { return 'chat_history_' + reportId }
function loadChatHistory(reportId) { try { return JSON.parse(localStorage.getItem(getChatKey(reportId)) || '[]') } catch { return [] } }
function saveChatHistory(reportId, history) { try { localStorage.setItem(getChatKey(reportId), JSON.stringify(history)) } catch {} }

const products = ref([])
const selectedIds = ref([])
const activityType = ref('daily')
const categoryFilter = ref('')
const searchQuery = ref('')
const loading = ref(false)
const generating = ref(false)
const currentReport = ref(null)
const error = ref('')
const viewingReport = ref(null)
const chatMessages = ref([])
const chatInput = ref('')
const chatLoading = ref(false)
const chatContainer = ref(null)
const historyReports = ref([])

const ACTIVITY_OPTIONS = [
  { value:'double11',label:'双11大促'},{ value:'618',label:'618大促'},{ value:'new_product',label:'新品发布'},
  { value:'clearance',label:'清仓促销'},{ value:'daily',label:'日常促销'},{ value:'flash_sale',label:'限时秒杀'},
  { value:'member_day',label:'会员日'},{ value:'festival',label:'节日促销'},{ value:'pre_sale',label:'预售活动'},
  { value:'group_buy',label:'拼团活动'},{ value:'anniversary',label:'店庆活动'},{ value:'season_change',label:'换季清仓'},
]
const CATEGORIES = ['','食品','服饰','家居','数码','园艺','宠物用品','文具','箱包']

function formatTime(ts) {
  if (!ts) return ''
  const d = new Date(ts); const y = d.getFullYear(); const m = String(d.getMonth()+1).padStart(2,'0')
  const day = String(d.getDate()).padStart(2,'0'); const h = String(d.getHours()).padStart(2,'0'); const min = String(d.getMinutes()).padStart(2,'0')
  return y+'-'+m+'-'+day+' '+h+':'+min
}

const statCards = computed(() => {
  const recent = store.recentAnalyses || []; const today = new Date().toDateString()
  return [
    { label:'商品总数',value:store.productCount,color:'#9c27b0' },
    { label:'分析类目',value:recent.length?[...new Set(recent.map(r=>r.category))].length:0,color:'#2196f3' },
    { label:'今日分析',value:recent.filter(r=>{try{return new Date(r.time).toDateString()===today}catch{return false}}).length,color:'#ff9800' },
  ]
})

const ringOption = computed(() => {
  const stats = store.categoryStats || []
  const data = stats.length ? stats.map(c=>({name:c.name,value:c.product_count})) : categories.map(c=>({name:c,value:0}))
  return { tooltip:{trigger:'item',formatter:'{b}: {c} ({d}%)'}, legend:{bottom:0,textStyle:{fontSize:12}},
    series:[{type:'pie',radius:['45%','75%'],center:['50%','42%'],data,label:{formatter:'{b}\n{d}%',fontSize:11},itemStyle:{borderRadius:4,borderColor:'#fff',borderWidth:2}}] }
})

const mergedRecords = computed(() => {
  const items = []
  for (const r of (store.recentAnalyses||[])) items.push({type:'recent',category:r.category,activity:r.activity,time:r.time,id:r.reportId})
  for (const h of historyReports.value) { if (!items.find(i=>i.id===h.id)) items.push({type:'history',category:h.category,activity:h.activity_type,time:h.created_at,id:h.id,productCount:h.product_count}) }
  items.sort((a,b)=>new Date(b.time)-new Date(a.time))
  return items.slice(0,10)
})

const filteredProducts = computed(() => {
  let list = products.value
  if (categoryFilter.value) list = list.filter(p=>p.category===categoryFilter.value)
  if (searchQuery.value) { const q=searchQuery.value.toLowerCase(); list=list.filter(p=>p.title.toLowerCase().includes(q)||String(p.product_id).includes(q)) }
  return list
})
const canGenerate = computed(()=>selectedIds.value.length>=1&&!generating.value)

function toggleProduct(id) { const sid=String(id); const idx=selectedIds.value.indexOf(sid); if(idx>=0)selectedIds.value.splice(idx,1); else selectedIds.value.push(sid) }
function selectAll() { selectedIds.value = filteredProducts.value.map(p=>String(p.product_id)) }
function clearSel() { selectedIds.value = [] }

function saveRecentAnalysis(report) {
  const KEY='ecommerce_recent_analyses'
  try { let recent=JSON.parse(localStorage.getItem(KEY)||'[]'); recent.unshift({category:report.category||'综合',activity:report.activity_label||report.activity_type||'',productCount:report.product_count||0,time:new Date().toISOString(),reportId:report.report_id||''}); if(recent.length>20)recent=recent.slice(0,20); localStorage.setItem(KEY,JSON.stringify(recent)); store.refreshRecent() } catch {}
}

async function loadProducts() { loading.value=true; try{const res=await getProducts(categoryFilter.value);products.value=res.data.products||[]}catch(e){error.value='加载失败:'+(e.response?.data?.detail||e.message)}finally{loading.value=false} }
async function loadHistory() { try{const res=await getReportHistory(0,50);historyReports.value=res.data.reports||[]}catch{} }

async function doGenerate() {
  if(!canGenerate.value)return; generating.value=true;error.value='';currentReport.value=null
  try{const res=await generateReport(selectedIds.value,activityType.value,getSessionId());currentReport.value=res.data;saveRecentAnalysis(res.data);chatMessages.value=loadChatHistory(res.data.report_id);await loadHistory()}catch(e){error.value='报告生成失败:'+(e.response?.data?.detail||e.message)}finally{generating.value=false}
}

async function downloadReport() {
  if(!currentReport.value?.report_id)return
  try{const res=await exportReportPdf(currentReport.value.report_id);const blob=new Blob([res.data],{type:'application/pdf'});const url=window.URL.createObjectURL(blob);const a=document.createElement('a');a.href=url;a.download='分析报告_'+(currentReport.value.category||'')+'_'+(currentReport.value.activity_label||'')+'.pdf';document.body.appendChild(a);a.click();document.body.removeChild(a);window.URL.revokeObjectURL(url)}catch(e){alert('导出失败:'+(e.response?.data?.detail||e.message))}
}

async function viewHistoryReport(record) { if(!record.id)return; try{const res=await getReportDetail(record.id);viewingReport.value=res.data;chatMessages.value=loadChatHistory(record.id);await nextTick();scrollChatBottom()}catch{} }

async function sendChatMessage() {
  const msg=chatInput.value.trim();if(!msg||chatLoading.value)return;const rid=currentReport.value?.report_id||viewingReport.value?.id;if(!rid)return
  chatInput.value='';chatMessages.value.push({role:'user',content:msg});chatLoading.value=true;await nextTick();scrollChatBottom()
  try{const res=await chatFollowup(rid,msg,chatMessages.value.slice(0,-1));if(res.data.conversation_history)chatMessages.value=res.data.conversation_history;else chatMessages.value.push({role:'assistant',content:res.data.reply});saveChatHistory(rid,chatMessages.value)}catch(e){chatMessages.value.push({role:'assistant',content:'发送失败:'+(e.response?.data?.detail||e.message)})}finally{chatLoading.value=false;await nextTick();scrollChatBottom()}
}
function handleChatKeydown(e) { if(e.key==='Enter'&&!e.shiftKey){e.preventDefault();sendChatMessage()} }
function scrollChatBottom() { if(chatContainer.value)chatContainer.value.scrollTop=chatContainer.value.scrollHeight }
function activityLabel(type) { const m=ACTIVITY_OPTIONS.find(o=>o.value===type);return m?m.label:type }

const AGENT_LABELS_MD = { product_selection:'选品分析',trend_forecast:'趋势预测',competitor_analysis:'竞品分析',user_profile:'用户画像',pricing_strategy:'定价策略',marketing_copy:'营销文案',inventory_advice:'补货/清仓建议',promotion_plan:'活动策划' }
function buildMarkdown(report) {
  const rc=report.report_content||{};const orch=rc.orchestrator_result||{};const prodList=rc.products||[];const al=rc.activity_label||report.activity_type||'';const cat=report.category||'综合';const dt=report.created_at?new Date(report.created_at).toLocaleString():'';const lines=[]
  lines.push('# 电商选品分析报告');lines.push('');lines.push('**分析类目**: '+cat+'  ');lines.push('**活动类型**: '+al+'  ');lines.push('**分析商品数**: '+(report.product_count||prodList.length)+' 个  ');lines.push('**生成时间**: '+dt);lines.push('');lines.push('## 商品清单');lines.push('')
  if(prodList.length){lines.push('| 商品ID | 商品名称 | 类目 | 售价 | 库存 |');lines.push('|--------|----------|------|------|------|');for(const p of prodList)lines.push('| '+[p.product_id,p.title,p.category,p.price,p.stock].join(' | ')+' |')}else lines.push('（无商品数据）')
  lines.push('');if(report.summary){lines.push('## 报告摘要');lines.push('');lines.push(report.summary);lines.push('')}
  lines.push('## 智能体分析详情');lines.push('');const phases=orch.phase_results||rc.phase_results||[]
  if(phases.length){for(const phase of phases){lines.push('### 第 '+(phase.phase||'?')+' 阶段');lines.push('');for(const agent of(phase.agents||[])){const tt=agent.task_type||agent.agent_name||'';const label=AGENT_LABELS_MD[tt]||tt;lines.push('#### '+label);lines.push('');const summary=agent.summary||'';if(summary){lines.push(summary)}else{const output=agent.output||agent.result||'';let payload={};if(typeof output==='object'&&output!==null)payload=output.payload||{};if(payload&&Object.keys(payload).length>0){const fd=payload.for_display||'';if(fd)lines.push(String(fd));else{for(const[k,v]of Object.entries(payload)){if(k==='for_downstream'||k==='agent_name'||k==='envelope')continue;if(v!=null&&v!=='')lines.push('- **'+k+'**: '+String(v).substring(0,500))}}}else if(typeof output==='object'&&output!==null){for(const[k,v]of Object.entries(output)){if(k==='envelope')continue;if(v!=null&&v!=='')lines.push('- **'+k+'**: '+String(v).substring(0,300))}}else if(typeof output==='string'&&output)lines.push(output)}const rec=agent.recommendation;if(rec)lines.push('> '+rec);lines.push('')}}}else{const fd=orch.for_display||orch.final_report||'';if(fd)lines.push(String(fd));else lines.push('（暂无明显数据）')}
  return lines.join('\n')
}
const reportMarkdown = computed(()=>{const report=currentReport.value||viewingReport.value;if(!report)return '<p style="color:#999">请先生成报告</p>';const md=buildMarkdown(report);try{return marked.parse(md)}catch{return '<pre>'+md+'</pre>'}})

onMounted(()=>{store.checkHealth();store.fetchCategoryStats();store.refreshRecent();loadProducts();loadHistory()})
</script>

<template>
  <div class="dash-root">
    <div class="stats-row">
      <div v-for="card in statCards" :key="card.label" class="stat-card" :style="{ borderTopColor: card.color }">
        <div class="stat-icon">{{ card.label==='商品总数'?'📦':card.label==='分析类目'?'📂':'📈' }}</div>
        <div class="stat-body"><div class="stat-label">{{ card.label }}</div><div class="stat-value" :style="{ color: card.color }">{{ card.value }}</div></div>
      </div>
    </div>
    <div class="mid-row">
      <div class="card"><div class="card-head"><span class="card-head-icon">🍩</span> 类目商品分布</div><v-chart :option="ringOption" style="height:300px" autoresize /></div>
      <div class="card">
        <div class="card-head"><span class="card-head-icon">📋</span> 分析记录</div>
        <div v-if="mergedRecords.length===0" class="empty-state"><div class="empty-icon">📭</div><div>暂无分析记录</div><div class="empty-sub">生成报告后在此显示</div></div>
        <div v-else class="record-list">
          <div v-for="(r,i) in mergedRecords" :key="i" class="record-item" @click="viewHistoryReport(r)" style="cursor:pointer">
            <div class="record-left"><span class="record-cat">{{ r.category||'综合' }}</span><span class="record-act">{{ r.activity||'' }}</span><span v-if="r.productCount" class="record-num">· {{ r.productCount }}件</span></div>
            <span class="record-time">{{ formatTime(r.time) }}</span>
          </div>
        </div>
      </div>
    </div>
    <div class="dual-cards">
      <div class="card dual-card">
        <div class="card-head"><span class="card-head-icon">🎯</span> 选择活动类型</div>
        <div class="activity-pills">
          <label v-for="opt in ACTIVITY_OPTIONS" :key="opt.value" class="pill" :class="{ active: activityType===opt.value }"><input type="radio" :value="opt.value" v-model="activityType" />{{ opt.label }}</label>
        </div>
      </div>
      <div class="card dual-card">
        <div class="card-head"><span class="card-head-icon">📦</span> 选择商品<span class="card-head-right">已选 {{ selectedIds.length }} / {{ products.length }}</span></div>
        <div class="filter-bar"><select v-model="categoryFilter" @change="loadProducts" class="filter-select"><option v-for="c in CATEGORIES" :key="c" :value="c">{{ c||'全部类目' }}</option></select><input v-model="searchQuery" placeholder="搜索商品名称或ID..." class="filter-input" /></div>
        <div class="batch-row"><button class="btn-batch" @click="selectAll">全选当前</button><button class="btn-batch outline" @click="clearSel">清空选择</button></div>
        <div class="product-grid" v-if="!loading">
          <div v-if="filteredProducts.length===0" class="empty-state"><div class="empty-icon">📦</div><div>暂无商品</div></div>
          <label v-for="p in filteredProducts" :key="p.product_id" class="prod-card" :class="{ selected: selectedIds.includes(String(p.product_id)) }">
            <input type="checkbox" :checked="selectedIds.includes(String(p.product_id))" @change="toggleProduct(p.product_id)" />
            <div class="prod-info"><div class="prod-title">{{ p.title }}</div><div class="prod-meta"><span class="prod-price">¥{{ p.price }}</span><span class="prod-cat">{{ p.category }}</span></div></div>
          </label>
        </div>
        <div v-else class="empty-state"><div class="empty-icon">⏳</div><div>加载中...</div></div>
      </div>
    </div>
    <button class="btn-main" :disabled="!canGenerate" @click="doGenerate">{{ generating?'⏳ 智能体协作中...':'🚀 生成报告（'+selectedIds.length+' 个商品）' }}</button>
    <div v-if="error" class="error-box">{{ error }}</div>
    <div class="report-area" v-if="currentReport||viewingReport">
      <div class="card report-result">
        <div class="report-top">
          <div><h2 class="report-title">📋 分析报告</h2><div class="report-tags"><span class="rtag">{{ (currentReport||viewingReport).activity_label||activityLabel((currentReport||viewingReport).activity_type) }}</span><span class="rtag">{{ (currentReport||viewingReport).category }}</span><span class="rtag dim">{{ (currentReport||viewingReport).product_count }} 个商品</span></div></div>
          <div class="report-actions"><span class="report-date">{{ formatTime((currentReport||viewingReport).created_at) }}</span><button class="btn-dl" @click="downloadReport">📥 导出 PDF</button></div>
        </div>
        <div class="report-abstract">{{ (currentReport||viewingReport).summary||'无摘要' }}</div>
        <details class="report-detail" open><summary>查看详细结果</summary><div class="md-view" v-html="reportMarkdown"></div></details>
      </div>
      <div class="card chat-box">
        <div class="card-head"><span class="card-head-icon">💬</span> 追问分析</div>
        <div ref="chatContainer" class="chat-msgs">
          <div v-if="chatMessages.length===0" class="chat-empty">生成报告后可以在此追问，比如"推荐哪个最值得推""帮我调低价格"</div>
          <div v-for="(msg,i) in chatMessages" :key="i" :class="['chat-msg',msg.role]"><span class="chat-role-tag">{{ msg.role==='user'?'👤 你':'🤖 AI' }}</span><div class="chat-text">{{ msg.content }}</div></div>
          <div v-if="chatLoading" class="chat-msg assistant"><span class="chat-role-tag">🤖 AI</span><div class="chat-text dim-text">思考中...</div></div>
        </div>
        <div class="chat-send-row"><textarea v-model="chatInput" @keydown="handleChatKeydown" placeholder="输入追问内容..." class="chat-input" rows="2"></textarea><button class="btn-send" :disabled="!chatInput.trim()||chatLoading" @click="sendChatMessage">发送</button></div>
      </div>
    </div>
    <div v-else-if="!currentReport&&!viewingReport" class="empty-report"><div class="empty-icon">📊</div><div class="empty-title">选择商品和活动类型</div><div class="empty-desc">点击「生成报告」按钮，10个智能体将协作分析</div></div>
  </div>
</template>

<style scoped>
.dash-root { max-width:1400px;margin:0 auto; }
.stats-row { display:grid;grid-template-columns:repeat(3,1fr);gap:16px;margin-bottom:20px; }
.stat-card { background:#fff;border-radius:12px;padding:20px 24px;display:flex;align-items:center;gap:16px;border-top:3px solid #e0e0e0;box-shadow:0 1px 3px rgba(0,0,0,0.04);transition:transform 0.15s; }
.stat-card:hover { transform:translateY(-2px); }
.stat-icon { font-size:32px;width:48px;height:48px;display:flex;align-items:center;justify-content:center;background:#f8faff;border-radius:12px; }
.stat-label { font-size:13px;color:#888; }
.stat-value { font-size:32px;font-weight:700;line-height:1.1; }
.mid-row { display:grid;grid-template-columns:1fr 1fr;gap:16px;margin-bottom:20px; }
@media(max-width:900px){.mid-row{grid-template-columns:1fr}}
.card { background:#fff;border-radius:12px;padding:20px;box-shadow:0 1px 3px rgba(0,0,0,0.04); }
.card-head { font-size:15px;font-weight:600;color:#333;margin-bottom:14px;display:flex;align-items:center;gap:8px; }
.card-head-icon { font-size:18px; }
.card-head-right { margin-left:auto;font-size:13px;color:#888;font-weight:400; }
.record-list { max-height:300px;overflow-y:auto;display:flex;flex-direction:column;gap:4px; }
.record-item { display:flex;justify-content:space-between;align-items:center;padding:10px 12px;background:#f8faff;border-radius:8px;font-size:13px;transition:background 0.15s; }
.record-item:hover { background:#eef2ff; }
.record-left { display:flex;gap:8px;align-items:center; }
.record-cat { color:#3f51b5;font-weight:600; }
.record-act { color:#666; }
.record-num { color:#aaa; }
.record-time { color:#aaa;font-size:12px; }
.dual-cards { display:grid;grid-template-columns:1fr 1fr;gap:14px;margin-bottom:14px; }
@media(max-width:900px){.dual-cards{grid-template-columns:1fr}}
.dual-card { min-height:0; }
.dual-card .product-grid { max-height:260px; }
.dual-card .activity-pills { max-height:260px;overflow-y:auto; }
.activity-pills { display:flex;flex-wrap:wrap;gap:8px; }
.pill { display:flex;align-items:center;gap:4px;padding:7px 14px;border:1.5px solid #e0e0e0;border-radius:20px;font-size:13px;cursor:pointer;transition:all 0.2s;user-select:none;background:#fafafa; }
.pill:hover { border-color:#4fc3f7;background:#f0f9ff; }
.pill.active { background:#e3f2fd;border-color:#4fc3f7;color:#1976d2;font-weight:600; }
.pill input { display:none; }
.filter-bar { display:flex;gap:8px;margin-bottom:10px; }
.filter-select { padding:8px 12px;border:1.5px solid #e0e0e0;border-radius:8px;font-size:13px;background:#fff;min-width:100px; }
.filter-input { flex:1;padding:8px 12px;border:1.5px solid #e0e0e0;border-radius:8px;font-size:13px;outline:none; }
.filter-input:focus { border-color:#4fc3f7; }
.batch-row { display:flex;gap:8px;margin-bottom:10px; }
.btn-batch { padding:5px 14px;font-size:12px;border:1.5px solid #4fc3f7;background:#4fc3f7;color:#fff;border-radius:6px;cursor:pointer;font-weight:500; }
.btn-batch.outline { background:#fff;color:#4fc3f7; }
.product-grid { display:grid;grid-template-columns:1fr 1fr;gap:6px;max-height:340px;overflow-y:auto; }
.prod-card { display:flex;align-items:center;gap:8px;padding:8px 10px;border:1.5px solid #eee;border-radius:8px;cursor:pointer;transition:all 0.15s;font-size:12px; }
.prod-card:hover { border-color:#4fc3f7;background:#f8fdff; }
.prod-card.selected { border-color:#4fc3f7;background:#e3f2fd; }
.prod-card input[type="checkbox"] { width:15px;height:15px;cursor:pointer;accent-color:#4fc3f7; }
.prod-info { flex:1;min-width:0; }
.prod-title { font-weight:500;color:#333;white-space:nowrap;overflow:hidden;text-overflow:ellipsis; }
.prod-meta { display:flex;gap:6px;align-items:center;margin-top:2px; }
.prod-price { color:#e53935;font-weight:600; }
.prod-cat { color:#888;font-size:11px;background:#f5f5f5;padding:1px 6px;border-radius:4px; }
.btn-main { width:100%;padding:16px;margin-top:14px;font-size:16px;font-weight:700;color:#fff;border:none;border-radius:12px;cursor:pointer;transition:all 0.2s;background:linear-gradient(135deg,#43a047,#66bb6a); }
.btn-main:hover:not(:disabled) { transform:translateY(-2px);box-shadow:0 6px 20px rgba(76,175,80,0.35); }
.btn-main:disabled { opacity:0.45;cursor:not-allowed; }
.report-area { margin-top:20px;display:flex;flex-direction:column;gap:16px; }
.report-top { display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:14px; }
.report-title { margin:0;font-size:20px;color:#1a1a2e; }
.report-tags { display:flex;gap:6px;margin-top:8px;flex-wrap:wrap; }
.rtag { padding:3px 10px;background:#f0f4ff;color:#3f51b5;border-radius:12px;font-size:12px;font-weight:500; }
.rtag.dim { color:#888;background:#f5f5f5; }
.report-actions { text-align:right;display:flex;flex-direction:column;align-items:flex-end;gap:6px; }
.report-date { font-size:12px;color:#aaa; }
.btn-dl { padding:7px 16px;background:#fff;border:1.5px solid #4caf50;color:#4caf50;border-radius:8px;font-size:13px;cursor:pointer;font-weight:600;transition:all 0.2s; }
.btn-dl:hover { background:#4caf50;color:#fff; }
.report-abstract { font-size:14px;line-height:1.7;color:#555;padding:12px 16px;background:#fafbff;border-radius:8px;white-space:pre-wrap;margin-bottom:12px; }
.report-detail summary { cursor:pointer;color:#4fc3f7;font-weight:600;font-size:14px;padding:4px 0; }
.md-view { margin-top:14px;padding:24px 28px;background:#fcfcfd;border:1px solid #eee;border-radius:10px;max-height:550px;overflow-y:auto;font-size:14px;line-height:1.8;color:#333; }
.md-view :deep(h1) { font-size:22px;color:#1a1a2e;border-bottom:2px solid #4fc3f7;padding-bottom:8px;margin:0 0 16px 0; }
.md-view :deep(h2) { font-size:18px;color:#333;margin:20px 0 10px 0;padding-bottom:4px;border-bottom:1px solid #eee; }
.md-view :deep(h3) { font-size:16px;color:#555;margin:16px 0 8px 0; }
.md-view :deep(h4) { font-size:14px;color:#3f51b5;margin:12px 0 6px 0; }
.md-view :deep(table) { width:100%;border-collapse:collapse;margin:10px 0;font-size:13px; }
.md-view :deep(th) { background:#f8faff;padding:8px 10px;text-align:left;font-weight:600;color:#555;border-bottom:2px solid #e0e0e0; }
.md-view :deep(td) { padding:7px 10px;border-bottom:1px solid #f0f0f0; }
.md-view :deep(blockquote) { border-left:4px solid #4fc3f7;margin:10px 0;padding:8px 14px;background:#f8faff;color:#555;border-radius:0 6px 6px 0; }
.chat-msgs { max-height:300px;overflow-y:auto;margin-bottom:10px;padding:4px 0; }
.chat-empty { text-align:center;color:#bbb;font-size:13px;padding:24px 0; }
.chat-msg { margin-bottom:10px; }
.chat-msg.user .chat-text { background:#4fc3f7;color:#fff;margin-left:50px;border-radius:8px 8px 0 8px; }
.chat-msg.assistant .chat-text { background:#f5f5f5;color:#333;margin-right:50px;border-radius:8px 8px 8px 0; }
.chat-role-tag { font-size:11px;color:#999;display:block;margin-bottom:2px;padding-left:4px; }
.chat-text { padding:10px 14px;font-size:13px;line-height:1.6;white-space:pre-wrap;word-break:break-word; }
.chat-text.dim-text { color:#aaa;font-style:italic; }
.chat-send-row { display:flex;gap:8px;align-items:flex-end; }
.chat-input { flex:1;padding:10px 14px;border:1.5px solid #e0e0e0;border-radius:10px;font-size:13px;resize:none;font-family:inherit;outline:none; }
.chat-input:focus { border-color:#4fc3f7; }
.btn-send { padding:10px 22px;background:#4fc3f7;color:#fff;border:none;border-radius:10px;font-size:14px;font-weight:600;cursor:pointer; }
.btn-send:disabled { opacity:0.4;cursor:not-allowed; }
.empty-state { display:flex;flex-direction:column;align-items:center;justify-content:center;padding:30px 0;color:#aaa;font-size:14px;gap:6px; }
.empty-icon { font-size:36px; }
.empty-sub { font-size:12px;color:#ccc; }
.empty-report { display:flex;flex-direction:column;align-items:center;justify-content:center;padding:80px 20px;text-align:center; }
.empty-title { font-size:18px;color:#555;margin-top:16px; }
.empty-desc { font-size:14px;color:#aaa;margin-top:6px; }
.error-box { margin-top:8px;padding:12px 16px;background:#fff0f0;border:1px solid #ffcdd2;border-radius:8px;color:#c62828;font-size:13px; }
</style>
