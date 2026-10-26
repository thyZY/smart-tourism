import { test, expect } from '@playwright/test'

const viewports = [
  { name: 'phone-390x844', width: 390, height: 844 },
  { name: 'phone-360x800', width: 360, height: 800 },
  { name: 'phone-430x932', width: 430, height: 932 },
  { name: 'phone-landscape-844x390', width: 844, height: 390 },
  { name: 'tablet-768x1024', width: 768, height: 1024 },
  { name: 'desktop-1366x768', width: 1366, height: 768 }
]

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
places.push(...Array.from({ length: 8 }, (_, index) => ({
  type: 'Feature',
  properties: { id: index + 5, name: `测试景点${index + 1}`, category: '测试分类', address: '验收样例' },
  geometry: { type: 'Point', coordinates: [118.78 + index * 0.002, 32.03 + index * 0.001] }
})))

const collection = { type: 'FeatureCollection', features: places }

test.beforeEach(async ({ page }) => {
  await page.route('**/api/places**', route => {
    const query = new URL(route.request().url()).searchParams.get('q')?.trim().toLowerCase()
    const features = query
      ? collection.features.filter(feature => `${feature.properties.name} ${feature.properties.category}`.toLowerCase().includes(query))
      : collection.features
    return route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ type: 'FeatureCollection', features })
    })
  })
  await page.route('**/api/statistics', route => route.fulfill({
    status: 200,
    contentType: 'application/json',
    body: JSON.stringify({ total_places: places.length, category_counts: {}, top_categories: [] })
  }))

  // This file validates UI and navigation with simulated API data. External map requests are
  // deliberately aborted here; real tile/font loading is covered by real-map-road.spec.mjs.
  await page.route('https://tile.openstreetmap.org/**', route => route.abort())
  await page.route('https://demotiles.maplibre.org/**', route => route.abort())
})

test('workspace, selection, and scroll behavior stay usable across responsive viewports', async ({ page }, testInfo) => {
  // This single test cycles six viewport sizes and exercises search, detail, route, and panels.
  test.setTimeout(90000)
  const pageErrors = []
  page.on('pageerror', error => pageErrors.push(error.message))

  for (const viewport of viewports) {
    await page.setViewportSize({ width: viewport.width, height: viewport.height })
    const initialPlacesResponse = page.waitForResponse(response => {
      const url = new URL(response.url())
      return url.pathname === '/api/places' &&
        response.request().method() === 'GET' &&
        !url.searchParams.has('q')
    })
    await page.goto('/full-app-e2e.html', { waitUntil: 'domcontentloaded' })
    const mapCanvas = page.locator('.map canvas')
    await expect(mapCanvas).toBeVisible({ timeout: 20000 })
    await initialPlacesResponse
    await expect(page.locator('.result-item').first()).toBeVisible()

    const isMobileShell = viewport.width <= 1020
    const mobileNav = page.getByRole('tablist', { name: '主要工作区' })
    if (isMobileShell) {
      await expect(mobileNav).toBeVisible()
      await mobileNav.getByRole('tab', { name: '探索' }).click()
    } else {
      await expect(mobileNav).toBeHidden()
    }

    const resultList = page.locator('.result-list')
    await expect(resultList).toBeVisible()
    if (isMobileShell) {
      const targetSizes = await page.evaluate(() => [
        '.search-submit', '.category-button', '.favorite-toggle',
        '.maplibregl-ctrl-zoom-in', '.mobile-sheet-toggle'
      ].map(selector => {
        const element = document.querySelector(selector)
        const rect = element?.getBoundingClientRect()
        return { selector, width: rect?.width ?? 0, height: rect?.height ?? 0 }
      }))
      expect(targetSizes.every(target => target.width >= 44 && target.height >= 44), JSON.stringify(targetSizes)).toBe(true)
    }
    const scrollStyle = await resultList.evaluate(element => ({
      overflowY: getComputedStyle(element).overflowY,
      clientHeight: element.clientHeight,
      scrollHeight: element.scrollHeight
    }))
    expect(scrollStyle.overflowY).toBe('auto')
    if (isMobileShell) expect(scrollStyle.scrollHeight).toBeGreaterThan(scrollStyle.clientHeight)

    const searchResponse = page.waitForResponse(response =>
      new URL(response.url()).pathname === '/api/places' &&
      new URL(response.url()).searchParams.get('q') === '夫子庙'
    )
    await page.locator('.search-box').fill('夫子庙')
    await page.getByRole('button', { name: '搜索', exact: true }).click()
    await searchResponse
    const result = page.locator('.result-item[data-place-id="2"]')
    await expect(result).toContainText('夫子庙')
    await result.scrollIntoViewIfNeeded()
    await result.click()
    await expect(page.locator('aside[aria-label="景点详情"] h2')).toHaveText('夫子庙')
    if (isMobileShell) {
      const closeSize = await page.getByRole('button', { name: '关闭详情' }).evaluate(element => {
        const rect = element.getBoundingClientRect()
        return { width: rect.width, height: rect.height }
      })
      expect(closeSize.width).toBeGreaterThanOrEqual(44)
      expect(closeSize.height).toBeGreaterThanOrEqual(44)
    }
    await page.getByRole('button', { name: '加入路线', exact: true }).click()

    const routeTab = page.getByRole('tab', { name: '我的路线', exact: true })
    await routeTab.click()
    await expect(page.locator('aside[aria-label="我的路线"]')).toContainText('夫子庙')
    await expect(mapCanvas).toBeVisible()
    expect(await mapCanvas.evaluate(element => element.isConnected)).toBe(true)

    if (isMobileShell) {
      await mobileNav.getByRole('tab', { name: '更多' }).click()
      const themeTab = page.getByRole('tab', { name: '主题推荐' })
      await expect(themeTab).toBeVisible()
      await themeTab.click()
      await expect(page.locator('aside[aria-label="推荐主题"]')).toBeVisible()
      for (const [name, panel] of [
        ['文化线路', 'aside[aria-label="文化关联线路"]'],
        ['景点统计', '.statistics-panel'],
        ['空间分析', 'aside[aria-label="旅游资源空间分析"]']
      ]) {
        const tab = page.getByRole('tab', { name, exact: true })
        await expect(tab).toBeVisible()
        await tab.click()
        await expect(page.locator(panel)).toBeVisible()
      }
      await mobileNav.getByRole('tab', { name: 'AI 行程' }).click()
      await expect(page.getByRole('button', { name: '生成并加载到地图' })).toBeVisible()
      await mobileNav.getByRole('tab', { name: '探索' }).click()
      await page.getByRole('button', { name: '收起工作面板' }).click()
      await page.getByRole('button', { name: '展开工作面板' }).click()
    }

    const dimensions = await page.evaluate(() => ({
      viewportWidth: innerWidth,
      documentWidth: document.documentElement.scrollWidth,
      appWidth: document.querySelector('.map-wrapper').clientWidth,
      appScrollWidth: document.querySelector('.map-wrapper').scrollWidth
    }))
    expect(dimensions.documentWidth).toBeLessThanOrEqual(dimensions.viewportWidth + 2)
    expect(dimensions.appScrollWidth).toBeLessThanOrEqual(dimensions.appWidth + 2)
    expect(pageErrors).toEqual([])

    await page.screenshot({
      path: testInfo.outputPath(`mobile-workspace-${viewport.name}.png`),
      fullPage: true
    })
  }
})
