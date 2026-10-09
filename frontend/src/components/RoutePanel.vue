<script setup>
import { computed } from 'vue'

const transportModes = [
  { value: 'pedestrian', label: '🚶 步行' },
  { value: 'bicycle', label: '🚲 骑行' },
  { value: 'auto', label: '🚗 驾车' }
]

const props = defineProps({
  places: { type: Array, required: true },
  distanceKm: { type: Number, required: true },
  roadRoute: { type: Object, default: null },
  roadPending: { type: Boolean, default: false },
  roadError: { type: String, default: '' },
  roadMode: { type: String, default: 'pedestrian' },
  roadResults: { type: Object, default: () => ({}) },
  multiRoute: { type: Object, default: null },
  multiPending: { type: Boolean, default: false },
  multiError: { type: String, default: '' },
  multiResults: { type: Object, default: () => ({}) }
})

defineEmits(['clear', 'calculate-road', 'calculate-multi', 'change-mode'])

const routingPoints = computed(() =>
  props.places.length === 2
    ? props.roadRoute?.routing_points ?? []
    : props.multiRoute?.routing_points ?? []
)
const reviewedEntranceCount = computed(() =>
  routingPoints.value.filter(point => point.kind === 'reviewed_access_point').length
)
const resultFor = mode => props.places.length === 2
  ? props.roadResults[mode]?.properties
  : props.multiResults[mode]
</script>

<template>
  <aside class="route-panel" aria-label="我的路线">
    <div class="route-panel-header">
      <h2>我的路线</h2>
      <button type="button" :disabled="places.length === 0" @click="$emit('clear')">
        清空路线
      </button>
    </div>
    <p>已选择：{{ places.length }} 个景点</p>
    <ol v-if="places.length" class="route-places">
      <li v-for="place in places" :key="place.properties.id">{{ place.properties.name }}</li>
    </ol>
    <p class="route-distance">原选定顺序直线距离：{{ distanceKm.toFixed(2) }} km</p>

    <template v-if="places.length >= 2 && places.length <= 6">
      <p class="transport-label">选择交通方式</p>
      <div class="transport-modes" role="group" aria-label="选择交通方式">
        <button v-for="mode in transportModes" :key="mode.value"
          type="button" :class="{ selected: roadMode === mode.value }"
          :aria-pressed="roadMode === mode.value"
          @click="$emit('change-mode', mode.value)">{{ mode.label }}</button>
      </div>

      <button v-if="places.length === 2" class="road-button" type="button"
        :disabled="roadPending" @click="$emit('calculate-road')">
        {{ roadPending ? '正在计算道路路线…' : roadResults[roadMode] ? '重新计算当前路线' : '计算当前交通方式路线' }}
      </button>
      <button v-else class="road-button" type="button"
        :disabled="multiPending" @click="$emit('calculate-multi')">
        {{ multiPending ? '正在计算道路时间矩阵…'
          : multiResults[roadMode] ? '重新优化当前交通方式' : '按道路时间优化多站顺序' }}
      </button>

      <details v-if="routingPoints.length" class="access-summary">
        <summary>道路入口资料：{{ reviewedEntranceCount }}/{{ routingPoints.length }} 站使用已审核入口</summary>
        <p v-if="reviewedEntranceCount < routingPoints.length">
          其余站点仍使用景点原坐标寻路，不能视为经过验证的出入口，可能产生路网吸附或绕行。
        </p>
        <p>紫色圆点仅标识已审核入口；红色景点标记仍表示原POI位置。
          资料审核不代表入口实时开放或该交通方式始终可通行。</p>
        <ul>
          <li v-for="point in routingPoints" :key="point.id">
            <strong>{{ point.name }}</strong>：
            <template v-if="point.kind === 'reviewed_access_point'">
              {{ point.access_name }}（审核日期：{{ point.reviewed_on }}）
              <a :href="point.source_url" target="_blank" rel="noopener noreferrer">来源</a>
            </template>
            <template v-else>入口未核实，使用景点原坐标</template>
          </li>
        </ul>
      </details>

      <template v-if="places.length === 2 && roadRoute">
        <p class="road-result">道路距离：{{ roadRoute.distance_km.toFixed(3) }} km</p>
        <p class="road-result">预计用时：{{ roadRoute.duration_minutes.toFixed(1) }} 分钟</p>
        <p class="road-notice">彩色折线为 OSM 路网估算，可能存在起终点吸附偏移。</p>
      </template>
      <p v-if="places.length === 2 && roadError" class="road-error" role="alert">{{ roadError }}</p>

      <template v-if="places.length >= 3 && multiRoute">
        <p class="road-result">优化后道路总距离：{{ multiRoute.distance_km.toFixed(2) }} km</p>
        <p class="road-result">交通时间：{{ multiRoute.duration_minutes.toFixed(1) }} 分钟</p>
        <p class="road-notice">矩阵估算节省：{{ multiRoute.travel_minutes_saved_estimate.toFixed(1) }} 分钟（首站固定）</p>
        <h3 class="multi-heading">优化后游览顺序</h3>
        <ol class="multi-stops">
          <li v-for="stop in multiRoute.ordered_stops" :key="stop.id">
            {{ stop.name }}
            <small> · {{ stop.visit_duration == null ? '游览时长未知' : '建议停留约' + stop.visit_duration + '分钟' }}</small>
          </li>
        </ol>
        <p v-if="multiRoute.total_plan_minutes != null" class="road-result">
          含停留的总估算：{{ multiRoute.total_plan_minutes.toFixed(1) }} 分钟
        </p>
        <p v-else class="road-notice">
          {{ multiRoute.missing_visit_duration_count }}个景点缺少停留时间，暂不计算完整行程总用时。
        </p>
        <p class="road-notice">只优化已选站点的路网交通时间，不含开放时间、停车、休息或实时路况。</p>
      </template>
      <p v-if="places.length >= 3 && multiError" class="road-error" role="alert">{{ multiError }}</p>

      <table class="mode-comparison" aria-label="已计算交通方式比较">
        <thead><tr><th>交通方式</th><th>道路距离</th><th>预计时间</th></tr></thead>
        <tbody>
          <tr v-for="mode in transportModes" :key="mode.value" :class="{ active: roadMode === mode.value }">
            <td>{{ mode.label }}</td>
            <td>{{ resultFor(mode.value) ? resultFor(mode.value).distance_km.toFixed(2) + ' km' : '待计算' }}</td>
            <td>{{ resultFor(mode.value) ? resultFor(mode.value).duration_minutes.toFixed(1) + ' 分' : '—' }}</td>
          </tr>
        </tbody>
      </table>
      <p class="road-notice">不同交通方式需分别计算；表格仅展示实际返回结果，无需 DeepSeek Key。</p>
    </template>
    <p v-else-if="places.length > 6" class="road-notice">
      最多支持6个景点，请移除多余景点后再优化。
    </p>
  </aside>
</template>

<style scoped>
.route-panel {
  position: relative;
  flex: 1 1 auto;
  width: 100%;
  max-height: none;
  min-height: 0;
  overflow-y: auto;
  padding: 12px;
  box-sizing: border-box;
  border: 1px solid #dbe4ee;
  border-radius: 12px;
  background: white;
  box-shadow: 0 4px 16px #12253e26;
  color: #222;
  text-align: left;
}
.route-panel-header { display: flex; align-items: center; justify-content: space-between; gap: 8px; }
h2, p { margin: 0; }
h2 { font-size: 18px; }
.route-panel-header button {
  padding: 5px 8px;
  border: 1px solid #ddd;
  border-radius: 4px;
  background: white;
  color: #333;
  cursor: pointer;
}
.route-panel-header button:disabled { cursor: not-allowed; opacity: .5; }
.route-panel > p:not(.route-distance) { margin-top: 10px; }
.route-places { max-height: 130px; margin: 8px 0; padding-left: 24px; overflow-y: auto; }
.route-places li { padding: 3px 0; }
.route-distance { padding-top: 8px; border-top: 1px solid #eee; font-weight: 600; }
.transport-label { font-size: 12px; color: #475569; }
.transport-modes { display: grid; grid-template-columns: repeat(3, 1fr); gap: 4px; margin-top: 8px; }
.transport-modes button { border: 1px solid #cbd5e1; border-radius: 6px; padding: 8px 2px; color: #334155; background: #f8fafc; cursor: pointer; font-size: 12px; }
.transport-modes button.selected { color: white; border-color: #1d4ed8; background: #2563eb; font-weight: 600; }
.road-button { margin-top: 10px; padding: 9px; width: 100%; border: 0; border-radius: 6px; color: white; background: #16803d; cursor: pointer; }
.road-button:disabled { opacity: .6; cursor: wait; }
.road-result { margin-top: 8px; font-weight: 600; color: #166534; }
.road-notice { color: #64748b; font-size: 11px; line-height: 1.5; margin-top: 8px; }
.road-error { color: #b42318; font-size: 12px; }
.mode-comparison { width: 100%; border-collapse: collapse; margin-top: 12px; font-size: 11px; text-align: left; }
.mode-comparison th, .mode-comparison td { border-bottom: 1px solid #e2e8f0; padding: 7px 2px; }
.mode-comparison th { color: #64748b; font-weight: 500; }
.mode-comparison .active { background: #eff6ff; }
.multi-heading { font-size: 13px; margin: 12px 0 5px; color: #1d4ed8; }
.multi-stops { margin: 6px 0 4px; padding-left: 22px; max-height: 170px; overflow-y: auto; font-size: 13px; line-height: 1.7; }
.multi-stops small { color: #64748b; font-size: 11px; }
.access-summary { margin-top: 9px; border: 1px solid #d8e3f5; padding: 7px; border-radius: 7px; font-size: 11px; background: #f7f9fd; }
.access-summary summary { cursor: pointer; color: #3b4488; font-weight: 600; }
.access-summary ul { padding-left: 16px; line-height: 1.6; }
.access-summary p { color: #566378; margin: 6px 0; line-height: 1.45; }
.access-summary a { color: #214bbb; }
</style>
