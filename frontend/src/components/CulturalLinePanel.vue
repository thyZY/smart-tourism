<script setup>
defineProps({
  lines: {
    type: Array,
    required: true
  },
  selectedLine: {
    type: Object,
    default: null
  }
})

defineEmits(['select', 'clear'])
</script>

<template>
  <aside class="cultural-line-panel" aria-label="文化关联线路">
    <div class="cultural-line-header">
      <h2>文化关联线路</h2>
      <button type="button" :disabled="!selectedLine" @click="$emit('clear')">
        清除文化线路
      </button>
    </div>
    <p class="cultural-line-intro">展示景点之间的历史文化关联。</p>
    <button
      v-for="line in lines"
      :key="line.id"
      class="cultural-line-card"
      :class="{ active: selectedLine?.id === line.id }"
      type="button"
      :aria-pressed="selectedLine?.id === line.id"
      @click="$emit('select', line)"
    >
      <strong>{{ line.name }}</strong>
      <span>{{ line.description }}</span>
      <small>文化关联景点：{{ line.places.length }} 个</small>
    </button>
  </aside>
</template>

<style scoped>
.cultural-line-panel {
  position: absolute;
  top: 70px;
  right: 300px;
  z-index: 10;
  box-sizing: border-box;
  width: 280px;
  padding: 14px;
  border: 1px solid #ddd;
  border-radius: 10px;
  background: white;
  box-shadow: 0 2px 10px rgb(0 0 0 / 12%);
  color: #222;
}

.cultural-line-header { display: flex; align-items: center; justify-content: space-between; gap: 8px; }
h2, .cultural-line-intro { margin: 0; }
h2 { font-size: 18px; }
.cultural-line-header button { padding: 5px 7px; border: 1px solid #ddd; border-radius: 5px; background: white; color: #333; cursor: pointer; font-size: 12px; }
.cultural-line-header button:disabled { cursor: not-allowed; opacity: 0.5; }
.cultural-line-intro { margin-top: 4px; color: #6b7280; font-size: 13px; line-height: 1.4; }
.cultural-line-card { display: grid; width: 100%; gap: 4px; margin-top: 10px; padding: 10px; border: 1px solid #ddd; border-radius: 8px; background: #fff; color: #222; cursor: pointer; text-align: left; }
.cultural-line-card:hover, .cultural-line-card.active { border-color: #c4b5fd; background: #f5f3ff; }
.cultural-line-card strong { font-size: 15px; }
.cultural-line-card span, .cultural-line-card small { color: #4b5563; font-size: 13px; line-height: 1.35; }
.cultural-line-card small { color: #6d28d9; }
</style>
