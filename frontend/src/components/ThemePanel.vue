<script setup>
defineProps({
  themes: { type: Array, required: true },
  selectedTheme: { type: Object, default: null }
})

defineEmits(['select'])
</script>

<template>
  <aside class="theme-panel" aria-label="推荐主题">
    <details>
      <summary>
        <span class="theme-heading">推荐主题 <span v-if="selectedTheme" class="chosen">· {{ selectedTheme.name }}</span></span>
        <span class="theme-hint">展开选择</span>
      </summary>
      <div class="theme-body">
        <p class="theme-panel-intro">按主题筛选已收录景点，生成观光路线预览。</p>
        <button v-for="theme in themes" :key="theme.id" type="button"
          class="theme-card" :class="{ active: selectedTheme?.id === theme.id }"
          :aria-pressed="selectedTheme?.id === theme.id" @click="$emit('select', theme)">
          <strong>{{ theme.name }}</strong>
          <span>{{ theme.description }}</span>
          <small>建议时长：{{ theme.recommendedDuration }}</small>
        </button>
      </div>
    </details>
  </aside>
</template>

<style scoped>
.theme-panel {
  position: relative;
  box-sizing: border-box;
  width: 100%;
  min-height: 0;
  overflow-y: auto;
  max-height: 42vh;
  border: 1px solid #dbe4ee;
  border-radius: 12px;
  background: white;
  box-shadow: 0 3px 14px #12253e1c;
  color: #26374b;
}
.theme-panel summary {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  padding: 12px 14px;
  cursor: pointer;
  list-style-position: inside;
  font-weight: 700;
}
.theme-heading { flex: 1; min-width: 0; }
.chosen { color: #2563eb; font-size: 12px; }
.theme-hint { flex: 0 0 auto; color: #738399; font-size: 11px; font-weight: 400; }
.theme-panel details[open] .theme-hint { display: none; }
.theme-body { padding: 0 12px 12px; }
.theme-panel-intro { margin: 0 0 6px; color: #6b7280; font-size: 12px; line-height: 1.4; }
.theme-card {
  display: grid;
  width: 100%;
  gap: 3px;
  margin-top: 8px;
  padding: 10px;
  border: 1px solid #dce5ee;
  border-radius: 9px;
  background: #fff;
  color: #26374b;
  cursor: pointer;
  text-align: left;
}
.theme-card:hover, .theme-card.active { border-color: #91b8f2; background: #eff6ff; }
.theme-card strong { font-size: 14px; }
.theme-card span, .theme-card small { font-size: 12px; line-height: 1.35; color: #56677d; }
.theme-card small { color: #2563eb; }
</style>
