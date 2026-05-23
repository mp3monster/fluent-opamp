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
    headless: true,
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
    video: "retain-on-failure",
  },
  projects: [
    {
      name: "with-endpoints",
      use: {
        baseURL: "http://127.0.0.1:8181",
      },
    },
    {
      name: "without-endpoints",
      use: {
        baseURL: "http://127.0.0.1:8182",
      },
    },
    {
      name: "catalog-readonly",
      use: {
        baseURL: "http://127.0.0.1:8183",
      },
    },
  ],
  webServer: [
    {
      command:
        "PYTHONPATH=provider/src:config-service/src APP_ENABLE_DEV_FEATURES=1 OPAMP_CONFIG_PATH=provider/ui-tests/fixtures/opamp-with-endpoints.json python3 -m opamp_provider.server --host 127.0.0.1 --port 8181",
      url: "http://127.0.0.1:8181/ui",
      cwd: "..",
      reuseExistingServer: true,
      timeout: 180_000,
    },
    {
      command:
        "PYTHONPATH=provider/src:config-service/src APP_ENABLE_DEV_FEATURES=1 OPAMP_CONFIG_PATH=provider/ui-tests/fixtures/opamp-without-endpoints.json python3 -m opamp_provider.server --host 127.0.0.1 --port 8182",
      url: "http://127.0.0.1:8182/ui",
      cwd: "..",
      reuseExistingServer: true,
      timeout: 180_000,
    },
    {
      command:
        "PYTHONPATH=provider/src:config-service/src APP_ENABLE_DEV_FEATURES=1 OPAMP_CONFIG_PATH=provider/ui-tests/fixtures/opamp-catalog-readonly.json python3 -m opamp_provider.server --host 127.0.0.1 --port 8183",
      url: "http://127.0.0.1:8183/ui",
      cwd: "..",
      reuseExistingServer: true,
      timeout: 180_000,
    },
  ],
});
