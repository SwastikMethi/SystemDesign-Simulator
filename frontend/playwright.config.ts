import { defineConfig, devices } from '@playwright/test'

export default defineConfig({
  testDir: './e2e',
  timeout: 120_000,
  expect: { timeout: 20_000 },
  use: { ...devices['Desktop Chrome'], baseURL: process.env.AISD_FRONTEND_URL || 'http://127.0.0.1:8771', screenshot: 'only-on-failure', trace: 'retain-on-failure', video: 'on' },
  webServer: process.env.AISD_FRONTEND_URL ? undefined : {
    command: `npm run build && cd .. && AISD_DATA_DIR=/tmp/aisd-playwright-${process.pid} .venv/bin/uvicorn backend.main:app --host 127.0.0.1 --port 8771`,
    url: 'http://127.0.0.1:8771/api/v1/health',
    reuseExistingServer: false,
    timeout: 60_000,
  },
  reporter: [['list']],
})
