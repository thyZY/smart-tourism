<script setup>
import axios from 'axios'
import { computed, ref } from 'vue'

const props = defineProps({
  mapReady: { type: Boolean, default: false },
  center: { type: Object, default: null },
  currentRouteIds: { type: Array, default: () => [] }
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
const editIds = ref([])
const lockedIds = ref([])
const placeChoices = ref([])
const choicesPending = ref(false)
const replanning = ref(false)
const editError = ref('')
const editDirty = ref(false)
const autoTrim = ref(true)
const replaceValue = ref({})
const routeOutOfSync = computed(() => {
  if (!planResult.value) return false
  const expected = planResult.value.itinerary.optimized_order_ids
  return props.currentRouteIds.length !== expected.length ||
    expected.some((id, i) => id !== props.currentRouteIds[i])
})
const editName = id => (
  placeChoices.value.find(p => p.properties.id === id)?.properties.name ??
  planResult.value?.selected_places?.features.find(p => p.properties.id === id)?.properties.name ??
  '未知景点（' + id + '）'
)
const replacementChoices = computed(() =>
  placeChoices.value.filter(p => !editIds.value.includes(p.properties.id))
)
const initEditing = response => {
  editIds.value = [...response.itinerary.optimized_order_ids]
  maxStops.value = editIds.value.length
  lockedIds.value = (response.locked_place_ids || []).filter(id => editIds.value.includes(id))
  editDirty.value = false
  editError.value = ''
  replaceValue.value = {}
}
const toggleLock = id => {
  if (replanning.value) return
  lockedIds.value = lockedIds.value.includes(id)
    ? lockedIds.value.filter(item => item !== id)
    : [...lockedIds.value, id]
  editDirty.value = true
}
const removeStop = id => {
  if (replanning.value || id === editIds.value[0]) return
  if (editIds.value.length <= 3) {
    editError.value = '至少保留3站；可通过替换景点调整行程'
    return
  }
  if (lockedIds.value.includes(id)) {
    editError.value = '请先解除锁定，才能移除这个景点'
    return
  }
  editIds.value = editIds.value.filter(item => item !== id)
  editError.value = ''
  editDirty.value = true
}
const replaceStop = (oldId, rawId) => {
  const id = Number(rawId)
  if (replanning.value || oldId === editIds.value[0] ||
      lockedIds.value.includes(oldId) || !Number.isInteger(id) ||
      editIds.value.includes(id) ||
      !placeChoices.value.some(p => p.properties.id === id)) return
  editIds.value = editIds.value.map(item => item === oldId ? id : item)
  replaceValue.value = {}
  editError.value = ''
  editDirty.value = true
}
const syncFromMap = () => {
  const ids = props.currentRouteIds
  if (ids.length < 3 || ids.length > 6 || new Set(ids).size !== ids.length) {
    editError.value = '请先在地图中选择3—6个不同的景点'
    return
  }
  editIds.value = [...ids]
  lockedIds.value = lockedIds.value.filter(id => ids.includes(id))
  editError.value = ''
  editDirty.value = true
}
const loadChoices = async () => {
  if (choicesPending.value || replanning.value) return
  choicesPending.value = true
  editError.value = ''
  try {
    const response = await axios.get('http://127.0.0.1:8010/api/places', { timeout: 20000 })
    const items = response.data?.features
    if (!Array.isArray(items)) throw new Error('POI列表无效')
    placeChoices.value = items.filter(p =>
      Number.isInteger(p.properties?.id) && p.geometry?.type === 'Point')
  } catch (err) {
    editError.value = errorMessage(err)
  } finally {
    choicesPending.value = false
  }
}
const replan = async () => {
  if (!planResult.value || !props.mapReady || replanning.value || pending.value || planning.value) return
  replanning.value = true
  editError.value = ''
  try {
    const response = await axios.post('http://127.0.0.1:8010/api/ai/itinerary/replan', {
      place_ids: editIds.value,
      locked_place_ids: lockedIds.value,
      transport_mode: transportMode.value || planResult.value.travel_mode,
      budget_hours: budgetHours.value,
      start_time: startTime.value,
      auto_trim: autoTrim.value
    }, { timeout: 120000 })
    planResult.value = response.data
    initEditing(response.data)
    message.value = response.data.explanation
    emit('planned', response.data)
  } catch (err) {
    editError.value = errorMessage(err)
    editDirty.value = true
  } finally {
    replanning.value = false
  }
}

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
  if (!props.mapReady || pending.value || planning.value || replanning.value || !query.value.trim() || !props.center) return
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
    initEditing(response.data)
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
          <select v-model.number="budgetHours" :disabled="planning || pending || replanning"
            @change="planResult && (editDirty = true)">
            <option v-for="n in [3, 4, 5, 6, 7, 8, 9, 10, 11, 12]" :key="n" :value="n">{{ n }}小时</option>
          </select>
        </label>
        <label>出发时间
          <input v-model="startTime" type="time" aria-label="计划出发时间" :disabled="planning || pending || replanning"
            @change="planResult && (editDirty = true)" />
        </label>
        <label>交通方式
          <select v-model="transportMode" :disabled="planning || pending || replanning"
            @change="planResult && (editDirty = true)">
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
      <p><strong>{{ planResult.ai_mode === 'deepseek' ? 'DeepSeek 已解析' : planResult.ai_mode === 'manual_replan' ? '用户调整后重新规划' : '规则降级已启用' }}</strong>
        · {{ planResult.travel_mode === 'auto' ? '驾车' : planResult.travel_mode === 'bicycle' ? '骑行' : '步行' }}
        · {{ planResult.itinerary.distance_km.toFixed(2) }}km /
        {{ planResult.itinerary.duration_minutes.toFixed(1) }}分钟交通时间
      </p>
      <p v-if="planResult.recommendation_summary" class="recommendation-note">
        候选覆盖 {{ planResult.recommendation_summary.distinct_categories }} 种景点类别；
        {{ planResult.recommendation_summary.verified_tag_match_pois }} 个景点有数据库标签与需求词匹配。
        <span>评分是可解释的启发式推荐，不是客观景点评级。</span>
      </p>
      <details v-if="planResult.recommendation_criteria?.length" class="recommendation-method">
        <summary>为什么推荐这些景点？</summary>
        <ul><li v-for="item in planResult.recommendation_criteria" :key="item">{{ item }}</li></ul>
      </details>
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
      <section class="edit-panel" aria-label="动态调整AI行程">
        <h3>调整当前行程</h3>
        <p>上方“景点数量”用于重新生成新行程；本区重新规划以实际编辑后的站点数量为准。</p>
        <p>保留第一站作为起点。可锁定必去景点、替换或移除其他站点；
          修改上方预算、出发时间或交通方式后，点击下方按钮重新计算道路。</p>
        <p v-if="routeOutOfSync" class="plan-alert" role="status">
          地图路线已由外部操作修改，目前左侧仍显示上次AI行程。可以同步地图当前站点。
        </p>
        <button v-if="routeOutOfSync" class="minor-button" type="button" @click="syncFromMap">
          同步地图已选景点
        </button>
        <ol class="editable-stops">
          <li v-for="(id, index) in editIds" :key="id">
            <div class="edit-stop-heading">
              <strong>{{ index + 1 }}. {{ editName(id) }}</strong>
              <small v-if="index === 0">起点固定</small>
            </div>
            <div v-if="index > 0" class="edit-stop-actions">
              <label>
                <input type="checkbox" :checked="lockedIds.includes(id)" :disabled="replanning"
                  @change="toggleLock(id)" /> 锁定必去
              </label>
              <button type="button" class="minor-button"
                :disabled="replanning || lockedIds.includes(id)"
                @click="removeStop(id)">移除</button>
              <select :aria-label="'替换' + editName(id)" :value="replaceValue[id] ?? ''"
                :disabled="replanning || lockedIds.includes(id) || !placeChoices.length"
                @change="replaceStop(id, $event.target.value)">
                <option value="">替换为…</option>
                <option v-for="candidate in replacementChoices" :key="candidate.properties.id"
                  :value="candidate.properties.id">{{ candidate.properties.name }}</option>
              </select>
            </div>
          </li>
        </ol>
        <button v-if="!placeChoices.length" type="button" class="minor-button"
          :disabled="choicesPending || replanning" @click="loadChoices">
          {{ choicesPending ? '正在读取数据库景点…' : '加载可替换景点（PostGIS）' }}
        </button>
        <label class="auto-trim">
          <input v-model="autoTrim" type="checkbox" :disabled="replanning"
            @change="editDirty = true" />
          超时则自动移除末尾未锁定景点（至少保留3站）
        </label>
        <p v-if="editDirty || routeOutOfSync" class="edit-warning" role="status">
          修改尚未应用到地图；旧道路与时间仍是上次计算结果。
        </p>
        <p v-if="editError" class="plan-alert" role="alert">{{ editError }}</p>
        <button type="button" class="plan-button" :disabled="replanning || pending || planning || !mapReady"
          @click="replan">
          {{ replanning ? '重新计算实际道路与时间…' : '重新规划已调整行程' }}
        </button>
        <p v-if="planResult.dropped_place_ids?.length" class="edit-warning">
          预算自动调整：本次已删除{{ planResult.dropped_place_ids.length }}个非锁定景点。
        </p>
      </section>
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
  flex: 1 1 auto;
  min-height: 0;
  height: 100%;
  max-height: none;
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
.natural-search.has-plan { max-height: none; }
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
.recommendation-note { padding: 8px; border-radius: 7px; background: #eef7f6; color: #186055; }
.recommendation-note span { display: block; font-size: 11px; color: #526a6a; margin-top: 3px; }
.plan-output details { border-top: 1px solid #eef2f7; }
.plan-timeline { padding-left: 20px; margin: 5px 0 8px; font-size: 12px; }
.plan-timeline li { padding: 5px 0; }
.plan-timeline small { display: block; color: #64748b; line-height: 1.5; }
.plan-output ul { padding-left: 20px; margin: 6px 0; font-size: 11px; color: #64748b; }
.edit-panel { margin-top: 12px; padding: 10px; border: 1px solid #d1e5e7; border-radius: 9px; background: #f8fcfd; }
.edit-panel h3 { margin: 0 0 5px; font-size: 13px; color: #0f766e; }
.editable-stops { margin: 8px 0; padding-left: 3px; list-style: none; }
.editable-stops li { padding: 8px 0; border-bottom: 1px solid #dce8ec; }
.edit-stop-heading { display: flex; align-items: baseline; justify-content: space-between; gap: 6px; font-size: 12px; }
.edit-stop-heading small { font-size: 10px; color: #64748b; white-space: nowrap; }
.edit-stop-actions { display: flex; flex-wrap: wrap; align-items: center; gap: 5px; margin-top: 5px; }
.edit-stop-actions label, .auto-trim { font-size: 11px; color: #52677c; display: flex; gap: 4px; align-items: center; }
.edit-stop-actions select { width: 100%; max-width: 180px; min-width: 0; padding: 6px 2px; border: 1px solid #cbd5e1; border-radius: 6px; background: white; font-size: 11px; }
.edit-panel .minor-button { background: #e9f1fc; color: #1d4ed8; border: 1px solid #bcd1f3; padding: 6px; font-size: 11px; }
.auto-trim { margin-top: 10px; }
.edit-warning { color: #9a5307; background: #fff7e6; padding: 6px; border-radius: 5px; }
</style>
