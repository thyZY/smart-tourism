<script setup>
defineProps({
  themes: {
    type: Array,
    required: true
  },
  selectedTheme: {
    type: Object,
    default: null
  }
})

defineEmits(['select'])
</script>

<template>
  <aside class="theme-panel" aria-label="推荐主题">
    <h2>推荐主题</h2>
    <p class="theme-panel-intro">按游览主题筛选景点，并生成观光路线。</p>
    <button
      v-for="theme in themes"
      :key="theme.id"
      class="theme-card"
      :class="{ active: selectedTheme?.id === theme.id }"
      type="button"
      :aria-pressed="selectedTheme?.id === theme.id"
      @click="$emit('select', theme)"
    >
      <strong>{{ theme.name }}</strong>
      <span>{{ theme.description }}</span>
      <small>预计时间：{{ theme.recommendedDuration }}</small>
    </button>
  </aside>
</template>

<style scoped>
.theme-panel {
  position: absolute;
  top: 70px;
  right: 20px;
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

h2, .theme-panel-intro { margin: 0; }
h2 { font-size: 18px; }
.theme-panel-intro { margin-top: 4px; color: #6b7280; font-size: 13px; line-height: 1.4; }
.theme-card { display: grid; width: 100%; gap: 4px; margin-top: 10px; padding: 10px; border: 1px solid #ddd; border-radius: 8px; background: #fff; color: #222; cursor: pointer; text-align: left; }
.theme-card:hover, .theme-card.active { border-color: #8ab4f8; background: #e8f0fe; }
.theme-card strong { font-size: 15px; }
.theme-card span, .theme-card small { color: #4b5563; font-size: 13px; line-height: 1.35; }
.theme-card small { color: #0b57d0; }
</style>
