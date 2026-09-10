// Exercise the actual component request/lifecycle code with controlled network timing.
// Real MapLibre rendering is verified separately in the browser.
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import vm from 'node:vm'

const script = readFileSync(new URL('../frontend/src/App.vue', import.meta.url), 'utf8')
  .split('<script setup>')[1].split('</script>')[0].replace(/^import .*$/gm, '')
const requests = []
let mounted, unmounted, load
const source = { data: null, setData(data) { this.data = data } }
const bounds = {
  getWest: () => 118.785,
  getSouth: () => 32.025,
  getEast: () => 118.800,
  getNorth: () => 32.050
}
const map = {
  addControl() {}, once(event, fn) { load = fn },
  addSource(id, config) { source.data = config.data }, addLayer() {}, on() {},
  getSource() { return source }, stop() {}, getBounds() { this.boundsCalls++; return bounds },
  getCenter() { return { lng: 118.7921, lat: 32.0407 } },
  flyTo() { this.flyToCalls++ }, fitBounds() { this.fitBoundsCalls++ }, remove() { this.removed = true },
  boundsCalls: 0, flyToCalls: 0, fitBoundsCalls: 0
}
const context = vm.createContext({
  ref: value => ({ value }), onMounted: fn => { mounted = fn },
  onUnmounted: fn => { unmounted = fn },
  Map: function () { return map }, NavigationControl: function () {},
  setWorkerUrl() {}, workerUrl: '', AbortController,
  axios: {
    isCancel: () => false,
    get: (url, options) => new Promise((resolve, reject) => requests.push({ url, options, resolve, reject }))
  }
})
vm.runInContext(script + '\nthis.api = { searchPlaces, searchNearbyPlaces, searchCurrentArea, loading, searchMessage, searchQuery, selectedCategory };', context)
const api = context.api
const empty = { type: 'FeatureCollection', features: [] }
const tick = () => new Promise(resolve => setImmediate(resolve))
mounted()
await api.searchNearbyPlaces()
assert.equal(requests.length, 0, 'no query before map load')
load()
assert.equal(source.data.type, 'FeatureCollection', 'source created before initial request')
assert.equal(api.loading.value, true)
await api.searchPlaces()
await api.searchNearbyPlaces()
assert.equal(requests.length, 1, 'initial load blocks competing requests')
requests[0].reject(new Error('Network Error'))
await tick()
assert.equal(api.searchMessage.value, '无法连接后端服务')
assert.equal(api.loading.value, false)
for (const method of ['searchPlaces', 'searchNearbyPlaces']) {
  const pending = api[method]()
  assert.equal(api.searchMessage.value, '')
  requests.at(-1).reject(new Error('Network Error'))
  await pending
  assert.equal(api.searchMessage.value, '无法连接后端服务')
  assert.equal(api.loading.value, false)
}
const nearby = api.searchNearbyPlaces()
assert.equal(requests.at(-1).options.params.lng, 118.7921)
assert.equal(requests.at(-1).options.params.radius, 5000)
requests.at(-1).resolve({ data: empty })
await nearby
assert.equal(api.searchMessage.value, '附近5公里内未找到景点')
const ordinary = api.searchPlaces()
requests.at(-1).resolve({ data: empty })
await ordinary
assert.equal(api.searchMessage.value, '未找到相关景点')
api.searchQuery.value = '夫子'
api.selectedCategory.value = '历史文化'
const flyToCallsBeforeCurrentArea = map.flyToCalls
const fitBoundsCallsBeforeCurrentArea = map.fitBoundsCalls
const currentArea = api.searchCurrentArea()
const currentAreaRequest = requests.at(-1)
assert.equal(map.boundsCalls, 1, 'current-area search reads map bounds once')
assert.equal(currentAreaRequest.options.params.min_lng, 118.785)
assert.equal(currentAreaRequest.options.params.min_lat, 32.025)
assert.equal(currentAreaRequest.options.params.max_lng, 118.800)
assert.equal(currentAreaRequest.options.params.max_lat, 32.050)
assert.equal(currentAreaRequest.options.params.q, '夫子')
assert.equal(currentAreaRequest.options.params.category, '历史文化')
const currentAreaData = {
  type: 'FeatureCollection',
  features: [{
    type: 'Feature',
    properties: { id: 2, name: '夫子庙', category: '历史文化', address: '贡院街' },
    geometry: { type: 'Point', coordinates: [118.7877, 32.0270] }
  }]
}
currentAreaRequest.resolve({ data: currentAreaData })
await currentArea
assert.equal(source.data, currentAreaData, 'current-area search updates the GeoJSON source')
assert.equal(map.flyToCalls, flyToCallsBeforeCurrentArea, 'current-area search does not call overview or flyTo')
assert.equal(map.fitBoundsCalls, fitBoundsCallsBeforeCurrentArea, 'current-area search does not frame results')
const pending = api.searchPlaces()
const last = requests.at(-1)
const previous = source.data
unmounted()
assert.equal(last.options.signal.aborted, true)
last.resolve({ data: { type: 'FeatureCollection', features: ['stale'] } })
await pending
assert.equal(source.data, previous, 'late response does not update removed map')
assert.equal(map.removed, true)
console.log('PASS: initialization lock, duplicate suppression, failure paths, current-area bounds/query behavior, and unmount cancellation')
