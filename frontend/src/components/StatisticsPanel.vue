<script setup>
import axios from 'axios'
import { computed, onMounted, onUnmounted, ref } from 'vue'

const expanded = ref(false)
const loading = ref(true)
const errorMessage = ref('')
const statistics = ref({
  total_places: 0,
  category_counts: {},
  top_categories: []
})
let requestController = null

const categoryEntries = computed(() =>
  Object.entries(statistics.value.category_counts)
)

const loadStatistics = async () => {
  requestController?.abort()
  const controller = new AbortController()
  requestController = controller
  loading.value = true
  errorMessage.value = ''

  try {
    const response = await axios.get('http://127.0.0.1:8010/api/statistics', {
      signal: controller.signal,
      timeout: 10000
    })
    if (!controller.signal.aborted) {
      statistics.value = response.data
    }
  } catch (error) {
    if (!controller.signal.aborted && !axios.isCancel(error)) {
      errorMessage.value = '统计数据加载失败'
    }
  } finally {
    if (requestController === controller) {
      requestController = null
      loading.value = false
    }
  }
}

onMounted(() => {
  void loadStatistics()
})

onUnmounted(() => {
  requestController?.abort()
})
</script>

<template>
  <aside class="statistics-panel" :class="{ collapsed: !expanded }">
    <button
      class="statistics-toggle"
      type="button"
      :aria-expanded="expanded"
      aria-controls="statistics-content"
      @click="expanded = !expanded"
    >
      {{ expanded ? '收起统计' : '展开统计' }}
    </button>

    <div v-if="expanded" id="statistics-content" class="statistics-content">
      <h2>智慧旅游统计</h2>
      <p v-if="loading" class="statistics-status">正在加载统计数据…</p>
      <p v-else-if="errorMessage" class="statistics-status error">{{ errorMessage }}</p>
      <template v-else>
        <div class="statistics-total">
          <span>景点总数</span>
          <strong>{{ statistics.total_places }}</strong>
        </div>
        <div class="statistics-total">
          <span>分类数量</span>
          <strong>{{ categoryEntries.length }}</strong>
        </div>

        <h3>各类别数量</h3>
        <ul class="category-counts">
          <li v-for="[category, count] in categoryEntries" :key="category">
            <span>{{ category }}</span>
            <strong>{{ count }}</strong>
          </li>
        </ul>
      </template>
    </div>
  </aside>
</template>

<style scoped>
.statistics-panel {
  position: relative;
  width: 100%;
  min-height: 0;
  max-height: 38vh;
  overflow-y: auto;
  box-sizing: border-box;
  border: 1px solid #dbe4ee;
  border-radius: 12px;
  background: white;
  color: #26374b;
  box-shadow: 0 3px 14px #12253e1c;
}
.statistics-toggle {
  width: 100%;
  padding: 12px 14px;
  border: 0;
  background: #fff;
  color: #26374b;
  cursor: pointer;
  font-weight: 700;
  text-align: left;
}
.statistics-toggle:hover { background: #f6f9fc; }
.statistics-content { padding: 0 14px 12px; }
.statistics-content h2 { font-size: 15px; margin: 4px 0 8px; }
.statistics-content h3 { font-size: 13px; margin: 12px 0 6px; }
.statistics-total, .category-counts li {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 10px;
  padding: 4px 0;
}
.statistics-total strong, .category-counts strong { color: #0b57d0; }
.category-counts { padding: 0; margin: 0; list-style: none; }
.category-counts li { border-bottom: 1px solid #eff2f5; font-size: 12px; }
.statistics-status { margin: 8px 0; color: #56677d; }
.statistics-status.error { color: #b42318; }
</style>
