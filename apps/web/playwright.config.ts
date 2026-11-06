import { defineConfig } from "@playwright/test";

// Uses the Chrome already installed on the machine, so no browser download is needed.
export default defineConfig({
  testDir: "./e2e",
  timeout: 360_000,
  retries: 0,
  workers: 1,
  reporter: [["list"]],
  use: { baseURL: process.env.E2E_URL || "http://localhost:3000", channel: "chrome", trace: "off" },
  projects: [
    { name: "desktop", use: { viewport: { width: 1280, height: 800 } } },
    { name: "mobile", use: { viewport: { width: 360, height: 640 }, isMobile: true, hasTouch: true } },
  ],
});
