<script setup>
import axios from 'axios'
import { ref, onMounted, onUnmounted, nextTick } from 'vue'
import { Map, NavigationControl, Popup, LngLatBounds, setWorkerUrl } from 'maplibre-gl'
import StatisticsPanel from './components/StatisticsPanel.vue'
import NaturalSearchPanel from './components/NaturalSearchPanel.vue'
import ItineraryPreviewPanel from './components/ItineraryPreviewPanel.vue'
import RoutePanel from './components/RoutePanel.vue'
import PlaceDetailPanel from './components/PlaceDetailPanel.vue'
import ThemePanel from './components/ThemePanel.vue'
import themes from './data/themes.js'
import 'maplibre-gl/dist/maplibre-gl.css'
import workerUrl from 'maplibre-gl/dist/maplibre-gl-worker.mjs?worker&url'

setWorkerUrl(workerUrl)
const mapContainer = ref(null)
const searchQuery = ref('')
const searchMessage = ref('')
const searchResults = ref([])
const naturalSearchCenter = ref({ lng: 118.7969, lat: 32.0603 })
const selectedPlaceId = ref(null)
const selectedPlace = ref(null)
const selectedCategory = ref('')
const mapDisplayMode = ref('points')
const selectedRoutePlaces = ref([])
const routeDistanceKm = ref(0)
const roadRoute = ref(null)
const roadRoutePending = ref(false)
const roadRouteError = ref('')
const roadMode = ref('pedestrian')
const roadResults = ref({})
const multiRoute = ref(null)
const multiPending = ref(false)
const multiError = ref('')
const multiResults = ref({})
let multiRequestController = null
const roadModeColors = { pedestrian: '#16a34a', bicycle: '#f97316', auto: '#2563eb' }
let roadRequestController = null
const selectedTheme = ref(null)
const favoriteStorageKey = 'smart-tourism-favorites'
const tourismCard = ref(null)
const tourismLoading = ref(false)
const tourismError = ref('')
let detailRequestController = null

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
let themeBaseFeatures = null

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

  exitThemeMode()
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

const resetRoadRoute = (clearResults = true) => {
  roadRequestController?.abort()
  roadRequestController = null
  roadRoute.value = null
  roadRoutePending.value = false
  roadRouteError.value = ''
  if (clearResults) roadResults.value = {}
  map?.getSource('road-route')?.setData(emptyRoute())
  if (map?.getLayer('route-line')) {
    map.setLayoutProperty('route-line', 'visibility', 'visible')
  }
}

const resetMultiRoute = (clearResults = true) => {
  multiRequestController?.abort()
  multiRequestController = null
  multiRoute.value = null
  multiPending.value = false
  multiError.value = ''
  if (clearResults) multiResults.value = {}
}

const showMultiRoute = (result) => {
  multiRoute.value = result
  map?.getSource('road-route')?.setData(result.geometry)
  if (map?.getLayer('road-route')) {
    map.setPaintProperty('road-route', 'line-color', roadModeColors[result.mode])
  }
  if (map?.getLayer('route-line')) {
    map.setLayoutProperty('route-line', 'visibility', 'none')
  }
}

const showRoadResult = (feature) => {
  roadRoute.value = feature.properties
  map?.getSource('road-route')?.setData({ type: 'FeatureCollection', features: [feature] })
  if (map?.getLayer('road-route')) {
    map.setPaintProperty('road-route', 'line-color', roadModeColors[feature.properties.mode])
  }
  if (map?.getLayer('route-line')) {
    map.setLayoutProperty('route-line', 'visibility', 'none')
  }
}

const selectRoadMode = (mode) => {
  if (!Object.prototype.hasOwnProperty.call(roadModeColors, mode)) return
  resetRoadRoute(false)
  resetMultiRoute(false)
  roadMode.value = mode
  if (selectedRoutePlaces.value.length >= 3) {
    const cachedMulti = multiResults.value[mode]
    if (cachedMulti) showMultiRoute(cachedMulti)
  } else {
    const cached = roadResults.value[mode]
    if (cached) showRoadResult(cached)
  }
}

const updateRoute = () => {
  // Every selection change invalidates an earlier road geometry or in-flight request.
  resetRoadRoute()
  resetMultiRoute()
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

const calculateRoadRoute = async () => {
  if (!mapReady.value || !map || roadRoutePending.value ||
      selectedRoutePlaces.value.length !== 2) return

  const [from, to] = selectedRoutePlaces.value
  const controller = new AbortController()
  roadRequestController = controller
  roadRoutePending.value = true
  roadRouteError.value = ''
  try {
    const response = await axios.post('http://127.0.0.1:8010/api/routing/route', {
      from_id: from.properties.id,
      to_id: to.properties.id,
      mode: roadMode.value
    }, { signal: controller.signal, timeout: 20000 })
    if (controller.signal.aborted || roadRequestController !== controller) return
    const feature = response.data
    if (feature.type !== 'Feature' || feature.geometry?.type !== 'LineString' ||
        !Array.isArray(feature.geometry.coordinates) || feature.geometry.coordinates.length < 2 ||
        feature.properties?.mode !== roadMode.value ||
        !Number.isFinite(feature.properties?.distance_km) ||
        !Number.isFinite(feature.properties?.duration_minutes)) {
      throw new Error('道路寻路结果缺少有效折线或交通方式不一致')
    }
    roadResults.value = { ...roadResults.value, [roadMode.value]: feature }
    showRoadResult(feature)
  } catch (error) {
    if (controller.signal.aborted || axios.isCancel(error)) return
    roadRoute.value = null
    roadRouteError.value = error.response?.data?.detail || '道路寻路失败，仍可查看原有直线预览'
  } finally {
    if (roadRequestController === controller) {
      roadRequestController = null
      roadRoutePending.value = false
    }
  }
}

const calculateMultiRoute = async () => {
  const places = selectedRoutePlaces.value
  if (!mapReady.value || !map || multiPending.value || places.length < 3 || places.length > 6) return

  const controller = new AbortController()
  multiRequestController = controller
  multiPending.value = true
  multiError.value = ''
  try {
    const response = await axios.post('http://127.0.0.1:8010/api/routing/itinerary', {
      place_ids: places.map(p => p.properties.id),
      mode: roadMode.value
    }, { signal: controller.signal, timeout: 60000 })
    if (controller.signal.aborted || multiRequestController !== controller) return
    const result = response.data
    const selectedIds = places.map(p => p.properties.id)
    if (result.mode !== roadMode.value ||
        result.geometry?.type !== 'FeatureCollection' ||
        result.geometry.features?.length !== selectedIds.length - 1 ||
        result.optimized_order_ids?.length !== selectedIds.length ||
        result.optimized_order_ids[0] !== selectedIds[0] ||
        result.optimized_order_ids.some(id => !selectedIds.includes(id)) ||
        !Number.isFinite(result.distance_km) ||
        !Number.isFinite(result.duration_minutes)) {
      throw new Error('多站路线响应与景点选择不一致')
    }
    multiResults.value = { ...multiResults.value, [roadMode.value]: result }
    showMultiRoute(result)
  } catch (error) {
    if (controller.signal.aborted || axios.isCancel(error)) return
    multiRoute.value = null
    multiError.value = typeof error.response?.data?.detail === 'string'
      ? error.response.data.detail
      : '多站道路规划失败；仍可使用原有直线顺序预览'
    map?.getSource('road-route')?.setData(emptyRoute())
    if (map?.getLayer('route-line')) {
      map.setLayoutProperty('route-line', 'visibility', 'visible')
    }
  } finally {
    if (multiRequestController === controller) {
      multiRequestController = null
      multiPending.value = false
    }
  }
}

const exitThemeMode = () => {
  selectedTheme.value = null
  themeBaseFeatures = null
}

const selectTheme = (theme) => {
  if (!mapReady.value || loading.value || !theme) return

  if (!selectedTheme.value) themeBaseFeatures = searchResults.value

  selectedTheme.value = theme
  showFavoritesOnly.value = false
  clearPopup()

  const features = (themeBaseFeatures ?? searchResults.value).filter(
    (feature) => theme.categories.includes(feature.properties.category)
  )
  const collection = { type: 'FeatureCollection', features }

  searchResults.value = features
  map?.getSource('places')?.setData(collection)
  selectedRoutePlaces.value = features
  updateRoute()
  searchMessage.value = features.length ? '' : '该主题暂无景点'

  if (selectedPlace.value && !features.some(
    (feature) => feature.properties.id === selectedPlace.value.properties.id
  )) {
    closePlaceDetail()
  }
}

const clearPopup = () => {
  searchPopup?.remove()
  searchPopup = null
}

const closePlaceDetail = () => {
  detailRequestController?.abort()
  detailRequestController = null
  selectedPlace.value = null
  selectedPlaceId.value = null
  tourismCard.value = null
  tourismError.value = ''
  tourismLoading.value = false
  highlightSelectedPlace(null)
}

const openPlaceDetail = async (feature) => {
  const placeId = feature?.properties?.id
  if (!Number.isInteger(placeId) || placeId <= 0) return

  detailRequestController?.abort()
  const controller = new AbortController()
  detailRequestController = controller
  selectedPlace.value = feature
  selectedPlaceId.value = placeId
  tourismCard.value = null
  tourismError.value = ''
  tourismLoading.value = true
  clearPopup()
  highlightSelectedPlace(placeId)

  try {
    const response = await axios.get(
      `http://127.0.0.1:8010/api/tourism/places/${placeId}`,
      { signal: controller.signal, timeout: 10000 }
    )
    if (!controller.signal.aborted && selectedPlaceId.value === placeId) {
      tourismCard.value = response.data
    }
  } catch (error) {
    if (controller.signal.aborted || axios.isCancel(error)) return
    tourismError.value = error.response?.status === 404
      ? '数据库中未找到该景点'
      : '旅游资料加载失败，请检查后端或数据库'
  } finally {
    if (detailRequestController === controller) {
      detailRequestController = null
      tourismLoading.value = false
    }
  }
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

  openPlaceDetail(feature)
  scrollSelectedIntoView(feature.properties.id)

  map.flyTo({
    center: feature.geometry.coordinates,
    zoom: 15
  })

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

const applyItineraryPreview = (stops) => {
  if (!mapReady.value || !map || loading.value) return
  exitThemeMode()
  selectedRoutePlaces.value = Array.isArray(stops) ? [...stops] : []
  updateRoute()
  if (selectedRoutePlaces.value.length) frameResults(selectedRoutePlaces.value)
}

const applyNaturalResults = (collection) => {
  if (!map || !mapReady.value || loading.value) return
  exitThemeMode()
  showFavoritesOnly.value = false
  clearPopup()
  closePlaceDetail()
  searchResults.value = collection.features ?? []
  map.getSource('places')?.setData(collection)
  searchMessage.value = searchResults.value.length ? '' : '没有找到符合条件的已收录景点'
  if (searchResults.value.length) frameResults(searchResults.value)
}

const applyAiPlan = (plan) => {
  if (!map || !mapReady.value || loading.value) return
  const places = plan?.selected_places?.features
  const result = plan?.itinerary
  const ids = result?.optimized_order_ids
  if (!Array.isArray(places) || !Array.isArray(ids) ||
      ids.length < 3 || ids.length > 6 || places.length !== ids.length ||
      !Object.prototype.hasOwnProperty.call(roadModeColors, result.mode) ||
      result.geometry?.type !== 'FeatureCollection' ||
      result.geometry.features?.length !== ids.length - 1) return
  const byId = new Map(places.map(place => [place.properties?.id, place]))
  if (byId.size !== ids.length || ids.some(id => !byId.has(id))) return

  exitThemeMode()
  showFavoritesOnly.value = false
  clearPopup()
  closePlaceDetail()
  const ordered = ids.map(id => byId.get(id))
  searchResults.value = ordered
  map.getSource('places')?.setData({ type: 'FeatureCollection', features: ordered })
  roadMode.value = result.mode
  selectedRoutePlaces.value = ordered
  // Preserve exactly the computed geometry and avoid recalculating travel with straight lines.
  updateRoute()
  multiResults.value = { [result.mode]: result }
  showMultiRoute(result)
  searchMessage.value = ''
  frameResults(ordered)
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

  exitThemeMode()
  showFavoritesOnly.value = false
  loading.value = true
  clearPopup()
  searchMessage.value = ''
  map.stop()

  const q = searchQuery.value.trim()
  const center = map.getCenter()
  naturalSearchCenter.value = { lng: center.lng, lat: center.lat }
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
    map.addSource('road-route', { type: 'geojson', data: emptyRoute() })
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
        'line-opacity': 0.85,
        'line-dasharray': [2, 2]
      }
    })
    map.addLayer({
      id: 'road-route',
      type: 'line',
      source: 'road-route',
      layout: { 'line-join': 'round', 'line-cap': 'round' },
      paint: { 'line-color': '#16a34a', 'line-width': 6, 'line-opacity': 0.92 }
    })
    map.on('click', 'places-points', (e) => {
      const feature = e.features?.[0]

      if (!feature) return

      openPlaceDetail(feature)
    })
    map.on('mouseenter', 'places-points', () => {
      map.getCanvas().style.cursor = 'pointer'
    })
    map.on('mouseleave', 'places-points', () => {
      map.getCanvas().style.cursor = ''
    })
    map.on('moveend', () => {
      const center = map.getCenter()
      naturalSearchCenter.value = { lng: center.lng, lat: center.lat }
    })
    mapReady.value = true
    void searchPlaces()
  })
})

onUnmounted(() => {
  mapReady.value = false
  detailRequestController?.abort()
  roadRequestController?.abort()
  multiRequestController?.abort()
  requestController?.abort()
  clearPopup()
  map?.remove()
  map = null
})
</script>

<template>
  <main class="map-wrapper" aria-label="南京智慧文旅地图">
    <div ref="mapContainer" class="map" aria-label="南京景点地图"></div>

    <header class="map-toolbar" aria-label="地图检索工具">
      <input
        v-model="searchQuery"
        class="search-box"
        aria-label="搜索景点"
        :disabled="loading || !mapReady"
        type="search"
        placeholder="搜索南京景点..."
        @keyup.enter="searchPlaces"
      />
      <button class="toolbar-button nearby-button" type="button" :disabled="loading || !mapReady" @click="searchNearbyPlaces">
        {{ loading ? '加载中…' : '附近 5km' }}
      </button>
      <button class="toolbar-button favorites-button" type="button"
        :class="{ active: showFavoritesOnly }" :disabled="loading || !mapReady" @click="showFavoritePlaces">
        我的收藏 ({{ favoritePlaceIds.length }})
      </button>
      <button class="toolbar-button area-button" type="button" :disabled="loading || !mapReady" @click="searchCurrentArea">
        {{ loading ? '加载中…' : '搜索当前区域' }}
      </button>

      <div class="map-display-control" role="group" aria-label="地图显示模式">
        <button type="button" :class="{ active: mapDisplayMode === 'points' }"
          :disabled="!mapReady" @click="setMapDisplayMode('points')">点位</button>
        <button type="button" :class="{ active: mapDisplayMode === 'heatmap' }"
          :disabled="!mapReady" @click="setMapDisplayMode('heatmap')">热力图</button>
      </div>
    </header>

    <nav class="category-filter" aria-label="景点类型筛选">
      <button class="category-button" type="button"
        :class="{ active: selectedCategory === '' }" @click="selectCategory('')">全部</button>
      <button v-for="category in categories" :key="category" type="button"
        class="category-button" :class="{ active: selectedCategory === category }"
        @click="selectCategory(category)">{{ category }}</button>
    </nav>

    <section class="left-workspace" aria-label="景点发现">
      <div v-if="searchMessage" class="search-message" role="status">{{ searchMessage }}</div>

      <div v-if="searchResults.length" class="result-list">
        <div class="result-count">找到 {{ searchResults.length }} 个景点</div>
        <div v-for="feature in searchResults" :key="feature.properties.id"
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
          @click="focusResult(feature)">
          <button class="favorite-toggle" type="button"
            :aria-label="isFavorite(feature.properties.id) ? '取消收藏' : '收藏'"
            :title="isFavorite(feature.properties.id) ? '取消收藏' : '收藏'"
            @click.stop="toggleFavorite(feature)">
            {{ isFavorite(feature.properties.id) ? '★' : '☆' }}
          </button>
          <strong>{{ feature.properties.name }}</strong>
          <div class="result-category">{{ feature.properties.category }}</div>
        </div>
      </div>

      <div class="left-tools">
        <ItineraryPreviewPanel :map-ready="mapReady" :center="naturalSearchCenter"
          @route="applyItineraryPreview" />
        <NaturalSearchPanel :map-ready="mapReady" :center="naturalSearchCenter"
          @results="applyNaturalResults" @route="applyItineraryPreview" @planned="applyAiPlan" />
      </div>
    </section>

    <section class="right-workspace" aria-label="行程规划与信息">
      <RoutePanel
        :places="selectedRoutePlaces"
        :distance-km="routeDistanceKm"
        :road-route="roadRoute"
        :road-pending="roadRoutePending"
        :road-error="roadRouteError"
        :road-mode="roadMode"
        :road-results="roadResults"
        :multi-route="multiRoute"
        :multi-pending="multiPending"
        :multi-error="multiError"
        :multi-results="multiResults"
        @calculate-multi="calculateMultiRoute"
        @change-mode="selectRoadMode"
        @calculate-road="calculateRoadRoute"
        @clear="clearRoute"
      />
      <ThemePanel :themes="themes" :selected-theme="selectedTheme" @select="selectTheme" />
      <StatisticsPanel />
    </section>

    <PlaceDetailPanel
      :place="selectedPlace"
      :tourism-card="tourismCard"
      :tourism-loading="tourismLoading"
      :tourism-error="tourismError"
      :is-favorite="selectedPlace ? isFavorite(selectedPlace.properties.id) : false"
      :is-in-route="selectedPlace ? selectedRoutePlaces.some((place) => place.properties.id === selectedPlace.properties.id) : false"
      @close="closePlaceDetail"
      @toggle-favorite="selectedPlace && toggleFavorite(selectedPlace)"
      @toggle-route="selectedPlace && toggleRoutePlace(selectedPlace)"
    />
  </main>
</template>

<style>
html, body, #app {
  margin: 0;
  width: 100%;
  height: 100%;
}
body { overflow: hidden; }

.map-wrapper {
  --rail-width: 320px;
  --workspace-top: 126px;
  position: relative;
  width: 100vw;
  height: 100vh;
  height: 100dvh;
  overflow: hidden;
  font-family: system-ui, 'Microsoft YaHei', 'Segoe UI', sans-serif;
  font-size: 14px;
  color: #182534;
}
.map { position: absolute; inset: 0; width: 100%; height: 100%; }
.map-wrapper button, .map-wrapper input { font: inherit; }
.map-wrapper button:focus-visible,
.map-wrapper input:focus-visible,
.map-wrapper summary:focus-visible {
  outline: 2px solid #2563eb;
  outline-offset: 2px;
}
.maplibregl-popup-content { color: #243346; text-align: left; }

.map-toolbar {
  position: absolute;
  top: 14px;
  left: 16px;
  right: 76px;
  z-index: 14;
  box-sizing: border-box;
  display: flex;
  align-items: center;
  gap: 8px;
  min-width: 0;
}
.search-box {
  flex: 0 1 270px;
  min-width: 165px;
  padding: 11px 12px;
  border: 1px solid #d4dee9;
  border-radius: 10px;
  background: #fff;
  color: #172638;
  box-shadow: 0 3px 12px #12253e18;
  outline: none;
}
.search-box::placeholder { color: #7b8797; }
.toolbar-button {
  flex: 0 0 auto;
  white-space: nowrap;
  padding: 10px 13px;
  border: 1px solid #d4dee9;
  border-radius: 10px;
  background: #fff;
  color: #1c3047;
  box-shadow: 0 3px 12px #12253e12;
  cursor: pointer;
}
.toolbar-button:hover:not(:disabled), .toolbar-button.active {
  background: #eef5ff;
  border-color: #9cc3ff;
}
.toolbar-button:disabled, .map-display-control button:disabled { opacity: 0.6; cursor: wait; }
.map-display-control {
  display: flex;
  flex: 0 0 auto;
  margin-left: auto;
  overflow: hidden;
  border: 1px solid #d4dee9;
  border-radius: 10px;
  background: #fff;
  box-shadow: 0 3px 12px #12253e12;
}
.map-display-control button {
  padding: 10px 11px;
  border: 0;
  border-right: 1px solid #e5eaf0;
  background: transparent;
  color: #37465c;
  cursor: pointer;
  white-space: nowrap;
}
.map-display-control button:last-child { border-right: 0; }
.map-display-control button.active { background: #e6f0ff; color: #0b57d0; font-weight: 700; }

.category-filter {
  position: absolute;
  top: 72px;
  left: 16px;
  right: calc(var(--rail-width) + 32px);
  z-index: 13;
  box-sizing: border-box;
  display: flex;
  flex-wrap: nowrap;
  gap: 6px;
  min-width: 0;
  padding: 2px 1px 7px;
  overflow-x: auto;
  scrollbar-width: thin;
}
.category-button {
  flex: 0 0 auto;
  white-space: nowrap;
  padding: 8px 11px;
  border: 1px solid #d5dfeb;
  border-radius: 9px;
  background: #fff;
  color: #37465c;
  cursor: pointer;
  box-shadow: 0 2px 8px #12253e12;
}
.category-button:hover, .category-button.active {
  background: #eaf2ff;
  border-color: #9bbfff;
  color: #1356ac;
}
.category-button.active { font-weight: 700; }

.left-workspace, .right-workspace {
  position: absolute;
  top: var(--workspace-top);
  bottom: 16px;
  z-index: 12;
  display: flex;
  flex-direction: column;
  gap: 10px;
  width: var(--rail-width);
  min-height: 0;
  box-sizing: border-box;
}
.left-workspace { left: 16px; pointer-events: none; }
.right-workspace { right: 16px; }
.left-workspace > *, .right-workspace > * { pointer-events: auto; min-width: 0; }
.left-tools { display: flex; flex-direction: column; gap: 10px; flex: 0 0 auto; }
.search-message {
  flex: 0 0 auto;
  max-height: 72px;
  overflow-y: auto;
  padding: 9px 12px;
  border: 1px solid #ffddbc;
  border-radius: 9px;
  background: #fff8ee;
  color: #9a3412;
  box-shadow: 0 2px 8px #12253e12;
}
.result-list {
  flex: 1 1 auto;
  min-height: 70px;
  max-height: min(48vh, 440px);
  overflow-y: auto;
  border: 1px solid #dbe4ee;
  border-radius: 12px;
  background: #fff;
  box-shadow: 0 4px 16px #0c274024;
}
.result-count {
  position: sticky;
  top: 0;
  z-index: 1;
  padding: 11px 14px;
  border-bottom: 1px solid #e5edf5;
  background: #f8fbff;
  color: #38516c;
  font-weight: 700;
  text-align: left;
}
.result-item {
  position: relative;
  padding: 10px 46px 10px 14px;
  border-bottom: 1px solid #edf1f6;
  background: #fff;
  cursor: pointer;
  text-align: left;
}
.result-item:last-child { border-bottom: none; }
.result-item:hover { background: #f3f7fd; }
.result-item strong { display: block; font-size: 14px; color: #25374b; }
.result-category { margin-top: 3px; color: #78899b; font-size: 12px; }
.result-item-selected { background: #eaf3ff; }
.result-item-route-selected { border-left: 4px solid #2563eb; padding-left: 10px; }
.favorite-toggle {
  position: absolute;
  top: 8px;
  right: 11px;
  padding: 1px 4px;
  border: 0;
  background: transparent;
  color: #db8424;
  font-size: 22px !important;
  cursor: pointer;
}
.left-tools { margin-top: auto; }

.right-workspace > .route-panel {
  flex: 1 1 auto;
  min-height: 140px;
}
.right-workspace > .theme-panel,
.right-workspace > .statistics-panel { flex: 0 1 auto; }

@media (max-width: 1180px) {
  .map-wrapper { --rail-width: 280px; }
  .map-toolbar { gap: 6px; }
  .search-box { flex-basis: 210px; }
  .toolbar-button { padding: 10px 9px; font-size: 13px; }
}

@media (max-width: 760px) {
  .map-wrapper { --rail-width: min(340px, calc(100vw - 24px)); --workspace-top: 124px; }
  .map-toolbar {
    top: 10px;
    left: 12px;
    right: 58px;
    gap: 6px;
    overflow-x: auto;
    scrollbar-width: thin;
  }
  .search-box { min-width: 180px; flex: 0 0 180px; }
  .map-display-control { margin-left: 0; }
  .category-filter { top: 70px; left: 12px; right: 12px; }
  .left-workspace {
    left: 12px;
    top: var(--workspace-top);
    bottom: calc(43vh + 24px);
    width: var(--rail-width);
    overflow-y: auto;
    pointer-events: auto;
    scrollbar-width: thin;
  }
  .right-workspace {
    top: auto;
    right: 12px;
    bottom: 12px;
    height: 42vh;
    width: var(--rail-width);
  }
  .result-list { max-height: 30vh; }
  .left-tools { gap: 6px; }
}
@media (max-height: 680px) and (min-width: 761px) {
  .left-workspace, .right-workspace { --workspace-top: 110px; }
  .result-list { max-height: 35vh; }
}
</style>
