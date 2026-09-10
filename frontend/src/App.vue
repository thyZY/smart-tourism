<script setup>
import axios from 'axios'
import { ref, onMounted, onUnmounted, nextTick } from 'vue'
import { Map, NavigationControl, Popup, LngLatBounds, setWorkerUrl } from 'maplibre-gl'
import 'maplibre-gl/dist/maplibre-gl.css'
import workerUrl from 'maplibre-gl/dist/maplibre-gl-worker.mjs?worker&url'

setWorkerUrl(workerUrl)
const mapContainer = ref(null)
const searchQuery = ref('')
const searchMessage = ref('')
const searchResults = ref([])
const selectedPlaceId = ref(null)
const selectedCategory = ref('')

const categories = [
  '博物馆',
  '历史文化',
  '陵园景区',
  '寺庙宗教',
  '城市公园',
  '自然景区',
  '古迹遗址',
  '文化商业'
]


let map = null
let searchPopup = null

const loading = ref(false)
const mapReady = ref(false)
let requestController = null
const emptyPlaces = () => ({ type: 'FeatureCollection', features: [] })

const clearPopup = () => {
  searchPopup?.remove()
  searchPopup = null
}

const showPopup = (feature) => {
  clearPopup()
  const content = document.createElement('div')
  const name = document.createElement('strong')
  name.textContent = feature.properties.name
  content.append(name)
  const lines = [feature.properties.category, `地址：${feature.properties.address ?? ''}`]
  const distance = feature.properties.distance_km
  if (typeof distance === 'number' && Number.isFinite(distance)) {
    lines.push(`距离：${distance.toFixed(2)} km`)
  }
  for (const text of lines) {
    const line = document.createElement('div')
    line.textContent = text
    content.append(line)
  }
  searchPopup = new Popup().setLngLat(feature.geometry.coordinates)
    .setDOMContent(content).addTo(map)
}

const highlightSelectedPlace = (placeId) => {
  if (!map?.getLayer('places-points')) return

  map.setPaintProperty('places-points', 'circle-radius', [
    'case',
    ['==', ['get', 'id'], placeId],
    18,
    12
  ])

  map.setPaintProperty('places-points', 'circle-color', [
    'case',
    ['==', ['get', 'id'], placeId],
    '#ff9800',
    '#ff0000'
  ])
}

const scrollSelectedIntoView = async (placeId) => {
  await nextTick()

  const item = document.querySelector(
    `.result-item[data-place-id="${placeId}"]`
  )

  item?.scrollIntoView({
    behavior: 'smooth',
    block: 'nearest'
  })
}

const focusResult = (feature) => {
  if (!map || !feature?.geometry?.coordinates) return

  selectedPlaceId.value = feature.properties.id
  highlightSelectedPlace(feature.properties.id)
  scrollSelectedIntoView(feature.properties.id)

  map.flyTo({
    center: feature.geometry.coordinates,
    zoom: 15
  })

  showPopup(feature)
}

const overview = () => map.flyTo({ center: [118.7969, 32.0603], zoom: 10 })

const frameResults = (features) => {
  if (features.length === 1) {
    map.flyTo({ center: features[0].geometry.coordinates, zoom: 14 })
  } else if (features.length > 1) {
    const bounds = new LngLatBounds()
    features.forEach(feature => bounds.extend(feature.geometry.coordinates))
    map.fitBounds(bounds, { padding: 80, maxZoom: 14 })
  }
}

// All three request paths share one lock; the source exists before any request starts.
const loadPlaces = async (nearby = false, currentArea = false) => {
  if (!mapReady.value || loading.value) return

  loading.value = true
  clearPopup()
  searchMessage.value = ''
  map.stop()

  const q = searchQuery.value.trim()
  const center = map.getCenter()
  const bounds = currentArea ? map.getBounds() : null

  const controller = new AbortController()
  requestController = controller

  try {
    const response = await axios.get(
      `http://127.0.0.1:8010/api/places${nearby ? '/nearby' : ''}`,
      {
        params: nearby
          ? {
              lng: center.lng,
              lat: center.lat,
              radius: 5000,
              ...(selectedCategory.value
                ? { category: selectedCategory.value }
                : {})
            }
          : currentArea
            ? {
                min_lng: bounds.getWest(),
                min_lat: bounds.getSouth(),
                max_lng: bounds.getEast(),
                max_lat: bounds.getNorth(),
                ...(q ? { q } : {}),
                ...(selectedCategory.value
                  ? { category: selectedCategory.value }
                  : {})
              }
            : {
                ...(q ? { q } : {}),
                ...(selectedCategory.value
                  ? { category: selectedCategory.value }
                  : {})
              },

        signal: controller.signal,
        timeout: 10000
      }
    )

    if (controller.signal.aborted || !map) return

    const features = response.data.features

    searchResults.value = features
    map.getSource('places').setData(response.data)

    if (!features.length) {
      searchMessage.value = nearby
        ? '附近5公里内未找到景点'
        : currentArea
          ? '当前区域未找到景点'
          : '未找到相关景点'
    }

    if (nearby) {
      frameResults(features)
    } else if (currentArea) {
      // 当前区域查询不改变地图视野
    } else if ((!q && !selectedCategory.value) || !features.length) {
      overview()
    } else {
      frameResults(features)

      if (features.length === 1) {
        showPopup(features[0])
      }
    }
  } catch (error) {
    if (controller.signal.aborted || axios.isCancel(error)) return

    searchResults.value = []
    map?.getSource('places')?.setData(emptyPlaces())

    searchMessage.value = error.response
      ? '景点查询失败，请稍后重试'
      : '无法连接后端服务'
  } finally {
    if (requestController === controller) {
      requestController = null
      loading.value = false
    }
  }
}

const selectCategory = async (category) => {
  selectedCategory.value = category
  await loadPlaces(false)
}

const searchPlaces = () => loadPlaces()
const searchNearbyPlaces = () => loadPlaces(true)
const searchCurrentArea = () => loadPlaces(false, true)

onMounted(() => {
  map = new Map({
    container: mapContainer.value,
    style: {
      version: 8,
      sources: {
          osm: {
              type: 'raster',
              tiles: [
                'https://tile.openstreetmap.org/{z}/{x}/{y}.png'
              ],
              tileSize: 256,
              attribution: '© OpenStreetMap contributors'
           }
        },
        layers: [
           {
               id: 'osm',
               type: 'raster',
               source: 'osm'
           }
         ]
      },
    center: [118.7969, 32.0603],
    zoom: 10
  })

  map.addControl(
    new NavigationControl(),
    'top-right'
  )
  map.once('load', () => {
    map.addSource('places', { type: 'geojson', data: emptyPlaces() })
    map.addLayer({
      id: 'places-points',
      type: 'circle',
      source: 'places',
      paint: {
        'circle-radius': 12,
        'circle-color': '#ff0000',
        'circle-stroke-color': '#ffffff',
        'circle-stroke-width': 3
      }
    })
    map.on('click', 'places-points', (e) => {
      const feature = e.features?.[0]

      if (!feature) return

      selectedPlaceId.value = feature.properties.id
      highlightSelectedPlace(feature.properties.id)

      showPopup(feature)
    })
    map.on('mouseenter', 'places-points', () => {
      map.getCanvas().style.cursor = 'pointer'
    })
    map.on('mouseleave', 'places-points', () => {
      map.getCanvas().style.cursor = ''
    })
    mapReady.value = true
    void searchPlaces()
  })
})

onUnmounted(() => {
  mapReady.value = false
  requestController?.abort()
  clearPopup()
  map?.remove()
  map = null
})
</script>

<template>
  <div class="map-wrapper">
    <input
      v-model="searchQuery"
      class="search-box"
      aria-label="搜索景点"
      :disabled="loading || !mapReady"
      type="text"
      placeholder="搜索景点..."
      @keyup.enter="searchPlaces"
    />

    <button
      class="nearby-button"
      :disabled="loading || !mapReady"
      @click="searchNearbyPlaces"
    >
      {{ loading ? '加载中…' : '附近 5km' }}
    </button>

    <button
      @click="searchCurrentArea"
      :disabled="loading || !mapReady"
    >
      {{ loading ? '加载中...' : '搜索当前区域' }}
    </button>

  <div class="category-filter">
    <button
      class="category-button"
      :class="{ active: selectedCategory === '' }"
      @click="selectCategory('')"
    >
      全部
    </button>

    <button
      v-for="category in categories"
      :key="category"
      class="category-button"
      :class="{ active: selectedCategory === category }"
      @click="selectCategory(category)"
    >
      {{ category }}
    </button>
  </div>

  <div v-if="searchMessage" class="search-message" role="status">
    {{ searchMessage }}
  </div>

  <div v-if="searchResults.length" class="result-list">
    <div class="result-count">
      找到 {{ searchResults.length }} 个景点
    </div>

    <div
      v-for="feature in searchResults"
      :key="feature.properties.id"
      :data-place-id="feature.properties.id"
      :class="[
        'result-item',
        { 'result-item-selected': selectedPlaceId === feature.properties.id }
      ]"
      @click="focusResult(feature)"
    >
      <strong>{{ feature.properties.name }}</strong>
      <div>{{ feature.properties.category }}</div>
    </div>
  </div>

    <div ref="mapContainer" class="map"></div>
  </div>
</template>

<style>
html,
body,
#app {
  margin: 0;
  width: 100%;
  height: 100%;
}

body {
  overflow: hidden;
}

.map {
  width: 100vw;
  height: 100vh;
}

.map-wrapper {
  position: relative;
  width: 100vw;
  height: 100vh;
}

.search-box {
  position: absolute;
  top: 20px;
  left: 20px;
  z-index: 10;

  width: 260px;
  padding: 10px 14px;

  font-size: 16px;
  color: #222;
  border: 1px solid #ccc;
  border-radius: 6px;
  background: white;
  outline: none;
}

.search-box::placeholder {
  color: #777;
}

.search-message {
  position: absolute;
  top: 70px;
  left: 20px;
  z-index: 10;

  width: 260px;
  padding: 8px 14px;

  font-size: 14px;
  color: #b42318;
  background: white;
  border: 1px solid #f0b8b8;
  border-radius: 6px;
}

.nearby-button {
  position: absolute;
  top: 20px;
  left: 330px;
  z-index: 10;

  padding: 10px 16px;
  font-size: 16px;
  color: #222;

  border: 1px solid #ccc;
  border-radius: 6px;
  background: white;
  cursor: pointer;
}

.nearby-button:disabled {
  cursor: wait;
  opacity: 0.65;
}

.maplibregl-popup-content {
  color: #222;
  text-align: left;
}

.nearby-button:hover {
  background: #f5f5f5;
}

.result-list {
  position: absolute;
  top: 110px;
  left: 20px;
  z-index: 10;

  width: 280px;
  max-height: 420px;
  overflow-y: auto;

  background: white;
  border: 1px solid #ddd;
  border-radius: 6px;
}

.result-count {
  padding: 10px 12px;
  font-weight: bold;
  border-bottom: 1px solid #eee;
}

.result-item {
  padding: 10px 12px;
  border-bottom: 1px solid #eee;
  cursor: pointer;
}

.result-item:hover {
  background: #f5f5f5;
}

.result-item:last-child {
  border-bottom: none;
}

.result-item-selected {
  background: #e8f0fe;
  font-weight: 600;
}

.category-filter {
  position: absolute;
  top: 70px;
  left: 20px;
  z-index: 10;

  display: flex;
  flex-wrap: wrap;
  gap: 6px;

  width: 740px;
}

.category-button {
  padding: 6px 10px;
  border: 1px solid #ddd;
  border-radius: 6px;
  background: white;
  color: #333;
  white-space: nowrap;
  cursor: pointer;
}

.category-button:hover {
  background: #f5f5f5;
}

.category-button.active {
  background: #e8f0fe;
  border-color: #8ab4f8;
  font-weight: 600;
}
</style>
