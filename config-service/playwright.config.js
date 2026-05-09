import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: "./ui-tests",
  timeout: 30_000,
  expect: {
    timeout: 5_000,
  },
  fullyParallel: false,
  retries: 0,
  reporter: [["list"]],
  use: {
    baseURL: "http://127.0.0.1:8091",
    headless: true,
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
    video: "retain-on-failure",
  },
  webServer: {
    command:
      "PYTHONPATH=src APP_ENABLE_DEV_FEATURES=1 python3 -m config_service --config-path config/config-service.json --port 8091",
    url: "http://127.0.0.1:8091/config-service/api/v1/health",
    cwd: ".",
    reuseExistingServer: true,
    timeout: 120_000,
  },
});
