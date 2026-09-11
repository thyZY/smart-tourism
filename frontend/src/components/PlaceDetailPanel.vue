<script setup>
import { computed } from 'vue'

const props = defineProps({
  place: { type: Object, default: null },
  placeDetails: { type: Object, required: true },
  isFavorite: { type: Boolean, default: false },
  isInRoute: { type: Boolean, default: false }
})

defineEmits(['close', 'toggle-favorite', 'toggle-route'])

const detail = computed(() => {
  const placeId = props.place?.properties?.id
  return placeId == null ? null : props.placeDetails[placeId]
})
</script>

<template>
  <aside v-if="place" class="place-detail-panel" aria-label="景点详情">
    <div class="place-detail-header">
      <div>
        <p class="place-detail-eyebrow">景点详情</p>
        <h2>{{ place.properties.name }}</h2>
      </div>
      <button class="place-detail-close" type="button" aria-label="关闭详情" @click="$emit('close')">×</button>
    </div>

    <p class="place-detail-category">{{ place.properties.category }}</p>
    <p class="place-detail-address">{{ place.properties.address || '暂无地址信息' }}</p>

    <template v-if="detail">
      <p class="place-detail-intro">{{ detail.intro }}</p>
      <dl class="place-detail-meta">
        <div><dt>开放时间</dt><dd>{{ detail.opening }}</dd></div>
        <div><dt>推荐指数</dt><dd>{{ detail.rating }}</dd></div>
      </dl>
    </template>
    <p v-else class="place-detail-empty">暂无详细介绍</p>

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
  right: 290px;
  bottom: 30px;
  z-index: 10;
  box-sizing: border-box;
  width: 290px;
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
.place-detail-close { width: 28px; height: 28px; padding: 0; border: 0; border-radius: 50%; background: #f3f4f6; color: #333; cursor: pointer; font-size: 22px; line-height: 1; }
.place-detail-category { margin-top: 12px; color: #0b57d0; font-weight: 600; }
.place-detail-address, .place-detail-intro, .place-detail-empty { margin-top: 8px; color: #4b5563; font-size: 14px; line-height: 1.5; }
.place-detail-meta { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; margin: 14px 0 0; }
.place-detail-meta div { padding: 8px; border-radius: 6px; background: #f8fafc; }
dt { color: #6b7280; font-size: 12px; }
dd { margin: 3px 0 0; color: #222; font-size: 14px; font-weight: 600; }
.place-detail-actions { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; margin-top: 16px; }
.place-detail-actions button { padding: 9px 8px; border: 1px solid #ddd; border-radius: 6px; background: white; color: #333; cursor: pointer; font-weight: 600; }
.place-detail-actions button:hover, .place-detail-actions button.active { border-color: #8ab4f8; background: #e8f0fe; color: #0b57d0; }
</style>
