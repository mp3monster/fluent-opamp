const { defineConfig } = require("@playwright/test");

module.exports = defineConfig({
  testDir: "./ui-tests",
  timeout: 45_000,
  expect: {
    timeout: 8_000,
  },
  fullyParallel: false,
  retries: 0,
  reporter: [["list"]],
  use: {
    baseURL: "http://127.0.0.1:8191",
    headless: true,
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
    video: "retain-on-failure",
  },
  webServer: {
    command:
      "PYTHONPATH=src:plaintext-keyring/src PLAYWRIGHT_SVR_CREDENTIALS_PORT=8191 python3 ui-tests/scripts/start_playwright_service.py",
    url: "http://127.0.0.1:8191/svr-credentials-manager-service/ui",
    cwd: ".",
    reuseExistingServer: true,
    timeout: 180_000,
  },
});
