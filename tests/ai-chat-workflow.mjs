// Exercise the actual Vue conversation panel without secrets, browser or network.
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import vm from 'node:vm'

const source = readFileSync(new URL('../frontend/src/components/AiChatPanel.vue', import.meta.url), 'utf8')
  .split('<script setup>')[1].split('</script>')[0].replace(/^import .*$/gm, '')
const route = ids => ({
  itinerary: { optimized_order_ids: ids },
  travel_mode: 'auto', budget_minutes: 480, start_time: '09:00',
  locked_place_ids: [],
})
const props = { plan: route([1, 2, 3, 4]), currentRouteIds: [1, 2, 3, 4], disabled: false }
const requests = []
const emissions = []
let shouldFail = false
const axios = {
  post(url, body, options) {
    requests.push({ url, body, options })
    if (url.endsWith('/chat/preview')) {
      return Promise.resolve({ data: {
        mode: 'rule_based', needs_confirmation: true,
        reply: '请核对改动后手动确认。',
        base_state: {
          place_ids: [...body.place_ids], locked_place_ids: [...body.locked_place_ids],
          transport_mode: body.transport_mode, budget_hours: body.budget_hours,
          start_time: body.start_time,
        },
        proposed: { ...body, place_ids: [1, 5, 3, 4], locked_place_ids: [3],
          auto_trim: true },
        changes: ['第二站替换为数据库景点5', '锁定第三站'],
        selected_names: ['景点1', '景点5', '景点3', '景点4'],
        warnings: ['道路尚未核实'],
      } })
    }
    if (shouldFail) {
      return Promise.reject({ response: { status: 409, data: { detail: '锁定景点超出预算' } } })
    }
    return Promise.resolve({ data: {
      ...route([1, 5, 3, 4]), locked_place_ids: [3],
      travel_mode: body.transport_mode, budget_minutes: body.budget_hours * 60,
      start_time: body.start_time, ai_mode: 'manual_replan',
      dropped_place_ids: [],
    } })
  },
}
const ref = value => ({ value })
const computed = getter => ({ get value() { return getter() } })
const context = vm.createContext({
  ref, computed, axios, JSON, Number,
  defineProps: () => props,
  defineEmits: () => (type, data) => {
    emissions.push({ type, data })
    if (type === 'applied') {
      props.plan = data
      props.currentRouteIds = [...data.itinerary.optimized_order_ids]
    }
  },
})
vm.runInContext(source + '\nthis.api = { input, messages, preview, error, send, confirm, cancel, matchesBase, canConfirm, pending, applying };', context)
const ui = context.api
const plain = value => JSON.parse(JSON.stringify(value))

ui.input.value = '把第二站换成公园，第三站必须保留'
await ui.send()
assert.equal(ui.preview.value.needs_confirmation, true)
assert.equal(requests.length, 1, 'preview request must not call routing/replan')
assert.deepEqual(plain(ui.preview.value.proposed.place_ids), [1, 5, 3, 4])
assert.equal(emissions.length, 0, 'preview cannot mutate map')
assert.equal(ui.canConfirm.value, true)
ui.cancel()
assert.equal(ui.preview.value, null)
assert.equal(emissions.length, 0, 'cancel must not apply plan')

ui.input.value = '换第二站，锁定第三站'
await ui.send()
assert.equal(ui.canConfirm.value, true)
props.currentRouteIds = [1, 2, 4]
assert.equal(ui.canConfirm.value, false, 'manual route changes invalidate confirmation')
await ui.confirm()
assert.equal(requests.filter(item => item.url.endsWith('/replan')).length, 0)
props.currentRouteIds = [1, 2, 3, 4]

shouldFail = true
await ui.confirm()
assert.equal(ui.error.value, '锁定景点超出预算')
assert.equal(emissions.length, 0, 'failed provider request leaves old map unchanged')
assert.equal(ui.preview.value.needs_confirmation, true)
shouldFail = false
await ui.confirm()
assert.equal(emissions.length, 1, 'confirmed successful replan updates map exactly once')
assert.deepEqual(plain(props.currentRouteIds), [1, 5, 3, 4])
assert.equal(props.plan.ai_mode, 'manual_replan')
assert.equal(ui.preview.value, null)

ui.input.value = '改成骑行'
await ui.send()
assert.equal(ui.messages.value.filter(m => m.role === 'user').length, 3)
const lastPreview = requests.at(-1)
assert.equal(lastPreview.body.history.length, 6, 'bounded local conversation carries history')
assert.deepEqual(plain(lastPreview.body.place_ids), [1, 5, 3, 4],
  'subsequent turns use the newly confirmed route')
assert.equal(emissions.length, 1)
console.log('PASS: chat preview/cancel, stale-map guard, 409 failure, confirmed replan and multiround state')
