import { test, expect } from '@playwright/test'

test('simulated basemap failure keeps live POIs usable and retries real tiles', async ({ page }, testInfo) => {
  test.setTimeout(90000)
  let forcedFailures = 0
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
  await page.route('https://tile.openstreetmap.org/**', async route => {
    if (forcedFailures < 1) {
      forcedFailures += 1
      await route.abort('failed')
      return
    }
    await route.continue()
  })

  await page.goto('/', { waitUntil: 'domcontentloaded' })
  await expect(page.locator('.map canvas')).toBeVisible()
  await expect(page.locator('.result-item[data-place-id="1"]')).toBeVisible({ timeout: 30000 })
  await expect(page.getByRole('alert')).toContainText('底图暂时无法加载', { timeout: 20000 })
  await expect(page.getByRole('button', { name: '搜索', exact: true })).toBeEnabled()
  await expect(page.locator('.result-item[data-place-id]').first()).toBeVisible()
  await page.screenshot({ path: testInfo.outputPath('simulated-basemap-failure-pois-usable.png') })

  const successfulBeforeRetry = tileResponses.filter(response => response.status === 200).length
  await page.getByRole('button', { name: '重试底图' }).click()
  await expect.poll(() => tileResponses.filter(response => response.status === 200).length,
    { timeout: 45000 }).toBeGreaterThan(successfulBeforeRetry)
  await expect(page.getByRole('alert')).toHaveCount(0, { timeout: 15000 })
  await page.screenshot({ path: testInfo.outputPath('basemap-recovered-live-tiles.png') })

  expect(forcedFailures).toBe(1)
  expect(tileFailures.some(failure => failure.error !== 'net::ERR_ABORTED')).toBe(true)
  console.log('BASEMAP_FAILURE_RECOVERY', JSON.stringify({
    forcedFailures,
    successfulTiles: tileResponses.filter(response => response.status === 200).length,
    failures: tileFailures
  }))
})
