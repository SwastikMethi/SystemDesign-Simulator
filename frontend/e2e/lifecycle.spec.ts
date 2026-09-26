import { test, expect } from '@playwright/test'

test('leaving a pending starter load releases library controls', async ({ page }) => {
  await page.goto('/')
  await expect(page.locator('.challenge-card')).toHaveCount(5)
  let release!: () => void
  let requested!: () => void
  const gate = new Promise<void>(resolve => { release = resolve })
  const seen = new Promise<void>(resolve => { requested = resolve })
  await page.route('**/fixtures/initial', async route => {
    const response = await route.fetch()
    requested()
    await gate
    await route.fulfill({ response })
  })
  await page.locator('.challenge-card').first().getByRole('button', { name: 'Load starter' }).click()
  await seen
  await page.getByRole('button', { name: 'Challenges' }).click()
  await expect(page.locator('.challenge-card').first().getByRole('button', { name: 'Start empty' })).toBeEnabled()
  release()
  await page.locator('.challenge-card').nth(1).getByRole('button', { name: 'Start empty' }).click()
  await expect(page.locator('.workspace-identity h1')).toContainText('URL lookup service')
})

test('failed run and failed save reactivate the previous result', async ({ page }) => {
  test.setTimeout(90_000)
  await page.goto('/')
  await expect(page.locator('.challenge-card')).toHaveCount(5)
  await page.locator('.challenge-card').first().getByRole('button', { name: 'Load starter' }).click()
  await page.getByRole('dialog', { name: 'Getting started' }).getByRole('button', { name: 'Close' }).click()
  await page.getByRole('button', { name: 'Save', exact: true }).click()
  await expect(page.locator('.revision-badge')).toContainText('Saved')
  await page.getByRole('button', { name: 'Preview', exact: true }).click()
  await expect(page.locator('.run-control')).toContainText('preview · completed', { timeout: 60_000 })

  const refreshFetchesResults = async () => {
    const fetched = page.waitForRequest(request => request.method() === 'GET' && /\/api\/v1\/runs\/[^/]+\/results$/.test(request.url()))
    await page.getByRole('button', { name: 'Refresh' }).click()
    await fetched
    await expect(page.locator('.run-control')).toContainText('preview · completed')
  }

  await page.route('**/api/v1/runs', route => route.request().method() === 'POST' ? route.abort('failed') : route.continue())
  await page.getByRole('button', { name: 'Assess design' }).click()
  await expect(page.getByRole('alert')).toContainText('Could not start run')
  await expect(page.locator('.run-control')).toContainText('preview · completed')
  await refreshFetchesResults()
  await page.unroute('**/api/v1/runs')

  await page.getByRole('tab', { name: 'Architecture' }).click()
  const node = page.locator('.lab-node').first()
  const before = await node.boundingBox()
  if (!before) throw new Error('Starter node unavailable')
  await page.mouse.move(before.x + before.width / 2, before.y + before.height / 2)
  await page.mouse.down()
  await page.mouse.move(before.x + before.width / 2 + 45, before.y + before.height / 2 + 25, { steps: 6 })
  await page.mouse.up()
  await expect(page.locator('.revision-badge')).toContainText('Unassessed changes')
  await expect(page.getByRole('button', { name: 'Assess design' })).toBeEnabled()
  await page.route('**/api/v1/designs/*/revisions', route => route.request().method() === 'POST' ? route.abort('failed') : route.continue())
  await page.getByRole('button', { name: 'Assess design' }).click()
  await expect(page.getByRole('alert')).toContainText('Save failed')
  await expect(page.locator('.run-control')).toContainText('preview · completed')
  await refreshFetchesResults()
})
