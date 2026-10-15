// Guard against reintroducing full-screen absolute-positioned overlays.
// This is a structural regression test; actual responsive visuals still
// require browser screenshot checks at desktop and mobile widths.
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

const source = readFileSync(new URL('../frontend/src/App.vue', import.meta.url), 'utf8')
const template = source.slice(source.indexOf('\n<template>'), source.lastIndexOf('\n</template>') + 12)
const styles = source.slice(source.lastIndexOf('\n<style>'))
const panels = [
  ['AIItineraryPanel','ai'],
  ['RoutePanel','route'],
  ['ThemePanel','themes'],
  ['CulturalLinePanel','culture'],
  ['StatisticsPanel','statistics'],
  ['SpatialAnalysisPanel','analysis'],
  ['PlaceDetailPanel','detail'],
]
assert.match(template, /class="toolbar-main"/, 'toolbar is separate from map')
assert.match(template, /class="category-filter"/, 'category controls remain accessible')
assert.match(template, /id="explorer-panel"/, 'explorer list has own pane')
assert.match(template, /class="map-stage"/, 'MapLibre has dedicated stage')
assert.match(template, /id="workspace-panel"/, 'workspace has own pane')
assert.match(template, /role="tablist"/, 'workspace has accessible tabs')
assert.match(template, /ref="mapContainer" class="map"/)
assert.match(styles, /grid-template-columns:\s*var\(--explorer-width\) minmax\(0,1fr\) var\(--workspace-width\)/)
assert.match(styles, /\.workspace-content\s*\{[^}]*overflow-y:auto/s, 'workspace scrolls independently')
assert.match(styles, /\.result-list\s*\{[^}]*overflow-y:auto/s, '40+ POIs scroll inside explorer')
assert.match(styles, /@media\(max-width:1020px\)/, 'narrow-screen fallback exists')
assert.match(styles, /@media\(max-width:600px\)/, 'mobile toolbar adaptation exists')
for (const [component, tab] of panels) {
  assert.equal((template.match(new RegExp('<' + component + '\\b', 'g')) || []).length, 1,
    component + ' occurs once, not duplicated in overlays')
  assert.ok(template.includes(`v-show="activeWorkspaceTab === '${tab}'"`),
    component + ' is displayed via matching tab')
}
assert.match(template, /@click="toggleExplorer"/)
assert.match(template, /@click="toggleWorkspace"/)
assert.match(template, /@click="searchNearbyPlaces"/)
assert.match(template, /@click="showFavoritePlaces"/)
assert.match(template, /@click="searchCurrentArea"/)
assert.match(template, /@click="setMapDisplayMode\('heatmap'\)"/)
assert.match(template, /@click\.stop="toggleFavorite\(feature\)"/)
assert.match(template, /@click="focusResult\(feature\)"/)
assert.match(template, /@click="selectCategory\(category\)"/)
assert.match(template, /@apply="applyAiPlan"/)
assert.match(template, /@export-grid="downloadAnalysisGrid"/)
console.log('Responsive workspace structural regression PASS')
