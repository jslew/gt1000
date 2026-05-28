import path from "node:path";
import { fileURLToPath } from "node:url";
import { defineConfig } from "@playwright/test";

const rootDir = path.dirname(fileURLToPath(import.meta.url));
process.env.PLAYWRIGHT_BROWSERS_PATH ??= path.join(rootDir, ".playwright-browsers");

const baseURL = process.env.GT1000_APP_URL ?? "http://127.0.0.1:38473";

export default defineConfig({
  testDir: "./tests",
  timeout: 300_000,
  expect: { timeout: 240_000 },
  retries: 0,
  workers: 1,
  reporter: [["list"]],
  use: {
    baseURL,
    headless: process.env.GT1000_E2E_HEADED !== "1",
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
    video: "retain-on-failure",
  },
  outputDir: "./test-results",
});
