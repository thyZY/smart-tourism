import { test, expect } from '@playwright/test'

test('simulated basemap failure keeps live POIs usable and recovers with controlled tile fixture', async ({ page }, testInfo) => {
  test.setTimeout(90000)
  let forcedFailures = 0
  let simulateOutage = true
  const tileResponses = []
  const tileFailures = []
  // Use a browser-generated, fully decodable raster tile. A tiny PNG can
  // return HTTP 200 while MapLibre rejects it as a usable tile, which would
  // test response delivery rather than recovery of the map source.
  const tileDataUrl = await page.evaluate(() => {
    const canvas = document.createElement('canvas')
    canvas.width = 256
    canvas.height = 256
    const context = canvas.getContext('2d')
    context.fillStyle = '#dce8d7'
    context.fillRect(0, 0, canvas.width, canvas.height)
    return canvas.toDataURL('image/png')
  })
  const testTile = Buffer.from(tileDataUrl.split(',')[1], 'base64')
  page.on('response', response => {
    if (response.url().includes('tile.openstreetmap.org')) {
      tileResponses.push({ url: response.url(), status: response.status() })
    }
  })
  page.on('requestfailed', request => {
    if (request.url().includes('tile.openstreetmap.org')) {
      tileFailures.push({ url: request.url(), error: request.failure()?.errorText })
    }
  })
  await page.route('https://tile.openstreetmap.org/**', async route => {
    if (simulateOutage) {
      forcedFailures += 1
      await route.abort('failed')
      return
    }
    // Recovery is deterministic in the ordinary CI suite. The separate
    // @live-map checks exercise public OSM availability without retry loops.
    await route.fulfill({ status: 200, contentType: 'image/png', body: testTile })
  })

  await page.goto('/', { waitUntil: 'domcontentloaded' })
  await expect(page.locator('.map canvas')).toBeVisible()
  await expect(page.locator('.result-item[data-place-id="1"]')).toBeVisible({ timeout: 30000 })
  await expect(page.getByRole('alert')).toContainText('底图暂时无法加载', { timeout: 20000 })
  await expect(page.getByRole('button', { name: '搜索', exact: true })).toBeEnabled()
  await expect(page.locator('.result-item[data-place-id]').first()).toBeVisible()
  await page.screenshot({ path: testInfo.outputPath('simulated-basemap-failure-pois-usable.png') })

  const successfulBeforeRetry = tileResponses.filter(response => response.status === 200).length
  simulateOutage = false
  await page.getByRole('button', { name: '重试底图' }).click()
  await expect.poll(() => tileResponses.filter(response => response.status === 200).length,
    { timeout: 15000 }).toBeGreaterThan(successfulBeforeRetry)
  await expect(page.getByRole('alert')).toHaveCount(0, { timeout: 15000 })
  await page.screenshot({ path: testInfo.outputPath('basemap-recovered-live-tiles.png') })

  expect(forcedFailures).toBeGreaterThan(0)
  expect(tileFailures.some(failure => failure.error !== 'net::ERR_ABORTED')).toBe(true)
  console.log('BASEMAP_FAILURE_RECOVERY', JSON.stringify({
    forcedFailures,
    recoveredFixtureTiles: tileResponses.filter(response => response.status === 200).length,
    failures: tileFailures
  }))
})
