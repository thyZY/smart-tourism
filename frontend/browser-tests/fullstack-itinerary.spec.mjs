import { test, expect } from '@playwright/test'

async function currentPlanSnapshot(page) {
  const workspace = page.getByRole('region', { name: 'AI 行程工作台' })
  const result = workspace.locator('.ai-results')
  const stopsDisclosure = result.locator('.ai-stops-disclosure')
  if (!(await stopsDisclosure.evaluate(details => details.open))) {
    await stopsDisclosure.locator('summary').click()
  }
  return {
    title: await result.locator('h4').first().innerText(),
    stops: (await result.locator('.ai-stops-disclosure ol li').allTextContents())
      .map(text => text.split(' · ')[0].trim()),
    route: await result.locator('p').filter({ hasText: /Valhalla道路：|道路未核验；地图直线只作景点顺序预览/ }).innerText()
  }
}

test.describe('full-stack itinerary API + Vue', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/e2e-harness.html')
  })

  test('real FastAPI generate -> edit-preview -> explicit confirm', async ({ page }) => {
    const generateResponse = page.waitForResponse(r =>
      r.url().endsWith('/api/ai/itinerary/generate') && r.request().method() === 'POST')
    await page.getByRole('button', { name: '生成并加载到地图' }).click()
    const generatedResponse = await generateResponse
    expect(generatedResponse.status()).toBe(200)
    const plan = await generatedResponse.json()
    const workspace = page.getByRole('region', { name: 'AI 行程工作台' })
    await expect(workspace).toBeVisible()
    await expect(workspace.getByText('当前行程 · 数据库景点')).toBeVisible()
    await expect(workspace.locator('.ai-results')).toContainText(
      plan.route?.status === 'verified_by_routing_service' ? 'Valhalla道路：' : '道路未核验；地图直线只作景点顺序预览'
    )
    expect(plan.stops.length).toBeGreaterThanOrEqual(3)
    const planBeforePreview = await currentPlanSnapshot(page)
    const removedStop = plan.stops.at(-1)
    const expectedPreviewStops = plan.stops.slice(0, -1).map(stop => stop.name).join(' → ')

    await page.getByRole('button', { name: '修改行程', exact: true }).click()
    await page.getByPlaceholder(/删除中山陵/).fill(`删除${removedStop.name}`)
    const editResponse = page.waitForResponse(r =>
      r.url().endsWith('/api/ai/itinerary/edit-preview') && r.request().method() === 'POST')
    await page.getByRole('button', { name: '生成修改预览' }).click()
    const response = await editResponse
    expect(response.status()).toBe(200)
    await expect(page.getByRole('region', { name: '待确认的行程修改' })).toContainText(expectedPreviewStops)
    await expect(page.getByRole('region', { name: '待确认的行程修改' })).toContainText('确定性规则')

    // Preview must not replace the visible current itinerary until confirmation.
    expect(await currentPlanSnapshot(page)).toEqual(planBeforePreview)
    await page.getByRole('button', { name: '确认替换当前行程' }).click()
    await expect(page.getByRole('region', { name: '待确认的行程修改' })).toHaveCount(0)
    const confirmedPlan = await currentPlanSnapshot(page)
    expect(confirmedPlan.stops).toEqual(plan.stops.slice(0, -1).map(stop => stop.name))
  })

  test('real FastAPI rejects unsupported edit without changing current plan', async ({ page }) => {
    const generation = page.waitForResponse(r =>
      r.url().endsWith('/api/ai/itinerary/generate') && r.request().method() === 'POST')
    await page.getByRole('button', { name: '生成并加载到地图' }).click()
    const generated = await generation
    expect(generated.status()).toBe(200)
    const planBeforeEdit = await currentPlanSnapshot(page)
    await page.getByPlaceholder(/删除中山陵/).fill('帮我安排得轻松一点')
    const responsePromise = page.waitForResponse(r =>
      r.url().endsWith('/api/ai/itinerary/edit-preview') && r.request().method() === 'POST')
    await page.getByRole('button', { name: '生成修改预览' }).click()
    const response = await responsePromise
    expect(response.status()).toBe(422)
    const errorBody = await response.json()
    expect(typeof errorBody.detail).toBe('string')
    expect(errorBody.detail.trim().length).toBeGreaterThan(0)
    await expect(page.getByRole('alert')).toHaveText(errorBody.detail)
    await expect(page.getByRole('region', { name: '待确认的行程修改' })).toHaveCount(0)
    await expect(page.getByText('当前行程 · 数据库景点')).toBeVisible()
    expect(await currentPlanSnapshot(page)).toEqual(planBeforeEdit)
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
