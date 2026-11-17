import { defineConfig } from '@playwright/test';

// SIGN-UP LIMIT. The product allows 10 sign-ups per peer per 15 minutes per account store; the limit is an authentication
// control and is deliberately not weakened or bypassed for tests. One full run registers 9 accounts on the account API
// (account-flow 4; analytics, csv, workspace, real-source-flow and real-source-focus 1 each) and 3 on the guarded F3 API
// (guarded-flow: owner, other, rpt). Run the suite ONCE per `tests/product/dev_env.py up`; to run again within 15 minutes, run
// `down` and `up` (a fresh account schema has a fresh counter). A 429 AUTH_RATE_LIMITED on a re-run is this limit, not a defect.
// Each test keeps its own account so tests stay independent of each other's state; reusing one owner would save sign-ups at the cost of that.

export default defineConfig({
  testDir: './e2e',
  use: {
    baseURL: process.env.FINWEB_WEB_BASE_URL ?? 'http://127.0.0.1:5173', headless: true,
    launchOptions: { executablePath: process.env.FINWEB_CHROMIUM_EXECUTABLE_PATH },
  },
  timeout: 60_000,
  fullyParallel: false,
  reporter: 'list',
});
