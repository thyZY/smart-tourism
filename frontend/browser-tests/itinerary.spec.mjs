import { test, expect } from '@playwright/test'

const feature = (id, name) => ({
  type: 'Feature',
  properties: { id, name, category: '历史文化', address: '南京' },
  geometry: { type: 'Point', coordinates: [118.78 + id * .001, 32.04] }
})
const plan = (ids) => ({
  title: '南京历史文化一日游',
  summary: '仅用于离线浏览器验收',
  mode: 'pedestrian',
  planning_method: 'local_rule_fallback',
  stops: ids.map(id => ({ id, name: ({ 1: '总统府', 2: '夫子庙', 3: '中山陵' })[id], category: '历史文化', reason: '当前数据库记录' })),
  selected_places: { type: 'FeatureCollection', features: ids.map(id => feature(id, ({ 1: '总统府', 2: '夫子庙', 3: '中山陵' })[id])) },
  route: { status: 'unavailable' }
})
test.beforeEach(async ({ page }) => {
  await page.route('**/api/places', route => route.fulfill({
    status: 200, contentType: 'application/json',
    body: JSON.stringify({ type: 'FeatureCollection', features: [feature(1, '总统府'), feature(2, '夫子庙'), feature(3, '中山陵')] })
  }))
  await page.route('**/api/ai/itinerary/**', async route => {
    const action = route.request().url()
    if (action.endsWith('/edit-preview')) {
      return route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({
        ...plan([1, 2]), edit_summary: { operation: 'remove', matched_place_id: 3, intent_source: 'deterministic_rule' }
      }) })
    }
    const ids = action.endsWith('/restore') ? route.request().postDataJSON().place_ids : [1, 2, 3]
    return route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(plan(ids)) })
  })
  await page.goto('/e2e-harness.html')
})

test('planning, preview confirmation, and save use real Vue browser events', async ({ page }) => {
  await page.getByRole('button', { name: '生成并加载到地图' }).click()
  await expect(page.getByText('当前行程 · 数据库景点')).toBeVisible()
  await expect(page.getByText('查看完整行程站点（3 站）')).toBeVisible()
  await page.getByRole('button', { name: '修改行程', exact: true }).click()
  await page.getByPlaceholder(/删除中山陵/).fill('删除中山陵')
  await page.getByRole('button', { name: '生成修改预览' }).click()
  await expect(page.getByRole('region', { name: '待确认的行程修改' })).toContainText('总统府 → 夫子庙')
  await expect(page.getByText('查看完整行程站点（3 站）')).toBeVisible()
  await page.getByRole('button', { name: '确认替换当前行程' }).click()
  await expect(page.getByText('查看完整行程站点（2 站）')).toBeVisible()
  await page.getByRole('button', { name: '保存到我的行程' }).click()
  await expect(page.getByText('总统府', { exact: true })).toHaveCount(0) // list remains collapsed
  await expect(page.getByText('南京历史文化一日游 · 2站')).toBeVisible()
  await page.reload()
  await expect(page.getByText('南京历史文化一日游 · 2站')).toBeVisible()
})

test('invalid edit fails without overwriting existing itinerary', async ({ page }) => {
  await page.route('**/api/ai/itinerary/edit-preview', route => route.fulfill({
    status: 422, contentType: 'application/json', body: JSON.stringify({ detail: '不支持的修改要求' })
  }))
  await page.getByRole('button', { name: '生成并加载到地图' }).click()
  await page.getByPlaceholder(/删除中山陵/).fill('帮我安排得轻松一点')
  await page.getByRole('button', { name: '生成修改预览' }).click()
  await expect(page.getByRole('alert')).toContainText('不支持的修改要求')
  await expect(page.getByText('查看完整行程站点（3 站）')).toBeVisible()
  await expect(page.getByRole('region', { name: '待确认的行程修改' })).toHaveCount(0)
})

test('quick navigation is keyboard-accessible and does not overflow screen', async ({ page }) => {
  await page.getByRole('button', { name: '生成并加载到地图' }).click()
  const nav = page.getByRole('navigation', { name: '行程工作台快捷导航' })
  await expect(nav).toBeVisible()
  await expect(nav.getByRole('button', { name: '修改行程' })).toBeVisible()
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth + 2)
  expect(overflow).toBe(false)
})
