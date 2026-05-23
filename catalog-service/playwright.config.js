import { defineConfig } from "@playwright/test";

export default defineConfig({
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
      name: "with-config-service",
      use: {
        baseURL: "http://127.0.0.1:8291",
      },
    },
    {
      name: "without-config-service",
      use: {
        baseURL: "http://127.0.0.1:8292",
      },
    },
  ],
  webServer: [
    {
      command:
        "PYTHONPATH=src:../config-service/src APP_ENABLE_DEV_FEATURES=1 python3 -m catalog_service --config-path ui-tests/fixtures/with-config-service/catalog-service.json --host 127.0.0.1 --port 8291",
      url: "http://127.0.0.1:8291/catalog",
      cwd: ".",
      reuseExistingServer: true,
      timeout: 180_000,
    },
    {
      command:
        "PYTHONPATH=src:../config-service/src APP_ENABLE_DEV_FEATURES=1 python3 -m catalog_service --config-path ui-tests/fixtures/without-config-service/catalog-service.json --host 127.0.0.1 --port 8292",
      url: "http://127.0.0.1:8292/catalog",
      cwd: ".",
      reuseExistingServer: true,
      timeout: 180_000,
    },
  ],
});
