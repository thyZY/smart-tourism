<script setup>
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
  roadTravelMinutes: { type: Number, default: null }
})

defineEmits(['clear', 'focus-place'])
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
</style>
