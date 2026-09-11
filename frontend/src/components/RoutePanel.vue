<script setup>
defineProps({
  places: {
    type: Array,
    required: true
  },
  distanceKm: {
    type: Number,
    required: true
  }
})

defineEmits(['clear'])
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
      <li v-for="place in places" :key="place.properties.id">
        {{ place.properties.name }}
      </li>
    </ol>
    <p class="route-distance">总距离：{{ distanceKm.toFixed(1) }} km</p>
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

.route-places li {
  padding: 3px 0;
}

.route-distance {
  padding-top: 8px;
  border-top: 1px solid #eee;
  font-weight: 600;
}
</style>
