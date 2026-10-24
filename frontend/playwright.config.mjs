import { defineConfig, devices } from '@playwright/test'

const runId = new Date().toISOString().replace(/[:.]/g, '-')
const reportRoot = process.env.PLAYWRIGHT_REPORT_ROOT || `test-results/runs/${runId}`
const proxyServer = process.env.PLAYWRIGHT_PROXY_SERVER?.trim()

export default defineConfig({
  testDir: './browser-tests',
  timeout: 30000,
  retries: 1,
  outputDir: `${reportRoot}/artifacts`,
  reporter: [['list'], ['html', { open: 'never', outputFolder: `${reportRoot}/html-report` }]],
  use: {
    baseURL: 'http://127.0.0.1:5173',
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
    ...(proxyServer ? { launchOptions: { proxy: { server: proxyServer } } } : {})
  },
  projects: [
    { name: 'desktop', use: { ...devices['Desktop Chrome'], viewport: { width: 1366, height: 768 } } },
    { name: 'mobile', use: { ...devices['Desktop Chrome'], viewport: { width: 390, height: 844 }, isMobile: true, hasTouch: true } }
  ],
  webServer: {
    command: 'npm run dev -- --host 127.0.0.1 --port 5173 --strictPort',
    url: 'http://127.0.0.1:5173/e2e-harness.html',
    reuseExistingServer: !process.env.CI,
    timeout: 45000
  }
})
