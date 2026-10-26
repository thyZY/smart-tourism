import { test, expect } from '@playwright/test'
import { readFile } from 'node:fs/promises'

const trackedHosts = /tile\.openstreetmap\.org|demotiles\.maplibre\.org/

test('real POIs, OSM basemap, and optimized Valhalla road render in MapLibre', async ({ page }, testInfo) => {
  test.setTimeout(120000)
  const resourceResponses = []
  const resourceFailures = []
  const consoleErrors = []
  const pageErrors = []
  page.on('response', response => {
    if (trackedHosts.test(response.url())) {
      resourceResponses.push({ url: response.url(), status: response.status() })
    }
  })
  page.on('requestfailed', request => {
    if (trackedHosts.test(request.url())) {
      resourceFailures.push({ url: request.url(), error: request.failure()?.errorText })
    }
  })
  page.on('console', message => {
    if (message.type() === 'error') consoleErrors.push(message.text())
  })
  page.on('pageerror', error => pageErrors.push(error.message))

  await page.goto('/', { waitUntil: 'domcontentloaded' })
  await expect(page.locator('.map canvas')).toBeVisible()
  const mobileWorkspaces = page.getByRole('tablist', { name: '主要工作区' })
  if (await mobileWorkspaces.isVisible()) {
    await mobileWorkspaces.getByRole('tab', { name: '探索' }).click()
    const expand = page.getByRole('button', { name: '展开工作面板' })
    if (await expand.isVisible()) await expand.click()
  }
  await expect(page.locator('.result-item[data-place-id="1"]')).toBeVisible({ timeout: 20000 })
  await expect(page.locator('.result-item[data-place-id="2"]')).toBeVisible()
  await expect(page.locator('.result-item[data-place-id="3"]')).toBeVisible()
  await expect(page.locator('.result-item[data-place-id="4"]')).toBeVisible()

  // Require successful real HTTP tile responses; a canvas alone is not a basemap pass.
  await expect.poll(() => resourceResponses.filter(r => r.url.includes('tile.openstreetmap.org') && r.status === 200).length,
    { timeout: 30000 }).toBeGreaterThanOrEqual(4)

  const expectedPlaces = [
    [1, '南京博物院'], [2, '夫子庙'], [3, '中山陵'], [4, '南京总统府']
  ]
  for (const [id, name] of expectedPlaces) {
    const result = page.locator(`.result-item[data-place-id="${id}"]`)
    await expect(result).toContainText(name)
    await result.click()
    await expect(page.locator('aside[aria-label="景点详情"]')).toContainText(name)
    await page.getByRole('button', { name: '加入路线' }).click()
    if (await mobileWorkspaces.isVisible()) {
      await page.getByRole('button', { name: '关闭详情' }).click()
    }
    await expect(page.locator(`.result-item[data-place-id="${id}"] .route-order-pill`)).toBeVisible()
  }
  await expect(page.locator('aside[aria-label="我的路线"]')).toContainText('4')
  const routeStopsBefore = await page.locator('.route-places li').allTextContents()
  expect(routeStopsBefore.join(' ')).toContain('南京博物院')
  expect(routeStopsBefore.join(' ')).toContain('夫子庙')
  expect(routeStopsBefore.join(' ')).toContain('中山陵')
  expect(routeStopsBefore.join(' ')).toContain('南京总统府')

  await page.getByRole('tab', { name: '我的路线' }).click()
  await expect(page.locator('aside[aria-label="我的路线"]')).toBeVisible()
  await page.getByLabel('道路交通方式').selectOption('auto')

  const initialRoadResponsePromise = page.waitForResponse(response =>
    response.url().endsWith('/api/ai/itinerary/road') && response.request().method() === 'POST')
  await page.getByRole('button', { name: '计算实际道路路线' }).click()
  const initialRoadResponse = await initialRoadResponsePromise
  expect(initialRoadResponse.status()).toBe(200)
  expect(initialRoadResponse.request().postDataJSON()).toMatchObject({
    place_ids: [1, 2, 3, 4], travel_mode: 'auto', optimize: false
  })
  const initialRoad = await initialRoadResponse.json()
  expect(initialRoad.status).toBe('verified_by_routing_service')
  expect(initialRoad.provider).toBe('Valhalla')
  expect(initialRoad.optimized).toBe(false)

  await page.getByLabel('使用时间矩阵优化顺序（固定首站）').check()
  const roadResponsePromise = page.waitForResponse(response =>
    response.url().endsWith('/api/ai/itinerary/road') && response.request().method() === 'POST')
  await page.getByRole('button', { name: '计算实际道路路线' }).click()
  const roadResponse = await roadResponsePromise
  expect(roadResponse.status()).toBe(200)
  expect(roadResponse.request().postDataJSON()).toMatchObject({
    place_ids: [1, 2, 3, 4], travel_mode: 'auto', optimize: true
  })
  const road = await roadResponse.json()
  expect(road.status).toBe('verified_by_routing_service')
  expect(road.provider).toBe('Valhalla')
  expect(road.mode).toBe('auto')
  expect(road.optimized).toBe(true)
  expect(road.ordered_place_ids).toEqual([1, 2, 4, 3])
  expect(road.geojson.type).toBe('FeatureCollection')
  expect(road.geojson.features[0].geometry.type).toBe('LineString')
  expect(road.geojson.features[0].geometry.coordinates.length).toBeGreaterThan(20)
  expect(road.distance_km).toBeGreaterThan(0)
  expect(road.duration_minutes).toBeGreaterThan(0)

  await expect(page.locator('.map-route-status')).toContainText('Valhalla')
  await expect(page.locator('.route-distance')).toContainText(`${road.distance_km.toFixed(1)} km`)
  await expect(page.locator('.route-time')).toContainText(`${road.duration_minutes.toFixed(1)} 分钟`)
  await expect(page.getByText('已按路网时间优化顺序')).toBeVisible()
  const routeLayerSource = await page.evaluate(() => {
    const root = document.querySelector('#app')?.__vue_app__?._instance?.setupState
    const instance = root?.map
    return instance?.getLayer('route-line')?.source ?? null
  })
  expect(routeLayerSource).toBe('route-line')
  await expect.poll(() => page.evaluate(() => {
    const instance = document.querySelector('#app')?.__vue_app__?._instance?.setupState?.map
    return instance?.queryRenderedFeatures({ layers: ['route-line'] }).length ?? 0
  }), { timeout: 10000 }).toBeGreaterThan(0)
  const displayedOrder = await page.locator('.route-stop-name').allTextContents()
  expect(displayedOrder).toEqual(['南京博物院', '夫子庙', '南京总统府', '中山陵'])

  const roadDownloadPromise = page.waitForEvent('download')
  await page.getByRole('button', { name: '导出道路 GeoJSON' }).click()
  const roadDownload = await roadDownloadPromise
  const geojsonPath = testInfo.outputPath('exported-current-route.geojson')
  await roadDownload.saveAs(geojsonPath)
  const exportedGeoJson = JSON.parse(await readFile(geojsonPath, 'utf8'))
  expect(exportedGeoJson.type).toBe('FeatureCollection')
  expect(exportedGeoJson.features[0].geometry.type).toBe('LineString')
  expect(exportedGeoJson.features[0].geometry.coordinates).toEqual(road.geojson.features[0].geometry.coordinates)

  const itineraryDownloadPromise = page.waitForEvent('download')
  await page.getByRole('button', { name: '导出当前行程 JSON' }).click()
  const itineraryDownload = await itineraryDownloadPromise
  const itineraryPath = testInfo.outputPath('exported-current-itinerary.json')
  await itineraryDownload.saveAs(itineraryPath)
  const exportedItinerary = JSON.parse(await readFile(itineraryPath, 'utf8'))
  expect(exportedItinerary.ordered_place_ids).toEqual(road.ordered_place_ids)
  expect(exportedItinerary.stops.map(stop => stop.name)).toEqual(displayedOrder)
  expect(exportedItinerary.travel_mode).toBe(road.mode)
  expect(exportedItinerary.route).toMatchObject({
    status: road.status,
    provider: road.provider,
    distance_km: road.distance_km,
    duration_minutes: road.duration_minutes,
    optimized: true
  })
  expect(exportedItinerary.route.geojson).toEqual(exportedGeoJson)

  // Trigger real map interaction and verify the route can be requested again without stacking sources.
  await page.getByRole('button', { name: 'Zoom in' }).click()
  const mapBounds = await page.locator('.map canvas').boundingBox()
  expect(mapBounds).not.toBeNull()
  await page.mouse.move(mapBounds.x + mapBounds.width / 2, mapBounds.y + mapBounds.height / 2)
  await page.mouse.down()
  await page.mouse.move(mapBounds.x + mapBounds.width / 2 + 90, mapBounds.y + mapBounds.height / 2 + 35, { steps: 6 })
  await page.mouse.up()
  await expect(page.locator('.map canvas')).toBeVisible()
  const secondRoadPromise = page.waitForResponse(response =>
    response.url().endsWith('/api/ai/itinerary/road') && response.request().method() === 'POST')
  await page.getByRole('button', { name: '计算实际道路路线' }).click()
  const secondRoad = await secondRoadPromise
  expect(secondRoad.status()).toBe(200)
  if (await mobileWorkspaces.isVisible()) {
    await page.getByRole('button', { name: '收起工作面板' }).click()
  }
  await page.screenshot({ path: testInfo.outputPath('real-valhalla-route.png'), fullPage: false })

  if (await mobileWorkspaces.isVisible()) {
    await mobileWorkspaces.getByRole('tab', { name: '探索' }).click()
  }
  await page.locator('.result-item[data-place-id="2"]').click()
  await page.getByRole('button', { name: '移出路线' }).click()
  await page.getByRole('tab', { name: '我的路线' }).click()
  await expect(page.getByRole('button', { name: '导出道路 GeoJSON' })).toBeDisabled()
  await page.getByRole('button', { name: '清空路线' }).click()
  await expect(page.getByRole('button', { name: '导出道路 GeoJSON' })).toBeDisabled()
  await expect(page.getByRole('button', { name: '导出当前行程 JSON' })).toBeDisabled()

  const glyphProbe = await page.evaluate(async () => {
    const url = 'https://demotiles.maplibre.org/font/Open%20Sans%20Semibold/0-255.pbf'
    const response = await fetch(url, { signal: AbortSignal.timeout(10000) })
    return { status: response.status, ok: response.ok, contentType: response.headers.get('content-type') }
  })
  expect(glyphProbe.status).toBe(200)
  expect(glyphProbe.ok).toBe(true)
  // MapLibre cancels stale tile requests when the camera moves; those are expected.
  const unexpectedResourceFailures = resourceFailures.filter(failure => failure.error !== 'net::ERR_ABORTED')
  expect(unexpectedResourceFailures).toEqual([])
  // Camera movement and zoom cancel stale tiles normally; those cancellations must
  // not show the persistent basemap outage alert.
  await expect(page.getByRole('alert')).toHaveCount(0)
  expect(pageErrors).toEqual([])
  console.log('REAL_MAP_RESOURCE_SUMMARY', JSON.stringify({
    route: {
      status: road.status,
      provider: road.provider,
      orderedPlaceIds: road.ordered_place_ids,
      mode: road.mode,
      optimized: road.optimized,
      distanceKm: road.distance_km,
      durationMinutes: road.duration_minutes,
      geometryType: road.geojson.features[0].geometry.type,
      coordinateCount: road.geojson.features[0].geometry.coordinates.length
    },
    tile200: resourceResponses.filter(r => r.url.includes('tile.openstreetmap.org') && r.status === 200).length,
    glyphResponses: resourceResponses.filter(r => r.url.includes('demotiles.maplibre.org')).map(r => r.status),
    glyphProbe,
    failures: resourceFailures,
    unexpectedFailures: unexpectedResourceFailures,
    consoleErrors
  }))
})

test('real database POIs and Valhalla road update the MapLibre route source without tile gating', async ({ page }, testInfo) => {
  test.setTimeout(90000)
  const pageErrors = []
  page.on('pageerror', error => pageErrors.push(error.message))

  await page.goto('/', { waitUntil: 'domcontentloaded' })
  await expect(page.locator('.map canvas')).toBeVisible()
  await page.waitForFunction(() =>
    document.querySelector('#app')?.__vue_app__?._instance?.setupState?.mapReady === true,
    undefined,
    { timeout: 20000 }
  )

  const mobileWorkspaces = page.getByRole('tablist', { name: '主要工作区' })
  if (await mobileWorkspaces.isVisible()) {
    await mobileWorkspaces.getByRole('tab', { name: '探索' }).click()
    const expand = page.getByRole('button', { name: '展开工作面板' })
    if (await expand.isVisible()) await expand.click()
  }

  const expectedPlaces = [
    [1, '南京博物院'], [2, '夫子庙'], [3, '中山陵'], [4, '南京总统府']
  ]
  for (const [id, name] of expectedPlaces) {
    const result = page.locator(`.result-item[data-place-id="${id}"]`)
    await expect(result).toContainText(name)
    await result.click()
    await expect(page.locator('aside[aria-label="景点详情"]')).toContainText(name)
    await page.getByRole('button', { name: '加入路线' }).click()
    if (await mobileWorkspaces.isVisible()) {
      await page.getByRole('button', { name: '关闭详情' }).click()
    }
  }

  if (await mobileWorkspaces.isVisible()) {
    await mobileWorkspaces.getByRole('tab', { name: '我的路线' }).click()
  } else {
    await page.getByRole('tablist', { name: '选择工作台功能' })
      .getByRole('tab', { name: '我的路线', exact: true }).click()
  }
  await expect(page.locator('aside[aria-label="我的路线"]')).toContainText('4')
  await page.getByLabel('道路交通方式').selectOption('auto')
  await page.getByLabel('使用时间矩阵优化顺序（固定首站）').check()

  const roadResponsePromise = page.waitForResponse(response =>
    response.url().endsWith('/api/ai/itinerary/road') &&
    response.request().method() === 'POST'
  )
  await page.getByRole('button', { name: '计算实际道路路线' }).click()
  const roadResponse = await roadResponsePromise
  expect(roadResponse.status()).toBe(200)
  expect(roadResponse.request().postDataJSON()).toMatchObject({
    place_ids: [1, 2, 3, 4], travel_mode: 'auto', optimize: true
  })
  const road = await roadResponse.json()
  expect(road.status).toBe('verified_by_routing_service')
  expect(road.provider).toBe('Valhalla')
  expect(road.optimized).toBe(true)
  expect(road.geojson.type).toBe('FeatureCollection')
  expect(road.geojson.features[0].geometry.type).toBe('LineString')
  expect(road.geojson.features[0].geometry.coordinates.length).toBeGreaterThan(20)
  expect(road.geojson.features[0].geometry.coordinates.every(coordinate =>
    Array.isArray(coordinate) && coordinate.length >= 2 && coordinate.every(Number.isFinite)
  )).toBe(true)

  await expect(page.locator('.map-route-status')).toContainText('Valhalla')
  await expect(page.locator('.route-distance')).toContainText(`${road.distance_km.toFixed(1)} km`)
  await expect(page.locator('.route-time')).toContainText(`${road.duration_minutes.toFixed(1)} 分钟`)
  const routeLayerSource = await page.evaluate(() => {
    const map = document.querySelector('#app')?.__vue_app__?._instance?.setupState?.map
    const source = map?.getSource('route-line')
    return {
      layerSource: map?.getLayer('route-line')?.source ?? null,
      data: source?._data?.geojson ?? source?._options?.data ?? null
    }
  })
  expect(routeLayerSource.layerSource).toBe('route-line')
  expect(routeLayerSource.data?.features?.[0]?.geometry).toEqual(road.geojson.features[0].geometry)

  const downloadPromise = page.waitForEvent('download')
  await page.getByRole('button', { name: '导出道路 GeoJSON' }).click()
  const download = await downloadPromise
  const outputPath = testInfo.outputPath('real-valhalla-route.geojson')
  await download.saveAs(outputPath)
  const exported = JSON.parse(await readFile(outputPath, 'utf8'))
  expect(exported).toEqual(road.geojson)
  expect(pageErrors).toEqual([])

  await page.screenshot({ path: testInfo.outputPath('real-valhalla-route-source.png'), fullPage: false })
  console.log('REAL_VALHALLA_SOURCE', JSON.stringify({
    status: road.status,
    provider: road.provider,
    orderedPlaceIds: road.ordered_place_ids,
    distanceKm: road.distance_km,
    durationMinutes: road.duration_minutes,
    coordinateCount: road.geojson.features[0].geometry.coordinates.length,
    layerSource: routeLayerSource.layerSource,
    externalBasemapRequired: false
  }))
})
