<script setup>
import axios from 'axios'
import { ref } from 'vue'

const props = defineProps({
  mapReady: { type: Boolean, default: false },
  center: { type: Object, default: null }
})
const emit = defineEmits(['results', 'route'])
const query = ref('')
const message = ref('未配置 DeepSeek Key 时自动使用规则检索，地图结果始终来自 PostGIS。')
const pending = ref(false)
const result = ref(null)

const search = async () => {
  if (!props.mapReady || pending.value || !query.value.trim()) return
  pending.value = true
  result.value = null
  message.value = '正在解析需求并检索已收录景点…'
  try {
    const response = await axios.post('http://127.0.0.1:8010/api/ai/tourism-search', {
      query: query.value.trim(),
      ...(props.center ?? {}),
      max_stops: 4
    }, { timeout: 20000 })
    result.value = response.data
    message.value = result.value.explanation + '；结果共' + result.value.places.features.length + '处'
    if (result.value.unsupported?.length) {
      message.value += '。限制：' + result.value.unsupported.join('、')
    }
    emit('results', result.value.places)
  } catch (error) {
    const detail = error.response?.data?.detail
    message.value = typeof detail === 'string' ? detail : '查询失败，请检查后端或数据库连接'
  } finally {
    pending.value = false
  }
}

const showPreview = () => {
  const stops = result.value?.itinerary_preview?.stops ?? []
  if (stops.length) emit('route', stops)
}
</script>

<template>
  <aside class="natural-search" aria-label="AI辅助景点检索">
    <h2>一句话找景点 <small>DeepSeek / 规则降级</small></h2>
    <p>例如：南京一天历史文化游，不想走太多路；附近5公里博物馆</p>
    <form @submit.prevent="search">
      <input v-model="query" :disabled="!mapReady || pending" maxlength="300"
        type="text" aria-label="描述你的景点需求" placeholder="描述你的景点需求..." />
      <button type="submit" :disabled="!mapReady || pending || !query.trim()">
        {{ pending ? '解析中…' : '查找' }}
      </button>
    </form>
    <p class="natural-message" role="status">{{ message }}</p>
    <template v-if="result?.itinerary_preview?.stops?.length">
      <p class="preview-notice">候选顺序仅按直线距离生成，不代表导航或合理日程。</p>
      <button class="route-button" type="button" @click="showPreview">
        在地图显示{{ result.itinerary_preview.stops.length }}站预览路线
      </button>
    </template>
  </aside>
</template>

<style scoped>
.natural-search {position:absolute;left:20px;bottom:24px;z-index:10;width:min(360px,calc(100vw - 40px));max-height:42vh;overflow-y:auto;box-sizing:border-box;padding:12px 14px;border:1px solid #ddd;border-radius:10px;background:#fff;color:#222;box-shadow:0 3px 12px #0002}
h2 {margin:0;font-size:16px}
h2 small {font-size:11px;font-weight:normal;color:#64748b}
p {margin:7px 0;font-size:12px;color:#475569;line-height:1.5}
form {display:flex;gap:6px}
input {width:100%;min-width:0;padding:9px;border:1px solid #cbd5e1;border-radius:6px}
button {padding:7px 10px;white-space:nowrap;border:0;border-radius:6px;background:#2563eb;color:white;cursor:pointer}
button:disabled {opacity:.55;cursor:not-allowed}
.natural-message {margin-bottom:0}
.preview-notice {color:#9a3412}
.route-button {margin-top:6px;background:#0f766e}
</style>
