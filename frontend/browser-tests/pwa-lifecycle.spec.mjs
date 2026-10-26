import { test, expect } from '@playwright/test'
import { readFile, writeFile } from 'node:fs/promises'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const frontendRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const builtWorkerPath = path.join(frontendRoot, 'dist', 'sw.js')
let apiMode = 'available'
let originalWorkerSource = null

const places = {
  type: 'FeatureCollection',
  features: [{
    type: 'Feature',
    properties: { id: 2, name: '夫子庙', category: '历史文化', address: '南京市' },
    geometry: { type: 'Point', coordinates: [118.7877, 32.027] }
  }]
}

test.beforeEach(async ({ page }) => {
  apiMode = 'available'
  await page.route('**/api/places**', route => apiMode === 'unavailable'
    ? route.abort('failed')
    : route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(places) }))
  await page.route('**/api/statistics', route => apiMode === 'unavailable'
    ? route.abort('failed')
    : route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ total_places: 1, category_counts: {} }) }))
  // External tiles and glyphs are intentionally isolated in this app-shell test.
  // Real map resource verification remains in real-map-road.spec.mjs.
  await page.route('https://tile.openstreetmap.org/**', route => route.abort())
  await page.route('https://demotiles.maplibre.org/**', route => route.abort())
})

test.afterEach(async ({ context }) => {
  await context.setOffline(false)
  await Promise.all(context.pages().map(page => page.evaluate(async () => {
    const registrations = await navigator.serviceWorker.getRegistrations()
    await Promise.all(registrations.map(registration => registration.unregister()))

    const cacheNames = (await caches.keys()).filter(name => name.startsWith('smart-tourism-shell-'))
    await Promise.all(cacheNames.map(name => caches.delete(name)))
  })))
  if (originalWorkerSource !== null) {
    await writeFile(builtWorkerPath, originalWorkerSource, 'utf8')
    originalWorkerSource = null
  }
})

async function waitForServiceWorker(page) {
  await page.evaluate(async () => {
    await navigator.serviceWorker.ready
    if (!navigator.serviceWorker.controller) {
      await new Promise(resolve => navigator.serviceWorker.addEventListener('controllerchange', resolve, { once: true }))
    }
  })
}

test('manifest icons load and production shell works offline without caching API responses', async ({ page, context }) => {
  const manifestResponse = await page.request.get('/manifest.webmanifest')
  expect(manifestResponse.status()).toBe(200)
  const manifest = await manifestResponse.json()
  expect(manifest).toMatchObject({
    name: '南京智慧文旅',
    short_name: '智慧文旅',
    start_url: '/',
    scope: '/',
    display: 'standalone',
    theme_color: '#215fc5'
  })
  for (const expectedSize of ['192x192', '512x512']) {
    const icon = manifest.icons.find(candidate => candidate.sizes === expectedSize)
    expect(icon?.type).toBe('image/png')
    const response = await page.request.get(icon.src)
    expect(response.status()).toBe(200)
    const dimensions = await page.evaluate(async src => {
      const image = new Image()
      image.src = new URL(src, 'http://127.0.0.1:4173').href
      await image.decode()
      return { width: image.naturalWidth, height: image.naturalHeight }
    }, icon.src)
    expect(dimensions.width).toBe(Number(expectedSize.split('x')[0]))
    expect(dimensions.height).toBe(Number(expectedSize.split('x')[1]))
  }

  await page.goto('/')
  await expect(page.getByRole('banner', { name: '智慧文旅地图工具栏' })).toBeVisible()
  await waitForServiceWorker(page)
  await page.reload()

  const shellCache = await page.evaluate(async () => {
    const names = (await caches.keys()).filter(name => name.startsWith('smart-tourism-shell-'))
    const entries = await Promise.all(names.map(async name =>
      (await caches.open(name)).keys().then(requests => requests.map(request => new URL(request.url).pathname))))
    return { names, entries: entries.flat() }
  })
  expect(shellCache.names.length).toBeGreaterThan(0)
  expect(shellCache.entries.some(entry => entry.startsWith('/assets/'))).toBe(true)
  expect(shellCache.entries).not.toContain('/api/places')
  expect(shellCache.entries.some(entry => entry.startsWith('/api/'))).toBe(false)
  expect(shellCache.entries.some(entry => entry.includes('tile.openstreetmap.org'))).toBe(false)

  apiMode = 'unavailable'
  await page.getByLabel('搜索景点').fill('夫子庙')
  await page.getByRole('button', { name: '搜索', exact: true }).click()
  await expect(page.locator('.pwa-status-message.is-api-unavailable')).toBeVisible()

  apiMode = 'unavailable'
  await context.setOffline(true)
  await page.reload()
  await expect(page.getByRole('banner', { name: '智慧文旅地图工具栏' })).toBeVisible()
  await expect(page.getByText('网络已断开。应用外壳可用；POI、路线和 AI 行程需要联网。')).toBeVisible()

  apiMode = 'available'
  await context.setOffline(false)
  const responsePromise = page.waitForResponse(response =>
    new URL(response.url()).pathname === '/api/places' && response.status() === 200)
  await page.getByLabel('搜索景点').fill('夫子庙')
  await page.getByRole('button', { name: '搜索', exact: true }).click()
  await responsePromise
  await expect(page.locator('.result-list')).toContainText('夫子庙')
  await expect(page.locator('.pwa-status-message.is-api-unavailable')).toHaveCount(0)
  await page.screenshot({ path: test.info().outputPath('pwa-online-recovered.png'), fullPage: true })
})

async function stageUpdatedWorker(page) {
  const workerSource = await readFile(builtWorkerPath, 'utf8')
  originalWorkerSource = workerSource
  const updatedSource = workerSource.replace(
    /smart-tourism-shell-[a-f0-9]{12}/,
    'smart-tourism-shell-update-test'
  )
  expect(updatedSource).not.toBe(workerSource)
  await writeFile(builtWorkerPath, updatedSource, 'utf8')
  await page.evaluate(async () => {
    const registration = await navigator.serviceWorker.getRegistration('/')
    await registration.update()
  })
  const updateNotice = page.getByRole('status').filter({ hasText: '发现新版本' })
  await expect(updateNotice).toBeVisible({ timeout: 15000 })
  return updateNotice
}

test('new worker is detected and can be deferred without interrupting the current app', async ({ page }) => {
  await page.goto('/')
  await waitForServiceWorker(page)
  const updateNotice = await stageUpdatedWorker(page)
  await page.getByRole('button', { name: '稍后' }).click()
  await expect(updateNotice).toHaveCount(0)
  await expect(page.getByRole('banner', { name: '智慧文旅地图工具栏' })).toBeVisible()
})

test('user-approved worker update reloads all controlled tabs without mixing versions', async ({ page, context }) => {
  await page.goto('/')
  await waitForServiceWorker(page)

  const secondPage = await context.newPage()
  await secondPage.addInitScript(() => {
    const count = Number(sessionStorage.getItem('pwa-reload-count') ?? '0')
    sessionStorage.setItem('pwa-reload-count', String(count + 1))
  })
  await secondPage.goto('/')
  await waitForServiceWorker(secondPage)
  await expect.poll(() => secondPage.evaluate(() => sessionStorage.getItem('pwa-reload-count'))).toBe('1')

  await stageUpdatedWorker(page)
  const secondTabNotice = secondPage.getByRole('status').filter({ hasText: '发现新版本' })
  await expect(secondTabNotice).toBeVisible()
  await secondPage.getByRole('button', { name: '稍后' }).click()

  const secondTabReloaded = secondPage.waitForFunction(() =>
    sessionStorage.getItem('pwa-reload-count') === '2'
  )
  await page.getByRole('button', { name: '立即更新' }).click()
  await expect(page.getByRole('banner', { name: '智慧文旅地图工具栏' })).toBeVisible({ timeout: 15000 })
  await expect.poll(() => page.evaluate(() => Boolean(navigator.serviceWorker.controller))).toBe(true)
  await secondTabReloaded
  await expect(secondPage.getByRole('banner', { name: '智慧文旅地图工具栏' })).toBeVisible()
  await page.screenshot({ path: test.info().outputPath('pwa-after-worker-update.png'), fullPage: true })
})
