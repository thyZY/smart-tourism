<script setup>
import { reactive, ref } from 'vue'
import { api } from '../services/api'

const emit = defineEmits(['apply'])
const storageKey = 'smart-tourism-saved-itineraries-v1'
const request = reactive({
  location: '南京历史文化', days: 1, style: '历史文化',
  people: '普通游客', walking_limit: '中等', max_stops: 4,
  travel_mode: 'pedestrian'
})
const excludedPlaceInput = ref('')
const exclusionSearch = ref('')
const exclusionChoices = ref([])
const selectedExcludedIds = ref([])
const exclusionLoading = ref(false)
const exclusionError = ref('')
async function loadExclusionChoices() {
  if (exclusionLoading.value) return
  exclusionLoading.value = true
  exclusionError.value = ''
  try {
    const response = await api.get('/api/places', { timeout: 10000 })
    const features = response.data?.features
    if (!Array.isArray(features)) throw new Error('invalid POI payload')
    exclusionChoices.value = features.filter(f => Number.isSafeInteger(f?.properties?.id) &&
      f.properties.id > 0 && typeof f.properties.name === 'string')
  } catch {
    exclusionError.value = '无法读取数据库景点，请检查后端连接'
  } finally {
    exclusionLoading.value = false
  }
}
function filteredExclusionChoices() {
  const q = exclusionSearch.value.trim().toLowerCase()
  return exclusionChoices.value.filter(f =>
    !q || f.properties.name.toLowerCase().includes(q) ||
    (f.properties.category || '').toLowerCase().includes(q)).slice(0, 40)
}
function toggleExcludedId(id) {
  if (selectedExcludedIds.value.includes(id)) {
    selectedExcludedIds.value = selectedExcludedIds.value.filter(value => value !== id)
  } else if (selectedExcludedIds.value.length < 40) {
    selectedExcludedIds.value = [...selectedExcludedIds.value, id]
  }
}
const result = ref(null)
const preview = ref(null)
const editInstruction = ref('')
const saved = ref(readSaved())
const error = ref('')
const notice = ref('')
const loading = ref(false)
const expanded = ref(true)
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
    const tokens = excludedPlaceInput.value.trim() ? excludedPlaceInput.value.split(/[,，\s]+/).filter(Boolean) : []
    if (tokens.length > 40 || tokens.some(token => !/^[1-9][0-9]*$/.test(token))) {
      error.value = '排除项须为最多40个正整数景点ID'
      loading.value = false
      return
    }
    const excluded = tokens.map(Number)
    if (excluded.some(id => !Number.isSafeInteger(id)) || new Set(excluded).size !== excluded.length) {
      error.value = '排除景点ID重复或无效'
      loading.value = false
      return
    }
    const combined = [...excluded, ...selectedExcludedIds.value]
    if (new Set(combined).size !== combined.length || combined.length > 40) {
      error.value = '排除项重复或超过40个，请检查选择列表'
      loading.value = false
      return
    }
    const payload = { ...request, excluded_place_ids: combined }
    if (onlyPreview) {
      payload.walking_limit = '低'
      payload.max_stops = Math.max(2, Math.min(6, ids(result.value).length - 1))
    }
    const response = await api.post('/api/ai/itinerary/generate', payload, { timeout: 30000 })
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
async function requestEditPreview() {
  if (!result.value || loading.value) return
  if (!editInstruction.value.trim()) { error.value = '请输入修改要求'; return }
  loading.value = true
  error.value = ''
  preview.value = null
  const seq = ++requestSeq
  try {
    const response = await api.post('/api/ai/itinerary/edit-preview', {
      place_ids: ids(result.value),
      instruction: editInstruction.value.trim(),
      travel_mode: result.value.mode || 'pedestrian'
    }, { timeout: 30000 })
    if (seq !== requestSeq) return
    preview.value = response.data
    notice.value = response.data.edit_summary?.intent_source === 'deepseek_bounded_json'
      ? 'DeepSeek 已提出受限修改意图；地图尚未改变，请确认'
      : '规则修改预览已生成，当前地图未变化；请检查后再确认'
  } catch (err) {
    if (seq === requestSeq) error.value = err?.response?.data?.detail || '修改预览失败，当前行程未变化'
  } finally {
    if (seq === requestSeq) loading.value = false
  }
}
function jumpToSection(sectionId) {
  const root = document.querySelector('.ai-itinerary-panel')
  const target = root?.querySelector('#' + sectionId)
  if (!target) return
  target.scrollIntoView({ behavior: 'smooth', block: 'start' })
}
function confirmPreview() {
  // A preview is advisory until explicit confirmation. Never apply while a new
  // request is running, after manual map edits or without an active plan.
  if (loading.value || !result.value || !preview.value) return
  apply(preview.value)
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
    const response = await api.post('/api/ai/itinerary/restore', {
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
function invalidateCurrent() {
  // Main map was changed manually: previous AI output is no longer the active itinerary.
  requestSeq += 1
  loading.value = false
  result.value = null
  preview.value = null
  error.value = ''
  notice.value = '地图路线已被手动修改；旧AI方案已失效，请重新生成后再保存或导出'
}
defineExpose({ invalidateCurrent })

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
    <div class="ai-panel-intro">
      <div class="ai-title-row"><span class="ai-title-icon" aria-hidden="true">✦</span><div><h3>AI 行程规划</h3><span class="ai-title-kicker">SMART ITINERARY</span></div></div>
      <p>从真实 PostGIS 景点中选择与排序，生成后可保存、修改及导出报告。</p>
    </div>
      <nav v-if="result || preview || saved.length" class="ai-quick-nav" aria-label="行程工作台快捷导航">
        <button type="button" @click="jumpToSection('ai-plan-section')">规划</button>
        <button v-if="result" type="button" @click="jumpToSection('ai-edit-section')">修改行程</button>
        <button v-if="preview" type="button" class="ai-quick-pending" @click="jumpToSection('ai-preview-section')">待确认预览</button>
        <button type="button" @click="jumpToSection('ai-saved-section')">已保存 ({{ saved.length }})</button>
      </nav>
    <div class="ai-content">
      <h4 id="ai-plan-section" class="ai-field-title"><span class="ai-section-index">01</span> 旅行条件</h4>
      <label>旅行需求
        <textarea v-model="request.location" maxlength="160" rows="2"
          placeholder="南京一日历史文化，老人同行，少步行" />
      </label>
      <label>排除景点 ID（可选，逗号分隔）
        <input v-model="excludedPlaceInput" maxlength="240" placeholder="例如 1, 3" />
      </label>
      <div class="ai-exclusion-picker">
        <button type="button" :disabled="exclusionLoading" @click="loadExclusionChoices">
          {{ exclusionLoading ? '读取中…' : '从数据库选择排除景点' }}
        </button>
        <p v-if="exclusionError" role="alert">{{ exclusionError }}</p>
        <template v-if="exclusionChoices.length">
          <input v-model="exclusionSearch" type="search" aria-label="搜索排除景点"
            placeholder="搜索景点名称或类别" />
          <p>已勾选 {{ selectedExcludedIds.length }} 处景点；列表来自当前数据库。</p>
          <div class="ai-exclusion-results">
            <label v-for="feature in filteredExclusionChoices()" :key="feature.properties.id">
              <input type="checkbox"
                :checked="selectedExcludedIds.includes(feature.properties.id)"
                :disabled="selectedExcludedIds.length >= 40 && !selectedExcludedIds.includes(feature.properties.id)"
                @change="toggleExcludedId(feature.properties.id)" />
              {{ feature.properties.name }}（{{ feature.properties.category }}）
            </label>
          </div>
        </template>
      </div>
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
      <button class="ai-primary-action" type="button" :disabled="loading" @click="generate(false)">
        {{ loading ? '生成中…' : '生成并加载到地图' }}
      </button>
      <p v-if="error" role="alert" class="ai-error">{{ error }}</p>
      <p v-if="notice" role="status" class="ai-notice">{{ notice }}</p>
      <div v-if="result" class="ai-results"><div class="ai-card-eyebrow"><span class="ai-status-dot"></span> 当前行程 · 数据库景点</div>
        <h4>{{ result.title }}</h4>
        <p>{{ result.summary }}</p>
        <p v-if="result.excluded_place_ids?.length">已排除景点 ID：{{ result.excluded_place_ids.join('、') }}</p>
        <small>排序方式：{{ result.planning_method === 'deepseek_ranked_verified_ids' ? 'DeepSeek从真实POI中排序' : '数据库规则排序（AI未使用或不可用）' }}</small>
        <details v-if="result.recommendation_audit" class="ai-audit">
          <summary>查看推荐依据与数据限制</summary>
          <p>参与候选：{{ result.recommendation_audit.candidate_count }} 个数据库景点</p>
          <p>{{ result.recommendation_audit.rule }}</p>
          <p v-if="!result.recommendation_audit.score_is_selection_basis">当前由 DeepSeek 排序，以下规则分只是参考，并非模型决策解释。</p>
          <p>未参与决策：{{ result.recommendation_audit.not_considered.join('、') }}</p>
          <p>说明：{{ result.recommendation_audit.limitations }}</p>
        </details>
        <details v-if="result.quality_diagnostics" class="ai-audit">
          <summary>推荐结果质量诊断（非准确率）</summary>
          <p>已选 {{ result.quality_diagnostics.selected_count }} / 候选 {{ result.quality_diagnostics.candidate_count }} 处景点</p>
          <p>类别数：{{ result.quality_diagnostics.distinct_category_count }}；类别多样性比例：{{ result.quality_diagnostics.category_diversity_ratio }}</p>
          <p>规则关键词命中：{{ result.quality_diagnostics.rule_keyword_match_count }} / {{ result.quality_diagnostics.selected_count }}（{{ result.quality_diagnostics.rule_keyword_match_ratio }}）</p>
          <p v-if="!result.quality_diagnostics.rule_is_actual_ranker">仅供对照，不能代表 DeepSeek 的推荐准确率。</p>
          <p>类别构成：{{ Object.entries(result.quality_diagnostics.category_counts).map(([name, count]) => name + ' ' + count).join('、') || '未分类' }}</p>
          <p v-for="limit in result.quality_diagnostics.limitations" :key="limit">{{ limit }}</p>
        </details>
        <details class="ai-stops-disclosure"><summary>查看完整行程站点（{{ result.stops.length }} 站）</summary><ol><li v-for="s in result.stops" :key="s.id">{{ s.name }} · {{ s.category }}<small> — {{ s.reason }}<template v-if="result.recommendation_audit?.score_is_selection_basis && Number.isFinite(s.rule_score)">（规则匹配分：{{ s.rule_score }}）</template></small></li></ol></details>
        <p v-if="result.route?.status === 'verified_by_routing_service'">
          Valhalla道路：{{ result.route.distance_km }} km，约 {{ result.route.duration_minutes }} 分钟
        </p>
        <p v-else>道路未核验；地图直线只作景点顺序预览。</p>
        <div id="ai-edit-section" class="ai-edit-workspace"><h4><span class="ai-section-index">02</span> 修改当前行程</h4>
          <label>按要求修改当前行程（仅生成预览）
            <input v-model="editInstruction" maxlength="160" placeholder="例如：删除中山陵；或将夫子庙调整到第2站" />
          </label>
          <button class="ai-secondary-action" type="button" :disabled="loading" @click="requestEditPreview">生成修改预览</button>
          <small>优先使用规则；配置 DeepSeek API Key 后可解析更灵活的删除或调整站次意图。每轮基于当前已确认行程，不会擅自修改。</small>
        </div>
        <div class="ai-actions">
          <button type="button" :disabled="loading" @click="generate(true)">减少景点并预览</button>
          <button type="button" @click="save">保存到我的行程</button>
          <button type="button" @click="exportJson">导出行程 JSON</button>
          <button type="button" :disabled="result.route?.status !== 'verified_by_routing_service'" @click="exportRoad">导出道路 GeoJSON</button>
          <button type="button" @click="printReport">打印报告 / 另存 PDF</button>
        </div>
      </div>
      <div v-if="preview" id="ai-preview-section" class="ai-preview" role="region" aria-label="待确认的行程修改">
        <h4>待确认优化方案</h4>
        <p>{{ preview.stops.map(s => s.name).join(' → ') }}</p>
        <p v-if="preview.edit_summary">来源：{{ preview.edit_summary.intent_source === 'deepseek_bounded_json' ? 'DeepSeek受限意图' : '确定性规则' }}；操作：{{ preview.edit_summary.operation === 'remove' ? '删除站点' : '调整顺序' }}；匹配景点ID：{{ preview.edit_summary.matched_place_id }}</p>
        <button class="ai-primary-action" type="button" :disabled="loading" @click="confirmPreview">确认替换当前行程</button>
        <button type="button" @click="preview = null">放弃调整</button>
      </div>
      <div id="ai-saved-section" class="ai-saved">
        <h4><span class="ai-section-index">03</span> 本地保存的行程</h4><small class="ai-muted">仅保存在当前浏览器，不同步到云端</small>
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
.ai-panel-intro{padding:14px 7px 10px;border-bottom:1px solid #e1e8f2}
.ai-panel-intro h3{margin:0 0 5px;color:#172e4d;font-size:16px}
.ai-panel-intro p{margin:0;color:#69778c;font-size:12px;line-height:1.55}
.ai-field-title{margin:4px 0 8px!important;color:#465a74;font-size:12px!important;font-weight:700}
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
.ai-audit{margin:10px 0;padding:8px;border:1px solid #d9e1ee;border-radius:6px;background:#f8fafc}
.ai-audit summary{cursor:pointer;font-weight:600;color:#1d3557}
.ai-audit p{font-size:12px;line-height:1.55}
.ai-edit-workspace{border:1px solid #d9e1ee;border-radius:7px;padding:8px;margin:9px 0;display:grid;gap:5px}
.ai-edit-workspace small{font-size:11px;color:#64748b}
.ai-exclusion-picker{margin:8px 0;padding:8px;border:1px solid #d9e1ee;border-radius:6px}
.ai-exclusion-results{max-height:156px;overflow-y:auto;margin-top:6px}
.ai-exclusion-results label{display:flex;align-items:center;gap:6px;padding:3px}
.ai-exclusion-results input[type="checkbox"]{width:auto;flex-shrink:0}
@media(max-height:650px){.ai-content{max-height:38vh}}

/* v2.0 visual refresh: design-only, no change to request or confirm flow */
.ai-itinerary-panel{--ai-ink:#19304a;--ai-blue:#2563c9;--ai-line:#e3ebf5;--ai-subtle:#f5f8fe;font-family:system-ui,"Microsoft YaHei","PingFang SC",sans-serif;line-height:1.6}
.ai-panel-intro{padding:17px 12px 15px;background:linear-gradient(125deg,#f0f6ff 0%,#fff 92%);border:1px solid #e5eefb;border-radius:12px}
.ai-title-row{display:flex;align-items:center;gap:10px}
.ai-title-row h3{margin:0;color:var(--ai-ink);font-size:17px;letter-spacing:-.2px}
.ai-title-icon{display:grid;place-items:center;width:38px;height:38px;flex-shrink:0;border-radius:12px;color:white;font-size:22px;background:linear-gradient(140deg,#276add,#174995);box-shadow:0 6px 12px #1c54a626}
.ai-title-kicker{color:#7691b6;font-weight:700;font-size:9px;letter-spacing:1.15px}
.ai-panel-intro>p{margin-top:8px;font-size:12px;color:#566b87;line-height:1.65}
.ai-field-title{display:flex;align-items:center;gap:7px;margin:14px 0 10px!important;color:var(--ai-ink)!important}
.ai-section-index{display:inline-grid;place-items:center;min-width:25px;height:21px;padding:0 4px;border-radius:6px;background:#e8f0fe;color:#2962b4;font-size:10px;font-weight:800;letter-spacing:.2px}
.ai-content{padding:12px 6px 16px;scrollbar-width:thin;scrollbar-color:#c4d5eb transparent}
.ai-content label{font-size:12px;font-weight:600;color:#445c78;line-height:1.7}
.ai-content textarea,.ai-content input,.ai-content select{min-height:35px;margin-top:4px;border:1px solid #cdd9e8;border-radius:8px;background:#fff;font-size:12px;transition:border-color .15s,box-shadow .15s}
.ai-content textarea:focus-visible,.ai-content input:focus-visible,.ai-content select:focus-visible{outline:2px solid #83b6ff;outline-offset:1px;border-color:#2d73d7}
.ai-fields{gap:10px 9px}
.ai-content button{min-height:34px;padding:7px 10px;border-radius:8px;border-color:#c8d8ed;background:#f7faff;font-weight:600;transition:background .15s,border-color .15s}
.ai-content button:hover:not(:disabled){background:#e8f1ff;border-color:#8bb4ee}
.ai-content button:focus-visible{outline:2px solid #2e74d4;outline-offset:2px}
.ai-content .ai-primary-action{color:#fff;background:linear-gradient(115deg,#2870df,#1954b4);border:1px solid #2365c4;box-shadow:0 3px 9px #1751a321}
.ai-content .ai-primary-action:hover:not(:disabled){background:#1855af;border-color:#164a98}
.ai-content .ai-secondary-action{color:#1a55a6;background:#eaf2ff;border-color:#b6cff2}
.ai-error,.ai-notice{padding:9px 10px;border-radius:8px;font-size:12px}
.ai-error{background:#fff2f2;border:1px solid #f5c9ca;color:#9d2738}
.ai-notice{background:#eaf8ef;border:1px solid #bde7ca;color:#17693f}
.ai-results,.ai-preview,.ai-saved{margin-top:15px;padding:14px 12px;border:1px solid var(--ai-line);border-radius:12px;background:#fff;box-shadow:0 2px 9px #233b5a08}
.ai-results h4,.ai-preview h4,.ai-saved h4{font-size:14px!important;color:var(--ai-ink);line-height:1.45}
.ai-card-eyebrow{display:flex;align-items:center;gap:7px;color:#39725c;font-size:11px;font-weight:700;letter-spacing:.2px}
.ai-status-dot{width:7px;height:7px;border-radius:50%;background:#20ae78}
.ai-results ol{padding-left:23px;line-height:1.85}
.ai-results ol li{padding:5px 0;border-bottom:1px dashed #edf1f6;overflow-wrap:anywhere}
.ai-results ol li:last-child{border-bottom:0}
.ai-results ol small{display:block;color:#708098;font-size:11px}
.ai-audit{border:1px solid #dfe9f7;background:#f7faff;border-radius:9px}
.ai-audit summary{padding:3px 0;color:#2459a2}
.ai-audit summary:focus-visible{outline:2px solid #2d73d7;outline-offset:2px}
.ai-exclusion-picker{border:1px solid #e1eaf5;border-radius:10px;background:#fbfdff;padding:11px}
.ai-exclusion-results{max-height:180px;scrollbar-width:thin}
.ai-exclusion-results label{padding:6px 4px;border-radius:6px;font-weight:400}
.ai-exclusion-results label:hover{background:#eef5ff}
.ai-exclusion-results input[type="checkbox"]{min-height:auto;margin:0;accent-color:#2463c1}
.ai-edit-workspace{gap:9px;padding:13px 11px;border:1px solid #d7e5f8;background:linear-gradient(145deg,#f4f8ff,#fff);border-radius:11px}
.ai-edit-workspace h4{margin:0!important;display:flex;align-items:center;gap:7px}
.ai-edit-workspace small,.ai-muted{color:#71849d;font-size:11px}
.ai-preview{background:#f2f9f5;border-color:#cce8d9}
.ai-preview h4{color:#1f6644}
.ai-saved-item{padding:10px 0;display:flex;flex-wrap:wrap;gap:5px}
.ai-saved-item span{flex-basis:100%;font-weight:600;color:#344a66}
.ai-actions{display:flex;flex-wrap:wrap;gap:4px}
.ai-actions button{flex:1 1 125px}
@media(max-width:600px){.ai-panel-intro{padding:12px}.ai-content{padding:10px 4px}.ai-fields{grid-template-columns:1fr 1fr}}

.ai-quick-nav{position:sticky;top:0;z-index:3;display:flex;gap:5px;flex-wrap:wrap;padding:9px 9px;background:#f8fbfffa;border-bottom:1px solid #dae6f7;box-shadow:0 3px 7px #20436a0a}
.ai-quick-nav button{flex:1 1 auto;min-width:68px;padding:7px 8px;color:#215bad;border:1px solid #cddff6;background:#fff;border-radius:8px;font-size:11px;font-weight:700;cursor:pointer}
.ai-quick-nav button:hover{background:#e7f0ff}
.ai-quick-nav .ai-quick-pending{border-color:#a9d9c4;background:#eaf8f1;color:#186843}
.ai-quick-nav button:focus-visible{outline:2px solid #286dd1;outline-offset:2px}
#ai-plan-section,#ai-edit-section,#ai-preview-section,#ai-saved-section{scroll-margin-top:65px}
.ai-stops-disclosure{margin:10px 0;border:1px solid #e0e8f4;border-radius:8px;background:#fbfdff;padding:8px 10px}
.ai-stops-disclosure summary{cursor:pointer;font-size:12px;font-weight:700;color:#2459a4}
.ai-stops-disclosure summary:focus-visible{outline:2px solid #2d73d7;outline-offset:2px}
.ai-stops-disclosure ol{margin:8px 0 0}
@media(max-width:600px){.ai-quick-nav{gap:4px;padding:7px 5px}.ai-quick-nav button{font-size:11px;padding:8px 5px}}
@media(prefers-reduced-motion:reduce){.ai-quick-nav button{transition:none}}
</style>
