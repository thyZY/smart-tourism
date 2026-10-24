import { test, expect } from '@playwright/test'
import { readFile } from 'node:fs/promises'

// These cases intentionally mock the application's APIs. Real Valhalla coverage lives in real-map-road.spec.mjs.
const places = [
  [1, '南京博物院', '博物馆', 118.7921, 32.0407],
  [2, '夫子庙', '历史文化', 118.7877, 32.0270],
  [3, '中山陵', '陵园景区', 118.8486, 32.0593],
  [4, '南京总统府', '历史文化', 118.7969, 32.0480]
].map(([id, name, category, lng, lat]) => ({
  type: 'Feature',
  properties: { id, name, category, address: '南京市' },
  geometry: { type: 'Point', coordinates: [lng, lat] }
}))

const collection = { type: 'FeatureCollection', features: places }
const verifiedRoad = {
  status: 'verified_by_routing_service',
  provider: 'Valhalla',
  mode: 'auto',
  distance_km: 10.965,
  duration_minutes: 25.4,
  optimized: true,
  ordered_place_ids: [1, 2, 4, 3],
  geojson: {
    type: 'FeatureCollection',
    features: [{
      type: 'Feature',
      properties: { source: 'Valhalla', mode: 'auto' },
      geometry: { type: 'LineString', coordinates: [
        [118.7921, 32.0407], [118.7909, 32.0382], [118.7884, 32.0315],
        [118.7877, 32.0270], [118.7881, 32.0300], [118.7969, 32.0480],
        [118.8172, 32.0520], [118.8390, 32.0582], [118.8486, 32.0593]
      ] }
    }]
  }
}

async function addFourPlaces(page) {
  for (const place of places) {
    const row = page.locator(`.result-item[data-place-id="${place.properties.id}"]`)
    await expect(row).toContainText(place.properties.name)
    await row.click()
    await expect(page.locator('aside[aria-label="景点详情"]')).toContainText(place.properties.name)
    await page.getByRole('button', { name: '加入路线' }).click()
  }
  await page.getByRole('tab', { name: '我的路线' }).click()
  await expect(page.locator('.route-stop-name')).toHaveCount(4)
}

test.beforeEach(async ({ page }) => {
  await page.route('**/api/places**', route => route.fulfill({
    status: 200, contentType: 'application/json', body: JSON.stringify(collection)
  }))
  await page.route('**/api/statistics', route => route.fulfill({
    status: 200, contentType: 'application/json', body: JSON.stringify({
      total_places: places.length, category_counts: {}, top_categories: []
    })
  }))
  await page.route('**/api/ai/itinerary/road', route => route.fulfill({
    status: 200, contentType: 'application/json', body: JSON.stringify(verifiedRoad)
  }))
  // This file tests mocked route-export behavior; real basemap resources are tested separately.
  await page.route('https://tile.openstreetmap.org/**', route => route.abort())
  await page.route('https://demotiles.maplibre.org/**', route => route.abort())
  await page.goto('/full-app-e2e.html', { waitUntil: 'domcontentloaded' })
  await expect(page.locator('.map canvas')).toBeVisible()
})

test('mocked route success exports matching optimized GeoJSON and itinerary; edits and failure invalidate it', async ({ page }, testInfo) => {
  let roadCall = 0
  await page.unroute('**/api/ai/itinerary/road')
  await page.route('**/api/ai/itinerary/road', route => {
    roadCall += 1
    return route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(roadCall <= 2
        ? verifiedRoad
        : { status: 'unavailable', message: 'mock routing failure' })
    })
  })
  await addFourPlaces(page)

  const unverifiedDownloadPromise = page.waitForEvent('download')
  await page.getByRole('button', { name: '导出当前行程 JSON' }).click()
  const unverifiedDownload = await unverifiedDownloadPromise
  const unverifiedPath = testInfo.outputPath('unverified-itinerary.json')
  await unverifiedDownload.saveAs(unverifiedPath)
  const unverified = JSON.parse(await readFile(unverifiedPath, 'utf8'))
  expect(unverified.ordered_place_ids).toEqual([1, 2, 3, 4])
  expect(unverified.route.status).toBe('unverified')
  expect(unverified.route).not.toHaveProperty('geojson')
  expect(unverified.data_source_note).toContain('尚未通过道路服务核验')
  await expect(page.getByRole('button', { name: '导出道路 GeoJSON' })).toBeDisabled()

  await page.getByLabel('道路交通方式').selectOption('auto')
  await page.getByLabel('使用时间矩阵优化顺序（固定首站）').check()
  const firstResponsePromise = page.waitForResponse(response =>
    response.url().endsWith('/api/ai/itinerary/road') && response.request().method() === 'POST')
  await page.getByRole('button', { name: '计算实际道路路线' }).click()
  const firstResponse = await firstResponsePromise
  expect(firstResponse.status()).toBe(200)
  expect(firstResponse.request().postDataJSON()).toMatchObject({
    place_ids: [1, 2, 3, 4], travel_mode: 'auto', optimize: true
  })
  await expect(page.locator('.route-stop-name').allTextContents()).resolves.toEqual([
    '南京博物院', '夫子庙', '南京总统府', '中山陵'
  ])

  const geoDownloadPromise = page.waitForEvent('download')
  await page.getByRole('button', { name: '导出道路 GeoJSON' }).click()
  const geoDownload = await geoDownloadPromise
  const geoPath = testInfo.outputPath('optimized-route.geojson')
  await geoDownload.saveAs(geoPath)
  const downloadedGeo = JSON.parse(await readFile(geoPath, 'utf8'))
  expect(downloadedGeo.type).toBe('FeatureCollection')
  expect(downloadedGeo.features[0].geometry.type).toBe('LineString')
  expect(downloadedGeo.features[0].geometry.coordinates).toEqual(verifiedRoad.geojson.features[0].geometry.coordinates)

  const itineraryDownloadPromise = page.waitForEvent('download')
  await page.getByRole('button', { name: '导出当前行程 JSON' }).click()
  const itineraryDownload = await itineraryDownloadPromise
  const itineraryPath = testInfo.outputPath('optimized-itinerary.json')
  await itineraryDownload.saveAs(itineraryPath)
  const itinerary = JSON.parse(await readFile(itineraryPath, 'utf8'))
  expect(itinerary.ordered_place_ids).toEqual([1, 2, 4, 3])
  expect(itinerary.stops.map(stop => stop.order)).toEqual([1, 2, 3, 4])
  expect(itinerary.stops.map(stop => stop.id)).toEqual([1, 2, 4, 3])
  expect(itinerary.travel_mode).toBe('auto')
  expect(itinerary.route).toMatchObject({
    status: 'verified_by_routing_service', provider: 'Valhalla',
    distance_km: 10.965, duration_minutes: 25.4, optimized: true
  })
  expect(itinerary.route.geojson).toEqual(downloadedGeo)

  // A successful road becomes stale immediately when a stop is removed.
  await page.locator('.result-item[data-place-id="2"]').click()
  await page.getByRole('button', { name: '移出路线' }).click()
  await page.getByRole('tab', { name: '我的路线' }).click()
  await expect(page.getByRole('button', { name: '导出道路 GeoJSON' })).toBeDisabled()

  // Restore the stop and calculate again to prove a later failed request cannot revive old data.
  await page.locator('.result-item[data-place-id="2"]').click()
  await page.getByRole('button', { name: '加入路线' }).click()
  await page.getByRole('tab', { name: '我的路线' }).click()
  const restoredResponsePromise = page.waitForResponse(response =>
    response.url().endsWith('/api/ai/itinerary/road') && response.request().method() === 'POST')
  await page.getByRole('button', { name: '计算实际道路路线' }).click()
  expect((await restoredResponsePromise).status()).toBe(200)
  await expect(page.getByRole('button', { name: '导出道路 GeoJSON' })).toBeEnabled()

  // A failed re-calculation invalidates the previous successful road download immediately.
  const failureResponsePromise = page.waitForResponse(response =>
    response.url().endsWith('/api/ai/itinerary/road') && response.request().method() === 'POST')
  await page.getByRole('button', { name: '计算实际道路路线' }).click()
  expect((await failureResponsePromise).status()).toBe(200)
  await expect(page.getByRole('button', { name: '导出道路 GeoJSON' })).toBeDisabled()
  const afterFailurePromise = page.waitForEvent('download')
  await page.getByRole('button', { name: '导出当前行程 JSON' }).click()
  const afterFailureDownload = await afterFailurePromise
  const afterFailurePath = testInfo.outputPath('after-failure-itinerary.json')
  await afterFailureDownload.saveAs(afterFailurePath)
  const afterFailure = JSON.parse(await readFile(afterFailurePath, 'utf8'))
  expect(afterFailure.route.status).toBe('unverified')
  expect(afterFailure.route).not.toHaveProperty('geojson')

  await page.getByRole('button', { name: '清空路线' }).click()
  await expect(page.getByRole('button', { name: '导出道路 GeoJSON' })).toBeDisabled()
  await expect(page.getByRole('button', { name: '导出当前行程 JSON' })).toBeDisabled()
})

test('AI itinerary export remains independent', async ({ page }, testInfo) => {
  const aiPlan = {
    title: 'AI 测试行程', summary: 'AI panel fixture', mode: 'pedestrian',
    planning_method: 'local_rule_fallback',
    stops: [places[0].properties, places[1].properties],
    selected_places: { type: 'FeatureCollection', features: places.slice(0, 2) },
    route: {
      ...verifiedRoad,
      mode: 'pedestrian',
      ordered_place_ids: undefined
    }
  }
  await page.route('**/api/ai/itinerary/generate', route => route.fulfill({
    status: 200, contentType: 'application/json', body: JSON.stringify(aiPlan)
  }))
  await page.goto('/e2e-harness.html', { waitUntil: 'domcontentloaded' })
  await page.getByRole('button', { name: '生成并加载到地图' }).click()
  await expect(page.getByText('当前行程 · 数据库景点')).toBeVisible()

  const roadDownloadPromise = page.waitForEvent('download')
  await page.getByRole('button', { name: '导出道路 GeoJSON' }).click()
  const roadDownload = await roadDownloadPromise
  const roadPath = testInfo.outputPath('ai-panel-road.geojson')
  await roadDownload.saveAs(roadPath)
  expect(JSON.parse(await readFile(roadPath, 'utf8'))).toEqual(aiPlan.route.geojson)

  const jsonDownloadPromise = page.waitForEvent('download')
  await page.getByRole('button', { name: '导出行程 JSON' }).click()
  const jsonDownload = await jsonDownloadPromise
  const jsonPath = testInfo.outputPath('ai-panel-itinerary.json')
  await jsonDownload.saveAs(jsonPath)
  const exported = JSON.parse(await readFile(jsonPath, 'utf8'))
  expect(exported.title).toBe(aiPlan.title)
  expect(exported.route.geojson).toEqual(aiPlan.route.geojson)
})
