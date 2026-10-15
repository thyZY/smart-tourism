// Real Vue <script setup> logic tested with controlled axios/localStorage mocks.
// No browser, database or API Key is used in CI.
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import vm from 'node:vm'

const panelSource = readFileSync(new URL('../frontend/src/components/AIItineraryPanel.vue', import.meta.url), 'utf8')
const appSource = readFileSync(new URL('../frontend/src/App.vue', import.meta.url), 'utf8')
const routePanelSource = readFileSync(new URL('../frontend/src/components/RoutePanel.vue', import.meta.url), 'utf8')
const script = panelSource.split('<script setup>')[1].split('</script>')[0]
  .replace(/^import .*$/gm, '')
const store = new Map()
const calls = []
const events = []
const downloads = []
let printed = ''
const buildFeature = (id, name, lon, lat) => ({
  type: 'Feature',
  properties: { id, name, category: '历史文化', address: '' },
  geometry: { type: 'Point', coordinates: [lon, lat] }
})
const buildPlan = (ids=[1,2,3]) => ({
  title: '南京历史文化一日游', summary: '真实POI',
  planning_method: 'local_rule_fallback', mode: 'pedestrian',
  stops: ids.map((id) => ({ id, name: '景点'+id, category: '历史文化', reason: '数据库记录' })),
  selected_places: { type:'FeatureCollection',features:ids.map(
    id => buildFeature(id, '景点'+id, 118.7 + id/1000, 32.0)
  )},
  route: { status: 'unavailable' }
})
let failure = false
const context = vm.createContext({
  reactive: obj => obj,
  ref: value => ({ value }),
  defineEmits: () => (name, plan) => events.push({ name, plan }),
  defineExpose: () => {},
  localStorage: {
    getItem(key) { return store.get(key) ?? null },
    setItem(key,value) { store.set(key,String(value)) }
  },
  axios: { post: async (url,payload) => {
    calls.push({ url,payload })
    if (failure) throw { response: { data: { detail:'历史景点失效' } } }
    return { data: buildPlan(url.endsWith('/restore') ? payload.place_ids : [1,2,3]) }
  }},
  crypto: { randomUUID: () => 'test-uuid' },
  Blob, Math, Date, Number, JSON,
  setTimeout(fn) { fn() },
  URL: { createObjectURL: ()=>'blob:test', revokeObjectURL() {} },
  document: { createElement: () => ({click(){downloads.push('download')}}) },
  window: { open: () => ({ document: {
    write: s=>{printed+=s},close() {}},focus() {},print() {}
  }) }
})
vm.runInContext(script + '\nthis.testApi={request,result,preview,saved,error,notice,generate,apply,confirmPreview,excludedPlaceInput,save,restore,removeSaved,invalidateCurrent,exportRoad,exportJson,printReport};',context)
const api=context.testApi

api.excludedPlaceInput.value = '1, 3'
await api.generate()
assert.equal(calls.length,1)
assert.deepEqual(JSON.parse(JSON.stringify(calls[0].payload.excluded_place_ids)), [1,3])
api.excludedPlaceInput.value = '1,1'
await api.generate()
assert.equal(calls.length,1,'duplicate exclusions are rejected before network')
assert.match(api.error.value,/重复/)
api.excludedPlaceInput.value = '1,abc'
await api.generate()
assert.equal(calls.length,1,'non-numeric exclusions are rejected before network')
api.excludedPlaceInput.value = ''
assert.equal(calls.length,1)
assert.match(api.error.value,/正整数/)
assert.equal(events[0].name,'apply')
assert.equal(api.result.value.stops.length,3)
assert.equal(api.notice.value, '', 'validation errors clear earlier notices')
assert.equal(api.result.value.route.status,'unavailable')
api.exportRoad()
assert.match(api.error.value,/不能导出直线/)
api.save()
assert.equal(api.saved.value.length,1)
assert.deepEqual(JSON.parse(store.get('smart-tourism-saved-itineraries-v1'))[0].place_ids,[1,2,3])
await api.generate(true)
assert.equal(api.preview.value.stops.length,3)
assert.equal(events.length,1,'optimization is not auto applied to map')
api.confirmPreview()
assert.equal(events.length,2,'user confirmation applies preview')
api.confirmPreview()
assert.equal(events.length,2,'confirmed preview cannot apply twice')
failure = true
await api.restore(api.saved.value[0])
assert.equal(api.result.value.stops.length,3,'failed restore preserves existing itinerary')
assert.match(api.error.value,/历史景点失效/)
failure = false
await api.restore(api.saved.value[0])
assert.equal(api.result.value.planning_method,'local_rule_fallback')
assert.ok(calls.some(c=>c.url.endsWith('/restore') && c.payload.place_ids.length===3))
api.result.value.title = '<img src=x onerror=alert(1)>'
api.printReport()
assert.ok(printed.includes('&lt;img'),'print safely escapes imported title')
assert.ok(!printed.includes('<img src=x onerror='))
api.exportJson()
assert.equal(downloads.length,1)
api.invalidateCurrent()
api.confirmPreview()
assert.equal(events.length,3,'stale preview confirmation does not alter the map')
assert.equal(api.result.value, null, 'manual map modification invalidates stale AI plan')
assert.equal(api.preview.value, null, 'manual edits invalidate unconfirmed previews')
assert.match(api.notice.value, /旧AI方案已失效/)
api.removeSaved('test-uuid')
assert.equal(api.saved.value.length,0)
assert.match(appSource, /<AIItineraryPanel ref="aiPanelRef" @apply="applyAiPlan"/)
assert.match(appSource, /routeKind.value = 'valhalla'/)
assert.match(routePanelSource, /景点间直线距离（非导航）/)
assert.match(panelSource, /:disabled="result.route\?\.status !== 'verified_by_routing_service'"/)
console.log('AI itinerary: map integration, preview confirmation, persistence, restore, safe export PASS')
