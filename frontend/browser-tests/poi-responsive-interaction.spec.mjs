import { test, expect } from '@playwright/test'

const viewports = [
  { name: '1920x1080', width: 1920, height: 1080 },
  { name: '1366x768', width: 1366, height: 768 },
  { name: '768x1024', width: 768, height: 1024 },
  { name: '390x844', width: 390, height: 844 }
]

for (const viewport of viewports) {
  test(`real POI search, detail, and route add at ${viewport.name}`, async ({ page }, testInfo) => {
    const pageErrors = []
    page.on('pageerror', error => pageErrors.push(error.message))
    await page.setViewportSize({ width: viewport.width, height: viewport.height })
    // This case verifies real same-origin POI data and responsive interactions;
    // public OSM/glyph availability has a separate, explicitly live integration gate.
    await page.route('https://tile.openstreetmap.org/**', route => route.abort())
    await page.route('https://demotiles.maplibre.org/**', route => route.abort())
    await page.goto('/')
    await expect(page.locator('.map canvas')).toBeVisible({ timeout: 20000 })

    const mobileWorkspaces = page.getByRole('tablist', { name: '主要工作区' })
    if (await mobileWorkspaces.isVisible()) {
      await mobileWorkspaces.getByRole('tab', { name: '探索' }).click()
      const expand = page.getByRole('button', { name: '展开工作面板' })
      if (await expand.isVisible()) await expand.click()
    }

    const search = async query => {
      const placesRequest = page.waitForResponse(response =>
        new URL(response.url()).pathname === '/api/places' &&
        new URL(response.url()).searchParams.get('q') === query &&
        response.request().method() === 'GET' && response.status() === 200
      )
      await page.locator('.search-box').fill(query)
      await page.locator('.search-submit').click()
      return placesRequest
    }

    const broadResponse = await search('南京')
    const broadData = await broadResponse.json()
    expect(broadData.features.length).toBeGreaterThan(1)
    const list = page.locator('.result-list')
    const scrollMetrics = await list.evaluate(element => ({
      overflowY: getComputedStyle(element).overflowY,
      scrollHeight: element.scrollHeight,
      clientHeight: element.clientHeight
    }))
    expect(scrollMetrics.overflowY).toBe('auto')
    const lastResult = page.locator('.result-item').last()
    if (scrollMetrics.scrollHeight > scrollMetrics.clientHeight) {
      await lastResult.scrollIntoViewIfNeeded()
    } else {
      await expect(lastResult).toBeVisible()
    }
    const lastResultHit = await lastResult.evaluate(element => {
      const rect = element.getBoundingClientRect()
      const hit = document.elementFromPoint(rect.left + rect.width / 2, rect.top + rect.height / 2)
      return hit === element || element.contains(hit)
    })
    expect(lastResultHit).toBe(true)

    const response = await search('夫子庙')
    const searchData = await response.json()
    expect(searchData.features.some(feature =>
      feature.properties.id === 2 && feature.properties.name === '夫子庙'
    )).toBe(true)

    const result = page.locator('.result-item').filter({ hasText: '夫子庙' }).first()
    await expect(result).toBeVisible()
    expect(await page.locator('.result-list').evaluate(element => getComputedStyle(element).overflowY)).toBe('auto')
    await result.scrollIntoViewIfNeeded()
    const hitTest = await result.evaluate(element => {
      const rect = element.getBoundingClientRect()
      const x = Math.max(0, Math.min(innerWidth - 1, rect.left + rect.width / 2))
      const y = Math.max(0, Math.min(innerHeight - 1, rect.top + rect.height / 2))
      const hit = document.elementFromPoint(x, y)
      const style = node => {
        if (!node) return null
        const css = getComputedStyle(node)
        const box = node.getBoundingClientRect()
        return {
          tag: node.tagName,
          className: typeof node.className === 'string' ? node.className : '',
          text: node.textContent?.trim().slice(0, 80),
          position: css.position,
          zIndex: css.zIndex,
          pointerEvents: css.pointerEvents,
          rect: { x: box.x, y: box.y, width: box.width, height: box.height }
        }
      }
      return {
        viewport: { width: innerWidth, height: innerHeight },
        result: style(element),
        point: { x, y },
        hit: style(hit),
        isResultTarget: hit === element || element.contains(hit),
        explorer: style(document.querySelector('.explorer-panel')),
        workspace: style(document.querySelector('.workspace-panel')),
        rows: getComputedStyle(document.querySelector('.map-wrapper')).gridTemplateRows,
        documentHeight: document.documentElement.scrollHeight
      }
    })
    await testInfo.attach(`hit-test-${viewport.name}.json`, {
      body: JSON.stringify(hitTest, null, 2),
      contentType: 'application/json'
    })
    console.log(`POI_HIT_TEST ${JSON.stringify(hitTest)}`)
    expect(hitTest.isResultTarget, `POI row center was intercepted at ${viewport.name}`).toBe(true)

    await result.click()
    await expect(page.locator('aside[aria-label="景点详情"] h2')).toHaveText('夫子庙')
    await page.getByRole('button', { name: '加入路线', exact: true }).click()
    await expect(page.locator('.result-item[data-place-id="2"] .route-order-pill')).toContainText('第 1 站')
    await expect(page.locator('.result-item[data-place-id="2"]')).toContainText('夫子庙')
    await page.getByRole('tab', { name: '我的路线', exact: true }).click()
    await expect(page.locator('aside[aria-label="我的路线"]')).toContainText('夫子庙')

    const dimensions = await page.evaluate(() => ({
      viewportWidth: innerWidth,
      documentWidth: document.documentElement.scrollWidth,
      appWidth: document.querySelector('.map-wrapper').clientWidth,
      appScrollWidth: document.querySelector('.map-wrapper').scrollWidth
    }))
    expect(dimensions.documentWidth).toBeLessThanOrEqual(dimensions.viewportWidth + 2)
    expect(dimensions.appScrollWidth).toBeLessThanOrEqual(dimensions.appWidth + 2)
    expect(pageErrors).toEqual([])
    await page.screenshot({ path: testInfo.outputPath(`poi-route-${viewport.name}.png`), fullPage: true })
  })
}
