import { test, expect } from '@playwright/test'

const places = Array.from({ length: 40 }, (_, index) => ({
  type: 'Feature',
  properties: {
    id: index + 1,
    name: `验收景点${index + 1}`,
    category: '验收类别',
    address: '南京市'
  },
  geometry: {
    type: 'Point',
    coordinates: [118.78 + index * 0.001, 32.02 + index * 0.001]
  }
}))

async function keepMapRequestsOutOfApiTests(page) {
  // These tests exercise API/UI state only; real map resources have their own gate.
  await page.route('https://tile.openstreetmap.org/**', route => route.abort())
  await page.route('https://demotiles.maplibre.org/**', route => route.abort())
}

test('real same-origin API response loads the database POIs and clears outage state', async ({ page }) => {
  const apiRequests = []
  page.on('request', request => {
    if (new URL(request.url()).pathname.startsWith('/api/')) apiRequests.push(request.url())
  })
  await keepMapRequestsOutOfApiTests(page)

  const placesResponsePromise = page.waitForResponse(response => {
    const url = new URL(response.url())
    return url.pathname === '/api/places' && response.request().method() === 'GET'
  })
  await page.goto('/', { waitUntil: 'domcontentloaded' })
  const response = await placesResponsePromise
  expect(response.status()).toBe(200)
  const collection = await response.json()
  expect(collection.type).toBe('FeatureCollection')
  expect(collection.features).toHaveLength(40)
  expect(new Set(collection.features.map(feature => feature.properties.id)).size).toBe(40)
  await expect(page.locator('.result-item')).toHaveCount(40, { timeout: 20000 })
  await expect(page.getByText('后端 API 暂不可达')).toHaveCount(0)
  expect(apiRequests.length).toBeGreaterThan(0)
  expect(apiRequests.every(url => new URL(url).origin === new URL(page.url()).origin)).toBe(true)
})

test('an endpoint HTTP 500 stays local when POI API succeeds', async ({ page }) => {
  const pageErrors = []
  page.on('pageerror', error => pageErrors.push(error.message))
  await page.route('**/api/places**', route => route.fulfill({
    status: 200,
    contentType: 'application/json',
    body: JSON.stringify({ type: 'FeatureCollection', features: places })
  }))
  await page.route('**/api/statistics', route => route.fulfill({
    status: 500,
    contentType: 'application/json',
    body: JSON.stringify({ detail: 'statistics endpoint failure for isolated regression test' })
  }))
  await keepMapRequestsOutOfApiTests(page)

  await page.goto('/', { waitUntil: 'domcontentloaded' })
  await expect(page.locator('.result-item')).toHaveCount(40, { timeout: 20000 })
  await expect(page.getByText('后端 API 暂不可达')).toHaveCount(0)
  const mobileNav = page.getByRole('tablist', { name: '主要工作区' })
  if (await mobileNav.isVisible()) await mobileNav.getByRole('tab', { name: '更多' }).click()
  await page.getByRole('tab', { name: '景点统计', exact: true }).click()
  await expect(page.locator('.statistics-status.error')).toHaveText('统计数据加载失败')
  expect(pageErrors).toEqual([])
})

test('when all API requests fail, the outage notice and POI error are visible', async ({ page }) => {
  await page.route('**/api/**', route => route.abort('failed'))
  await keepMapRequestsOutOfApiTests(page)

  await page.goto('/', { waitUntil: 'domcontentloaded' })
  await expect(page.getByText('后端 API 暂不可达')).toBeVisible({ timeout: 15000 })
  await expect(page.getByText('无法连接后端服务')).toBeVisible({ timeout: 15000 })
})
