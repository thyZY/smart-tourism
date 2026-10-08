<script setup>
defineProps({
  places: { type: Array, required: true },
  distanceKm: { type: Number, required: true },
  roadRoute: { type: Object, default: null },
  roadPending: { type: Boolean, default: false },
  roadError: { type: String, default: '' }
})

defineEmits(['clear', 'calculate-road'])
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
      <button class="road-button" type="button" :disabled="roadPending" @click="$emit('calculate-road')">
        {{ roadPending ? '正在计算步行道路…' : '计算真实道路步行路线' }}
      </button>
      <template v-if="roadRoute">
        <p class="road-result">道路距离：{{ roadRoute.distance_km.toFixed(3) }} km</p>
        <p class="road-result">预计步行：{{ roadRoute.duration_minutes.toFixed(1) }} 分钟</p>
        <p class="road-notice">绿色路线是基于 OpenStreetMap 的路网估算，不提供实时导航或无障碍保证。</p>
      </template>
      <p v-if="roadError" class="road-error" role="alert">{{ roadError }}</p>
    </template>
    <p v-else-if="places.length > 2" class="road-notice">
      当前道路寻路仅支持两个景点。多站路线仍为直线预览。
    </p>
  </aside>
</template>

<style scoped>
.route-panel {
  position: absolute;
  right: 20px;
  bottom: 30px;
  z-index: 10;
  width: 265px;
  max-height: 56vh;
  overflow-y: auto;
  padding: 12px;
  box-sizing: border-box;
  border: 1px solid #ddd;
  border-radius: 6px;
  background: white;
  box-shadow: 0 2px 8px rgb(0 0 0 / 12%);
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
.route-places { max-height: 150px; margin: 8px 0; padding-left: 24px; overflow-y: auto; }
.route-places li { padding: 3px 0; }
.route-distance { padding-top: 8px; border-top: 1px solid #eee; font-weight: 600; }
.road-button { margin-top: 10px; padding: 9px; width: 100%; border: 0; border-radius: 6px; color: white; background: #16803d; cursor: pointer; }
.road-button:disabled { opacity: .6; cursor: wait; }
.road-result { margin-top: 8px; font-weight: 600; color: #166534; }
.road-notice { color: #64748b; font-size: 12px; line-height: 1.5; margin-top: 8px; }
.road-error { color: #b42318; font-size: 12px; }
</style>
