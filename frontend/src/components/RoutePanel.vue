<script setup>
const transportModes = [
  { value: 'pedestrian', label: '🚶 步行' },
  { value: 'bicycle', label: '🚲 骑行' },
  { value: 'auto', label: '🚗 驾车' }
]

defineProps({
  places: { type: Array, required: true },
  distanceKm: { type: Number, required: true },
  roadRoute: { type: Object, default: null },
  roadPending: { type: Boolean, default: false },
  roadError: { type: String, default: '' },
  roadMode: { type: String, default: 'pedestrian' },
  roadResults: { type: Object, default: () => ({}) }
})

defineEmits(['clear', 'calculate-road', 'change-mode'])
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
    <p class="route-distance">直线距离：{{ distanceKm.toFixed(2) }} km</p>

    <template v-if="places.length === 2">
      <p class="transport-label">选择交通方式</p>
      <div class="transport-modes" role="group" aria-label="选择交通方式">
        <button
          v-for="mode in transportModes"
          :key="mode.value"
          type="button"
          :class="{ selected: roadMode === mode.value }"
          :aria-pressed="roadMode === mode.value"
          @click="$emit('change-mode', mode.value)"
        >{{ mode.label }}</button>
      </div>
      <button class="road-button" type="button" :disabled="roadPending" @click="$emit('calculate-road')">
        {{ roadPending ? '正在计算道路路线…' : roadResults[roadMode] ? '重新计算当前路线' : '计算当前交通方式路线' }}
      </button>

      <template v-if="roadRoute">
        <p class="road-result">道路距离：{{ roadRoute.distance_km.toFixed(3) }} km</p>
        <p class="road-result">预计用时：{{ roadRoute.duration_minutes.toFixed(1) }} 分钟</p>
        <p class="road-notice">彩色折线是基于 OpenStreetMap 的路网估算；非实时交通导航，可能存在起终点吸附偏移。</p>
      </template>
      <p v-if="roadError" class="road-error" role="alert">{{ roadError }}</p>

      <table class="mode-comparison" aria-label="已计算交通方式比较">
        <thead><tr><th>交通方式</th><th>道路距离</th><th>预计时间</th></tr></thead>
        <tbody>
          <tr v-for="mode in transportModes" :key="mode.value" :class="{ active: roadMode === mode.value }">
            <td>{{ mode.label }}</td>
            <td>{{ roadResults[mode.value] ? roadResults[mode.value].properties.distance_km.toFixed(2) + ' km' : '待计算' }}</td>
            <td>{{ roadResults[mode.value] ? roadResults[mode.value].properties.duration_minutes.toFixed(1) + ' 分' : '—' }}</td>
          </tr>
        </tbody>
      </table>
      <p class="road-notice">分别选择步行、骑行、驾车并计算，才能获得三种方式的比较结果。无需 DeepSeek Key。</p>
    </template>
    <p v-else-if="places.length > 2" class="road-notice">
      当前道路寻路仅支持两个景点；多站路线仍为直线预览。
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
</style>
