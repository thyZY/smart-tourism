<script setup>
import axios from 'axios'
import { onMounted, onBeforeUnmount, ref } from 'vue'
import { Map, NavigationControl, Popup, LngLatBounds, setWorkerUrl } from 'maplibre-gl'
import 'maplibre-gl/dist/maplibre-gl.css'
import workerUrl from 'maplibre-gl/dist/maplibre-gl-worker.mjs?worker&url'

setWorkerUrl(workerUrl)
const mapContainer = ref(null)
const searchQuery = ref('')
const searchMessage = ref('')

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
const loadPlaces = async (nearby = false) => {
  if (!mapReady.value || loading.value) return
  loading.value = true
  clearPopup()
  searchMessage.value = ''
  map.stop()
  const q = searchQuery.value.trim()
  const center = map.getCenter()
  const controller = new AbortController()
  requestController = controller
  try {
    const response = await axios.get(
      `http://127.0.0.1:8010/api/places${nearby ? '/nearby' : ''}`,
      {
        params: nearby ? { lng: center.lng, lat: center.lat, radius: 5000 } : (q ? { q } : {}),
        signal: controller.signal,
        timeout: 10000
      }
    )
    if (controller.signal.aborted || !map) return
    const features = response.data.features
    map.getSource('places').setData(response.data)
    if (!features.length) {
      searchMessage.value = nearby ? '附近5公里内未找到景点' : '未找到相关景点'
    }
    if (nearby) {
      frameResults(features)
    } else if (!q || !features.length) {
      overview()
    } else {
      frameResults(features)
      if (features.length === 1) showPopup(features[0])
    }
  } catch (error) {
    if (controller.signal.aborted || axios.isCancel(error)) return
    map?.getSource('places')?.setData(emptyPlaces())
    searchMessage.value = error.response ? '景点查询失败，请稍后重试' : '无法连接后端服务'
  } finally {
    if (requestController === controller) {
      requestController = null
      loading.value = false
    }
  }
}

const searchPlaces = () => loadPlaces()
const searchNearbyPlaces = () => loadPlaces(true)

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
      if (!loading.value && e.features?.[0]) showPopup(e.features[0])
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

onBeforeUnmount(() => {
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

  <div v-if="searchMessage" class="search-message" role="status">
    {{ searchMessage }}
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

</style>
