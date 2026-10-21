import { defineConfig, devices } from "@playwright/test";

// Browser tests of the production build. The API is mocked per test (e2e/fixtures.ts), so
// these check the frontend alone; scripts/smoke_test.py covers the real backend end to end.
const PORT = 3100;

export default defineConfig({
  testDir: "./e2e",
  fullyParallel: true,
  forbidOnly: Boolean(process.env.CI),
  retries: process.env.CI ? 1 : 0,
  reporter: process.env.CI ? [["github"], ["list"]] : "list",
  use: { baseURL: `http://localhost:${PORT}`, trace: "retain-on-failure" },
  projects: [
    { name: "desktop", use: { ...devices["Desktop Chrome"] } },
    { name: "mobile", use: { ...devices["Pixel 7"] } },
  ],
  webServer: {
    // Run `npm run build` first: this serves the same build that ships.
    command: `npx next start -p ${PORT}`,
    url: `http://localhost:${PORT}/privacy`,
    reuseExistingServer: !process.env.CI,
    timeout: 60_000,
  },
});
