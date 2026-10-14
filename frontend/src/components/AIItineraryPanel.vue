<template>
  <section class="ai-itinerary-panel">
    <h3>AI 智慧行程规划</h3>

    <textarea
      v-model="request.location"
      placeholder="请输入旅游需求，例如：南京一天历史文化路线，老人同行，少走路"
      rows="4"
    />

    <div class="options">
      <input v-model="request.style" placeholder="主题" />
      <input v-model="request.people" placeholder="同行人员" />
      <input v-model="request.walking_limit" placeholder="步行限制" />
    </div>

    <button :disabled="loading" @click="generate">
      {{ loading ? '生成中...' : '生成AI行程' }}
    </button>

    <div v-if="error" class="error">{{ error }}</div>

    <div v-if="result" class="result">
      <h4>{{ result.title }}</h4>
      <p>{{ result.summary }}</p>

      <ol>
        <li v-for="(stop, index) in result.stops ?? []" :key="index">
          <strong>{{ stop.time }}</strong>
          {{ stop.poi }}
          <br />
          <small>{{ stop.reason }}</small>
        </li>
      </ol>
    </div>
  </section>
</template>

<script setup>
import { reactive, ref } from 'vue'
import axios from 'axios'

const request = reactive({
  location: '',
  days: 1,
  style: '历史文化',
  people: '普通游客',
  walking_limit: '中等'
})

const result = ref(null)
const error = ref('')
const loading = ref(false)

const generate = async () => {
  if (!request.location.trim()) {
    error.value = '请输入旅游需求'
    return
  }

  loading.value = true
  error.value = ''

  try {
    const response = await axios.post(
      'http://127.0.0.1:8010/api/ai/itinerary/generate',
      request
    )
    result.value = response.data
  } catch (err) {
    error.value = 'AI行程生成失败，请检查后端服务和DeepSeek配置'
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.ai-itinerary-panel {
  padding: 16px;
}

textarea,
input {
  width: 100%;
  margin-bottom: 8px;
}

.options {
  display: grid;
  gap: 6px;
}

button {
  margin-top: 8px;
}

.error {
  color: #c62828;
}
</style>
