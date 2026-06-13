// Test-case reference: catalog-service/docs/TEST_CASES.md
// Detailed browser scenarios: catalog-service/docs/TEST_CASES.md
import fs from "node:fs/promises";
import path from "node:path";
import { expect, test } from "@playwright/test";

const WITH_CONFIG_SERVICE = "with-config-service";
const WITHOUT_CONFIG_SERVICE = "without-config-service";

async function openCatalog(page) {
  await page.goto("/catalog");
  await expect(page.getByRole("heading", { name: "Config Catalog" })).toBeVisible();
  await expect.poll(async () => page.locator("#catalogBody tr").count()).toBeGreaterThan(0);
}

function basenameForPath(pathValue) {
  const segments = String(pathValue || "").split(/[\\/]/);
  return String(segments[segments.length - 1] || "");
}

async function columnIndex(page, columnName) {
  const names = (await page.locator("#catalogHeaderRow th").allTextContents()).map((value) => value.trim());
  return names.indexOf(columnName);
}

async function columnSelectFilter(page, columnName) {
  const index = await columnIndex(page, columnName);
  expect(index).toBeGreaterThan(-1);
  return page.locator(`#catalogColumnFilterRow th:nth-child(${index + 1}) select`);
}

test("freestanding catalog shows config-service feature menu entry when configured", async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== WITH_CONFIG_SERVICE);
  await openCatalog(page);
  await expect(page.locator("#featureMenuGroup")).toBeVisible();
  await expect(page.locator("#featureMenuSelect option")).toContainText([
    "Config Catalog",
    "Config Editor",
  ]);
});

test("freestanding catalog feature menu navigates to config-service UI when configured", async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== WITH_CONFIG_SERVICE);
  await openCatalog(page);
  await page.locator("#featureMenuSelect").selectOption({ label: "Config Editor" });
  await expect(page).toHaveURL(/\/config-service\/ui/);
  await expect(page.getByRole("heading", { name: "Config Service" })).toBeVisible();
  await expect(page.locator("#featureMenuGroup")).toBeVisible();
  await expect(page.locator("#featureMenuSelect option")).toContainText([
    "Config Catalog",
    "Config Editor",
  ]);
});

test("freestanding catalog row click opens config-service editor when configured", async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== WITH_CONFIG_SERVICE);
  await openCatalog(page);
  await page.locator("#catalogBody tr", { hasText: "freestanding-fluentbit.yaml" }).first().click();
  await expect(page).toHaveURL(/\/config-service\/ui/);
  await expect(page.getByRole("heading", { name: "Config Service" })).toBeVisible();
  await expect(page.locator("#open-file-display")).toHaveValue("freestanding-fluentbit.yaml");
});

test("catalog-opened config saves through validate-and-save without browser download", async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== WITH_CONFIG_SERVICE);

  const tempSourcePath = path.resolve(
    "ui-tests",
    "fixtures",
    "with-config-service",
    "catalog",
    "playwright-catalog-server-save-" + String(process.pid || "pid") + "-" + String(testInfo.retry) + ".yaml"
  );
  await fs.writeFile(
    tempSourcePath,
    [
      "# catalog-backed save test",
      "service:",
      "  flush: 1",
      "pipeline:",
      "  inputs:",
      "    - name: forward",
      "      buffer_chunk_size: 1024",
      "      buffer_max_size: 2048",
      "      port: 24224",
      "  outputs:",
      "    - name: null",
      "      match: '*'",
      "",
    ].join("\n"),
    "utf-8"
  );

  await openCatalog(page);
  await page.locator("#catalogBody tr", { hasText: path.basename(tempSourcePath) }).first().click();
  await expect(page).toHaveURL(/\/config-service\/ui/);
  await expect(page.locator("#open-file-display")).toHaveValue(path.basename(tempSourcePath));

  const downloadOccurred = page.waitForEvent("download", { timeout: 1500 })
    .then(() => true)
    .catch(() => false);
  const validateResponsePromise = page.waitForResponse((response) => {
    return response.url().includes("/config-service/api/v1/validate/") && response.request().method() === "POST";
  });

  await page.locator("#save-config").click();
  const validateResponse = await validateResponsePromise;
  expect(validateResponse.ok()).toBeTruthy();
  const validatePayload = await validateResponse.json();

  expect(validatePayload.saved).toBeTruthy();
  expect(String(validatePayload.save_path || "")).toContain(path.basename(tempSourcePath));
  expect(await downloadOccurred).toBeFalsy();
  await expect(page.locator("#status-message")).toContainText("Saved validated configuration");

  const saved = await fs.readFile(tempSourcePath, "utf-8");
  expect(saved).toContain("# config-service: config_type=fluentbit");
  expect(saved).toContain("pipeline:");
  await fs.rm(tempSourcePath, { force: true });
});

test("freestanding catalog row click does not show stale config-service state before source load completes", async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== WITH_CONFIG_SERVICE);

  await page.addInitScript(() => {
    localStorage.setItem(
      "config_service_last_opened_doc",
      JSON.stringify({
        version: "5.0.4",
        configType: "fluentbit",
        config: {
          service: { flush: 99 },
          pipeline: { inputs: [], filters: [], outputs: [] },
        },
        annotations: {},
      }),
    );
    localStorage.setItem("config_service_last_header_comments", "stale header");
    document.cookie = "config_service_last_opened_name=stale-config.yaml; path=/";
  });

  let releaseSourceLoad;
  const sourceLoadGate = new Promise((resolve) => {
    releaseSourceLoad = resolve;
  });

  await page.route("**/config-service/api/v1/ui/load-source-file", async (route) => {
    await sourceLoadGate;
    await route.continue();
  });

  await openCatalog(page);
  await page.locator("#catalogBody tr", { hasText: "freestanding-fluentd.yaml" }).first().click();
  await expect(page).toHaveURL(/\/config-service\/ui\?source_path=/);
  await expect(page.getByRole("heading", { name: "Config Service" })).toBeVisible();
  await expect(page.locator("#open-file-display")).toHaveValue("");

  releaseSourceLoad();

  await expect(page.locator("#open-file-display")).toHaveValue("freestanding-fluentd.yaml");
  await expect(page.locator("#config-type-select")).toHaveValue("fluentd");
});

test("freestanding catalog falls back to readonly viewer when config-service is not configured", async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== WITHOUT_CONFIG_SERVICE);
  await openCatalog(page);
  await expect(page.locator("#featureMenuGroup")).toHaveClass(/hidden/);
  await page.locator("#catalogBody tr", { hasText: "freestanding-fluentbit.yaml" }).first().click();
  await expect(page.locator("#catalogReadonlyOverlay")).toBeVisible();
  await expect(page.locator("#catalogReadonlyTitle")).toContainText("freestanding-fluentbit.yaml");
  await expect(page.locator("#catalogReadonlyText")).toHaveValue(/service:/);
  await page.locator("#catalogReadonlyCloseTop").click();
  await expect(page.locator("#catalogReadonlyOverlay")).toHaveClass(/hidden/);
});

test("freestanding catalog hides Server Console navigation link", async ({ page }) => {
  await openCatalog(page);
  const providerLink = page.locator("a.button-link", { hasText: "Server Console" });
  await expect(providerLink).toHaveAttribute("aria-hidden", "true");
  await expect(providerLink).toHaveAttribute("style", /display:none/);
});

test("column filters for config type engine and version are discovered-value dropdowns", async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== WITH_CONFIG_SERVICE);
  await openCatalog(page);

  const configTypeFilter = await columnSelectFilter(page, "config type (metadata)");
  const engineFilter = await columnSelectFilter(page, "engine (inferred)");
  const versionFilter = await columnSelectFilter(page, "version");
  await expect(configTypeFilter).toBeVisible();
  await expect(engineFilter).toBeVisible();
  await expect(versionFilter).toBeVisible();

  await expect(configTypeFilter.locator("option")).toContainText(["All", "fluentbit", "fluentd"]);
  await expect(engineFilter.locator("option")).toContainText(["All", "fluentbit", "fluentd"]);
  await expect(versionFilter.locator("option")).toContainText(["All", "1.16", "5.0.4"]);
});

test("catalog table renders config_version metadata when present", async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== WITH_CONFIG_SERVICE);
  await openCatalog(page);

  await expect(page.locator("#catalogHeaderRow th")).toContainText(["config_version"]);
  await expect(page.locator("#catalogBody")).toContainText("freestanding-demo-42");
});

test("dropdown column filters reduce rows using discovered values", async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== WITH_CONFIG_SERVICE);
  await openCatalog(page);

  const configTypeFilter = await columnSelectFilter(page, "config type (metadata)");
  const versionFilter = await columnSelectFilter(page, "version");

  await configTypeFilter.selectOption({ label: "fluentd" });
  await expect(page.locator("#catalogBody tr")).toHaveCount(1);
  await expect(page.locator("#catalogBody")).toContainText("freestanding-fluentd.yaml");

  await configTypeFilter.selectOption({ label: "All" });
  await versionFilter.selectOption({ label: "5.0.4" });
  await expect(page.locator("#catalogBody tr")).toHaveCount(1);
  await expect(page.locator("#catalogBody")).toContainText("freestanding-fluentbit.yaml");
});

test("selection checkbox click marks the row without opening the readonly viewer", async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== WITHOUT_CONFIG_SERVICE);
  await openCatalog(page);

  const row = page.locator("#catalogBody tr", { hasText: "freestanding-fluentbit.yaml" }).first();
  const checkbox = row.locator('input[type="checkbox"]').first();

  await checkbox.click();

  await expect(checkbox).toBeChecked();
  await expect(page.locator("#catalogReadonlyOverlay")).toHaveClass(/hidden/);
  await expect(page).toHaveURL(/\/catalog$/);
});

test("auto refresh pauses while catalog entries are selected", async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== WITHOUT_CONFIG_SERVICE);
  await page.addInitScript(() => {
    const originalSetInterval = window.setInterval;
    window.setInterval = (callback, delay, ...args) => {
      if (delay === 120000) {
        return originalSetInterval(callback, 150, ...args);
      }
      return originalSetInterval(callback, delay, ...args);
    };
  });
  let fileRequestCount = 0;
  await page.route("**/catalog/api/files", async (route) => {
    fileRequestCount += 1;
    await route.continue();
  });

  await openCatalog(page);
  await expect.poll(() => fileRequestCount).toBeGreaterThan(1);

  const row = page.locator("#catalogBody tr", { hasText: "freestanding-fluentbit.yaml" }).first();
  await row.locator('input[type="checkbox"]').first().click();
  const requestCountAfterSelection = fileRequestCount;

  await page.waitForTimeout(450);
  expect(fileRequestCount).toBe(requestCountAfterSelection);
});

test("selection filter shows selected and unselected rows independently", async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== WITH_CONFIG_SERVICE);
  await openCatalog(page);

  const selectedFilter = await columnSelectFilter(page, "selected");
  const fluentbitRow = page.locator("#catalogBody tr", { hasText: "freestanding-fluentbit.yaml" }).first();
  const fluentbitCheckbox = fluentbitRow.locator('input[type="checkbox"]').first();

  await fluentbitCheckbox.click();
  await expect(page).toHaveURL(/\/catalog$/);
  await selectedFilter.selectOption({ label: "Selected" });
  await expect(page.locator("#catalogBody tr")).toHaveCount(1);
  await expect(page.locator("#catalogBody")).toContainText("freestanding-fluentbit.yaml");

  await selectedFilter.selectOption({ label: "Unselected" });
  await expect(page.locator("#catalogBody tr")).toHaveCount(1);
  await expect(page.locator("#catalogBody")).toContainText("freestanding-fluentd.yaml");
});

test("catalog apply button posts ordered selected files when a callback is provided", async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== WITH_CONFIG_SERVICE);
  let callbackPayload = null;
  await page.addInitScript(() => {
    window.__catalogCloseCalled = false;
    window.__catalogPostedMessage = null;
    Object.defineProperty(window, "opener", {
      configurable: true,
      value: {
        postMessage(payload, origin) {
          window.__catalogPostedMessage = { payload, origin };
        },
      },
    });
    window.close = () => {
      window.__catalogCloseCalled = true;
    };
  });

  await page.route("**/*", async (route) => {
    const requestUrl = new URL(route.request().url());
    if (requestUrl.pathname !== "/catalog/api/test-selection-callback") {
      await route.continue();
      return;
    }
    callbackPayload = JSON.parse(route.request().postData() || "{}");
    const files = Array.isArray(callbackPayload.files)
      ? callbackPayload.files.map((item) => {
        const sourcePath = String(item.source_path || "");
        const filename = basenameForPath(sourcePath);
        return {
          source_path: sourcePath,
          target_name: filename,
          filename,
        };
      })
      : [];
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        status: "accepted",
        client_id: "catalog-test-client",
        files,
      }),
    });
  });

  await page.goto("/catalog?selection_callback=/catalog/api/test-selection-callback");
  await expect(page.getByRole("heading", { name: "Config Catalog" })).toBeVisible();
  await expect.poll(async () => page.locator("#catalogBody tr").count()).toBeGreaterThan(0);

  await page.locator("#catalogBody tr", { hasText: "freestanding-fluentd.yaml" }).first().locator('input[type="checkbox"]').click();
  await page.locator("#catalogBody tr", { hasText: "freestanding-fluentbit.yaml" }).first().locator('input[type="checkbox"]').click();
  await page.locator("#catalogApplySelectionBtn").click();

  await expect(page.locator("#catalogApplySelectionStatus")).toContainText("Applied 2 selected files.");
  await expect.poll(async () => page.evaluate(() => window.__catalogCloseCalled)).toBe(true);
  const postedMessage = await page.evaluate(() => window.__catalogPostedMessage);

  expect(callbackPayload).toEqual({
    files: [
      {
        source_path: expect.stringMatching(/freestanding-fluentd\.yaml$/),
      },
      {
        source_path: expect.stringMatching(/freestanding-fluentbit\.yaml$/),
      },
    ],
  });
  expect(postedMessage).toEqual({
    origin: expect.stringMatching(/^http:\/\/127\.0\.0\.1:/),
    payload: {
      type: "opamp-catalog-selection-applied",
      client_id: "catalog-test-client",
      files: [
        {
          source_path: expect.stringMatching(/freestanding-fluentd\.yaml$/),
          target_name: "freestanding-fluentd.yaml",
          filename: "freestanding-fluentd.yaml",
        },
        {
          source_path: expect.stringMatching(/freestanding-fluentbit\.yaml$/),
          target_name: "freestanding-fluentbit.yaml",
          filename: "freestanding-fluentbit.yaml",
        },
      ],
    },
  });
});

test("table columns can be reordered by drag and drop and persist on reload", async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== WITH_CONFIG_SERVICE);
  await openCatalog(page);

  const versionHeader = page.locator("#catalogHeaderRow th", { hasText: /^version$/ }).first();
  const folderHeader = page.locator("#catalogHeaderRow th", { hasText: /^folder$/ }).first();
  await versionHeader.dragTo(folderHeader);
  await expect(page.locator("#catalogHeaderRow th").first()).toHaveText("selected");
  await expect(page.locator("#catalogHeaderRow th").nth(1)).toHaveText("version");

  await page.reload();
  await expect.poll(async () => page.locator("#catalogBody tr").count()).toBeGreaterThan(0);
  await expect(page.locator("#catalogHeaderRow th").first()).toHaveText("selected");
  await expect(page.locator("#catalogHeaderRow th").nth(1)).toHaveText("version");
});

test("catalog UI reports browser console errors to the standalone client-errors endpoint", async ({ page }) => {
  await openCatalog(page);
  const requestPromise = page.waitForRequest((request) => {
    if (!request.url().includes("/catalog/api/client-errors")) {
      return false;
    }
    if (request.method() !== "POST") {
      return false;
    }
    return request.postData()?.includes("playwright synthetic catalog console error") || false;
  });
  await page.evaluate(() => {
    console.error("playwright synthetic catalog console error");
  });
  await requestPromise;
});
