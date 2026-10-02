import { defineConfig } from '@playwright/test';

// The screens are driven in a headless browser against a real `querysolo serve` (app brief
// A12): global-setup inits a temp project and starts the sidecar with QUERYSOLO_DEV_ORIGIN set
// to the Vite dev server's origin, and each test opens the page with ?port=&token= from
// serve.json. QUERYSOLO_SIDECAR names the executable (core/.venv/bin/querysolo by default).
export default defineConfig({
  testDir: './tests',
  timeout: 60_000,
  // An assertion waits 5 s on a laptop, so a slowdown there still shows. On CI it waits 15 s:
  // the macOS runner is slow (the 20M-row import took 6.3 s there) and missed 5 s waits in
  // three different specs on 2026-10-01; the assertions themselves are unchanged.
  expect: { timeout: process.env.CI ? 15_000 : 5_000 },
  retries: 0,
  globalSetup: './tests/global-setup.ts',
  globalTeardown: './tests/global-teardown.ts',
  use: {
    baseURL: 'http://localhost:5173',
    trace: 'retain-on-failure',
    // A sandbox with its own Chromium can name it; CI and laptops use Playwright's.
    launchOptions: process.env.PLAYWRIGHT_CHROMIUM ? { executablePath: process.env.PLAYWRIGHT_CHROMIUM } : {},
  },
  webServer: {
    command: 'npm run dev',
    url: 'http://localhost:5173',
    reuseExistingServer: !process.env.CI,
    timeout: 60_000,
  },
  reporter: process.env.CI ? 'github' : 'list',
});
