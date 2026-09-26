import { test, expect, type Locator, type Page } from '@playwright/test'
import type { Case, Challenge, Comparison, Design, Run, Snapshot } from '../src/api/client'

const gate = () => {
  let release!: () => void, requested!: () => void
  const wait = new Promise<void>(resolve => { release = resolve })
  const seen = new Promise<void>(resolve => { requested = resolve })
  return { wait, seen, release, requested }
}

// Real catalogue/design endpoints with controlled recorded responses isolate child races.
// The journey tests separately execute the full real simulation/comparison.
async function recordedWorkspace(page: Page) {
  const challenge: Challenge = await (await page.request.get('/api/v1/challenges/product-catalogue')).json()
  const fixture: Design = await (await page.request.get('/api/v1/challenges/product-catalogue/fixtures/initial')).json()
  const operation = challenge.operations[0].id
  const freshness = challenge.requirements.find(req => req.metric === 'freshness_violation_rate')!
  const cases: Case[] = ['steady', 'burst'].map((scenario, index) => {
    const id = `${scenario}-${101 + index}`
    const evidenceId = `${id}:${freshness.id}:${operation}`
    return { case_id: id, scenario_id: scenario, seed: 101 + index, execution_status: 'completed', node_metrics: {}, operation_metrics: { [operation]: { response_p95_ms: { value: 222, unit: 'ms', sample_count: 100, unavailable_reason: null } } }, trace_refs: ['trace:warmup-error', 'trace:violation', 'trace:later'], evidence: [
      { evidence_id: `${id}:latency`, type: 'response_p95_ms', value: 222, unit: 'ms', scope: scenario, sample_count: 100, artifact_ref: `case:${id}:window:60000000:360000000` },
      { evidence_id: evidenceId, type: 'freshness_violation_rate', value: 0.2, unit: 'fraction', scope: scenario, sample_count: 100, artifact_ref: `case:${id}:window:60000000:360000000` },
      { evidence_id: `${evidenceId}:first`, type: 'first_violation', value: 'violation', unit: 'request', scope: scenario, sample_count: 1, artifact_ref: 'trace:violation' },
    ], requirement_outcomes: challenge.requirements.map(req => ({ requirement_id: req.id, scenario_id: scenario, seed: 101 + index, operation_id: operation, status: req.id === freshness.id || (index === 1 && req.id === 'R02') ? 'fail' : 'pass', measured: { value: 0.2, unit: 'fraction', sample_count: 100, unavailable_reason: null }, evidence_ids: req.id === freshness.id ? [evidenceId, `${evidenceId}:first`] : req.id === 'R02' ? [`${id}:latency`] : [] })) }
  })
  let run = { run_id: 'ui-baseline', mode: 'assessment', execution_status: 'completed', assessment_status: 'fail', challenge_id: challenge.challenge_id, challenge_version: challenge.version, case_ids: cases.map(c => c.case_id), completed_case_ids: cases.map(c => c.case_id), workload_bundle_id: 'ui-bundle' } as Run
  const snapshots = (index: number): { items: Snapshot[] } => ({ items: [0, 360_000_000].map(time_us => ({ time_us, nodes: { app: { queue_depth: index ? 222 : 111, busy_slots: 0, available_slots: 4 } }, edges: {} })) })
  await page.route('**/api/v1/runs', async route => {
    if (route.request().method() !== 'POST') return route.continue()
    run = { ...run, ...route.request().postDataJSON(), run_id: 'ui-baseline' }
    await route.fulfill({ status: 202, json: { run_id: run.run_id } })
  })
  await page.route('**/api/v1/runs/ui-baseline', route => route.fulfill({ json: run }))
  await page.route('**/api/v1/runs/ui-baseline/results', route => route.fulfill({ json: { cases, assessment: null } }))
  await page.route('**/api/v1/runs/ui-baseline/cases/*/snapshots', route => route.fulfill({ json: snapshots(route.request().url().includes(cases[1].case_id) ? 1 : 0) }))
  await page.route('**/api/v1/runs/ui-baseline/cases/*/traces/*', route => {
    const trace_id = decodeURIComponent(route.request().url().split('/').at(-1)!)
    return route.fulfill({ json: { trace_id, request_id: trace_id.slice(6), operation_id: operation, events: [{ time_us: 70_000_000, event: 'returned', node_id: 'app', edge_id: null, attempt: 0, job_id: null, details: { status: 'success', fresh: false } }] } })
  })
  await page.goto('/')
  await page.locator('.challenge-card').nth(2).getByRole('button', { name: 'Load starter' }).click()
  await page.getByRole('dialog', { name: 'Getting started' }).getByRole('button', { name: 'Close' }).click()
  await expect(page.getByRole('button', { name: 'Guide', exact: true })).toBeFocused()
  await page.getByRole('button', { name: 'Assess design' }).click()
  await expect(page.locator('.run-control')).toContainText('assessment · completed')
  return { run, cases, fixture, snapshots }
}

test('results retain complete operation measurements and usable controls at narrow widths', async ({ page }) => {
  await recordedWorkspace(page)
  await page.getByRole('button', { name: 'Jump to first failure' }).click()
  for (const width of [1440, 1024, 390]) {
    await page.setViewportSize({ width, height: width === 1440 ? 900 : 844 })
    await page.getByRole('button', { name: 'Jump to first failure' }).scrollIntoViewIfNeeded()
    await expect(page.getByRole('button', { name: 'Jump to first failure' })).toBeInViewport()
    await expect.poll(() => page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(width)
    const metrics = page.locator('details').filter({ has: page.locator('summary', { hasText: 'Operation metrics' }) })
    await expect(metrics.locator('summary')).toBeVisible({ timeout: 3000 })
    await metrics.locator('summary').click()
    const table = page.getByRole('table', { name: 'Operation measurements' })
    await expect(table).toBeVisible()
    const measurement = table.getByRole('row').filter({ hasText: /response p95 ms/i })
    await expect(measurement).toContainText('read_product')
    await expect(measurement).toContainText('222 ms')
    await expect(measurement).toContainText('100')
    await metrics.locator('summary').click()
    await page.screenshot({ path: `screenshots/redesign-results-${width}.png`, fullPage: true })
  }
})

test('saved first-violation references and within-workspace replay requests stay aligned', async ({ page }) => {
  const { cases, snapshots } = await recordedWorkspace(page)
  await page.getByRole('button', { name: 'Jump to first failure' }).click()
  await expect(page.getByRole('combobox', { name: 'Trace', exact: true })).toHaveValue('trace:violation')
  await expect(page.locator('.trace-section')).toContainText('request violation')
  const delayedSnapshot = gate()
  await page.route(`**/cases/${cases[0].case_id}/snapshots`, async route => {
    delayedSnapshot.requested(); await delayedSnapshot.wait
    await route.fulfill({ json: snapshots(0) })
  })
  const selectCase = page.getByLabel('Scenario and seed')
  await selectCase.selectOption(cases[1].case_id)
  await selectCase.selectOption(cases[0].case_id)
  await delayedSnapshot.seen
  await expect(page.locator('.recorded-counters')).toHaveCount(0)
  await selectCase.selectOption(cases[1].case_id)
  await expect(page.locator('.recorded-counters')).toContainText('Queue 222')
  delayedSnapshot.release()
  const delayedTrace = gate()
  await page.route(`**/cases/${cases[1].case_id}/traces/trace%3Aviolation`, async route => {
    delayedTrace.requested(); await delayedTrace.wait
    await route.fulfill({ json: { trace_id: 'trace:violation', request_id: 'violation', operation_id: 'read_product', events: [{ time_us: 71_000_000, event: 'returned', node_id: 'app', details: {} }] } })
  })
  await page.getByRole('combobox', { name: 'Trace', exact: true }).selectOption('trace:violation')
  await delayedTrace.seen
  await page.getByRole('combobox', { name: 'Trace', exact: true }).selectOption('trace:later')
  await expect(page.locator('.trace-section')).toContainText('request later')
  delayedTrace.release()
  await page.waitForTimeout(100)
  await expect(page.locator('.trace-section')).toContainText('request later')
  await expect(page.locator('.recorded-counters')).toContainText('Queue 222')
  await expect(selectCase).toHaveValue(cases[1].case_id)
  await page.getByRole('row').filter({ hasText: 'R02' }).getByRole('button', { name: 'Inspect evidence' }).click()
  await expect(page.locator('.evidence-section')).toContainText('Recorded calculation window: 60–360 s')
  await expect(page.getByRole('combobox', { name: 'Trace', exact: true })).toHaveValue('')
  await expect(page.getByRole('slider', { name: 'Replay position' })).toHaveValue('60000000')
  await page.getByRole('button', { name: 'Jump to first failure' }).click()
  await expect(selectCase).toHaveValue(cases[0].case_id)
  await expect(page.getByRole('combobox', { name: 'Trace', exact: true })).toHaveValue('trace:violation')
  await expect(page.locator('.trace-section')).toContainText('request violation')
})

test('successive comparisons and delayed candidate revisions and snapshots keep the current identity', async ({ page }) => {
  const { run, fixture, cases, snapshots } = await recordedWorkspace(page)
  const candidates: Design[] = []
  for (const name of ['Candidate A', 'Candidate B']) {
    const response = await page.request.post('/api/v1/designs', { data: { challenge_id: fixture.challenge_id, challenge_version: fixture.challenge_version, nodes: fixture.nodes.map(node => node.id === 'app' ? { ...node, label: name, instance_count: 2 } : node), edges: fixture.edges } })
    candidates.push((await response.json()).revision)
  }
  const delayedPoll = gate(), delayedRevision = gate(), delayedSnapshot = gate(), delayedScenario = gate()
  let starts = 0, oldReads = 0
  const old = { comparison_id: 'comparison-old', baseline_run_id: run.run_id, status: 'running', candidate_run_ids: [], differences: [], rejected_candidates: [], objective: 'old comparison' } as unknown as Comparison
  const current = { ...old, comparison_id: 'comparison-current', status: 'completed', candidate_run_ids: ['ui-candidate-a', 'ui-candidate-b'], differences: [{ assessment_status: 'fail' }, { assessment_status: 'pass' }], objective: 'current comparison' }
  await page.route('**/api/v1/comparisons', route => route.fulfill({ status: 202, json: { comparison_id: ++starts === 1 ? old.comparison_id : current.comparison_id } }))
  await page.route('**/api/v1/comparisons/comparison-old', async route => {
    if (++oldReads === 1) return route.fulfill({ json: old })
    delayedPoll.requested(); await delayedPoll.wait
    await route.fulfill({ json: { ...old, status: 'completed', error: 'obsolete comparison response' } })
  })
  await page.route('**/api/v1/comparisons/comparison-current', route => route.fulfill({ json: current }))
  for (const [index, id] of current.candidate_run_ids.entries()) {
    await page.route(`**/api/v1/runs/${id}`, route => route.fulfill({ json: { ...run, run_id: id, design_id: candidates[index].design_id, revision_id: candidates[index].revision_id } }))
    await page.route(`**/api/v1/runs/${id}/results`, route => route.fulfill({ json: { cases, assessment: null } }))
    await page.route(`**/api/v1/runs/${id}/cases/*/snapshots`, async route => {
      if (!route.request().url().includes(cases[1].case_id)) {
        const delayed = index ? delayedScenario : delayedSnapshot
        delayed.requested(); await delayed.wait
      }
      await route.fulfill({ json: snapshots(route.request().url().includes(cases[1].case_id) ? 1 : 0) })
    })
  }
  await page.route(`**/api/v1/designs/${candidates[0].design_id}/revisions/${candidates[0].revision_id}`, async route => {
    const response = await route.fetch()
    delayedRevision.requested(); await delayedRevision.wait
    await route.fulfill({ response })
  })
  await page.getByRole('tab', { name: 'Compare' }).click()
  await page.locator('.candidate-list label').filter({ hasText: candidates[0].revision_id.slice(0, 12) }).getByRole('checkbox').check()
  await page.getByRole('button', { name: 'Run comparison' }).click()
  await delayedPoll.seen
  await page.getByRole('button', { name: 'Run comparison' }).click()
  await expect(page.locator('.comparison-result')).toContainText('current comparison')
  await delayedRevision.seen
  await delayedSnapshot.seen
  await page.getByRole('combobox', { name: 'Candidate', exact: true }).selectOption('1')
  await delayedScenario.seen
  await expect(page.locator('.comparison-graph .recorded-legend')).toContainText(candidates[1].revision_id)
  await page.locator('.comparison-result').getByRole('combobox', { name: 'Scenario', exact: true }).selectOption(`${cases[1].scenario_id} · seed ${cases[1].seed}`)
  await expect(page.locator('.comparison-graph .recorded-counters')).toContainText('Queue 222')
  delayedPoll.release(); delayedRevision.release(); delayedSnapshot.release(); delayedScenario.release()
  await page.waitForTimeout(100)
  await expect(page.locator('.comparison-result')).toContainText('current comparison')
  await expect(page.locator('.comparison-result')).not.toContainText('obsolete comparison response')
  await expect(page.getByRole('combobox', { name: 'Candidate', exact: true })).toHaveValue('1')
  await expect(page.locator('.comparison-graph .recorded-legend')).toContainText(candidates[1].revision_id)
  await expect(page.locator('.comparison-graph .recorded-counters')).toContainText('Queue 222')
})

async function checkDialog(page: Page, opener: Locator, label: string, screenshot?: string) {
  await opener.focus()
  await page.keyboard.press('Enter')
  const dialog = page.getByRole('dialog', { name: label, exact: true })
  await expect(dialog).toBeVisible()
  expect(await dialog.evaluate(element => element.contains(document.activeElement))).toBeTruthy()
  const controls = dialog.locator('button:enabled, input:enabled, select:enabled, a[href]')
  await controls.last().focus()
  await page.keyboard.press('Tab')
  await expect(controls.first()).toBeFocused()
  await page.keyboard.press('Shift+Tab')
  await expect(controls.last()).toBeFocused()
  if (screenshot) await page.screenshot({ path: screenshot })
  await page.keyboard.press('Escape')
  await expect(dialog).toHaveCount(0)
  await expect(opener).toBeFocused()
}

for (const width of [1440, 1024]) test(`every modal confines keyboard focus, closes and restores focus at ${width}`, async ({ page }) => {
  await page.setViewportSize({ width, height: width === 1440 ? 900 : 768 })
  await page.route('**/api/v1/health', async route => {
    const response = await route.fetch()
    await route.fulfill({ json: { ...await response.json(), ai_configured: true, ai_model: 'controlled-test' } })
  })
  await recordedWorkspace(page)
  await checkDialog(page, page.getByRole('button', { name: 'Settings', exact: true }), 'Settings')
  await checkDialog(page, page.getByRole('button', { name: 'Guide', exact: true }), 'Getting started', `screenshots/dialog-${width}.png`)
  await checkDialog(page, page.getByRole('button', { name: 'AI coach', exact: true }), 'AI coach guidance')
  await checkDialog(page, page.getByRole('button', { name: 'Assumption test', exact: true }), 'Assumption test')
  await page.getByRole('tab', { name: 'Architecture' }).click()
  if (width === 1024) await page.getByRole('button', { name: 'Components', exact: true }).click()
  await checkDialog(page, page.getByRole('button', { name: 'Add component by keyboard' }), 'Add component')
  await page.getByRole('tab', { name: 'Compare' }).click()
  await checkDialog(page, page.getByRole('button', { name: 'Request AI review' }), 'AI review disclosure')
})
