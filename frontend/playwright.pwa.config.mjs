import { defineConfig, devices } from '@playwright/test'

const runId = new Date().toISOString().replace(/[:.]/g, '-')
const reportRoot = process.env.PLAYWRIGHT_PWA_REPORT_ROOT || `test-results/runs/${runId}-pwa`
const previewPort = Number(process.env.PLAYWRIGHT_PWA_PORT || 4173)

export default defineConfig({
  testDir: './browser-tests',
  testMatch: 'pwa-lifecycle.spec.mjs',
  workers: 1,
  globalSetup: './playwright.pwa-server.mjs',
  timeout: 45000,
  retries: 0,
  outputDir: `${reportRoot}/artifacts`,
  reporter: [['list'], ['html', { open: 'never', outputFolder: `${reportRoot}/html-report` }], ['json', { outputFile: `${reportRoot}/results.json` }], ['line']],
  use: {
    ...devices['Desktop Chrome'],
    baseURL: `http://127.0.0.1:${previewPort}`,
    viewport: { width: 390, height: 844 },
    serviceWorkers: 'allow',
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure'
  }
})
