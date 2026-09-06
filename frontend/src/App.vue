<script setup>
import axios from 'axios'
import { onMounted, onBeforeUnmount, ref } from 'vue'
import { Map, NavigationControl, Popup, setWorkerUrl } from 'maplibre-gl'
import 'maplibre-gl/dist/maplibre-gl.css'
import workerUrl from 'maplibre-gl/dist/maplibre-gl-worker.mjs?worker&url'

setWorkerUrl(workerUrl)
const mapContainer = ref(null)
const searchQuery = ref('')
const searchMessage = ref('')

let map = null
let searchPopup = null

const searchPlaces = async () => {
  if (!map) return

  const q = searchQuery.value.trim()

  const response = await axios.get('http://127.0.0.1:8010/api/places', {
    params: q ? { q } : {}
  })

  const source = map.getSource('places')

  if (source) {
    source.setData(response.data)
  }

  const features = response.data.features

  if (features.length === 0) {
    searchMessage.value = '未找到相关景点'
  } else {
    searchMessage.value = ''
  }
  if (features.length === 0 && searchPopup) {
    searchPopup.remove()
    searchPopup = null
  }

  if (!q) {
    if (searchPopup) {
      searchPopup.remove()
      searchPopup = null
    }

    map.flyTo({
      center: [118.7969, 32.0603],
      zoom: 10
    })
  }

  if (features.length === 1) {
    if (searchPopup) {
      searchPopup.remove()
      searchPopup = null
    }

    map.flyTo({
      center: features[0].geometry.coordinates,
      zoom: 14
    })

    const feature = features[0]

    searchPopup = new Popup()
      .setLngLat(feature.geometry.coordinates)
      .setHTML(
        `<strong>${feature.properties.name}</strong><br>
        ${feature.properties.category}<br>
        地址：${feature.properties.address}`
      )
      .addTo(map)
  }
}

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
  map.on('load', () => {
    axios
      .get('http://127.0.0.1:8010/api/places')
      .then((response) => {
        map.addSource('places', {
          type: 'geojson',
          data: response.data
        })

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

          new Popup()
            .setLngLat(feature.geometry.coordinates)
            .setHTML(
              `<strong>${feature.properties.name}</strong><br>
              ${feature.properties.category}<br>
              地址：${feature.properties.address}`
            )
            .addTo(map)
        })
        map.on('mouseenter', 'places-points', () => {
          map.getCanvas().style.cursor = 'pointer'
        })

        map.on('mouseleave', 'places-points', () => {
          map.getCanvas().style.cursor = ''
        })
      })
  })
})

onBeforeUnmount(() => {
  map?.remove()
})
</script>

<template>
  <div class="map-wrapper">
    <input
      v-model="searchQuery"
      class="search-box"
      type="text"
      placeholder="搜索景点..."
      @keyup.enter="searchPlaces"
    />

  <div v-if="searchMessage" class="search-message">
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

</style>

