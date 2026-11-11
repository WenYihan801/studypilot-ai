import { defineConfig, devices } from '@playwright/test'

// E2E_BASE_URL lets you point the suite at the deployed Vercel site; default is a local preview build.
const baseURL = process.env.E2E_BASE_URL ?? 'http://localhost:4173'

export default defineConfig({
  testDir: './e2e',
  timeout: 120_000,
  retries: process.env.CI ? 1 : 0,
  use: {
    baseURL,
    trace: 'retain-on-failure',
    // Optional: use an installed Chrome instead of `npx playwright install chromium`.
    launchOptions: process.env.PLAYWRIGHT_CHROME_PATH ? { executablePath: process.env.PLAYWRIGHT_CHROME_PATH } : {},
  },
  projects: [
    { name: 'desktop', use: { ...devices['Desktop Chrome'] } },
    { name: 'mobile', use: { ...devices['Pixel 7'] } },
  ],
  webServer: process.env.E2E_BASE_URL ? undefined : { command: 'npm run build && npx vite preview --port 4173', url: baseURL, reuseExistingServer: true, timeout: 120_000 },
})
