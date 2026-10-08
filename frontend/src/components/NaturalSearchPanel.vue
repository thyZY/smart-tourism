<script setup>
import axios from 'axios'
import { ref } from 'vue'

const props = defineProps({
  mapReady: { type: Boolean, default: false },
  center: { type: Object, default: null }
})
const emit = defineEmits(['results'])
const query = ref('')
const message = ref('本功能采用可解释的规则检索，尚未接入大模型。')
const pending = ref(false)

const search = async () => {
  if (!props.mapReady || pending.value || !query.value.trim()) return
  pending.value = true
  message.value = '正在检索已收录景点…'
  try {
    const response = await axios.get('http://127.0.0.1:8010/api/places/natural', {
      params: {
        query: query.value.trim(),
        ...(props.center ?? {})
      },
      timeout: 10000
    })
    const result = response.data
    message.value = result.explanation + '；结果共' + result.places.features.length + '处'
    emit('results', result.places)
  } catch (error) {
    message.value = error.response?.data?.detail || '查询失败，请检查后端连接'
  } finally {
    pending.value = false
  }
}
</script>

<template>
  <aside class="natural-search" aria-label="自然语言景点检索">
    <h2>一句话找景点 <small>规则检索 MVP</small></h2>
    <p>例如：附近5公里的博物馆、南京历史文化景点</p>
    <form @submit.prevent="search">
      <input v-model="query" :disabled="!mapReady || pending" maxlength="300"
        type="text" aria-label="描述你的景点需求" placeholder="描述你的景点需求..." />
      <button type="submit" :disabled="!mapReady || pending || !query.trim()">
        {{ pending ? '查询中…' : '查找' }}
      </button>
    </form>
    <p class="natural-message" role="status">{{ message }}</p>
  </aside>
</template>

<style scoped>
.natural-search {position:absolute;left:20px;bottom:24px;z-index:10;width:min(360px,calc(100vw - 40px));box-sizing:border-box;padding:12px 14px;border:1px solid #ddd;border-radius:10px;background:#fff;color:#222;box-shadow:0 3px 12px #0002}
h2 {margin:0;font-size:16px}
h2 small {font-size:11px;font-weight:normal;color:#64748b}
p {margin:7px 0;font-size:12px;color:#475569;line-height:1.5}
form {display:flex;gap:6px}
input {width:100%;min-width:0;padding:9px;border:1px solid #cbd5e1;border-radius:6px}
button {padding:7px 10px;white-space:nowrap;border:0;border-radius:6px;background:#2563eb;color:white;cursor:pointer}
button:disabled {opacity:.55;cursor:not-allowed}
.natural-message {margin-bottom:0}
</style>
