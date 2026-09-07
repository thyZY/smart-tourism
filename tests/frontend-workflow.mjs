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
const map = {
  addControl() {}, once(event, fn) { load = fn },
  addSource(id, config) { source.data = config.data }, addLayer() {}, on() {},
  getSource() { return source }, stop() {},
  getCenter() { return { lng: 118.7921, lat: 32.0407 } },
  flyTo() {}, fitBounds() {}, remove() { this.removed = true }
}
const context = vm.createContext({
  ref: value => ({ value }), onMounted: fn => { mounted = fn },
  onBeforeUnmount: fn => { unmounted = fn },
  Map: function () { return map }, NavigationControl: function () {},
  setWorkerUrl() {}, workerUrl: '', AbortController,
  axios: {
    isCancel: () => false,
    get: (url, options) => new Promise((resolve, reject) => requests.push({ url, options, resolve, reject }))
  }
})
vm.runInContext(script + '\nthis.api = { searchPlaces, searchNearbyPlaces, loading, searchMessage, searchQuery };', context)
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
const pending = api.searchPlaces()
const last = requests.at(-1)
const previous = source.data
unmounted()
assert.equal(last.options.signal.aborted, true)
last.resolve({ data: { type: 'FeatureCollection', features: ['stale'] } })
await pending
assert.equal(source.data, previous, 'late response does not update removed map')
assert.equal(map.removed, true)
console.log('PASS: initialization lock, duplicate suppression, all three network failure paths, recovery, empty nearby, unmount cancellation')
