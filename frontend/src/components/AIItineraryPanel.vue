<script setup>
import { reactive, ref } from 'vue'
import axios from 'axios'

const emit = defineEmits(['apply'])
const storageKey = 'smart-tourism-saved-itineraries-v1'
const apiRoot = 'http://127.0.0.1:8010/api/ai/itinerary'
const request = reactive({
  location: '南京历史文化', days: 1, style: '历史文化',
  people: '普通游客', walking_limit: '中等', max_stops: 4,
  travel_mode: 'pedestrian'
})
const result = ref(null)
const preview = ref(null)
const saved = ref(readSaved())
const error = ref('')
const notice = ref('')
const loading = ref(false)
const expanded = ref(false)
let requestSeq = 0

function validSnapshot(item) {
  return item && item.version === 1 && typeof item.id === 'string' &&
    typeof item.title === 'string' && item.title.length <= 120 &&
    Array.isArray(item.place_ids) && item.place_ids.length >= 2 &&
    item.place_ids.length <= 6 &&
    item.place_ids.every(id => Number.isInteger(id) && id > 0) &&
    new Set(item.place_ids).size === item.place_ids.length &&
    ['pedestrian', 'bicycle', 'auto'].includes(item.mode)
}
function readSaved() {
  try {
    const value = JSON.parse(localStorage.getItem(storageKey) || '[]')
    return Array.isArray(value) ? value.filter(validSnapshot).slice(0, 15) : []
  } catch {
    return []
  }
}
function persist() {
  try {
    localStorage.setItem(storageKey, JSON.stringify(saved.value))
    return true
  } catch {
    error.value = '浏览器本地存储失败；当前方案仍可使用'
    return false
  }
}
function ids(plan) {
  return (plan?.stops || []).map(s => s.id)
}
function apply(plan) {
  if (!plan?.selected_places?.features?.length) return
  result.value = plan
  preview.value = null
  emit('apply', plan)
  notice.value = plan.route?.status === 'verified_by_routing_service'
    ? '已加载真实 Valhalla 道路路线'
    : '已加载数据库景点；地图蓝线仅为直线顺序预览，非实际道路'
}
async function generate(onlyPreview = false) {
  if (!request.location.trim()) { error.value = '请输入旅游需求'; return }
  if (loading.value) return
  error.value = ''
  notice.value = ''
  loading.value = true
  const seq = ++requestSeq
  try {
    const payload = { ...request }
    if (onlyPreview) {
      payload.walking_limit = '低'
      payload.max_stops = Math.max(2, Math.min(6, ids(result.value).length - 1))
    }
    const response = await axios.post(apiRoot + '/generate', payload, { timeout: 30000 })
    if (seq !== requestSeq) return
    if (onlyPreview) {
      preview.value = response.data
      notice.value = '这是待确认的优化方案，当前地图没有变化'
    } else {
      apply(response.data)
    }
  } catch (err) {
    if (seq !== requestSeq) return
    error.value = err?.response?.data?.detail || '规划失败：请检查后端、数据库或连接'
  } finally {
    if (seq === requestSeq) loading.value = false
  }
}
function save() {
  if (!result.value || ids(result.value).length < 2) return
  const item = {
    version: 1,
    id: typeof crypto !== 'undefined' && crypto.randomUUID
      ? crypto.randomUUID() : String(Date.now()) + '-' + String(Math.random()),
    title: String(result.value.title || '我的行程').slice(0, 120),
    place_ids: ids(result.value),
    mode: result.value.mode || 'pedestrian',
    saved_at: new Date().toISOString()
  }
  if (!validSnapshot(item)) { error.value = '当前行程无法保存'; return }
  saved.value = [item, ...saved.value].slice(0, 15)
  if (persist()) notice.value = '行程已保存到当前浏览器（不会同步到云端）'
}
async function restore(item) {
  if (!validSnapshot(item) || loading.value) return
  loading.value = true
  error.value = ''
  const seq = ++requestSeq
  try {
    const response = await axios.post(apiRoot + '/restore', {
      place_ids: item.place_ids, travel_mode: item.mode
    }, { timeout: 30000 })
    if (seq !== requestSeq) return
    apply(response.data)
    notice.value = '已从数据库重新核实 POI，并重新尝试计算道路'
  } catch (err) {
    if (seq !== requestSeq) return
    error.value = err?.response?.data?.detail || '恢复失败；当前地图与行程保持不变'
  } finally {
    if (seq === requestSeq) loading.value = false
  }
}
function removeSaved(id) {
  saved.value = saved.value.filter(item => item.id !== id)
  persist()
}
function download(data, filename, mediaType) {
  const blob = new Blob([JSON.stringify(data, null, 2)], { type: mediaType })
  const url = URL.createObjectURL(blob)
  const anchor = document.createElement('a')
  anchor.href = url
  anchor.download = filename
  anchor.click()
  setTimeout(() => URL.revokeObjectURL(url), 1000)
}
function exportJson() {
  if (result.value) download(result.value, 'smart-tourism-itinerary.json', 'application/json')
}
function exportRoad() {
  const road = result.value?.route
  if (road?.status !== 'verified_by_routing_service' || !road.geojson) {
    error.value = '没有经道路服务核验的 GeoJSON 路线，不能导出直线为道路'
    return
  }
  download(road.geojson, 'smart-tourism-road.geojson', 'application/geo+json')
}
function escapeHtml(value) {
  return String(value ?? '').replace(/[&<>"']/g, c => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
  })[c])
}
function printReport() {
  if (!result.value) return
  const w = window.open('', '_blank')
  if (!w) { error.value = '浏览器阻止了打印窗口，请允许弹出窗口'; return }
  const plan = result.value
  const road = plan.route
  const roadInfo = road?.status === 'verified_by_routing_service'
    ? `Valhalla道路距离：${escapeHtml(road.distance_km)} km；预计交通时间：${escapeHtml(road.duration_minutes)} 分钟`
    : '路线尚未通过道路服务核验，不能提供道路距离与预计交通时间。'
  const list = (plan.stops || []).map((s, i) =>
    `<li><b>${i + 1}. ${escapeHtml(s.name)}</b>（${escapeHtml(s.category)}）— ${escapeHtml(s.reason)}</li>`
  ).join('')
  w.document.write(`<!doctype html><html lang="zh"><head><meta charset="utf-8"><title>行程报告</title>
    <style>body{font:15px/1.7 sans-serif;margin:32px auto;max-width:760px;color:#222}h1{font-size:24px}li{margin:12px 0}
    @media print{body{margin:18mm}}</style></head><body>
    <h1>${escapeHtml(plan.title)}</h1><p>${escapeHtml(plan.summary)}</p><ol>${list}</ol>
    <p>${roadInfo}</p><p>景点来自PostGIS；路线如有道路距离则来自Valhalla。地图底图 © OpenStreetMap contributors。</p>
    <p>开放时间、门票、客流、无障碍条件未独立核实；路线不代表实时交通或实际入园许可。</p>
    </body></html>`)
  w.document.close()
  w.focus()
  w.print()
}
</script>

<template>
  <section class="ai-itinerary-panel" aria-label="AI 行程工作台">
    <button type="button" class="ai-toggle" @click="expanded = !expanded">
      {{ expanded ? '收起' : '展开' }} AI 行程 · 保存 · 报告
    </button>
    <div v-if="expanded" class="ai-content">
      <h3>AI + PostGIS 真实景点行程</h3>
      <label>旅行需求
        <textarea v-model="request.location" maxlength="160" rows="2"
          placeholder="南京一日历史文化，老人同行，少步行" />
      </label>
      <div class="ai-fields">
        <label>兴趣主题 <input v-model="request.style" maxlength="80" /></label>
        <label>同行人员 <input v-model="request.people" maxlength="80" /></label>
        <label>步行强度
          <select v-model="request.walking_limit">
            <option>低</option><option>中等</option><option>高</option>
          </select>
        </label>
        <label>景点数量
          <select v-model.number="request.max_stops">
            <option :value="2">2</option><option :value="3">3</option>
            <option :value="4">4</option><option :value="5">5</option>
            <option :value="6">6</option>
          </select>
        </label>
        <label>交通方式
          <select v-model="request.travel_mode">
            <option value="pedestrian">步行</option>
            <option value="bicycle">骑行</option>
            <option value="auto">驾车</option>
          </select>
        </label>
      </div>
      <button type="button" :disabled="loading" @click="generate(false)">
        {{ loading ? '生成中…' : '生成并加载到地图' }}
      </button>
      <p v-if="error" role="alert" class="ai-error">{{ error }}</p>
      <p v-if="notice" role="status" class="ai-notice">{{ notice }}</p>
      <div v-if="result" class="ai-results">
        <h4>{{ result.title }}</h4>
        <p>{{ result.summary }}</p>
        <small>排序方式：{{ result.planning_method === 'deepseek_ranked_verified_ids' ? 'DeepSeek从真实POI中排序' : '数据库规则排序（AI未使用或不可用）' }}</small>
        <ol><li v-for="s in result.stops" :key="s.id">{{ s.name }} · {{ s.category }}<small> — {{ s.reason }}</small></li></ol>
        <p v-if="result.route?.status === 'verified_by_routing_service'">
          Valhalla道路：{{ result.route.distance_km }} km，约 {{ result.route.duration_minutes }} 分钟
        </p>
        <p v-else>道路未核验；地图直线只作景点顺序预览。</p>
        <div class="ai-actions">
          <button type="button" :disabled="loading" @click="generate(true)">减少景点并预览</button>
          <button type="button" @click="save">保存到我的行程</button>
          <button type="button" @click="exportJson">导出行程 JSON</button>
          <button type="button" :disabled="result.route?.status !== 'verified_by_routing_service'" @click="exportRoad">导出道路 GeoJSON</button>
          <button type="button" @click="printReport">打印报告 / 另存 PDF</button>
        </div>
      </div>
      <div v-if="preview" class="ai-preview">
        <h4>待确认优化方案</h4>
        <p>{{ preview.stops.map(s => s.name).join(' → ') }}</p>
        <button type="button" @click="apply(preview)">确认替换当前行程</button>
        <button type="button" @click="preview = null">放弃调整</button>
      </div>
      <div class="ai-saved">
        <h4>我的行程（仅当前浏览器）</h4>
        <p v-if="!saved.length">暂无保存记录</p>
        <div v-for="item in saved" :key="item.id" class="ai-saved-item">
          <span>{{ item.title }} · {{ item.place_ids.length }}站</span>
          <button type="button" :disabled="loading" @click="restore(item)">恢复并核实</button>
          <button type="button" @click="removeSaved(item.id)">删除</button>
        </div>
      </div>
    </div>
  </section>
</template>

<style scoped>
.ai-itinerary-panel{position:absolute;z-index:12;right:20px;top:112px;width:310px;max-width:calc(100vw - 40px);
  background:#fff;color:#253046;border:1px solid #cbd5e1;border-radius:10px;box-shadow:0 3px 14px #0002;
  text-align:left;font-size:13px}
.ai-toggle{width:100%;background:#e9f0ff;color:#1e3a8a;border:0;padding:11px;font-weight:700;cursor:pointer}
.ai-content{padding:12px;overflow:auto;max-height:calc(100vh - 460px);min-height:0}
.ai-content h3,.ai-content h4{font-size:14px;margin:6px 0}
.ai-content label{display:block;font-size:12px}
.ai-content textarea,.ai-content input,.ai-content select{width:100%;box-sizing:border-box;padding:7px;
  border:1px solid #aeb9ca;border-radius:5px;background:#fff;color:#222}
.ai-fields{display:grid;grid-template-columns:1fr 1fr;gap:7px;margin:9px 0}
.ai-content button{padding:7px;margin:3px 3px 3px 0;background:#f5f8fe;color:#1d3557;
  border:1px solid #a8b9d2;border-radius:5px;cursor:pointer}
.ai-content button:disabled{opacity:.45;cursor:not-allowed}
.ai-content p{margin:6px 0}
.ai-error{color:#ad182b}.ai-notice{color:#0e6b49}
.ai-results,.ai-preview,.ai-saved{margin-top:10px;padding-top:7px;border-top:1px solid #d9e1ee}
.ai-saved-item{border-bottom:1px solid #eee;padding:5px 0}
.ai-saved-item span{display:block}
.ai-results ol{padding-left:22px}
@media(max-height:650px){.ai-content{max-height:38vh}}
</style>
