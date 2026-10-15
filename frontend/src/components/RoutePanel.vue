<script setup>
import { ref } from 'vue'
const selectedMode = ref('pedestrian')
const optimizeOrder = ref(false)
defineProps({
  places: {
    type: Array,
    required: true
  },
  distanceKm: {
    type: Number,
    required: true
  },
  routeKind: { type: String, default: 'straight_line_preview' },
  roadTravelMinutes: { type: Number, default: null },
  roadMode: { type: String, default: 'pedestrian' },
  roadLoading: { type: Boolean, default: false },
  roadError: { type: String, default: '' },
  roadOptimized: { type: Boolean, default: false }
})

defineEmits(['clear', 'focus-place', 'calculate-road'])
</script>

<template>
  <aside class="route-panel" aria-label="我的路线">
    <div class="route-panel-header">
      <h2>我的路线</h2>
      <button
        type="button"
        :disabled="places.length === 0"
        @click="$emit('clear')"
      >
        清空路线
      </button>
    </div>

    <p>已选择：{{ places.length }} 个景点</p>
    <ol v-if="places.length" class="route-places">
      <li v-for="(place, index) in places" :key="place.properties.id">
        <button type="button" class="route-stop-focus" :aria-label="'在地图上定位第 ' + (index + 1) + ' 站 ' + place.properties.name"
          @click="$emit('focus-place', place)">
          <span class="route-stop-number">{{ index + 1 }}</span>
          <span class="route-stop-name">{{ place.properties.name }}</span>
          <span class="route-stop-locate">定位 ↗</span>
        </button>
      </li>
    </ol>
    <div class="route-road-controls">
      <label>道路交通方式
        <select v-model="selectedMode" :disabled="roadLoading">
          <option value="pedestrian">步行</option>
          <option value="bicycle">骑行</option>
          <option value="auto">驾车</option>
        </select>
      </label>
      <label v-if="places.length >= 3">
        <input v-model="optimizeOrder" type="checkbox" :disabled="roadLoading" />
        使用时间矩阵优化顺序（固定首站）
      </label>
      <button type="button" :disabled="roadLoading || places.length < 2 || places.length > 6"
        @click="$emit('calculate-road', { mode: selectedMode, optimize: optimizeOrder && places.length >= 3 })">
        {{ roadLoading ? '道路计算中…' : '计算实际道路路线' }}
      </button>
      <p v-if="roadError" role="alert">{{ roadError }}</p>
      <p v-if="routeKind === 'valhalla'">当前道路模式：{{ {pedestrian:'步行',bicycle:'骑行',auto:'驾车'}[roadMode] }}{{ roadOptimized ? ' · 已按路网时间优化顺序' : '' }}</p>
      <small>只连接已配置的本机 Valhalla；估算时间非实时导航。</small>
    </div>
    <p class="route-distance">
      {{ routeKind === 'valhalla' ? 'Valhalla道路距离' : '景点间直线距离（非导航）' }}：
      {{ distanceKm.toFixed(1) }} km
    </p>
    <p v-if="routeKind === 'valhalla' && roadTravelMinutes !== null">
      道路预计交通：{{ roadTravelMinutes.toFixed(1) }} 分钟
    </p>
  </aside>
</template>

<style scoped>
.route-panel {
  position: absolute;
  right: 20px;
  bottom: 30px;
  z-index: 10;
  width: 250px;
  padding: 12px;
  box-sizing: border-box;
  border: 1px solid #ddd;
  border-radius: 6px;
  background: white;
  box-shadow: 0 2px 8px rgb(0 0 0 / 12%);
  color: #222;
  text-align: left;
}

.route-panel-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}

h2,
p {
  margin: 0;
}

h2 {
  font-size: 18px;
}

.route-panel-header button {
  padding: 5px 8px;
  border: 1px solid #ddd;
  border-radius: 4px;
  background: white;
  color: #333;
  cursor: pointer;
}

.route-panel-header button:disabled {
  cursor: not-allowed;
  opacity: 0.5;
}

.route-panel > p:not(.route-distance) {
  margin-top: 10px;
}

.route-places {
  max-height: 180px;
  margin: 8px 0;
  padding-left: 24px;
  overflow-y: auto;
}

.route-places li { padding: 3px 0; list-style: none; }
.route-places { padding-left: 0; }
.route-stop-focus { display:flex;align-items:center;gap:9px;width:100%;text-align:left;
  background:#f8faff;border:1px solid #e1eaf7;border-radius:8px;
  padding:8px;color:#263c56;cursor:pointer; }
.route-stop-focus:hover { background:#e9f2ff;border-color:#a9c6f4; }
.route-stop-number { display:grid;place-items:center;flex:0 0 25px;height:25px;
  background:#245ac0;color:#fff;border-radius:50%;font-size:12px;font-weight:700; }
.route-stop-name {flex:1;min-width:0;overflow-wrap:anywhere;font-size:13px;font-weight:600;}
.route-stop-locate {color:#2563eb;font-size:11px;white-space:nowrap;}

.route-distance {
  padding-top: 8px;
  border-top: 1px solid #eee;
  font-weight: 600;
}
.route-road-controls{display:grid;gap:8px;margin:12px 0;padding:10px;border:1px solid #d9e1ee;border-radius:8px}
.route-road-controls label{display:flex;align-items:center;gap:8px;flex-wrap:wrap;font-size:12px}
.route-road-controls select{padding:5px;border:1px solid #cbd5e1;border-radius:5px}
.route-road-controls button{padding:8px;color:#164c9a;background:#eef5ff;border:1px solid #bad3fa;border-radius:6px;cursor:pointer}
.route-road-controls button:disabled{opacity:.5;cursor:not-allowed}
.route-road-controls small{color:#64748b;font-size:11px}
.route-road-controls [role="alert"]{color:#b42318;font-size:12px}
</style>
