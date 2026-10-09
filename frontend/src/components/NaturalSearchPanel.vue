<script setup>
import axios from 'axios'
import { ref } from 'vue'

const props = defineProps({
  mapReady: { type: Boolean, default: false },
  center: { type: Object, default: null }
})
const emit = defineEmits(['results', 'route', 'planned'])
const query = ref('')
const message = ref('输入需求后可查找景点或生成真实道路行程；DeepSeek 不可用时自动规则降级。')
const pending = ref(false)
const planning = ref(false)
const result = ref(null)
const planResult = ref(null)
const maxStops = ref(4)
const budgetHours = ref(8)
const startTime = ref('09:00')
const transportMode = ref('')

const errorMessage = err => {
  const detail = err.response?.data?.detail
  return typeof detail === 'string' ? detail : '无法完成请求，请检查后端、数据库和道路服务'
}

const search = async () => {
  if (!props.mapReady || pending.value || planning.value || !query.value.trim()) return
  pending.value = true
  result.value = null
  message.value = '正在解析需求并检索已收录景点…'
  try {
    const response = await axios.post('http://127.0.0.1:8010/api/ai/tourism-search', {
      query: query.value.trim(),
      ...(props.center ?? {}),
      max_stops: maxStops.value
    }, { timeout: 20000 })
    result.value = response.data
    message.value = result.value.explanation + '；结果共' + result.value.places.features.length + '处'
    if (result.value.unsupported?.length) message.value += '。限制：' + result.value.unsupported.join('、')
    emit('results', result.value.places)
  } catch (err) {
    message.value = errorMessage(err)
  } finally {
    pending.value = false
  }
}

const plan = async () => {
  if (!props.mapReady || pending.value || planning.value || !query.value.trim() || !props.center) return
  planning.value = true
  planResult.value = null
  message.value = '正在筛选真实景点并计算道路时间矩阵；公共路网服务可能需要等待…'
  try {
    const response = await axios.post('http://127.0.0.1:8010/api/ai/itinerary', {
      query: query.value.trim(),
      lng: props.center.lng, lat: props.center.lat,
      max_stops: maxStops.value,
      budget_hours: budgetHours.value,
      start_time: startTime.value,
      ...(transportMode.value ? { transport_mode: transportMode.value } : {})
    }, { timeout: 85000 })
    planResult.value = response.data
    message.value = planResult.value.explanation
    emit('planned', planResult.value)
  } catch (err) {
    message.value = errorMessage(err)
  } finally {
    planning.value = false
  }
}

const showPreview = () => {
  const stops = result.value?.itinerary_preview?.stops ?? []
  if (stops.length) emit('route', stops)
}
</script>

<template>
  <aside class="natural-search" :class="{ 'has-plan': !!planResult }" aria-label="AI文旅行程规划">
    <h2>AI 智慧文旅 <small>DeepSeek + PostGIS + Valhalla</small></h2>
    <p>例如：南京一天历史文化游，不想走太多路，最好驾车。</p>
    <form @submit.prevent="search">
      <input v-model="query" :disabled="!mapReady || pending || planning" maxlength="300"
        type="text" aria-label="描述你的旅游需求" placeholder="描述你想怎样玩南京…" />
      <button type="submit" :disabled="!mapReady || pending || planning || !query.trim()">
        {{ pending ? '检索中…' : '找景点' }}
      </button>
    </form>
    <details class="plan-options">
      <summary>行程参数：{{ maxStops }}站 / {{ budgetHours }}小时 / {{ startTime }}</summary>
      <div class="option-grid">
        <label>景点数量
          <select v-model.number="maxStops" :disabled="planning || pending">
            <option v-for="n in [3, 4, 5, 6]" :key="n" :value="n">{{ n }}站</option>
          </select>
        </label>
        <label>可用时间
          <select v-model.number="budgetHours" :disabled="planning || pending">
            <option v-for="n in [3, 4, 5, 6, 7, 8, 9, 10, 11, 12]" :key="n" :value="n">{{ n }}小时</option>
          </select>
        </label>
        <label>出发时间
          <input v-model="startTime" type="time" aria-label="计划出发时间" :disabled="planning || pending" />
        </label>
        <label>交通方式
          <select v-model="transportMode" :disabled="planning || pending">
            <option value="">根据需求选择</option>
            <option value="pedestrian">步行</option>
            <option value="bicycle">骑行</option>
            <option value="auto">驾车</option>
          </select>
        </label>
      </div>
    </details>
    <button class="plan-button" type="button"
      :disabled="!mapReady || pending || planning || !query.trim() || !center"
      @click="plan">
      {{ planning ? '正在生成道路行程…' : '生成 AI 个性化道路行程' }}
    </button>
    <p class="natural-message" role="status">{{ message }}</p>
    <template v-if="result?.itinerary_preview?.stops?.length && !planResult">
      <button class="route-button" type="button" @click="showPreview">
        显示{{ result.itinerary_preview.stops.length }}站直线顺序预览
      </button>
    </template>
    <section v-if="planResult" class="plan-output" aria-label="AI行程建议">
      <p><strong>{{ planResult.ai_mode === 'deepseek' ? 'DeepSeek 已解析' : '规则降级已启用' }}</strong>
        · {{ planResult.travel_mode === 'auto' ? '驾车' : planResult.travel_mode === 'bicycle' ? '骑行' : '步行' }}
        · {{ planResult.itinerary.distance_km.toFixed(2) }}km /
        {{ planResult.itinerary.duration_minutes.toFixed(1) }}分钟交通时间
      </p>
      <p v-if="planResult.within_time_budget === false" class="plan-alert">该行程预计超过时间预算，请减少景点或延长时间。</p>
      <p v-else-if="planResult.within_time_budget == null" class="plan-alert">停留时长不完整，无法确认是否符合时间预算。</p>
      <details open>
        <summary>查看推荐顺序和暂定时间（{{ planResult.timeline.length }}站）</summary>
        <ol class="plan-timeline">
          <li v-for="stop in planResult.timeline" :key="stop.id">
            <strong>{{ stop.arrival_time ?? '时间未确定' }} · {{ stop.name }}</strong>
            <small>{{ stop.reason }}</small>
            <small>预计停留：{{ stop.visit_duration == null ? '未知' : stop.visit_duration + '分钟' }}
              · 离开：{{ stop.departure_time ?? '未确定' }}</small>
          </li>
        </ol>
      </details>
      <details>
        <summary>查看规划限制与注意事项</summary>
        <ul><li v-for="item in planResult.limitations" :key="item">{{ item }}</li></ul>
      </details>
    </section>
  </aside>
</template>

<style scoped>
.natural-search {
  position: relative;
  width: 100%;
  max-height: min(35vh, 290px);
  overflow-y: auto;
  box-sizing: border-box;
  padding: 13px;
  border: 1px solid #dbe4ee;
  border-radius: 12px;
  background: white;
  color: #26374b;
  box-shadow: 0 4px 16px #12253e26;
  text-align: left;
}
.natural-search.has-plan { max-height: min(49vh, 470px); }
h2 { margin: 0; font-size: 15px; color: #1c3047; }
h2 small { font-size: 10px; font-weight: 400; color: #738399; }
p { margin: 6px 0; font-size: 12px; color: #687a8d; line-height: 1.45; }
form { display: flex; gap: 6px; }
form input { width: 100%; min-width: 0; padding: 9px; border: 1px solid #d2ddea; border-radius: 8px; }
button { padding: 8px 10px; border: 0; border-radius: 8px; background: #2563eb; color: #fff; cursor: pointer; white-space: nowrap; }
button:disabled { opacity: .55; cursor: not-allowed; }
.plan-options { margin-top: 8px; border: 1px solid #e2e8f0; border-radius: 7px; }
.plan-options summary, .plan-output summary { font-size: 12px; font-weight: 600; cursor: pointer; padding: 8px; }
.option-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 6px; padding: 8px; }
.option-grid label { display: grid; gap: 2px; color: #64748b; font-size: 11px; }
.option-grid select, .option-grid input { width: 100%; min-width: 0; padding: 6px 3px; border: 1px solid #cbd5e1; border-radius: 5px; font-size: 12px; background: #fff; color: #243447; }
.plan-button { width: 100%; margin-top: 8px; background: #0f766e; font-weight: 700; }
.natural-message { max-height: 55px; overflow-y: auto; font-size: 11px; }
.route-button { margin-top: 6px; background: #2563eb; }
.plan-output { padding-top: 8px; border-top: 1px solid #e2e8f0; }
.plan-output p strong { color: #0f766e; }
.plan-alert { color: #a34115; font-weight: 600; }
.plan-output details { border-top: 1px solid #eef2f7; }
.plan-timeline { padding-left: 20px; margin: 5px 0 8px; font-size: 12px; }
.plan-timeline li { padding: 5px 0; }
.plan-timeline small { display: block; color: #64748b; line-height: 1.5; }
.plan-output ul { padding-left: 20px; margin: 6px 0; font-size: 11px; color: #64748b; }
</style>
