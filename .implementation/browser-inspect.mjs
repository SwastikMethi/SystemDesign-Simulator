import { createRequire } from 'node:module';
import { mkdir, writeFile } from 'node:fs/promises';
import assert from 'node:assert/strict';

const require = createRequire(new URL('../frontend/package.json', import.meta.url));
const { chromium } = require('@playwright/test');
const browser = await chromium.launch({ headless: true });
const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });
const errors = [];
page.on('pageerror', error => errors.push(error.message));
await mkdir('.implementation/screenshots', { recursive: true });
await page.goto('http://127.0.0.1:8770');
await page.getByText('Product catalogue', { exact: true }).waitFor();
console.log(await page.locator('body').innerText());
await page.screenshot({ path: '.implementation/screenshots/library-1440.png', fullPage: true });
await page.getByRole('button', { name: 'Load starter', exact: true }).nth(2).click();
await page.locator('.react-flow__node').first().waitFor();
await page.getByRole('button', { name: 'Close', exact: true }).click();
console.log(await page.locator('body').innerText());
await page.screenshot({ path: '.implementation/screenshots/editor-1440.png', fullPage: true });
await page.setViewportSize({ width: 1024, height: 768 });
await page.screenshot({ path: '.implementation/screenshots/editor-1024.png', fullPage: true });
if (process.argv.includes('--measure')) {
  await page.setViewportSize({ width: 1440, height: 900 });
  const interactionMs = [];
  for (let index = 0; index < 20; index++) {
    const node = page.locator(`.react-flow__node[data-id="${index % 2 ? 'sql' : 'app'}"]`);
    await node.evaluate(element => {
      window.nextPaint = new Promise(resolve => element.addEventListener('pointerdown', () => {
        const start = performance.now();
        requestAnimationFrame(() => requestAnimationFrame(() => resolve(performance.now() - start)));
      }, { once: true }));
    });
    await node.click();
    interactionMs.push(await page.evaluate(() => window.nextPaint));
  }
  const frameMs = await page.evaluate(() => new Promise(resolve => {
    const deltas = [];
    let last;
    const sample = now => {
      if (last !== undefined) deltas.push(now - last);
      last = now;
      if (deltas.length === 240) resolve(deltas); else requestAnimationFrame(sample);
    };
    requestAnimationFrame(sample);
  }));
  const percentile = values => [...values].sort((a, b) => a - b)[Math.ceil(values.length * .95) - 1];
  const measurements = {
    captured_at: new Date().toISOString(), viewport: '1440x900', browser: await browser.version(),
    scope: 'Headless Chromium, catalogue starter canvas; pointerdown to second animation frame, then idle frame intervals. No 100-marker playback stress claim.',
    interaction_ms: interactionMs, interaction_p95_ms: percentile(interactionMs),
    frame_ms: frameMs, frame_p95_ms: percentile(frameMs), page_errors: errors,
  };
  await writeFile('.implementation/ui-performance.json', JSON.stringify(measurements, null, 2) + '\n');
  console.log(JSON.stringify({ interaction_p95_ms: measurements.interaction_p95_ms, frame_p95_ms: measurements.frame_p95_ms, page_errors: errors }));
}
if (process.argv.includes('--check-editor')) {
  await page.setViewportSize({ width: 1440, height: 900 });
  const node = page.locator('.react-flow__node[data-id="app"]');
  const before = await node.boundingBox();
  await page.mouse.move(before.x + before.width / 2, before.y + 20);
  await page.mouse.down();
  await page.mouse.move(before.x + before.width / 2 + 80, before.y + 116, { steps: 8 });
  const during = await node.boundingBox();
  assert(Math.hypot(during.x - before.x, during.y - before.y) > 40, 'The node must follow the pointer before drop');
  await page.mouse.up();
  const after = await node.boundingBox();
  assert(Math.hypot(after.x - before.x, after.y - before.y) > 40, 'Dragging must move the controlled node');
  await page.getByRole('button', { name: 'Undo', exact: true }).click();
  const undone = await node.boundingBox();
  assert(Math.hypot(undone.x - before.x, undone.y - before.y) < 2, 'Undo must restore the node position');
  console.log('Browser editor check passed: drag moves the node and Undo restores its position.');
}
if (process.argv.includes('--check-keyboard')) {
  await page.setViewportSize({ width: 1440, height: 900 });
  const before = await page.locator('.react-flow__node').count();
  await page.getByRole('button', { name: 'Add component by keyboard', exact: true }).focus();
  await page.keyboard.press('Enter');
  const dialog = page.getByRole('dialog', { name: 'Add component', exact: true });
  await dialog.getByRole('textbox', { name: 'Search', exact: true }).fill('Cache');
  await page.keyboard.press('Tab');
  assert.match(await page.locator(':focus').innerText(), /Cache/);
  await page.keyboard.press('Enter');
  await page.waitForFunction(count => document.querySelectorAll('.react-flow__node').length === count + 1, before);
  await page.getByRole('button', { name: 'Undo', exact: true }).focus();
  await page.keyboard.press('Enter');
  await page.waitForFunction(count => document.querySelectorAll('.react-flow__node').length === count, before);
  console.log('Keyboard check passed: Enter opens the component dialog, search/Tab/Enter adds a cache, and keyboard Undo restores the graph.');
}
if (process.argv.includes('--check-redesign')) {
  const capture = async (name, width) => {
    await page.evaluate(() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve))));
    assert((await page.evaluate(() => document.documentElement.scrollWidth)) <= width, `${name} must fit the viewport`);
    for (const dialog of await page.getByRole('dialog').all()) {
      assert(await dialog.evaluate(element => element.scrollWidth <= element.clientWidth), `${name} dialog must not clip its content horizontally`);
    }
    await mkdir('frontend/screenshots', { recursive: true });
    await page.screenshot({ path: `frontend/screenshots/redesign-${name}-${width}.png`, fullPage: true });
  };
  for (const width of [1440, 1024]) {
    await page.setViewportSize({ width, height: width === 1440 ? 900 : 768 });
    await page.getByRole('tab', { name: 'Architecture', exact: true }).click();
    await page.locator('.react-flow__node[data-id="app"]').click();
    await page.getByRole('textbox', { name: 'Name', exact: true }).fill('Catalogue application service with a deliberately long component name');
    await capture('inspector', width);
    await page.getByRole('textbox', { name: 'Name', exact: true }).fill('App');
    await page.getByRole('button', { name: 'Guide', exact: true }).click();
    await capture('guide', width);
    await page.keyboard.press('Escape');
    await page.getByRole('button', { name: 'AI coach', exact: true }).click();
    await capture('coach', width);
    await page.keyboard.press('Escape');
    await page.getByRole('tab', { name: 'Requirements', exact: true }).click();
    await capture('requirements', width);
  }
  await page.setViewportSize({ width: 390, height: 844 });
  await page.getByRole('button', { name: 'AI coach', exact: true }).click();
  await capture('coach', 390);
  await page.keyboard.press('Escape');
  await page.getByRole('button', { name: 'Saved work', exact: true }).click();
  for (const width of [1440, 1024, 390]) {
    await page.setViewportSize({ width, height: width === 1440 ? 900 : 844 });
    await capture('history', width);
    await page.getByRole('button', { name: 'Settings', exact: true }).click();
    await capture('settings', width);
    await page.keyboard.press('Escape');
  }
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.getByRole('button', { name: 'Challenges', exact: true }).click();
  await page.getByRole('button', { name: 'Start empty', exact: true }).first().click();
  await page.getByRole('dialog', { name: 'Getting started' }).getByRole('button', { name: 'Close' }).click();
  await capture('empty-editor', 1440);
  await page.route('**/api/v1/challenges', route => route.fulfill({ status: 503, json: { detail: 'Challenge service unavailable. Try again.' } }));
  await page.goto('http://127.0.0.1:8770');
  await page.getByRole('heading', { name: 'Challenges unavailable' }).waitFor();
  await capture('error', 1440);
  console.log('Redesign inspection passed: selected inspector, requirements, guide, coach, history, settings, empty editor and error state fit their viewports.');
}
assert.deepEqual(errors, [], 'The browser must not report uncaught page errors');
await browser.close();
