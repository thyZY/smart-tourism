import { test, expect } from '@playwright/test'
import { writeFile } from 'node:fs/promises'

test('real backend without DeepSeek key uses database rules and never claims fabricated roads', async ({ page }, testInfo) => {
  await page.goto('/e2e-harness.html')

  const placesResponse = await page.request.get('http://127.0.0.1:8010/api/places')
  expect(placesResponse.status()).toBe(200)
  const places = await placesResponse.json()
  expect(places.type).toBe('FeatureCollection')
  const livePlacesById = new Map(places.features.map(feature => [feature.properties.id, feature.properties.name]))
  expect(livePlacesById.size).toBeGreaterThanOrEqual(2)

  const generationPromise = page.waitForResponse(response =>
    response.url().endsWith('/api/ai/itinerary/generate') && response.request().method() === 'POST')
  await page.getByRole('button', { name: '生成并加载到地图' }).click()
  const response = await generationPromise
  expect(response.status()).toBe(200)
  const plan = await response.json()

  expect(plan.planning_method).toBe('local_rule_fallback')
  expect(plan.recommendation_audit.method).toBe('local_rule_fallback')
  expect(plan.stops.length).toBeGreaterThanOrEqual(2)
  expect(new Set(plan.stops.map(stop => stop.id)).size).toBe(plan.stops.length)
  for (const stop of plan.stops) {
    expect(livePlacesById.get(stop.id)).toBe(stop.name)
  }

  const workspace = page.getByRole('region', { name: 'AI 行程工作台' })
  const result = workspace.locator('.ai-results')
  await expect(result).toContainText('排序方式：数据库规则排序（AI未使用或不可用）')
  await expect(result).not.toContainText('DeepSeek从真实POI中排序')

  const route = plan.route || {}
  expect(plan.provenance.routing_status).toBe(route.status)
  if (route.status === 'verified_by_routing_service') {
    expect(route.provider).toBe('Valhalla')
    expect(route.geojson.type).toBe('FeatureCollection')
    expect(route.geojson.features[0].geometry.type).toBe('LineString')
    expect(route.geojson.features[0].geometry.coordinates.length).toBeGreaterThanOrEqual(2)
    await expect(result).toContainText('Valhalla道路：')
  } else {
    expect(route.status).toBe('unavailable')
    expect(route).not.toHaveProperty('distance_km')
    expect(route).not.toHaveProperty('duration_minutes')
    expect(route).not.toHaveProperty('geojson')
    await expect(result).toContainText('道路未核验；地图直线只作景点顺序预览')
  }

  await page.screenshot({ path: testInfo.outputPath('no-key-fallback.png'), fullPage: true })
  await writeFile(testInfo.outputPath('no-key-fallback-summary.json'), JSON.stringify({
    generationHttpStatus: response.status(),
    planningMethod: plan.planning_method,
    auditMethod: plan.recommendation_audit.method,
    livePostgisPlaceCount: livePlacesById.size,
    stops: plan.stops.map(({ id, name }) => ({ id, name })),
    allStopsMatchLiveDatabase: plan.stops.every(stop => livePlacesById.get(stop.id) === stop.name),
    routeStatus: route.status,
    routeProvider: route.provider || null,
    routeGeometryType: route.geojson?.features?.[0]?.geometry?.type || null,
    routeCoordinateCount: route.geojson?.features?.[0]?.geometry?.coordinates?.length || 0,
    routeHasNoInventedRoadMetrics: route.status !== 'unavailable' || (
      !Object.hasOwn(route, 'distance_km') && !Object.hasOwn(route, 'duration_minutes') && !Object.hasOwn(route, 'geojson')
    ),
    uiReportsRuleFallback: true
  }, null, 2), 'utf8')
})
