<script setup>
import { computed } from 'vue'

const props = defineProps({
  place: { type: Object, default: null },
  tourismCard: { type: Object, default: null },
  tourismLoading: { type: Boolean, default: false },
  tourismError: { type: String, default: '' },
  isFavorite: { type: Boolean, default: false },
  isInRoute: { type: Boolean, default: false }
})

defineEmits(['close', 'toggle-favorite', 'toggle-route'])

const durationLabel = computed(() => {
  const minutes = props.tourismCard?.visit_duration
  if (!Number.isFinite(minutes) || minutes <= 0) return '暂无数据'
  return `约 ${minutes} 分钟（估算）`
})
const environmentLabel = computed(() => {
  if (props.tourismCard?.indoor === true) return '以室内为主'
  if (props.tourismCard?.indoor === false) return '以室外为主'
  return '混合场景或暂未确认'
})
const hasTourismMetadata = computed(() => {
  const card = props.tourismCard
  return Boolean(card && (card.visit_duration || card.description || card.tags?.length))
})
</script>

<template>
  <aside v-if="place" class="place-detail-panel" aria-label="景点详情">
    <div class="place-detail-header">
      <div>
        <p class="place-detail-eyebrow">景点旅游资料</p>
        <h2>{{ place.properties.name }}</h2>
      </div>
      <button class="place-detail-close" type="button" aria-label="关闭详情" @click="$emit('close')">×</button>
    </div>

    <p class="place-detail-category">{{ place.properties.category }}</p>
    <p class="place-detail-address">{{ place.properties.address || '暂无地址信息' }}</p>

    <p v-if="tourismLoading" role="status" class="place-detail-empty">正在读取数据库旅游资料…</p>
    <p v-else-if="tourismError" role="alert" class="place-detail-error">{{ tourismError }}</p>
    <template v-else-if="tourismCard">
      <p v-if="tourismCard.description" class="place-detail-intro">{{ tourismCard.description }}</p>
      <p v-else class="place-detail-empty">暂无景点介绍</p>

      <dl class="place-detail-meta">
        <div>
          <dt>建议停留</dt>
          <dd>{{ durationLabel }}</dd>
        </div>
        <div>
          <dt>游览环境</dt>
          <dd>{{ environmentLabel }}</dd>
        </div>
      </dl>
      <div v-if="tourismCard.tags?.length" class="tags" aria-label="旅游兴趣标签">
        <span v-for="tag in tourismCard.tags" :key="tag" class="tag">{{ tag }}</span>
      </div>
      <p v-if="tourismCard.best_time" class="place-detail-intro">参考游览时段：{{ tourismCard.best_time }}</p>
      <p v-if="hasTourismMetadata" class="place-detail-disclaimer">
        游览时间与分类描述为项目规划参考值，尚未经景区逐项核实。非实时开放时间、门票或导航信息。
      </p>
      <p v-else class="place-detail-empty">该景点尚未录入旅游语义资料。</p>
    </template>

    <div class="place-detail-actions">
      <button type="button" :class="{ active: isFavorite }" @click="$emit('toggle-favorite')">
        {{ isFavorite ? '★ 已收藏' : '☆ 收藏' }}
      </button>
      <button type="button" :class="{ active: isInRoute }" @click="$emit('toggle-route')">
        {{ isInRoute ? '移出路线' : '加入路线' }}
      </button>
    </div>
  </aside>
</template>

<style scoped>
.place-detail-panel {
  position: absolute;
  right: calc(var(--rail-width, 320px) + 28px);
  bottom: 16px;
  z-index: 18;
  box-sizing: border-box;
  width: 310px;
  max-width: calc(100vw - 720px);
  max-height: calc(100dvh - var(--workspace-top, 126px) - 16px);
  overflow-y: auto;
  padding: 16px;
  border: 1px solid #ddd;
  border-radius: 10px;
  background: white;
  box-shadow: 0 4px 16px rgb(0 0 0 / 16%);
  color: #222;
}
.place-detail-header { display: flex; align-items: flex-start; justify-content: space-between; gap: 12px; }
.place-detail-eyebrow, .place-detail-category, .place-detail-address, .place-detail-intro, .place-detail-empty { margin: 0; }
.place-detail-eyebrow { color: #6b7280; font-size: 12px; }
h2 { margin: 4px 0 0; font-size: 20px; }
.place-detail-close { width: 28px; min-width: 28px; height: 28px; padding: 0; border: 0; border-radius: 50%; background: #f3f4f6; color: #333; cursor: pointer; font-size: 22px; line-height: 1; }
.place-detail-category { margin-top: 12px; color: #0b57d0; font-weight: 600; }
.place-detail-address, .place-detail-intro, .place-detail-empty { margin-top: 8px; color: #4b5563; font-size: 14px; line-height: 1.5; }
.place-detail-error { color: #b42318; font-size: 13px; }
.place-detail-meta { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; margin: 14px 0 0; }
.place-detail-meta div { padding: 8px; border-radius: 6px; background: #f8fafc; }
dt { color: #6b7280; font-size: 12px; }
dd { margin: 3px 0 0; color: #222; font-size: 13px; font-weight: 600; }
.tags { display: flex; gap: 5px; flex-wrap: wrap; margin-top: 12px; }
.tag { font-size: 12px; color: #1d4ed8; border-radius: 20px; background: #eff6ff; padding: 4px 8px; }
.place-detail-disclaimer { color: #6b7280; font-size: 11px; line-height: 1.5; margin-top: 12px; }
.place-detail-actions { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; margin-top: 16px; }
.place-detail-actions button { padding: 9px 8px; border: 1px solid #ddd; border-radius: 6px; background: white; color: #333; cursor: pointer; font-weight: 600; }
.place-detail-actions button:hover, .place-detail-actions button.active { border-color: #8ab4f8; background: #e8f0fe; color: #0b57d0; }
@media (max-width: 1180px) {
  .place-detail-panel {
    position: absolute;
    top: 50%;
    left: 50%;
    right: auto;
    bottom: auto;
    transform: translate(-50%, -50%);
    width: min(380px, calc(100vw - 36px));
    max-width: calc(100vw - 36px);
    max-height: min(70dvh, 580px);
    box-shadow: 0 12px 42px rgb(0 0 0 / 26%);
  }
}
</style>
