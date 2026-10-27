import { test, expect } from '@playwright/test'

test('configured browser proxy loads real OSM basemap tiles @live-map', async ({ page }) => {
  test.setTimeout(45000)
  const tileResponses = []
  const tileFailures = []
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
  await page.goto('/', { waitUntil: 'domcontentloaded' })
  await expect(page.locator('.map canvas')).toBeVisible()
  await expect.poll(() => tileResponses.filter(response => response.status === 200).length,
    { timeout: 30000 }).toBeGreaterThanOrEqual(4)
  expect(tileFailures).toEqual([])
  console.log('PROXY_SMOKE', JSON.stringify({ successfulTiles: tileResponses.filter(r => r.status === 200).length, tileFailures }))
})
