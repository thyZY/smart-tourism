import { test, expect } from '@playwright/test'

const pois = [
  [1, '南京总统府', '历史文化', 118.7969, 32.0480],
  [2, '夫子庙', '历史文化', 118.7897, 32.0208],
  [3, '中华门瓮城', '古迹遗址', 118.7838, 32.0112],
  [4, '南京科举博物馆', '博物馆', 118.7880, 32.0212]
].map(([id, name, category, lng, lat]) => ({
  type: 'Feature',
  properties: { id, name, category, address: '南京市' },
  geometry: { type: 'Point', coordinates: [lng, lat] }
}))

const collection = () => ({ type: 'FeatureCollection', features: pois })

test.beforeEach(async ({ page }) => {
  await page.route('**/api/places**', route =>
    route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(collection()) })
  )
  await page.route('**/api/places/nearby**', route =>
    route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(collection()) })
  )
  await page.route('**/api/ai/itinerary/road', route =>
    route.fulfill({
      status: 200, contentType: 'application/json',
      body: JSON.stringify({
        status: 'verified_by_routing_service',
        provider: 'Valhalla',
        mode: 'pedestrian',
        distance_km: 3.7,
        duration_minutes: 26.5,
        optimized: false,
        geojson: {
          type: 'FeatureCollection',
          features: [{
            type: 'Feature', properties: {},
            geometry: { type: 'LineString', coordinates: pois.slice(0, 4).map(p => p.geometry.coordinates) }
          }]
        }
      })
    })
  )
  // Map rendering is still real MapLibre; external tile/font requests are outside this test's scope.
  await page.route('https://tile.openstreetmap.org/**', route => route.abort())
  await page.route('https://demotiles.maplibre.org/**', route => route.abort())
  await page.goto('/full-app-e2e.html')
  await expect(page.locator('.map canvas')).toBeVisible({ timeout: 15000 })
})

test('complete map + AI itinerary + route workspace flow', async ({ page }) => {
  await expect(page.getByRole('button', { name: '生成并加载到地图' })).toBeEnabled({ timeout: 15000 })
  await page.getByRole('button', { name: '生成并加载到地图' }).click()
  await expect(page.getByText('当前行程 · 数据库景点')).toBeVisible({ timeout: 15000 })
  await expect(page.locator('.map-route-status')).toContainText('Valhalla')
  await expect(page.getByRole('tab', { name: '我的路线', exact: true })).toBeVisible()

  await page.getByRole('tab', { name: '我的路线', exact: true }).click()
  await expect(page.locator('aside[aria-label="我的路线"]')).toBeVisible()
  await expect(page.getByText('路网已计算')).toBeVisible()
  await expect(page.getByText('ROAD DISTANCE')).toBeVisible()

  const road = page.waitForResponse(r =>
    r.url().endsWith('/api/ai/itinerary/road') && r.request().method() === 'POST')
  await page.getByRole('button', { name: '计算实际道路路线' }).click()
  expect((await road).status()).toBe(200)
  await expect(page.getByText('预计交通：')).toBeVisible()
  await expect(page.getByText(/26.5/)).toBeVisible()

  await page.getByRole('tab', { name: 'AI 行程', exact: true }).click()
  await expect(page.getByRole('navigation', { name: '行程工作台快捷导航' })).toBeVisible()
  await expect(page.locator('.map canvas')).toBeVisible()
})

test('manual POI route edit invalidates stale AI state while map remains usable', async ({ page }) => {
  await page.getByRole('button', { name: '生成并加载到地图' }).click()
  await expect(page.getByText('当前行程 · 数据库景点')).toBeVisible({ timeout: 15000 })
  await expect(page.getByRole('navigation', { name: '行程工作台快捷导航' })).toBeVisible()

  await page.locator('.result-item[data-place-id]').first().click()
  await expect(page.locator('aside[aria-label="景点详情"]')).toBeVisible()
  await expect(page.getByRole('button', { name: '移出路线' })).toBeVisible()
  await page.getByRole('button', { name: '移出路线' }).click()

  // A manual route edit invalidates the stale AI plan, but the MapLibre map remains mounted.
  await page.getByRole('tab', { name: 'AI 行程', exact: true }).click()
  await expect(page.getByText('地图路线已被手动修改；旧AI方案已失效')).toBeVisible()
  await expect(page.getByRole('navigation', { name: '行程工作台快捷导航' })).toHaveCount(0)
  await expect(page.locator('.map canvas')).toBeVisible()
})

test('desktop and narrow layout keep the main map inside viewport', async ({ page }) => {
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth + 2)
  expect(overflow).toBe(false)
  await page.setViewportSize({ width: 390, height: 844 })
  await page.reload()
  await expect(page.locator('.map canvas')).toBeVisible({ timeout: 15000 })
  const mobileOverflow = await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth + 2)
  expect(mobileOverflow).toBe(false)
})
