import { defineConfig, devices } from '@playwright/test'

const runId = new Date().toISOString().replace(/[:.]/g, '-')
const reportRoot = process.env.PLAYWRIGHT_REPORT_ROOT || `test-results/runs/${runId}`
const proxyServer = process.env.PLAYWRIGHT_PROXY_SERVER?.trim()

export default defineConfig({
  testDir: './browser-tests',
  globalSetup: './playwright.dev-server.mjs',
  // PWA lifecycle tests require the production preview origin and service worker;
  // they run through playwright.pwa.config.mjs rather than the Vite dev server.
  testIgnore: ['pwa-lifecycle.spec.mjs'],
  // Public OSM availability is checked once on demand via the live-map config.
  // The regular desktop/mobile suite uses a local tile fixture for deterministic recovery.
  grepInvert: /@live-map/,
  timeout: 30000,
  retries: 1,
  outputDir: `${reportRoot}/artifacts`,
  reporter: [
    ['list'],
    ['html', { open: 'never', outputFolder: `${reportRoot}/html-report` }],
    ['json', { outputFile: `${reportRoot}/results.json` }]
  ],
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
})
