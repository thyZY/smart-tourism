// Exercise the actual Vue AI editor script with no browser, database, or API key.
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import vm from 'node:vm'

const source = readFileSync(new URL('../frontend/src/components/NaturalSearchPanel.vue', import.meta.url), 'utf8')
  .split('<script setup>')[1].split('</script>')[0].replace(/^import .*$/gm, '')
const props = {
  mapReady: true, center: { lng: 118.79, lat: 32.04 },
  currentRouteIds: [],
}
const emitted = []
const requests = []
let failReplan = false
const makePlan = (ids, mode, aiMode) => ({
  ai_mode: aiMode,
  travel_mode: mode,
  explanation: '真实POI与道路服务提供结果',
  selected_places: { type: 'FeatureCollection', features: ids.map(id => ({
    type: 'Feature', properties: { id, name: '景点' + id },
    geometry: { type: 'Point', coordinates: [118.79, 32.04] },
  })) },
  itinerary: {
    optimized_order_ids: ids, distance_km: 4.2, duration_minutes: 12,
    geometry: { type: 'FeatureCollection', features: [] },
  },
  timeline: ids.map(id => ({ id, name: '景点' + id, visit_duration: 90,
    arrival_time: '09:00', departure_time: '10:30', reason: '数据库核实' })),
  limitations: [],
})
const initialPlan = makePlan([1, 2, 3, 4], 'auto', 'deepseek')
const changedPlan = makePlan([1, 3, 5], 'bicycle', 'manual_replan')

const apiClient = {
  get(url, options) {
    requests.push({ url, options })
    return Promise.resolve({ data: { type: 'FeatureCollection', features:
      [1, 2, 3, 4, 5, 6].map(id => ({
        type: 'Feature', properties: { id, name: '数据库景点' + id },
        geometry: { type: 'Point', coordinates: [118.79, 32.04] },
      })),
    } })
  },
  post(url, body, options) {
    requests.push({ url, body, options })
    if (url.endsWith('/itinerary/replan')) {
      return failReplan
        ? Promise.reject({ response: { data: { detail: '锁定景点超出预算' }, status: 409 } })
        : Promise.resolve({ data: changedPlan })
    }
    return Promise.resolve({ data: initialPlan })
  },
}
const ref = value => ({ value })
const computed = callback => ({ get value() { return callback() } })
const context = vm.createContext({
  ref, computed, axios: apiClient, Number, Set, Array,
  defineProps: () => props,
  defineEmits: () => (name, value) => {
    emitted.push({ name, value })
    if (name === 'planned') props.currentRouteIds = [...value.itinerary.optimized_order_ids]
  },
})
vm.runInContext(source + '\nthis.api = { query, plan, loadChoices, toggleLock, removeStop, replaceStop, replan, syncFromMap, planResult, editIds, lockedIds, editDirty, editError, autoTrim, transportMode, budgetHours, routeOutOfSync, placeChoices };', context)
const api = context.api
const json = x => JSON.parse(JSON.stringify(x))
api.query.value = '南京一天历史文化游，少走路'
await api.plan()
assert.equal(api.planResult.value.ai_mode, 'deepseek')
assert.deepEqual(json(api.editIds.value), [1, 2, 3, 4])
assert.equal(api.routeOutOfSync.value, false)
await api.loadChoices()
assert.equal(api.placeChoices.value.length, 6)

api.toggleLock(3)
api.removeStop(2)
assert.deepEqual(json(api.editIds.value), [1, 3, 4])
assert.deepEqual(json(api.lockedIds.value), [3])
api.replaceStop(4, '5')
assert.deepEqual(json(api.editIds.value), [1, 3, 5])
api.budgetHours.value = 7
api.transportMode.value = 'bicycle'
await api.replan()
const replanRequest = requests.find(req => req.url.endsWith('/itinerary/replan'))
assert(replanRequest)
assert.deepEqual(json(replanRequest.body.place_ids), [1, 3, 5])
assert.deepEqual(json(replanRequest.body.locked_place_ids), [3])
assert.equal(replanRequest.body.transport_mode, 'bicycle')
assert.equal(replanRequest.body.budget_hours, 7)
assert.equal(replanRequest.body.start_time, '09:00')
assert.equal(replanRequest.body.auto_trim, true)
assert.equal(api.planResult.value.ai_mode, 'manual_replan')
assert.equal(api.editDirty.value, false)
assert.equal(api.routeOutOfSync.value, false)
assert.equal(emitted.filter(e => e.name === 'planned').length, 2)

api.toggleLock(5)
failReplan = true
const previous = api.planResult.value
await api.replan()
assert.equal(api.planResult.value, previous, 'server failure must not overwrite last valid itinerary')
assert.equal(api.editDirty.value, true)
assert.equal(api.editError.value, '锁定景点超出预算')
assert.equal(emitted.filter(e => e.name === 'planned').length, 2, 'failed edit does not redraw map')

props.currentRouteIds = [1, 2, 3]
assert.equal(api.routeOutOfSync.value, true)
api.syncFromMap()
assert.deepEqual(json(api.editIds.value), [1, 2, 3])
assert.equal(api.editDirty.value, true)
console.log('PASS: AI itinerary editor load/lock/remove/replace/replan, no stale redraw on 409, map-sync detection')
