import { test, expect, type Page } from '@playwright/test'

async function openStarter(page: Page) {
  await page.goto('/')
  await page.locator('.challenge-card').first().getByRole('button', { name: 'Load starter' }).click()
  await page.getByRole('dialog', { name: 'Getting started' }).getByRole('button', { name: 'Close', exact: true }).click()
}

for (const width of [1440, 1024]) {
  test(`reference preview preserves unsaved edits and undo without AI at ${width}px`, async ({ page }) => {
    await page.setViewportSize({ width, height: 900 })
    await page.route('**/api/v1/health', route => route.fulfill({ json: { status: 'ok', engine_version: 'test', ai_configured: false, ai_model: null } }))
    await openStarter(page)
    await page.getByRole('button', { name: 'Save', exact: true }).click()
    await expect(page.locator('.revision-badge')).toContainText('Saved')
    await page.locator('.lab-node').filter({ hasText: 'Client' }).click()
    await page.getByRole('textbox', { name: 'Name', exact: true }).fill('My edited client')
    const inspectorClose = page.getByRole('complementary', { name: 'Inspector' }).getByRole('button', { name: 'Close', exact: true })
    if (await inspectorClose.isVisible()) await inspectorClose.click()
    const mutations: string[] = []
    page.on('request', request => { if (request.method() === 'POST' && !request.url().endsWith('/validate')) mutations.push(request.url()) })
    await page.getByRole('tab', { name: 'Requirements' }).click()
    const reveal = page.getByRole('button', { name: 'View reference solution', exact: true })
    await expect(reveal).toBeEnabled()
    await reveal.click()
    const preview = page.getByRole('dialog', { name: 'Reference solution' })
    await expect(preview.getByRole('region', { name: 'Reference architecture' })).toBeVisible()
    await expect(preview.locator('.recorded-node')).toHaveCount(3)
    await expect(preview.getByRole('heading', { name: 'How it works' })).toBeVisible()
    await expect(preview.getByRole('heading', { name: 'Components and settings' })).toBeVisible()
    await expect(preview.getByRole('heading', { name: 'Connections' })).toBeVisible()
    await expect(preview.locator('.reference-component').filter({ hasText: 'app.medium.v1' })).toContainText('dependency timeout ms')
    expect(await preview.evaluate(dialog => dialog.scrollWidth <= dialog.clientWidth)).toBe(true)
    await preview.getByRole('button', { name: 'Close', exact: true }).focus()
    await page.keyboard.press('Shift+Tab')
    await expect(preview.locator(':focus')).toHaveCount(1)
    await page.screenshot({ path: `screenshots/reference-answer-${width}.png`, fullPage: false })
    await page.keyboard.press('Escape')
    await expect(preview).not.toBeVisible()
    await expect(reveal).toBeFocused()
    await expect(page.locator('.revision-badge')).toContainText('Unassessed changes')
    await page.getByRole('tab', { name: 'Architecture' }).click()
    await expect(page.locator('.lab-node').filter({ hasText: 'My edited client' })).toBeVisible()
    await page.getByRole('button', { name: 'Undo', exact: true }).click()
    await expect(page.locator('.lab-node').filter({ hasText: 'My edited client' })).toHaveCount(0)
    await page.getByRole('button', { name: 'Redo', exact: true }).click()
    await expect(page.locator('.lab-node').filter({ hasText: 'My edited client' })).toBeVisible()
    expect(mutations).toEqual([])
  })
}

test('walkthrough can preview an answer and resume the same lesson step', async ({ page }) => {
  await page.goto('/')
  await page.getByRole('button', { name: 'Start walkthrough' }).click()
  const guide = page.getByRole('dialog', { name: 'First design guide' })
  await expect(guide).toHaveAttribute('data-step', 'client')
  await guide.getByRole('button', { name: 'Skip guide' }).click()
  await page.getByRole('tab', { name: 'Requirements' }).click()
  await page.getByRole('button', { name: 'View reference solution', exact: true }).click()
  const preview = page.getByRole('dialog', { name: 'Reference solution' })
  await expect(preview).toContainText('sql.medium.v1')
  await preview.getByRole('button', { name: 'Close', exact: true }).click()
  await page.getByRole('tab', { name: 'Architecture' }).click()
  await expect(page.locator('.lab-node')).toHaveCount(0)
  await page.getByRole('button', { name: 'Resume guide', exact: true }).click()
  await expect(guide).toHaveAttribute('data-step', 'client')
})

test('answer actions retain hint context through provider failure and reference preview', async ({ page }) => {
  const question = 'Where should an update go before it is acknowledged?'
  const explanation = 'Write to SQL before acknowledging the update.'
  const requests: Record<string, unknown>[] = []
  const records: Record<string, object> = {}
  let answerAttempts = 0
  await page.route('**/api/v1/health', route => route.fulfill({ json: { status: 'ok', engine_version: 'test', ai_configured: true, ai_model: 'test' } }))
  await page.route('**/api/v1/designs/*/guidance', async route => {
    const body = route.request().postDataJSON()
    requests.push(body)
    const id = `guidance-${requests.length}`
    const failed = body.mode === 'answer' && ++answerAttempts === 1
    records[id] = { ...body, guidance_id: id, design_id: route.request().url().split('/').at(-2), status: failed ? 'failed' : 'completed', question: body.mode === 'hint' ? question : null, explanation: body.mode === 'hint' || failed ? null : explanation, error: failed ? 'Provider temporarily unavailable' : null, validation_errors: failed ? ['Provider temporarily unavailable'] : [], authored_refs: [], created_at: new Date().toISOString() }
    await route.fulfill({ status: 202, json: { guidance_id: id, status: 'queued' } })
  })
  await page.route('**/api/v1/designs/*/guidance/*', route => route.fulfill({ json: records[route.request().url().split('/').at(-1)!] }))
  await openStarter(page)
  await page.getByRole('button', { name: 'AI coach', exact: true }).click()
  const coach = page.getByRole('dialog', { name: 'AI coach guidance' })
  await expect(coach.getByRole('button', { name: 'Answer', exact: true })).toBeVisible()
  await coach.getByRole('textbox', { name: 'Focus (optional)' }).fill('persistence')
  await coach.getByRole('button', { name: 'Ask for hint' }).click()
  await expect(coach.getByText(question, { exact: true })).toBeVisible()
  const reveal = coach.getByRole('button', { name: 'View reference solution', exact: true })
  let firstPreview = true
  await page.route('**/api/v1/challenges/*/reference', async route => {
    if (firstPreview) { firstPreview = false; await route.fulfill({ status: 503, json: { message: 'Reference temporarily unavailable' } }) }
    else await route.continue()
  })
  await reveal.click()
  const preview = page.getByRole('dialog', { name: 'Reference solution' })
  await expect(preview.getByRole('alert')).toContainText('Reference temporarily unavailable')
  await preview.getByRole('button', { name: 'Retry', exact: true }).click()
  await expect(preview.locator('.recorded-node')).toHaveCount(3)
  await page.keyboard.press('Escape')
  await expect(reveal).toBeFocused()
  await expect(coach.getByText(question, { exact: true })).toBeVisible()
  await coach.getByRole('button', { name: 'Show answer', exact: true }).click()
  await expect(coach.getByText('Provider temporarily unavailable', { exact: true })).toHaveCount(1)
  await expect(coach.getByText(question, { exact: true })).toBeVisible()
  await coach.getByRole('button', { name: 'Show answer', exact: true }).click()
  await expect(coach.getByRole('heading', { name: 'Answer', exact: true })).toBeVisible()
  await expect(coach.getByText(explanation, { exact: true })).toBeVisible()
  expect(requests[1]).toMatchObject({ mode: 'answer', source_guidance_id: 'guidance-1', focus: 'persistence', evidence_step: false, consent: true })
  expect(requests[2]).toEqual(requests[1])
  await coach.getByRole('button', { name: 'Answer', exact: true }).click()
  await coach.getByRole('textbox', { name: 'Focus (optional)' }).fill('the request flow')
  await coach.getByRole('button', { name: 'Show answer', exact: true }).click()
  await expect(coach.getByText(explanation, { exact: true })).toBeVisible()
  expect(requests[3]).toMatchObject({ mode: 'answer', source_guidance_id: null, focus: 'the request flow' })
})
