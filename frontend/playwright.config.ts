import { defineConfig, devices } from '@playwright/test'

/**
 * UI tests for the Stage 3 + 4 panels. The backend is mocked at the network
 * edge with JSON exported from the real pipeline (scripts/export_ui_fixtures.py),
 * so these run with no Python, database, Redis or ngspice — only Next.js.
 *
 *   npm run test:e2e
 *
 * NEXT_PUBLIC_API_URL points at a host that does not exist: any call a test
 * forgot to mock fails loudly instead of reaching a real server.
 */
const PORT = 3100
export const API = 'http://backend.test'

export default defineConfig({
  testDir: './e2e',
  timeout: 60_000,
  expect: { timeout: 10_000 },
  fullyParallel: false,
  retries: 0,
  reporter: [['list']],
  use: {
    baseURL: `http://localhost:${PORT}`,
    trace: 'retain-on-failure',
  },
  projects: [{ name: 'chromium', use: { ...devices['Desktop Chrome'] } }],
  webServer: {
    command: `npx next dev -p ${PORT}`,
    url: `http://localhost:${PORT}`,
    timeout: 180_000,
    reuseExistingServer: false,
    env: { NEXT_PUBLIC_API_URL: API },
  },
})
