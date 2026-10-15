<script setup>
import axios from 'axios'
import { ref, onMounted, onUnmounted, nextTick } from 'vue'
import { Map, NavigationControl, Popup, LngLatBounds, setWorkerUrl } from 'maplibre-gl'
import StatisticsPanel from './components/StatisticsPanel.vue'
import RoutePanel from './components/RoutePanel.vue'
import AIItineraryPanel from './components/AIItineraryPanel.vue'
import PlaceDetailPanel from './components/PlaceDetailPanel.vue'
import ThemePanel from './components/ThemePanel.vue'
import CulturalLinePanel from './components/CulturalLinePanel.vue'
import SpatialAnalysisPanel from './components/SpatialAnalysisPanel.vue'
import themes from './data/themes.js'
import culturalLines from './data/culturalLines.js'
import 'maplibre-gl/dist/maplibre-gl.css'
import workerUrl from 'maplibre-gl/dist/maplibre-gl-worker.mjs?worker&url'

setWorkerUrl(workerUrl)
const mapContainer = ref(null)
const searchQuery = ref('')
const searchMessage = ref('')
const searchResults = ref([])
const selectedPlaceId = ref(null)
const selectedPlace = ref(null)
const selectedCategory = ref('')
const mapDisplayMode = ref('points')
const selectedRoutePlaces = ref([])
const routeDistanceKm = ref(0)
const aiPanelRef = ref(null)
const invalidateAiPanel = () => aiPanelRef.value?.invalidateCurrent?.()
const routeKind = ref('straight_line_preview')
const roadTravelMinutes = ref(null)
const roadMode = ref('pedestrian')
const roadLoading = ref(false)
const roadError = ref('')
const roadOptimized = ref(false)
const selectedTheme = ref(null)
const selectedCulturalLine = ref(null)
const showExplorer = ref(true)
const showWorkspace = ref(true)
const activeWorkspaceTab = ref('ai')
const workspaceTabs = [
  { id: 'ai', title: 'AI 行程' },
  { id: 'route', title: '我的路线' },
  { id: 'themes', title: '主题推荐' },
  { id: 'culture', title: '文化线路' },
  { id: 'statistics', title: '景点统计' },
  { id: 'analysis', title: '空间分析' }
]
const toggleExplorer = () => {
  showExplorer.value = !showExplorer.value
  void nextTick(() => map?.resize?.())
}
const toggleWorkspace = () => {
  showWorkspace.value = !showWorkspace.value
  void nextTick(() => map?.resize?.())
}

const favoriteStorageKey = 'smart-tourism-favorites'
// The POI table currently supplies name/category/address/geometry only.
// Never present unverified opening hours, ratings or editorial copy as facts.
const placeDetails = {}

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
let gridPopup = null

const loading = ref(false)
const mapReady = ref(false)
let requestController = null
const emptyPlaces = () => ({ type: 'FeatureCollection', features: [] })
// Raw POIs remain intact for heatmaps; only the point display is clustered.
const setVisiblePlaces = (collection) => {
  map?.getSource('places')?.setData(collection)
  map?.getSource('places-clusters')?.setData(collection)
}
const routeStopCollection = () => ({
  type: 'FeatureCollection',
  features: selectedRoutePlaces.value
    .filter(place => Array.isArray(place.geometry?.coordinates) &&
      place.geometry.coordinates.length === 2 &&
      place.geometry.coordinates.every(Number.isFinite))
    .map((place, index) => ({
      type: 'Feature',
      properties: { ...place.properties, stop_order: index + 1 },
      geometry: { type: 'Point', coordinates: place.geometry.coordinates }
    }))
})
const emptyRoute = () => ({ type: 'FeatureCollection', features: [] })
const emptyCulturalLine = () => ({ type: 'FeatureCollection', features: [] })
const emptyTourismGrid = () => ({ type: 'FeatureCollection', features: [] })
const tourismGrid = ref(emptyTourismGrid())
const gridAnalysisVisible = ref(false)
const gridCellSize = 0.02

// A lightweight degree-based grid for comparison, not an equal-area 2 km grid.
const gridCellOrigin = (value) => Number((Math.floor(value / gridCellSize) * gridCellSize).toFixed(6))

const richnessLevel = (poiCount, categoryCount) => {
  if (poiCount >= 5 || (poiCount >= 4 && categoryCount >= 3)) return 'high'
  if (poiCount >= 3 || categoryCount >= 2) return 'medium'
  return 'low'
}

const buildTourismGrid = (features) => {
  const cells = {}

  for (const feature of features) {
    const [lng, lat] = feature.geometry?.coordinates ?? []
    if (!Number.isFinite(lng) || !Number.isFinite(lat)) continue

    const west = gridCellOrigin(lng)
    const south = gridCellOrigin(lat)
    const gridId = `${west}:${south}`
    cells[gridId] ??= { gridId, west, south, features: [] }
    cells[gridId].features.push(feature)
  }

  return {
    type: 'FeatureCollection',
    features: Object.values(cells).map((cell) => {
      const poiCount = cell.features.length
      const categories = [...new Set(cell.features.map(
        (feature) => feature.properties.category
      ))].filter(Boolean).sort()
      const categoryCounts = {}
      for (const place of cell.features) {
        const name = place.properties.category || '未分类'
        categoryCounts[name] = (categoryCounts[name] || 0) + 1
      }
      const east = Number((cell.west + gridCellSize).toFixed(6))
      const north = Number((cell.south + gridCellSize).toFixed(6))

      return {
        type: 'Feature',
        properties: {
          grid_id: cell.gridId,
          poi_count: poiCount,
          category_count: categories.length,
          category_counts: categoryCounts,
          categories,
          place_names: cell.features.map((feature) => feature.properties.name),
          richness_level: richnessLevel(poiCount, categories.length)
        },
        geometry: {
          type: 'Polygon',
          coordinates: [[
            [cell.west, cell.south],
            [east, cell.south],
            [east, north],
            [cell.west, north],
            [cell.west, cell.south]
          ]]
        }
      }
    })
  }
}

const refreshTourismGrid = () => {
  tourismGrid.value = buildTourismGrid(allPlacesCache?.features ?? [])
  map?.getSource('tourism-grid')?.setData(tourismGrid.value)
}

const clearGridPopup = () => {
  gridPopup?.remove()
  gridPopup = null
}

const setGridAnalysisVisible = (visible) => {
  if (!map?.getLayer('tourism-grid-fill') || !map.getLayer('tourism-grid-outline')) return

  if (visible) refreshTourismGrid()
  gridAnalysisVisible.value = visible
  map.setLayoutProperty('tourism-grid-fill', 'visibility', visible ? 'visible' : 'none')
  map.setLayoutProperty('tourism-grid-outline', 'visibility', visible ? 'visible' : 'none')
  if (!visible) clearGridPopup()
}

const focusAnalysisGrid = (gridId) => {
  const feature = tourismGrid.value.features.find(
    f => f.properties.grid_id === gridId
  )
  if (!feature || !mapReady.value) return
  const ring = feature.geometry.coordinates?.[0]
  if (!ring?.length) return
  setGridAnalysisVisible(true)
  const bounds = new LngLatBounds(ring[0], ring[2])
  map?.fitBounds(bounds, { padding: 140, maxZoom: 15 })
}

const downloadAnalysisGrid = () => {
  if (!tourismGrid.value.features.length) return
  // Export only observed POI counts, never simulated crowd or equal-area figures.
  const report = { ...tourismGrid.value, name: 'POI_degree_grid_observed_not_equal_area' }
  const blob = new Blob([JSON.stringify(report, null, 2)], { type: 'application/geo+json' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = 'nanjing-poi-grid-observed.geojson'
  a.click()
  setTimeout(() => URL.revokeObjectURL(url), 1000)
}

const showGridPopup = (feature, lngLat) => {
  clearGridPopup()
  const content = document.createElement('div')
  const title = document.createElement('strong')
  title.textContent = '旅游资源格网'
  content.append(title)
  const details = [
    `景点数量：${feature.properties.poi_count}`,
    `类型数量：${feature.properties.category_count}`,
    `包含景点：${feature.properties.place_names.join('、')}`
  ]
  details.forEach((text) => {
    const line = document.createElement('div')
    line.textContent = text
    content.append(line)
  })
  gridPopup = new Popup().setLngLat(lngLat).setDOMContent(content).addTo(map)
}

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
  setVisiblePlaces(collection)
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
    refreshTourismGrid()
    renderFavoritePlaces()
  } catch (error) {
    if (controller.signal.aborted || axios.isCancel(error)) return

    searchResults.value = []
    setVisiblePlaces(emptyPlaces())
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
  roadRequestSequence += 1
  roadLoading.value = false
  roadError.value = ''
  roadOptimized.value = false
  routeKind.value = 'straight_line_preview'
  roadTravelMinutes.value = null
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
  map?.getSource('route-stops')?.setData(routeStopCollection())
}

let roadRequestSequence = 0
const calculateSelectedRoad = async ({ mode, optimize }) => {
  if (roadLoading.value || selectedRoutePlaces.value.length < 2) return
  const seq = ++roadRequestSequence
  const ids = selectedRoutePlaces.value.map(p => p.properties.id)
  roadLoading.value = true
  roadError.value = ''
  try {
    const response = await axios.post('http://127.0.0.1:8010/api/ai/itinerary/road', {
      place_ids: ids, travel_mode: mode, optimize
    }, { timeout: 45000 })
    if (seq !== roadRequestSequence ||
        ids.join(',') !== selectedRoutePlaces.value.map(p => p.properties.id).join(',')) return
    const data = response.data
    if (data.status !== 'verified_by_routing_service' ||
        data.geojson?.type !== 'FeatureCollection') {
      roadError.value = data.message || '道路服务不可用，继续显示直线预览'
      return
    }
    if (optimize && Array.isArray(data.ordered_place_ids)) {
      const places = new Map(selectedRoutePlaces.value.map(p => [p.properties.id, p]))
      if (data.ordered_place_ids.length !== ids.length ||
          new Set(data.ordered_place_ids).size !== ids.length ||
          data.ordered_place_ids.some(id => !places.has(id))) {
        roadError.value = '道路服务返回的站点顺序无效'
        return
      }
      invalidateAiPanel()
      selectedRoutePlaces.value = data.ordered_place_ids.map(id => places.get(id))
    }
    map?.getSource('route-line')?.setData(data.geojson)
    map?.getSource('route-stops')?.setData(routeStopCollection())
    routeDistanceKm.value = data.distance_km
    roadTravelMinutes.value = data.duration_minutes
    routeKind.value = 'valhalla'
    roadMode.value = mode
    roadOptimized.value = Boolean(data.optimized)
  } catch {
    if (seq === roadRequestSequence) roadError.value = '道路计算失败，保留当前线路'
  } finally {
    if (seq === roadRequestSequence) roadLoading.value = false
  }
}

const applyAiPlan = (plan) => {
  const features = plan?.selected_places?.features
  if (!mapReady.value || !Array.isArray(features) || features.length < 2) return
  // All coordinates come from backend PostGIS; never directly from LLM.
  const valid = features.every(f =>
    Number.isInteger(f?.properties?.id) &&
    Array.isArray(f?.geometry?.coordinates) &&
    f.geometry.coordinates.length === 2 &&
    f.geometry.coordinates.every(Number.isFinite)
  )
  if (!valid) return
  exitThemeMode()
  showFavoritesOnly.value = false
  selectedRoutePlaces.value = features
  searchResults.value = features
  setVisiblePlaces({ type: 'FeatureCollection', features })
  clearPopup()
  updateRoute()
  const road = plan.route
  if (road?.status === 'verified_by_routing_service' &&
      road.geojson?.type === 'FeatureCollection' &&
      road.geojson.features?.[0]?.geometry?.type === 'LineString' &&
      Number.isFinite(road.distance_km) && Number.isFinite(road.duration_minutes)) {
    map?.getSource('route-line')?.setData(road.geojson)
    routeDistanceKm.value = road.distance_km
    roadTravelMinutes.value = road.duration_minutes
    routeKind.value = 'valhalla'
  }
  map?.getSource('route-stops')?.setData(routeStopCollection())
  frameResults(features)
}

const toggleRoutePlace = (feature) => {
  invalidateAiPanel()
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
  invalidateAiPanel()
  selectedRoutePlaces.value = []
  updateRoute()
}

const culturalLineCollection = (line) => {
  const availablePlaces = allPlacesCache?.features ?? searchResults.value
  const matchingPlaces = line.places
    .map((placeName) => availablePlaces.find(
      (feature) => feature.properties.name === placeName
    ))
    .filter(Boolean)
  const coordinates = matchingPlaces
    .map((feature) => feature.geometry?.coordinates)
    .filter(Array.isArray)

  const data = coordinates.length >= 2
    ? {
        type: 'FeatureCollection',
        features: [{
          type: 'Feature',
          properties: { id: line.id, name: line.name },
          geometry: { type: 'LineString', coordinates }
        }]
      }
    : emptyCulturalLine()

  return { data, matchingPlaces }
}

const selectCulturalLine = (line) => {
  if (!line) return

  const { data } = culturalLineCollection(line)
  selectedCulturalLine.value = line
  map?.getSource('cultural-line')?.setData(data)
}

const clearCulturalLine = () => {
  selectedCulturalLine.value = null
  map?.getSource('cultural-line')?.setData(emptyCulturalLine())
}

const exitThemeMode = () => {
  selectedTheme.value = null
  themeBaseFeatures = null
}

const selectTheme = (theme) => {
  if (!mapReady.value || loading.value || !theme) return
  invalidateAiPanel()

  if (!selectedTheme.value) themeBaseFeatures = searchResults.value

  selectedTheme.value = theme
  showFavoritesOnly.value = false
  clearPopup()

  const features = (themeBaseFeatures ?? searchResults.value).filter(
    (feature) => theme.categories.includes(feature.properties.category)
  )
  const collection = { type: 'FeatureCollection', features }

  searchResults.value = features
  setVisiblePlaces(collection)
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
  if (activeWorkspaceTab.value === 'detail') activeWorkspaceTab.value = 'route'
  selectedPlace.value = null
  selectedPlaceId.value = null
  highlightSelectedPlace(null)
}

const openPlaceDetail = (feature) => {
  if (!feature?.properties?.id) return
  activeWorkspaceTab.value = 'detail'
  showWorkspace.value = true
  void nextTick(() => map?.resize?.())

  selectedPlace.value = feature
  selectedPlaceId.value = feature.properties.id
  clearPopup()
  highlightSelectedPlace(feature.properties.id)
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
  const candidates = [...(allPlacesCache?.features ?? []),
    ...searchResults.value, ...selectedRoutePlaces.value]
  const place = candidates.find(feature => feature.properties?.id === placeId)
  map?.getSource('selected-place')?.setData(place
    ? { type: 'FeatureCollection', features: [place] } : emptyPlaces())
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

const setMapDisplayMode = (mode) => {
  if (!map?.getLayer('places-points') || !map.getLayer('places-heatmap')) return
  mapDisplayMode.value = mode
  for (const layer of ['places-points', 'places-clusters', 'places-cluster-count']) {
    map.setLayoutProperty(layer, 'visibility', mode === 'points' ? 'visible' : 'none')
  }
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
      refreshTourismGrid()
    }
    searchResults.value = features
    setVisiblePlaces(response.data)

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
    setVisiblePlaces(emptyPlaces())

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
      // Glyphs are required for numbered cluster and itinerary marker labels.
      glyphs: 'https://demotiles.maplibre.org/font/{fontstack}/{range}.pbf',
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
    map.addSource('places-clusters', {
      type: 'geojson', data: emptyPlaces(),
      cluster: true, clusterMaxZoom: 13, clusterRadius: 48
    })
    map.addSource('route-stops', { type: 'geojson', data: emptyPlaces() })
    map.addSource('selected-place', { type: 'geojson', data: emptyPlaces() })
    map.addSource('route-line', { type: 'geojson', data: emptyRoute() })
    map.addSource('cultural-line', { type: 'geojson', data: emptyCulturalLine() })
    map.addSource('tourism-grid', { type: 'geojson', data: emptyTourismGrid() })
    map.addLayer({
      id: 'places-clusters',
      type: 'circle', source: 'places-clusters',
      filter: ['has', 'point_count'],
      paint: {
        'circle-radius': ['step', ['get', 'point_count'], 17, 10, 21, 30, 26],
        'circle-color': ['step', ['get', 'point_count'],
          '#2a68c1', 10, '#2257a4', 30, '#184477'],
        'circle-stroke-color': '#fff', 'circle-stroke-width': 2,
        'circle-opacity': 0.93
      }
    })
    map.addLayer({
      id: 'places-cluster-count', type: 'symbol', source: 'places-clusters',
      filter: ['has', 'point_count'],
      layout: {
        'text-field': ['get', 'point_count_abbreviated'],
        'text-font': ['Open Sans Semibold'], 'text-size': 13,
        'text-allow-overlap': true
      },
      paint: { 'text-color': '#fff' }
    })
    map.addLayer({
      id: 'places-points',
      type: 'circle',
      source: 'places-clusters',
      filter: ['!', ['has', 'point_count']],
      paint: {
        'circle-radius': ['interpolate', ['linear'], ['zoom'], 9, 5, 12, 7, 15, 9],
        'circle-color': '#eb654b',
        'circle-stroke-color': '#ffffff',
        'circle-stroke-width': 2
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
    map.addLayer({
      id: 'route-stop-circles',
      type: 'circle', source: 'route-stops',
      paint: {
        'circle-radius': 13, 'circle-color': '#1d4ed8',
        'circle-stroke-color': '#ffffff', 'circle-stroke-width': 2.5
      }
    })
    map.addLayer({
      id: 'route-stop-numbers',
      type: 'symbol', source: 'route-stops',
      layout: {
        'text-field': ['to-string', ['get', 'stop_order']],
        'text-font': ['Open Sans Semibold'], 'text-size': 13,
        'text-allow-overlap': true, 'text-ignore-placement': true
      },
      paint: { 'text-color': '#ffffff' }
    })
    map.addLayer({
      id: 'selected-place-halo',
      type: 'circle', source: 'selected-place',
      paint: {
        'circle-radius': 20, 'circle-color': '#ffbb40',
        'circle-opacity': 0.24,
        'circle-stroke-color': '#f59e0b', 'circle-stroke-width': 3
      }
    })
    map.addLayer({
      id: 'cultural-line-layer',
      type: 'line',
      source: 'cultural-line',
      layout: {
        'line-join': 'round',
        'line-cap': 'round'
      },
      paint: {
        'line-color': '#7c3aed',
        'line-width': 4,
        'line-opacity': 0.8,
        'line-dasharray': [2, 1]
      }
    })
    map.addLayer({
      id: 'tourism-grid-fill',
      type: 'fill',
      source: 'tourism-grid',
      layout: { visibility: 'none' },
      paint: {
        'fill-color': [
          'step', ['get', 'poi_count'],
          '#dbeafe',
          3, '#93c5fd',
          5, '#2563eb'
        ],
        'fill-opacity': 0.38
      }
    })
    map.addLayer({
      id: 'tourism-grid-outline',
      type: 'line',
      source: 'tourism-grid',
      layout: { visibility: 'none' },
      paint: {
        'line-color': '#1d4ed8',
        'line-width': 1.5,
        'line-opacity': 0.8
      }
    })
    map.on('click', 'places-clusters', async (event) => {
      if (gridAnalysisVisible.value) return
      const clusterId = event.features?.[0]?.properties?.cluster_id
      const coordinate = event.features?.[0]?.geometry?.coordinates
      if (!Number.isInteger(clusterId) || !Array.isArray(coordinate)) return
      const source = map?.getSource('places-clusters')
      if (!source?.getClusterExpansionZoom) return
      try {
        const zoom = await source.getClusterExpansionZoom(clusterId)
        if (!map || !Number.isFinite(zoom)) return
        map.easeTo({ center: coordinate, zoom: Math.min(zoom, 16) })
      } catch {
        // Source may be replaced between clicks and cluster expansion.
      }
    })
    map.on('mouseenter', 'places-clusters', () => {
      map.getCanvas().style.cursor = 'zoom-in'
    })
    map.on('mouseleave', 'places-clusters', () => {
      map.getCanvas().style.cursor = ''
    })
    map.on('click', 'route-stop-circles', (event) => {
      if (gridAnalysisVisible.value) return
      const feature = event.features?.[0]
      if (feature) openPlaceDetail(feature)
    })
    map.on('click', 'places-points', (e) => {
      if (gridAnalysisVisible.value) return

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
    let hoverPopup = null
    map.on('mouseenter', 'places-points', event => {
      const poi = event.features?.[0]
      if (!poi || !map) return
      hoverPopup?.remove()
      hoverPopup = new Popup({ closeButton: false, closeOnClick: false, offset: 14 })
        .setLngLat(poi.geometry.coordinates)
        .setText(poi.properties.name || '景点')
        .addTo(map)
    })
    map.on('mouseleave', 'places-points', () => {
      hoverPopup?.remove()
      hoverPopup = null
    })
    map.on('click', 'tourism-grid-fill', (event) => {
      const feature = event.features?.[0]
      if (feature) showGridPopup(feature, event.lngLat)
    })
    map.on('mouseenter', 'tourism-grid-fill', () => {
      map.getCanvas().style.cursor = 'pointer'
    })
    map.on('mouseleave', 'tourism-grid-fill', () => {
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
  clearGridPopup()
  map?.remove()
  map = null
})
</script>


<template>
  <div
    class="map-wrapper"
    :class="{
      'explorer-hidden': !showExplorer,
      'workspace-hidden': !showWorkspace
    }"
  >
    <header class="app-toolbar" aria-label="智慧文旅地图工具栏">
      <div class="toolbar-main">
        <div class="brand-mark">
          <span class="brand-icon" aria-hidden="true">◎</span>
          <div class="brand-copy">
            <strong>南京智慧文旅</strong>
            <small>AI × GIS 探索工作台</small>
          </div>
        </div>
        <button
          type="button"
          class="toolbar-button panel-toggle"
          :aria-expanded="showExplorer"
          aria-controls="explorer-panel"
          @click="toggleExplorer"
        >{{ showExplorer ? '隐藏景点' : '景点列表' }}</button>

        <div class="toolbar-search">
          <input
            v-model="searchQuery"
            class="search-box"
            aria-label="搜索景点"
            :disabled="loading || !mapReady"
            type="search"
            placeholder="搜索景点名称或类型"
            @keyup.enter="searchPlaces"
          />
          <button class="toolbar-button search-submit" type="button"
            :disabled="loading || !mapReady" @click="searchPlaces">搜索</button>
        </div>

        <button
          type="button"
          class="toolbar-button nearby-button"
          :disabled="loading || !mapReady"
          @click="searchNearbyPlaces"
        >{{ loading ? '查询中…' : '附近 5 km' }}</button>

        <button
          type="button"
          class="toolbar-button favorites-button"
          :class="{ active: showFavoritesOnly }"
          :disabled="loading || !mapReady"
          @click="showFavoritePlaces"
        >我的收藏 ({{ favoritePlaceIds.length }})</button>

        <button
          type="button"
          class="toolbar-button current-area-button"
          :disabled="loading || !mapReady"
          @click="searchCurrentArea"
        >搜索当前区域</button>

        <div class="toolbar-spacer"></div>
        <div class="map-display-control" role="group" aria-label="地图显示模式">
          <button
            type="button"
            :class="{ active: mapDisplayMode === 'points' }"
            :disabled="!mapReady"
            @click="setMapDisplayMode('points')"
          >点位</button>
          <button
            type="button"
            :class="{ active: mapDisplayMode === 'heatmap' }"
            :disabled="!mapReady"
            @click="setMapDisplayMode('heatmap')"
          >热力</button>
        </div>
        <button
          type="button"
          class="toolbar-button panel-toggle"
          :aria-expanded="showWorkspace"
          aria-controls="workspace-panel"
          @click="toggleWorkspace"
        >{{ showWorkspace ? '隐藏工作台' : '打开工作台' }}</button>
      </div>

      <div class="category-filter" aria-label="景点类型筛选">
        <button
          type="button"
          class="category-button"
          :class="{ active: selectedCategory === '' }"
          @click="selectCategory('')"
        >全部类型</button>
        <button
          v-for="category in categories"
          :key="category"
          type="button"
          class="category-button"
          :class="{ active: selectedCategory === category }"
          @click="selectCategory(category)"
        >{{ category }}</button>
      </div>
    </header>

    <aside
      v-show="showExplorer"
      id="explorer-panel"
      class="explorer-panel"
      aria-label="景点搜索结果"
    >
      <div class="explorer-heading">
        <div>
          <h2>景点探索</h2>
          <span>点击景点查看详情，在右侧添加至路线</span>
        </div>
        <span class="result-pill">{{ searchResults.length }}</span>
      </div>
      <div v-if="searchMessage" class="search-message" role="status">
        {{ searchMessage }}
      </div>
      <div v-if="searchResults.length" class="result-list">
        <div class="result-count">找到 {{ searchResults.length }} 个景点</div>
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
          @click="focusResult(feature)"
        >
          <button
            class="favorite-toggle"
            type="button"
            :aria-label="isFavorite(feature.properties.id) ? '取消收藏' : '收藏'"
            :title="isFavorite(feature.properties.id) ? '取消收藏' : '收藏'"
            @click.stop="toggleFavorite(feature)"
          >{{ isFavorite(feature.properties.id) ? '★' : '☆' }}</button>
          <strong>{{ feature.properties.name }}</strong>
          <span v-if="selectedRoutePlaces.some(p => p.properties.id === feature.properties.id)"
            class="route-order-pill"
            :title="'行程第 ' + (selectedRoutePlaces.findIndex(p => p.properties.id === feature.properties.id) + 1) + ' 站'"
          >第 {{ selectedRoutePlaces.findIndex(p => p.properties.id === feature.properties.id) + 1 }} 站</span>
          <div>{{ feature.properties.category }}</div>
        </div>
      </div>
      <div v-else-if="!loading && !searchMessage" class="explorer-empty">
        暂无景点结果，可在上方搜索或浏览当前区域。
      </div>
      <div class="explorer-footnote">
        <span class="online-dot" aria-hidden="true"></span>
        结果来自后端 POI 数据库
      </div>
    </aside>

    <main class="map-stage" aria-label="南京地图">
      <div ref="mapContainer" class="map"></div>
      <div v-if="selectedRoutePlaces.length >= 2" class="map-route-status" role="status">
        <span class="map-status-dot" aria-hidden="true"></span>
        {{ routeKind === 'valhalla'
          ? '已验证的 Valhalla 道路线路'
          : '直线串联预览 · 非实际导航路径' }}
      </div>
      <div class="map-attribution-note">地图 © OpenStreetMap · 空间结果以数据源为准</div>
    </main>

    <aside
      v-show="showWorkspace"
      id="workspace-panel"
      class="workspace-panel"
      aria-label="智慧文旅功能工作台"
    >
      <div class="workspace-heading">
        <div>
          <h2>功能工作台</h2>
          <span>选择功能标签，不再叠加遮挡地图</span>
        </div>
      </div>
      <nav class="workspace-tabs" role="tablist" aria-label="选择工作台功能">
        <button
          v-for="tab in workspaceTabs"
          :key="tab.id"
          type="button"
          role="tab"
          :aria-selected="activeWorkspaceTab === tab.id"
          :class="{ active: activeWorkspaceTab === tab.id }"
          @click="activeWorkspaceTab = tab.id"
        >{{ tab.title }}</button>
        <button
          v-if="selectedPlace"
          type="button"
          role="tab"
          :aria-selected="activeWorkspaceTab === 'detail'"
          :class="{ active: activeWorkspaceTab === 'detail' }"
          @click="activeWorkspaceTab = 'detail'"
        >景点详情</button>
      </nav>
      <div class="workspace-content">
        <div v-show="activeWorkspaceTab === 'ai'" class="workspace-slot" role="tabpanel">
          <AIItineraryPanel ref="aiPanelRef" @apply="applyAiPlan" />
        </div>
        <div v-show="activeWorkspaceTab === 'route'" class="workspace-slot" role="tabpanel">
          <RoutePanel
            :places="selectedRoutePlaces"
            :distance-km="routeDistanceKm"
            :route-kind="routeKind"
            :road-travel-minutes="roadTravelMinutes"
            :road-mode="roadMode"
            :road-loading="roadLoading"
            :road-error="roadError"
            :road-optimized="roadOptimized"
            @calculate-road="calculateSelectedRoad"
            @clear="clearRoute"
            @focus-place="focusResult"
          />
        </div>
        <div v-show="activeWorkspaceTab === 'themes'" class="workspace-slot" role="tabpanel">
          <ThemePanel
            :themes="themes"
            :selected-theme="selectedTheme"
            @select="selectTheme"
          />
        </div>
        <div v-show="activeWorkspaceTab === 'culture'" class="workspace-slot" role="tabpanel">
          <CulturalLinePanel
            :lines="culturalLines"
            :selected-line="selectedCulturalLine"
            @select="selectCulturalLine"
            @clear="clearCulturalLine"
          />
        </div>
        <div v-show="activeWorkspaceTab === 'statistics'" class="workspace-slot" role="tabpanel">
          <StatisticsPanel />
        </div>
        <div v-show="activeWorkspaceTab === 'analysis'" class="workspace-slot" role="tabpanel">
          <SpatialAnalysisPanel
            :grid-features="tourismGrid.features"
            :visible="gridAnalysisVisible"
            @show="setGridAnalysisVisible(true)"
            @hide="setGridAnalysisVisible(false)"
            @focus-grid="focusAnalysisGrid"
            @export-grid="downloadAnalysisGrid"
          />
        </div>
        <div v-show="activeWorkspaceTab === 'detail'" class="workspace-slot" role="tabpanel">
          <PlaceDetailPanel
            :place="selectedPlace"
            :place-details="placeDetails"
            :is-favorite="selectedPlace ? isFavorite(selectedPlace.properties.id) : false"
            :is-in-route="selectedPlace ? selectedRoutePlaces.some((place) => place.properties.id === selectedPlace.properties.id) : false"
            @close="closePlaceDetail"
            @toggle-favorite="selectedPlace && toggleFavorite(selectedPlace)"
            @toggle-route="selectedPlace && toggleRoutePlace(selectedPlace)"
          />
        </div>
      </div>
    </aside>
  </div>
</template>

<style>
:root { color-scheme: light; }
html, body, #app { margin: 0; width: 100%; height: 100%; min-height: 0; }
#app { max-width: none; border: 0; display: block; background: #f5f8fd; color: #233047; text-align: left; }
body { overflow: hidden; font-family: Inter, 'Segoe UI', 'Microsoft YaHei', sans-serif; }
.map-wrapper, .map-wrapper * { box-sizing: border-box; }
.map-wrapper button, .map-wrapper input, .map-wrapper textarea,
.map-wrapper select { font-family: inherit; }
.map-wrapper button:focus-visible, .map-wrapper input:focus-visible,
.map-wrapper select:focus-visible { outline: 2px solid #2563eb; outline-offset: 2px; }
.map-wrapper {
  --explorer-width: 288px;
  --workspace-width: 358px;
  display: grid;
  grid-template-columns: var(--explorer-width) minmax(0,1fr) var(--workspace-width);
  grid-template-rows: auto minmax(0,1fr);
  width: 100%; height: 100dvh; min-height: 0; overflow: hidden;
  background: #e9f0f7;
}
.map-wrapper.explorer-hidden { --explorer-width: 0px; }
.map-wrapper.workspace-hidden { --workspace-width: 0px; }
.app-toolbar {
  grid-column: 1 / -1; grid-row: 1;
  z-index: 20; min-width: 0;
  background: #fff; border-bottom: 1px solid #e1e8f1;
  box-shadow: 0 2px 12px rgb(16 35 62 / 7%);
}
.toolbar-main {
  display: flex; align-items: center; gap: 9px;
  min-height: 64px; padding: 10px 16px;
}
.brand-mark { display:flex;align-items:center;gap:9px;min-width:153px;flex-shrink:0; }
.brand-icon { display:grid;place-items:center;width:35px;height:35px;border-radius:11px;color:#fff;
 background: linear-gradient(145deg,#2563eb,#0f766e);font-size:25px;font-weight:700; }
.brand-copy { display:flex;flex-direction:column;white-space:nowrap;line-height:1.3;gap:3px; }
.brand-copy strong { font-size:14px;letter-spacing:.1px;color:#142c52; }
.brand-copy small { font-size:10px;color:#64748b; }
.toolbar-button {
  border:1px solid #d6e0ec;border-radius:8px;color:#34445d;background:#fff;
  white-space:nowrap;padding:9px 11px;min-height:36px;font-size:12px;cursor:pointer;
  transition: background .15s, border-color .15s;
}
.toolbar-button:hover:not(:disabled) { background:#eff5ff;border-color:#92b3eb; }
.toolbar-button:disabled {opacity:.48;cursor:not-allowed;}
.toolbar-button.active,.search-submit { color:#1453bd;border-color:#bad3fa;background:#eaf2ff; }
.toolbar-search { display:flex;min-width:150px;max-width:410px;flex:1 1 220px;gap:6px; }
.search-box { min-width:0;width:100%;height:36px;box-sizing:border-box;padding:7px 10px;
  border:1px solid #cbd5e1;border-radius:8px;color:#1f2937;background:#fff;font-size:13px;outline:none; }
.search-box:focus {border-color:#438ae2;box-shadow:0 0 0 3px #cce5ff99;}
.toolbar-spacer {flex:1 1 auto;min-width:0;}
.map-display-control {display:flex;align-items:center;border:1px solid #d6e0ec;
  border-radius:8px;overflow:hidden;background:#fff;flex-shrink:0;}
.map-display-control button {padding:9px 11px;border:0;cursor:pointer;font-size:12px;
  color:#334155;background:#fff;min-height:34px;}
.map-display-control button + button {border-left:1px solid #e1e8f1;}
.map-display-control button.active {background:#dceafe;color:#174da3;font-weight:700;}
.map-display-control button:disabled {opacity:.5;cursor:not-allowed;}
.category-filter {display:flex;gap:7px;align-items:center;min-width:0;overflow-x:auto;
  padding:0 16px 10px;scrollbar-width:thin;}
.category-button {flex-shrink:0;padding:6px 11px;border-radius:20px;border:1px solid #e1e8f1;
  background:#f6f8fc;color:#526178;font-size:12px;cursor:pointer;white-space:nowrap;}
.category-button.active {color:#185cbb;border-color:#91b8f4;background:#eaf3ff;font-weight:700;}
.category-button:hover {background:#e8f0fb;}
.explorer-panel {grid-column:1;grid-row:2;display:flex;flex-direction:column;min-width:0;min-height:0;
  overflow:hidden;background:#fff;border-right:1px solid #dfe6ef;}
.explorer-heading {display:flex;align-items:center;justify-content:space-between;gap:12px;
  padding:20px 16px 16px;border-bottom:1px solid #edf1f7;flex-shrink:0;}
.explorer-heading h2,.workspace-heading h2 {font-size:17px;letter-spacing:0;margin:0 0 5px;color:#172e4d;font-weight:700;}
.explorer-heading span,.workspace-heading span {font-size:11px;color:#718095;line-height:1.35;}
.result-pill {background:#e8f1ff;color:#135aba!important;font-weight:700;min-width:32px;
  height:28px;padding:4px 7px;text-align:center;border-radius:9px;font-size:13px!important;}
.search-message {color:#9f1d2e;background:#fff7f7;border-bottom:1px solid #ffd8d8;
  padding:10px 15px;flex-shrink:0;font-size:12px;line-height:1.5;}
.result-list {display:block;flex:1 1 auto;min-height:0;overflow-y:auto;scrollbar-width:thin;background:#fff;}
.result-count {padding:10px 16px;background:#f9fbfe;color:#53647f;font-size:12px;font-weight:600;
  position:sticky;top:0;z-index:2;border-bottom:1px solid #edf1f7;}
.result-item {position:relative;padding:13px 42px 13px 16px;border-bottom:1px solid #f0f3f8;cursor:pointer;}
.result-item:hover {background:#f2f7ff;}
.result-item:last-child {border-bottom:0;}
.result-item strong {display:block;color:#253a53;font-size:13px;line-height:1.4;}
.result-item > div {margin-top:4px;font-size:12px;color:#8492a6;}
.result-item-selected {background:#eaf2ff;}
.result-item-route-selected {border-left:3px solid #2563eb;padding-left:13px;}
.route-order-pill {display:inline-flex;margin-top:6px;padding:2px 7px;border-radius:12px;
  background:#e2edff;color:#1955a4;font-size:11px;font-weight:700;}
.favorite-toggle {position:absolute;right:12px;top:12px;cursor:pointer;border:0;background:none;
  font-size:22px;color:#e8a018;padding:2px;line-height:1;}
.explorer-empty {padding:20px 16px;color:#66758d;font-size:13px;}
.explorer-footnote {margin-top:auto;padding:13px 15px;border-top:1px solid #edf1f7;
  flex-shrink:0;display:flex;align-items:center;gap:7px;color:#8290a2;font-size:11px;}
.online-dot,.map-status-dot {display:inline-block;width:7px;height:7px;background:#1ca879;border-radius:50%;}
.map-stage {grid-column:2;grid-row:2;position:relative;overflow:hidden;min-width:0;min-height:0;background:#e1e9ef;}
.map {position:absolute;inset:0;width:100%;height:100%;}
.map-route-status {position:absolute;left:18px;bottom:37px;z-index:5;display:flex;align-items:center;gap:8px;
  max-width:calc(100% - 36px);font-size:11px;background:#ffffffed;border:1px solid #d9e1ec;border-radius:9px;
  padding:8px 12px;box-shadow:0 2px 10px #0002;color:#31445e;pointer-events:none;}
.map-attribution-note {position:absolute;bottom:8px;left:12px;background:#ffffffcc;pointer-events:none;
  font-size:10px;color:#66758d;padding:4px 6px;border-radius:4px;}
.workspace-panel {grid-column:3;grid-row:2;display:flex;flex-direction:column;min-height:0;min-width:0;
  background:#fff;border-left:1px solid #dfe6ef;overflow:hidden;}
.workspace-heading {flex-shrink:0;padding:20px 16px 13px;border-bottom:1px solid #edf1f7;}
.workspace-tabs {display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:5px;flex-shrink:0;
  padding:10px 10px 12px;border-bottom:1px solid #e6edf5;background:#f9fbfe;}
.workspace-tabs button {padding:10px 3px;min-width:0;border:1px solid transparent;border-radius:7px;
  color:#58677b;background:transparent;cursor:pointer;font-size:12px;white-space:nowrap;}
.workspace-tabs button:hover {background:#eef4fc;}
.workspace-tabs button.active,.workspace-tabs button[aria-selected="true"] {
  background:#e5efff;border-color:#bad2f6;color:#1e56a4;font-weight:700;}
.workspace-content {flex:1;min-height:0;overflow-y:auto;overflow-x:hidden;padding:0 12px 16px;
  scrollbar-width:thin;overscroll-behavior:contain;}
.workspace-slot {display:block;min-width:0;padding:6px 0;}
/* Existing child components used map-wide absolute positioning. Inside a workspace slot
   they must participate in normal document flow, not paint over other features. */
.map-wrapper .workspace-slot > .ai-itinerary-panel,
.map-wrapper .workspace-slot > .route-panel,
.map-wrapper .workspace-slot > .theme-panel,
.map-wrapper .workspace-slot > .cultural-line-panel,
.map-wrapper .workspace-slot > .statistics-panel,
.map-wrapper .workspace-slot > .place-detail-panel,
.map-wrapper .workspace-slot > .spatial-analysis-panel {
  position:static;width:100%;max-width:100%;height:auto;min-height:0;top:auto;right:auto;bottom:auto;left:auto;
  z-index:auto;margin:0;box-shadow:none;box-sizing:border-box;border:0;border-radius:0;
  background:transparent;overflow:visible;color:#233047;
}
.map-wrapper .workspace-slot > .statistics-panel.collapsed {width:100%;}
.map-wrapper .workspace-slot .ai-content {max-height:none;min-height:0;overflow:visible;padding:13px 4px;}
.map-wrapper .workspace-slot .ai-toggle {border-radius:8px;}
.map-wrapper .workspace-slot .ai-itinerary-panel {font-size:13px;}
.map-wrapper .workspace-slot .route-panel-header {align-items:flex-start;}
.map-wrapper .workspace-slot .route-panel-header h2 {min-width:0;}
.map-wrapper .workspace-slot .route-panel-header button {flex-shrink:0;}
.map-wrapper .workspace-slot .theme-card,.workspace-slot .cultural-line-card {width:100%;}
.map-wrapper .workspace-slot .spatial-analysis-panel {padding:12px 2px;}
.map-wrapper .workspace-slot .place-detail-panel {padding:10px 2px;}
.map-wrapper .workspace-slot .statistics-panel {padding:8px 0;}
.maplibregl-popup-content {color:#263347;text-align:left;}
@media(max-width:1370px){
  .map-wrapper{--explorer-width:252px;--workspace-width:320px;}
  .toolbar-main{gap:6px;padding:9px 12px;}
  .brand-mark{min-width:126px;gap:6px;}
  .brand-icon{width:30px;height:30px;font-size:22px;}
  .brand-copy strong{font-size:12px;}
  .brand-copy small{font-size:9px;}
  .toolbar-button {padding:8px 8px;font-size:11px;}
}
@media(max-width:1020px){
  body{overflow:auto;}
  .map-wrapper,.map-wrapper.explorer-hidden,.map-wrapper.workspace-hidden{
    display:grid;grid-template-columns:minmax(0,1fr);grid-template-rows:auto minmax(36vh,1fr) auto auto;
    height:100dvh;min-height:640px;overflow-y:auto;
  }
  .app-toolbar{grid-column:1;grid-row:1;}
  .toolbar-main{flex-wrap:wrap;row-gap:8px;}
  .toolbar-search{flex:1 1 220px;}
  .map-stage{grid-column:1;grid-row:2;min-height:36vh;}
  .explorer-panel{grid-column:1;grid-row:3;min-height:0;max-height:260px;border:0;border-top:1px solid #e0e6f0;}
  .result-list{max-height:170px;min-height:45px;}
  .workspace-panel{grid-column:1;grid-row:4;min-height:250px;max-height:480px;border:0;border-top:1px solid #e0e6f0;}
  .workspace-content{overflow-y:auto;max-height:350px;}
}
@media(max-width:600px){
  .brand-mark{min-width:auto;}
  .brand-copy small{display:none;}
  .panel-toggle{padding:7px;}
  .toolbar-main{padding:9px 10px;}
  .toolbar-spacer{display:none;}
  .toolbar-search{order:3;flex-basis:100%;max-width:none;}
  .category-filter{padding:0 10px 9px;}
  .workspace-tabs{grid-template-columns:repeat(3,minmax(0,1fr));}
  .workspace-heading,.explorer-heading{padding:12px;}
}
</style>
