<script setup>
const props = defineProps({
  active: { type: String, default: 'explore' },
  expanded: { type: Boolean, default: false },
  detailOpen: { type: Boolean, default: false },
  routeCount: { type: Number, default: 0 }
})

const emit = defineEmits(['update:active', 'update:expanded'])

const entries = [
  { id: 'explore', label: '探索', icon: '⌕' },
  { id: 'route', label: '路线', icon: '↗' },
  { id: 'ai', label: 'AI 行程', icon: '✦' },
  { id: 'more', label: '更多', icon: '⋯' }
]

function toggleExpanded() {
  emit('update:expanded', !props.expanded)
}
</script>

<template>
  <section
    class="mobile-workspace-sheet"
    :class="{ 'is-expanded': expanded, 'has-place-detail': detailOpen }"
    :data-active="active"
    aria-label="移动端工作面板"
  >
    <button
      class="mobile-sheet-toggle"
      type="button"
      :aria-expanded="expanded"
      aria-controls="mobile-sheet-content"
      :aria-label="expanded ? '收起工作面板' : '展开工作面板'"
      @click="toggleExpanded"
    >
      <span class="mobile-sheet-grabber" aria-hidden="true"></span>
      <span class="mobile-sheet-summary">
        <strong>{{ detailOpen ? '景点详情' : entries.find((entry) => entry.id === active)?.label }}</strong>
        <small v-if="active === 'explore' && !detailOpen">搜索结果与收藏</small>
        <small v-else-if="active === 'route'">{{ routeCount }} 个路线站点</small>
        <small v-else-if="active === 'ai'">生成、调整与保存行程</small>
        <small v-else-if="active === 'more'">主题、图层与空间分析</small>
        <small v-else>返回探索结果</small>
      </span>
      <span class="mobile-sheet-chevron" aria-hidden="true">{{ expanded ? '⌄' : '⌃' }}</span>
    </button>

    <div id="mobile-sheet-content" class="mobile-sheet-content">
      <slot></slot>
    </div>

    <nav class="mobile-workspace-nav" role="tablist" aria-label="主要工作区">
      <button
        v-for="entry in entries"
        :key="entry.id"
        type="button"
        role="tab"
        :class="{ active: active === entry.id }"
        :aria-current="active === entry.id ? 'page' : undefined"
        :aria-selected="active === entry.id"
        aria-controls="mobile-sheet-content"
        :aria-label="entry.id === 'route' ? '我的路线' : undefined"
        @click="emit('update:active', entry.id); emit('update:expanded', true)"
      >
        <span class="mobile-nav-icon" aria-hidden="true">{{ entry.icon }}</span>
        <span>{{ entry.label }}</span>
        <span v-if="entry.id === 'route' && routeCount" class="mobile-route-badge">{{ routeCount }}</span>
      </button>
    </nav>
  </section>
</template>
