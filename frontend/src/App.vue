<script setup>
import axios from 'axios'
import { ref, onMounted, onUnmounted, nextTick } from 'vue'
import { Map, NavigationControl, Popup, LngLatBounds, setWorkerUrl } from 'maplibre-gl'
import StatisticsPanel from './components/StatisticsPanel.vue'
import RoutePanel from './components/RoutePanel.vue'
import 'maplibre-gl/dist/maplibre-gl.css'
import workerUrl from 'maplibre-gl/dist/maplibre-gl-worker.mjs?worker&url'

setWorkerUrl(workerUrl)
const mapContainer = ref(null)
const searchQuery = ref('')
const searchMessage = ref('')
const searchResults = ref([])
const selectedPlaceId = ref(null)
const selectedCategory = ref('')
const mapDisplayMode = ref('points')
const selectedRoutePlaces = ref([])
const routeDistanceKm = ref(0)
const favoriteStorageKey = 'smart-tourism-favorites'

const readFavoritePlaceIds = () => {
  try {
    const savedIds = JSON.parse(localStorage.getItem(favoriteStorageKey) ?? '[]')
    if (!Array.isArray(savedIds)) return []

    return [...new Set(savedIds.filter((id) => Number.isInteger(id)))]
  } catch {
    return []
  }
}

const favoritePlaceIds = ref(readFavoritePlaceIds())
const showFavoritesOnly = ref(false)
let allPlacesCache = null

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
const emptyRoute = () => ({ type: 'FeatureCollection', features: [] })

const persistFavorites = () => {
  try {
    localStorage.setItem(favoriteStorageKey, JSON.stringify(favoritePlaceIds.value))
  } catch {
    // Storage can be unavailable or full; favorites remain usable for this session.
  }
}

const isFavorite = (placeId) => favoritePlaceIds.value.includes(placeId)

const favoriteCollection = () => {
  const favoriteIds = new Set(favoritePlaceIds.value)
  const features = (allPlacesCache?.features ?? []).filter(
    (feature) => favoriteIds.has(feature.properties.id)
  )

  return { type: 'FeatureCollection', features }
}

const renderFavoritePlaces = () => {
  const collection = favoriteCollection()
  searchResults.value = collection.features
  map?.getSource('places')?.setData(collection)
  searchMessage.value = collection.features.length ? '' : '暂无收藏景点'
}

const toggleFavorite = (feature) => {
  const placeId = feature?.properties?.id
  if (placeId == null) return

  favoritePlaceIds.value = isFavorite(placeId)
    ? favoritePlaceIds.value.filter((id) => id !== placeId)
    : [...favoritePlaceIds.value, placeId]
  persistFavorites()

  if (showFavoritesOnly.value) renderFavoritePlaces()
}

const showFavoritePlaces = async () => {
  if (!mapReady.value || loading.value) return

  showFavoritesOnly.value = true
  clearPopup()
  searchMessage.value = ''

  if (allPlacesCache) {
    renderFavoritePlaces()
    return
  }

  loading.value = true
  const controller = new AbortController()
  requestController = controller

  try {
    const response = await axios.get('http://127.0.0.1:8010/api/places', {
      signal: controller.signal,
      timeout: 10000
    })
    if (controller.signal.aborted || !map) return

    allPlacesCache = response.data
    renderFavoritePlaces()
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

const calculateDistanceKm = (from, to) => {
  const [fromLng, fromLat] = from
  const [toLng, toLat] = to
  const toRadians = (degrees) => degrees * Math.PI / 180
  const deltaLat = toRadians(toLat - fromLat)
  const deltaLng = toRadians(toLng - fromLng)
  const a = Math.sin(deltaLat / 2) ** 2 +
    Math.cos(toRadians(fromLat)) * Math.cos(toRadians(toLat)) *
    Math.sin(deltaLng / 2) ** 2

  return 6371 * 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a))
}

const updateRoute = () => {
  const routeCoordinates = selectedRoutePlaces.value
    .map((feature) => feature.geometry?.coordinates)
    .filter((coordinates) => Array.isArray(coordinates))

  routeDistanceKm.value = routeCoordinates.slice(1).reduce(
    (total, currentCoordinates, index) => total + calculateDistanceKm(
      routeCoordinates[index],
      currentCoordinates
    ),
    0
  )

  const routeData = routeCoordinates.length >= 2
    ? {
        type: 'FeatureCollection',
        features: [{
          type: 'Feature',
          properties: {},
          geometry: { type: 'LineString', coordinates: routeCoordinates }
        }]
      }
    : emptyRoute()

  map?.getSource('route-line')?.setData(routeData)
}

const toggleRoutePlace = (feature) => {
  const placeId = feature?.properties?.id
  if (placeId == null) return

  const existingIndex = selectedRoutePlaces.value.findIndex(
    (place) => place.properties.id === placeId
  )

  if (existingIndex === -1) {
    selectedRoutePlaces.value = [...selectedRoutePlaces.value, feature]
  } else {
    selectedRoutePlaces.value = selectedRoutePlaces.value.filter(
      (place) => place.properties.id !== placeId
    )
  }

  updateRoute()
}

const clearRoute = () => {
  selectedRoutePlaces.value = []
  updateRoute()
}

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
  const favoriteButton = document.createElement('button')
  const updateFavoriteButton = () => {
    favoriteButton.textContent = isFavorite(feature.properties.id) ? '取消收藏' : '收藏'
  }
  updateFavoriteButton()
  favoriteButton.addEventListener('click', (event) => {
    event.stopPropagation()
    toggleFavorite(feature)
    updateFavoriteButton()
  })
  content.append(favoriteButton)
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

const setMapDisplayMode = (mode) => {
  if (!map?.getLayer('places-points') || !map.getLayer('places-heatmap')) return

  mapDisplayMode.value = mode
  map.setLayoutProperty('places-points', 'visibility', mode === 'points' ? 'visible' : 'none')
  map.setLayoutProperty('places-heatmap', 'visibility', mode === 'heatmap' ? 'visible' : 'none')
}

// All three request paths share one lock; the source exists before any request starts.
const loadPlaces = async (nearby = false, currentArea = false) => {
  if (!mapReady.value || loading.value) return

  showFavoritesOnly.value = false
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

    if (!nearby && !currentArea && !q && !selectedCategory.value) {
      allPlacesCache = response.data
    }
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
  showFavoritesOnly.value = false
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
    map.addSource('route-line', { type: 'geojson', data: emptyRoute() })
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
    map.addLayer({
      id: 'places-heatmap',
      type: 'heatmap',
      source: 'places',
      layout: {
        visibility: 'none'
      },
      paint: {
        'heatmap-intensity': 1.1,
        'heatmap-radius': [
          'interpolate', ['linear'], ['zoom'],
          8, 18,
          14, 40
        ],
        'heatmap-opacity': 0.85,
        'heatmap-color': [
          'interpolate', ['linear'], ['heatmap-density'],
          0, 'rgba(33, 102, 172, 0)',
          0.25, '#4dabf7',
          0.5, '#ffd43b',
          0.75, '#ff922b',
          1, '#e03131'
        ]
      }
    })
    map.addLayer({
      id: 'route-line',
      type: 'line',
      source: 'route-line',
      layout: {
        'line-join': 'round',
        'line-cap': 'round'
      },
      paint: {
        'line-color': '#2563eb',
        'line-width': 5,
        'line-opacity': 0.85
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
    <StatisticsPanel />
    <RoutePanel
      :places="selectedRoutePlaces"
      :distance-km="routeDistanceKm"
      @clear="clearRoute"
    />

    <div class="map-display-control" role="group" aria-label="地图显示模式">
      <button
        type="button"
        :class="{ active: mapDisplayMode === 'points' }"
        :disabled="!mapReady"
        @click="setMapDisplayMode('points')"
      >
        点位
      </button>
      <button
        type="button"
        :class="{ active: mapDisplayMode === 'heatmap' }"
        :disabled="!mapReady"
        @click="setMapDisplayMode('heatmap')"
      >
        热力图
      </button>
    </div>

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
      class="favorites-button"
      :class="{ active: showFavoritesOnly }"
      :disabled="loading || !mapReady"
      @click="showFavoritePlaces"
    >
      我的收藏 ({{ favoritePlaceIds.length }})
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
        {
          'result-item-selected': selectedPlaceId === feature.properties.id,
          'result-item-route-selected': selectedRoutePlaces.some(
            (place) => place.properties.id === feature.properties.id
          )
        }
      ]"
      @click="toggleRoutePlace(feature); focusResult(feature)"
    >
      <button
        class="favorite-toggle"
        type="button"
        :aria-label="isFavorite(feature.properties.id) ? '取消收藏' : '收藏'"
        :title="isFavorite(feature.properties.id) ? '取消收藏' : '收藏'"
        @click.stop="toggleFavorite(feature)"
      >
        {{ isFavorite(feature.properties.id) ? '★' : '☆' }}
      </button>
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

.favorites-button {
  position: absolute;
  top: 20px;
  left: 460px;
  z-index: 10;
  padding: 10px 16px;
  border: 1px solid #ccc;
  border-radius: 6px;
  background: white;
  color: #222;
  cursor: pointer;
}

.favorites-button:hover:not(:disabled),
.favorites-button.active {
  background: #e8f0fe;
  border-color: #8ab4f8;
}

.favorites-button:disabled {
  cursor: wait;
  opacity: 0.65;
}

.map-display-control {
  position: absolute;
  top: 20px;
  right: 70px;
  z-index: 10;

  display: flex;
  overflow: hidden;
  border: 1px solid #ddd;
  border-radius: 6px;
  background: white;
}

.map-display-control button {
  padding: 8px 10px;
  border: 0;
  border-right: 1px solid #ddd;
  background: white;
  color: #333;
  cursor: pointer;
}

.map-display-control button:last-child {
  border-right: 0;
}

.map-display-control button:hover:not(:disabled) {
  background: #f5f5f5;
}

.map-display-control button.active {
  background: #e8f0fe;
  color: #0b57d0;
  font-weight: 600;
}

.map-display-control button:disabled {
  cursor: wait;
  opacity: 0.65;
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
  position: relative;
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

.result-item-route-selected {
  border-left: 4px solid #2563eb;
  padding-left: 8px;
}

.favorite-toggle {
  position: absolute;
  top: 8px;
  right: 8px;
  padding: 0;
  border: 0;
  background: transparent;
  color: #d97706;
  cursor: pointer;
  font-size: 24px;
  line-height: 1;
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
