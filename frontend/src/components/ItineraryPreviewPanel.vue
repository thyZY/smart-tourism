<script setup>
import axios from 'axios'
import { ref } from 'vue'

const props = defineProps({
  mapReady: { type: Boolean, default: false },
  center: { type: Object, default: null }
})
const emit = defineEmits(['route', 'expanded-change'])
const expanded = ref(false)

const handleToggle = (event) => {
  expanded.value = event.currentTarget.open
  emit('expanded-change', expanded.value)
}
const query = ref('')
const maxStops = ref(4)
const pending = ref(false)
const result = ref(null)
const error = ref('')

const preview = async () => {
  if (!props.mapReady || pending.value) return
  pending.value = true
  error.value = ''
  try {
    const response = await axios.get('http://127.0.0.1:8010/api/places/itinerary-preview', {
      params: { ...(props.center ?? {}), max_stops: maxStops.value, query: query.value.trim() },
      timeout: 10000
    })
    result.value = response.data
    emit('route', result.value.stops)
  } catch (err) {
    error.value = err.response?.data?.detail || '预览生成失败，请确认后端运行状态'
    result.value = null
  } finally {
    pending.value = false
  }
}
</script>

<template>
  <aside class="preview-panel" :class="{ 'is-expanded': expanded }" aria-label="景点顺序预览">
    <details @toggle="handleToggle">
      <summary>景点顺序预览（直线距离）</summary>
      <p>根据地图中心和已收录景点生成候选顺序，不是道路导航。</p>
      <form @submit.prevent="preview">
        <input v-model="query" maxlength="300" aria-label="筛选景点（可选）"
          placeholder="可选：如历史文化景点" :disabled="pending || !mapReady" />
        <label for="stop-count">站点</label>
        <select id="stop-count" v-model.number="maxStops" :disabled="pending">
          <option v-for="count in [2,3,4,5,6]" :key="count" :value="count">{{ count }}</option>
        </select>
        <button type="submit" :disabled="pending || !mapReady">{{ pending ? '计算中…' : '生成' }}</button>
      </form>
      <p v-if="error" class="error" role="alert">{{ error }}</p>
      <template v-if="result">
        <p>{{ result.explanation }}</p>
        <ol>
          <li v-for="place in result.stops" :key="place.properties.id">{{ place.properties.name }}</li>
        </ol>
        <p>景点间直线距离合计：{{ result.between_stops_direct_km.toFixed(2) }} km</p>
        <p>含地图中心起点：{{ result.from_origin_direct_km.toFixed(2) }} km</p>
        <p class="notice">{{ result.limitations.join('；') }}</p>
      </template>
    </details>
  </aside>
</template>

<style scoped>
.preview-panel {
  position: relative;
  width: 100%;
  flex: 0 0 auto;
  min-height: 0;
  max-height: none;
  overflow-y: auto;
  box-sizing: border-box;
  border: 1px solid #dbe4ee;
  border-radius: 12px;
  background: #fff;
  color: #26374b;
  box-shadow: 0 3px 14px #12253e1c;
  text-align: left;
}
summary { cursor: pointer; padding: 12px 14px; font-size: 13px; font-weight: 700; }
summary:focus-visible { outline: 2px solid #2563eb; outline-offset: -3px; }
details > p, ol, form { margin: 8px 13px; font-size: 12px; line-height: 1.55; }
form { display: flex; flex-wrap: wrap; align-items: center; gap: 5px; }
input { flex: 1; min-width: 130px; padding: 7px; border: 1px solid #cbd5e1; border-radius: 6px; }
select { padding: 6px; border: 1px solid #cbd5e1; border-radius: 6px; }
button { padding: 7px 9px; background: #2563eb; border: 0; border-radius: 7px; color: white; cursor: pointer; }
button:disabled { opacity: .5; cursor: not-allowed; }
ol { max-height: 100px; overflow: auto; padding-left: 25px; }
.notice { color: #64748b; }
.error { color: #b42318; }
</style>
