import { test, expect } from '@playwright/test'

test.describe('full-stack itinerary API + Vue', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/e2e-harness.html')
  })

  test('real FastAPI generate -> edit-preview -> explicit confirm', async ({ page }) => {
    const generateResponse = page.waitForResponse(r =>
      r.url().endsWith('/api/ai/itinerary/generate') && r.request().method() === 'POST')
    await page.getByRole('button', { name: '生成并加载到地图' }).click()
    await generateResponse
    await expect(page.getByText('当前行程 · 数据库景点')).toBeVisible()
    await expect(page.getByText('ROAD DISTANCE')).toBeVisible()
    await expect(page.getByText('Valhalla道路')).toHaveCount(0)

    await page.getByRole('button', { name: '修改行程', exact: true }).click()
    await page.getByPlaceholder(/删除中山陵/).fill('删除南京科举博物馆')
    const editResponse = page.waitForResponse(r =>
      r.url().endsWith('/api/ai/itinerary/edit-preview') && r.request().method() === 'POST')
    await page.getByRole('button', { name: '生成修改预览' }).click()
    const response = await editResponse
    expect(response.status()).toBe(200)
    await expect(page.getByRole('region', { name: '待确认的行程修改' })).toContainText('南京总统府 → 夫子庙 → 中华门瓮城')
    await expect(page.getByRole('region', { name: '待确认的行程修改' })).toContainText('确定性规则')

    // Preview must not replace active plan until this click.
    await expect(page.getByText('ROAD DISTANCE')).toBeVisible()
    await page.getByRole('button', { name: '确认替换当前行程' }).click()
    await expect(page.getByRole('region', { name: '待确认的行程修改' })).toHaveCount(0)
    await expect(page.getByText('南京总统府 → 夫子庙 → 中华门瓮城')).toBeVisible()
  })

  test('real FastAPI rejects unsupported edit without changing current plan', async ({ page }) => {
    await page.getByRole('button', { name: '生成并加载到地图' }).click()
    await page.getByPlaceholder(/删除中山陵/).fill('帮我安排得轻松一点')
    const responsePromise = page.waitForResponse(r =>
      r.url().endsWith('/api/ai/itinerary/edit-preview') && r.request().method() === 'POST')
    await page.getByRole('button', { name: '生成修改预览' }).click()
    const response = await responsePromise
    expect(response.status()).toBe(422)
    await expect(page.getByRole('alert')).toContainText('当前支持')
    await expect(page.getByRole('region', { name: '待确认的行程修改' })).toHaveCount(0)
    await expect(page.getByText('当前行程 · 数据库景点')).toBeVisible()
  })

  test('real FastAPI restore revalidates IDs from server data', async ({ page }) => {
    await page.getByRole('button', { name: '生成并加载到地图' }).click()
    await page.getByRole('button', { name: '保存到我的行程' }).click()
    await expect(page.getByText(/南京历史文化·历史文化一日游 · 4站/)).toBeVisible()
    const restoreResponse = page.waitForResponse(r =>
      r.url().endsWith('/api/ai/itinerary/restore') && r.request().method() === 'POST')
    await page.getByRole('button', { name: '恢复并核实' }).click()
    const response = await restoreResponse
    expect(response.status()).toBe(200)
    await expect(page.getByText('已从数据库重新核实 POI，并重新尝试计算道路')).toBeVisible()
  })
})
