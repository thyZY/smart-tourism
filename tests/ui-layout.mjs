// Layout contract checks: keep map controls usable and prevent independent
// absolutely positioned panels from covering the route comparison.
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
const read = path => readFileSync(new URL('../frontend/' + path, import.meta.url), 'utf8')

const app = read('src/App.vue')
const css = read('src/style.css')
const theme = read('src/components/ThemePanel.vue')
const stats = read('src/components/StatisticsPanel.vue')
const route = read('src/components/RoutePanel.vue')
const ai = read('src/components/NaturalSearchPanel.vue')
const preview = read('src/components/ItineraryPreviewPanel.vue')
const detail = read('src/components/PlaceDetailPanel.vue')

const rootTemplate = app.split('<template>')[1].split('</template>')[0]
assert(rootTemplate.includes('class="map-toolbar"'), 'search/display controls share a toolbar')
assert(rootTemplate.includes('class="category-filter"'), 'category bar remains present')
assert(rootTemplate.includes('class="left-workspace"'), 'search and AI share the left rail')
assert(rootTemplate.includes('class="left-view-tabs"'), 'AI and POI results have separate tabs')
assert(rootTemplate.includes('v-show="leftView === \'places\'"'), 'POI list has its own pane')
assert(rootTemplate.includes('v-show="leftView === \'ai\'"'), 'AI timeline has its own pane')
assert(app.includes('.places-workspace, .ai-workspace'), 'left views are flex height-constrained')
assert(app.includes('.places-workspace > .result-list'), 'result list scrolls inside list pane')
assert(rootTemplate.indexOf('class="result-list"') < rootTemplate.indexOf('<ItineraryPreviewPanel'),
       'classic itinerary preview remains directly below the scenic list')
assert(rootTemplate.includes(':class="{ \'preview-expanded\': previewExpanded }"'),
       'preview expanded state controls parent height allocation')
assert(rootTemplate.includes('@expanded-change="previewExpanded = $event"'),
       'native preview disclosure notifies the parent on expand and collapse')
assert(preview.includes("emit('expanded-change', expanded.value)"),
       'preview emits both open and closed state')
assert(preview.includes('@toggle="handleToggle"'),
       'native details toggle is observable')
assert(app.includes('.places-workspace.preview-expanded > .result-list'),
       'expanded preview shortens scenic list height')
assert(app.includes('.places-workspace.preview-expanded > .itinerary-tool'),
       'expanded preview gets additional vertical space')
assert(app.includes('max-height: min(31vh, 270px)'), 'expanded list receives reduced cap')
assert(app.includes('max-height: min(51vh, 440px)'), 'collapsed list starts with readable cap')

assert(app.includes('.ai-workspace > .natural-search'), 'AI content scrolls in its own pane')
assert(ai.includes('max-height: none;'), 'generated AI itinerary has no competing fixed height limit')
assert(rootTemplate.includes('class="right-workspace"'), 'routing, themes and statistics share the right rail')
assert(
  rootTemplate.indexOf('<RoutePanel') < rootTemplate.indexOf('<ThemePanel') &&
  rootTemplate.indexOf('<ThemePanel') < rootTemplate.indexOf('<StatisticsPanel'),
  'route comparison has priority over collapsible recommendations and statistics'
)
assert(rootTemplate.indexOf('<ItineraryPreviewPanel') < rootTemplate.indexOf('<NaturalSearchPanel'))
assert(rootTemplate.includes('@change-mode="selectRoadMode"'), 'transport mode switching remains wired')
assert(rootTemplate.includes('@calculate-road="calculateRoadRoute"'), 'Valhalla requests remain wired')
assert(rootTemplate.includes('@planned="applyAiPlan"'), 'AI itinerary reaches the map renderer')
assert(ai.includes("'/api/ai/itinerary'") || ai.includes("127.0.0.1:8010/api/ai/itinerary"),
       'AI panel has the personalized route endpoint')
assert(ai.includes("planResult.timeline"), 'AI itinerary includes a provisional schedule')
assert(ai.includes("planResult.limitations"), 'unverified constraints are disclosed')
assert(rootTemplate.includes('@toggle-route="selectedPlace && toggleRoutePlace(selectedPlace)"'))
assert(rootTemplate.includes('aria-label="南京景点地图"'))

for (const [name, component, classname] of [
  ['RoutePanel', route, 'route-panel'],
  ['ThemePanel', theme, 'theme-panel'],
  ['StatisticsPanel', stats, 'statistics-panel'],
  ['NaturalSearchPanel', ai, 'natural-search'],
  ['ItineraryPreviewPanel', preview, 'preview-panel']
]) {
  const style = component.split('<style scoped>')[1]?.split('</style>')[0]
  assert(style, name + ' has scoped styles')
  assert(
    new RegExp('\\.' + classname + '\\s*\\{[^}]*position:\\s*relative').test(style),
    name + ' is docked instead of independently positioned over the map'
  )
}
assert(theme.includes('<details>') && !theme.includes('<details open'), 'themes collapse initially')
assert(stats.includes('const expanded = ref(false)'), 'statistics collapse initially')
assert(app.includes('.right-workspace > .route-panel'), 'right route panel receives available height')
assert(app.includes('overflow-y: auto;'), 'rails and lists can scroll rather than overflow')
assert(app.includes('@media (max-width: 760px)'), 'small screens have independent layouts')
assert(detail.includes('right: calc(var(--rail-width, 320px) + 28px)'), 'details avoid desktop route rail')
assert(detail.includes('@media (max-width: 1180px)'), 'details remain reachable on narrow displays')
assert(!css.includes('width: 1126px'), 'Vite starter max-width restriction is removed')
console.log('PASS: workspace hierarchy, no floating-panel overlap CSS, responsive layout and existing route actions')
