<script setup>
import axios from 'axios'
import { onMounted, onBeforeUnmount, ref } from 'vue'
import { Map, NavigationControl, Popup, setWorkerUrl } from 'maplibre-gl'
import 'maplibre-gl/dist/maplibre-gl.css'
import workerUrl from 'maplibre-gl/dist/maplibre-gl-worker.mjs?worker&url'

setWorkerUrl(workerUrl)
const mapContainer = ref(null)

let map = null

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
              `<strong>${feature.properties.name}</strong><br>${feature.properties.category}`
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
  <div ref="mapContainer" class="map"></div>
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
</style>