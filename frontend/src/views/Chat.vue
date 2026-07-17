<script setup>
import { ref, nextTick } from 'vue'
import { useAnalysisStore } from '../stores/analysis.js'

const store = useAnalysisStore()
const messages = ref([])
const input = ref('')
const loading = ref(false)
const sessionId = 'sess_' + Date.now()
const msgContainer = ref(null)

const presets = [
  '分析数码类目，推荐3个爆款',
  '食品类目做促销活动方案',
  '帮我全面分析家居类目',
]

async function sendMessage(msg) {
  const userMsg = (typeof msg === 'string' ? msg : input.value).trim()
  if (!userMsg || loading.value) return
  if (typeof msg !== 'string') input.value = ''

  loading.value = true
  try {
    const data = await store.chat(userMsg, sessionId)
    const intent = data.intent_result
    const orch = data.orchestrator_result

    messages.value.push({
      type: 'result',
      userMessage: userMsg,
      intent: intent,
      orchestrator: orch,
      timestamp: Date.now(),
    })
    await nextTick()
    if (msgContainer.value) {
      msgContainer.value.scrollTop = msgContainer.value.scrollHeight
    }
  } catch (e) {
    const detail = e.response?.data?.detail || e.message || '请求失败'
    messages.value.push({
      type: 'error',
      userMessage: userMsg,
      error: detail,
      timestamp: Date.now(),
    })
  } finally {
    loading.value = false
  }
}

function handleKeydown(e) {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault()
    sendMessage()
  }
}

function statusIcon(status) {
  return status === 'completed' ? '✅' : status === 'skipped' ? '⏭️' : '❌'
}
function statusColor(status) {
  return status === 'completed' ? '#2e7d32' : status === 'skipped' ? '#e65100' : '#c62828'
}
</script>

<template>
  <div style="display:flex;flex-direction:column;height:calc(100vh - 48px)">
    <div style="margin-bottom:16px">
      <h2 style="font-size:20px;font-weight:700;color:#1a1a2e">智能对话</h2>
      <p style="color:#888;font-size:13px;margin-top:4px">用自然语言描述需求，系统自动调度多智能体协作分析</p>
    </div>

    <div class="card" style="flex:1;display:flex;flex-direction:column;overflow:hidden">
      <div ref="msgContainer" style="flex:1;overflow-y:auto;padding:16px">
        <div v-if="messages.length === 0" style="text-align:center;padding:40px 20px">
          <div style="font-size:48px;margin-bottom:16px">{emoji}🤖</div>
          <div style="font-size:15px;color:#888;margin-bottom:20px">输入你的需求，例如：</div>
          <div style="display:flex;gap:8px;justify-content:center;flex-wrap:wrap">
            <button v-for="p in presets" :key="p" class="preset-btn" @click="sendMessage(p)">{{ p }}</button>
          </div>
        </div>

        <div v-for="(msg, i) in messages" :key="i" style="margin-bottom:20px">
          <div style="display:flex;justify-content:flex-end;margin-bottom:12px">
            <div style="max-width:70%;padding:10px 16px;border-radius:8px;background:#4fc3f7;color:#fff;font-size:13px">
              {{ msg.userMessage }}
            </div>
          </div>

          <div v-if="msg.type === 'error'" style="padding:12px;background:#fff0f0;border:1px solid #ffcdd2;border-radius:8px;color:#c62828;font-size:13px">
            {{ msg.error }}
          </div>

          <div v-if="msg.type === 'result' && msg.orchestrator" style="background:#fff;border:1px solid #e0e0e0;border-radius:10px;overflow:hidden">
            <div v-if="msg.intent && msg.intent.parsed_result" style="padding:12px 16px;background:#f5f5f5;border-bottom:1px solid #eee;font-size:13px;color:#555">
              {{ msg.intent.for_display }}
            </div>

            <div v-if="msg.orchestrator.phase_results" style="padding:12px 16px">
              <div v-for="phase in msg.orchestrator.phase_results" :key="phase.phase" style="margin-bottom:12px">
                <div style="display:flex;align-items:center;gap:8px;margin-bottom:8px">
                  <div :style="{ width:28, height:28, borderRadius:'50%', background: phase.agents.every(a => a.status === 'completed') ? '#4caf50' : '#ff9800', color:'#fff', display:'flex', alignItems:'center', justifyContent:'center', fontSize:12, fontWeight:700 }">{{ phase.phase }}</div>
                  <span style="font-size:14px;font-weight:600;color:#333">
                    阶段 {{ phase.phase }}
                    <span v-if="phase.phase === 1">— 分析层</span>
                    <span v-else-if="phase.phase === 2">— 决策层</span>
                    <span v-else>— 输出层</span>
                  </span>
                </div>
                <div style="margin-left:36px">
                  <div v-for="agent in phase.agents" :key="agent.task_type" style="display:flex;align-items:center;gap:8px;padding:6px 0;border-bottom:1px solid #f5f5f5;font-size:13px">
                    <span style="font-size:16px">{{ statusIcon(agent.status) }}</span>
                    <span style="flex:1;color:#333">{{ agent.task_label }}</span>
                    <span :style="{fontSize:11,color:statusColor(agent.status),fontWeight:500}">
                      {{ agent.status === 'completed' ? '完成' : agent.status === 'skipped' ? '跳过' : '失败' }}
                    </span>
                  </div>
                </div>
              </div>
            </div>

            <div v-if="msg.orchestrator.final_report" style="padding:12px 16px;border-top:1px solid #eee;background:#fafafa">
              <div style="font-size:12px;color:#888;margin-bottom:4px">
                报告摘要
                <span style="margin-left:8px;font-weight:600;color:#2e7d32">
                  {{ msg.orchestrator.final_report.completed_tasks }}/{{ msg.orchestrator.final_report.total_tasks }} 完成
                </span>
              </div>
              <div style="font-size:13px;color:#333;line-height:1.6;white-space:pre-wrap">{{ msg.orchestrator.final_report.summary }}</div>
            </div>
          </div>
        </div>

        <div v-if="loading" style="display:flex;justify-content:flex-start;align-items:center;gap:8px;padding:12px 16px">
          <div class="loading-dot" style="width:8px;height:8px;border-radius:50%;background:#4fc3f7;animation:pulse 1.2s infinite"></div>
          <div class="loading-dot" style="width:8px;height:8px;border-radius:50%;background:#4fc3f7;animation:pulse 1.2s infinite 0.2s"></div>
          <div class="loading-dot" style="width:8px;height:8px;border-radius:50%;background:#4fc3f7;animation:pulse 1.2s infinite 0.4s"></div>
          <span style="font-size:13px;color:#888;margin-left:6px">智能体协作中...</span>
        </div>
      </div>

      <div style="border-top:1px solid #eee;padding:12px;display:flex;gap:12px">
        <textarea v-model="input" @keydown="handleKeydown" placeholder="输入你的需求，如：分析数码类目，推荐3个爆款" style="flex:1;padding:10px;border:1px solid #ddd;border-radius:6px;font-size:13px;resize:none;height:44px"></textarea>
        <button class="btn btn-primary" :disabled="loading || !input.trim()" @click="sendMessage()">发送</button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.preset-btn {
  background: #f0f4ff; border: 1px solid #c5d3f0; color: #3f51b5;
  padding: 8px 14px; border-radius: 20px; font-size: 13px; cursor: pointer;
  transition: all 0.2s;
}
.preset-btn:hover { background: #e3ecff; border-color: #3f51b5; }
@keyframes pulse { 0%, 100% { opacity: 0.4; } 50% { opacity: 1; } }
.loading-dot { animation: pulse 1.2s infinite; }
</style>
