<script setup>
import { computed } from 'vue'

const props = defineProps({
  gridFeatures: {
    type: Array,
    required: true
  },
  visible: {
    type: Boolean,
    required: true
  }
})

defineEmits(['show', 'hide'])

const topGridFeatures = computed(() => [...props.gridFeatures]
  .sort((first, second) => second.properties.poi_count - first.properties.poi_count)
  .slice(0, 3)
)

const maxPoiCount = computed(() => topGridFeatures.value[0]?.properties.poi_count ?? 0)
</script>

<template>
  <aside class="spatial-analysis-panel" aria-label="旅游资源空间分析">
    <h2>旅游资源空间分析</h2>
    <div class="analysis-summary">
      <span>有资源格网</span>
      <strong>{{ gridFeatures.length }}</strong>
    </div>
    <div class="analysis-summary">
      <span>最大单格 POI</span>
      <strong>{{ maxPoiCount }}</strong>
    </div>

    <h3>Top 3 资源集中格网</h3>
    <ol v-if="topGridFeatures.length" class="grid-ranking">
      <li v-for="feature in topGridFeatures" :key="feature.properties.grid_id">
        <span>POI {{ feature.properties.poi_count }} · {{ feature.properties.category_count }} 类</span>
        <small>{{ feature.properties.richness_level }}</small>
      </li>
    </ol>
    <p v-else class="analysis-empty">正在准备完整 POI 格网…</p>

    <div class="analysis-actions">
      <button type="button" :disabled="visible || !gridFeatures.length" @click="$emit('show')">
        显示格网分析
      </button>
      <button type="button" :disabled="!visible" @click="$emit('hide')">
        隐藏格网分析
      </button>
    </div>
  </aside>
</template>

<style scoped>
.spatial-analysis-panel {
  position: absolute;
  bottom: 30px;
  left: 20px;
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

h2, h3, p { margin: 0; }
h2 { font-size: 18px; }
h3 { margin-top: 12px; font-size: 14px; }
.analysis-summary { display: flex; justify-content: space-between; gap: 12px; margin-top: 9px; font-size: 14px; }
.analysis-summary strong { color: #0b57d0; }
.grid-ranking { margin: 8px 0 0; padding-left: 20px; }
.grid-ranking li { display: flex; justify-content: space-between; gap: 8px; padding: 4px 0; font-size: 13px; }
.grid-ranking small { color: #6d28d9; text-transform: uppercase; }
.analysis-empty { margin-top: 8px; color: #6b7280; font-size: 13px; }
.analysis-actions { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; margin-top: 12px; }
.analysis-actions button { padding: 8px 6px; border: 1px solid #ddd; border-radius: 6px; background: white; color: #333; cursor: pointer; font-size: 13px; }
.analysis-actions button:hover:not(:disabled) { border-color: #8ab4f8; background: #e8f0fe; }
.analysis-actions button:disabled { cursor: not-allowed; opacity: 0.5; }
</style>
