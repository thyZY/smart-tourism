<script setup>
import axios from 'axios'
import { computed, onMounted, onUnmounted, ref } from 'vue'

const expanded = ref(true)
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
  position: absolute;
  top: 110px;
  right: 20px;
  z-index: 10;
  width: 250px;
  overflow: hidden;
  border: 1px solid #ddd;
  border-radius: 6px;
  background: white;
  box-shadow: 0 2px 8px rgb(0 0 0 / 12%);
}

.statistics-toggle {
  width: 100%;
  padding: 10px 12px;
  border: 0;
  border-bottom: 1px solid #eee;
  background: white;
  color: #333;
  cursor: pointer;
  font-weight: 600;
  text-align: left;
}

.statistics-toggle:hover {
  background: #f5f5f5;
}

.statistics-panel.collapsed {
  width: 100px;
}

.statistics-panel.collapsed .statistics-toggle {
  border-bottom: 0;
  text-align: center;
}

.statistics-content {
  padding: 12px;
}

h2,
h3 {
  margin: 0;
  color: #222;
}

h2 {
  font-size: 18px;
}

h3 {
  margin-top: 14px;
  font-size: 14px;
}

.statistics-total,
.category-counts li {
  display: flex;
  justify-content: space-between;
  gap: 12px;
}

.statistics-total {
  margin-top: 10px;
}

.statistics-total strong,
.category-counts strong {
  color: #0b57d0;
}

.category-counts {
  margin: 8px 0 0;
  padding: 0;
  list-style: none;
}

.category-counts li {
  padding: 5px 0;
  border-bottom: 1px solid #f0f0f0;
  font-size: 14px;
}

.category-counts li:last-child {
  border-bottom: 0;
}

.statistics-status {
  margin: 12px 0 0;
  color: #555;
}

.statistics-status.error {
  color: #b42318;
}
</style>
