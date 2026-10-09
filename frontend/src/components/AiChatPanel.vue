<script setup>
import axios from 'axios'
import { computed, ref } from 'vue'

const props = defineProps({
  plan: { type: Object, required: true },
  currentRouteIds: { type: Array, default: () => [] },
  disabled: { type: Boolean, default: false },
})
const emit = defineEmits(['applied'])
const input = ref('')
const messages = ref([])
const pending = ref(false)
const applying = ref(false)
const error = ref('')
const preview = ref(null)

const currentState = computed(() => ({
  place_ids: props.plan.itinerary.optimized_order_ids,
  locked_place_ids: props.plan.locked_place_ids ?? [],
  transport_mode: props.plan.travel_mode,
  budget_hours: props.plan.budget_minutes / 60,
  start_time: props.plan.start_time,
}))
const matchesBase = computed(() => {
  const base = preview.value?.base_state
  const state = currentState.value
  return !!base &&
    JSON.stringify(base.place_ids) === JSON.stringify(state.place_ids) &&
    JSON.stringify([...base.locked_place_ids].sort()) ===
      JSON.stringify([...state.locked_place_ids].sort()) &&
    base.transport_mode === state.transport_mode &&
    base.budget_hours === state.budget_hours &&
    base.start_time === state.start_time &&
    JSON.stringify(props.currentRouteIds) === JSON.stringify(state.place_ids)
})
const canConfirm = computed(() => !props.disabled && !pending.value &&
  !applying.value && matchesBase.value)
const readableError = err => typeof err.response?.data?.detail === 'string'
  ? err.response.data.detail : '请求失败，请检查后端、网络或道路服务'

const send = async () => {
  const message = input.value.trim()
  if (!message || props.disabled || pending.value || applying.value) return
  const history = messages.value.slice(-6).map(item => ({
    role: item.role, content: item.text.slice(0, 300),
  }))
  preview.value = null // A new message discards the prior, unconfirmed preview.
  messages.value.push({ role: 'user', text: message })
  input.value = ''
  error.value = ''
  pending.value = true
  try {
    const response = await axios.post(
      'http://127.0.0.1:8010/api/ai/itinerary/chat/preview',
      { message, history, ...currentState.value },
      { timeout: 25000 },
    )
    preview.value = response.data
    messages.value.push({ role: 'assistant', text: response.data.reply +
      ' ' + response.data.changes.join('；') })
  } catch (err) {
    error.value = readableError(err)
    messages.value.push({ role: 'assistant', text: '本次未生成修改预览：' + error.value })
  } finally {
    pending.value = false
  }
}

const confirm = async () => {
  if (!canConfirm.value) return
  applying.value = true
  error.value = ''
  try {
    const response = await axios.post(
      'http://127.0.0.1:8010/api/ai/itinerary/replan',
      preview.value.proposed,
      { timeout: 120000 },
    )
    const result = response.data
    // The existing App.vue handler only redraws after a successful response.
    preview.value = null
    messages.value.push({ role: 'assistant',
      text: '已确认并重新计算实际道路与时间。' +
        (result.dropped_place_ids?.length
          ? ' 因预算约束自动减少了' + result.dropped_place_ids.length + '站。' : '') })
    emit('applied', result)
  } catch (err) {
    error.value = readableError(err)
    messages.value.push({ role: 'assistant',
      text: '未修改原行程，重新规划失败：' + error.value })
  } finally {
    applying.value = false
  }
}
const cancel = () => {
  if (applying.value) return
  preview.value = null
  error.value = ''
  messages.value.push({ role: 'assistant', text: '已取消本次修改，原行程保持不变。' })
}
</script>

<template>
  <section class="chat-assistant" aria-label="AI 多轮行程助手">
    <details>
      <summary>AI 多轮行程助手 · 先预览再确认</summary>
      <div class="chat-content">
        <p class="chat-note">例如：第二站换成自然风光类；第三站必须保留。也可要求改为骑行、缩短到6小时。
          助手只解析修改指令，不提供未经核实的景点或开放时间。</p>
        <p v-if="disabled" class="chat-warning">当前存在待应用的手动编辑，或地图与日程不一致。
          请先重新规划或同步地图路线，再使用对话助手。</p>
        <div class="chat-transcript" role="log" aria-live="polite">
          <p v-if="!messages.length" class="chat-placeholder">请在下方输入对当前行程的修改要求。</p>
          <div v-for="(msg, index) in messages" :key="index"
            :class="['chat-bubble', msg.role === 'user' ? 'from-user' : 'from-assistant']">
            <strong>{{ msg.role === 'user' ? '你' : '行程助手' }}</strong>
            <p>{{ msg.text }}</p>
          </div>
        </div>
        <form @submit.prevent="send">
          <input v-model="input" type="text" maxlength="300" aria-label="用自然语言调整当前行程"
            placeholder="如：第三站锁定，第二站换成公园…"
            :disabled="disabled || pending || applying"/>
          <button type="submit" :disabled="disabled || pending || applying || !input.trim()">
            {{ pending ? '解析中…' : '预览修改' }}
          </button>
        </form>
        <div v-if="preview" class="change-preview" aria-label="尚未应用的修改预览">
          <strong>待确认的修改（尚未改变地图）</strong>
          <ol><li v-for="(change, i) in preview.changes" :key="i">{{ change }}</li></ol>
          <p>预期景点顺序：{{ preview.selected_names.join(' → ') }}</p>
          <p>交通：{{ preview.proposed.transport_mode === 'auto' ? '驾车' : preview.proposed.transport_mode === 'bicycle' ? '骑行' : '步行' }}，
            {{ preview.proposed.budget_hours }}小时，从{{ preview.proposed.start_time }}开始</p>
          <p v-for="warning in preview.warnings" :key="warning" class="chat-note">{{ warning }}</p>
          <p v-if="!matchesBase" class="chat-warning" role="alert">
            当前行程或锁定状态已变化，这份预览已过期，请重新输入指令。
          </p>
          <div class="chat-actions">
            <button type="button" :disabled="!canConfirm" @click="confirm">
              {{ applying ? '实际道路计算中…' : '确认修改并重新规划' }}
            </button>
            <button type="button" class="cancel-button" :disabled="applying" @click="cancel">取消</button>
          </div>
        </div>
        <p v-if="error" class="chat-warning" role="alert">{{ error }}</p>
        <p class="chat-note">对话历史只保留在当前页面。未确认时不修改地图；失败时仍保留上一次有效道路结果。</p>
      </div>
    </details>
  </section>
</template>

<style scoped>
.chat-assistant { margin-top: 12px; border: 1px solid #c3d7ed; border-radius: 9px; background: #f7fbff; }
.chat-assistant > details > summary { padding: 11px; cursor: pointer; font-weight: 700; color: #174582; }
.chat-content { padding: 0 10px 10px; }
.chat-note { font-size: 11px; color: #65748b; line-height: 1.5; margin: 6px 0; }
.chat-warning { color: #9a3412; background: #fff4e5; border-radius: 6px; padding: 8px; font-size: 11px; }
.chat-transcript { max-height: 170px; overflow-y: auto; display: grid; gap: 7px; padding: 7px 0; }
.chat-placeholder { margin: 5px 0; font-size: 11px; color: #64748b; }
.chat-bubble { border-radius: 9px; padding: 7px 9px; background: #eef2f7; font-size: 11px; }
.chat-bubble.from-user { background: #e1efff; }
.chat-bubble strong { display: block; margin-bottom: 3px; color: #27486e; }
.chat-bubble p { margin: 0; overflow-wrap: anywhere; line-height: 1.5; color: #1e293b; }
form { display: flex; gap: 6px; margin-top: 8px; }
form input { min-width: 0; flex: 1; border: 1px solid #cbd5e1; border-radius: 7px; padding: 8px; background: white; }
form button, .chat-actions button { border: 0; border-radius: 7px; padding: 8px; color: white; background: #2563eb; font-size: 11px; cursor: pointer; }
button:disabled { opacity: .5; cursor: not-allowed; }
.change-preview { margin-top: 10px; border: 1px solid #bed9c6; background: white; border-radius: 8px; padding: 10px; }
.change-preview strong { font-size: 12px; color: #12613b; }
.change-preview ol { padding-left: 20px; margin: 6px 0; font-size: 11px; line-height: 1.6; }
.change-preview p { font-size: 11px; margin: 6px 0; }
.chat-actions { display: flex; gap: 6px; margin-top: 8px; }
.chat-actions .cancel-button { background: #e2e8f0; color: #25374b; }
</style>
