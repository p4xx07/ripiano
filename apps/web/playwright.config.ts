import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: "./e2e",
  timeout: 90000,
  workers: 2,
  expect: { timeout: 15000 },
  use: {
    baseURL: process.env.RIPIANO_E2E_ORIGIN ?? "http://localhost:8080",
    browserName: "chromium",
    channel: "chrome",
    headless: true,
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
  },
  projects: [
    { name: "desktop", use: { viewport: { width: 1440, height: 900 } } },
    {
      name: "mobile",
      use: {
        viewport: { width: 390, height: 844 },
        isMobile: true,
        hasTouch: true,
      },
    },
  ],
});
