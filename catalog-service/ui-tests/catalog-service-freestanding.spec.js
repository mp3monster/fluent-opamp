// Test-case reference: catalog-service/docs/TEST_CASES.md
// Detailed browser scenarios: catalog-service/docs/TEST_CASES.md
import { expect, test } from "@playwright/test";

const WITH_CONFIG_SERVICE = "with-config-service";
const WITHOUT_CONFIG_SERVICE = "without-config-service";

async function openCatalog(page) {
  await page.goto("/catalog");
  await expect(page.getByRole("heading", { name: "Config Catalog" })).toBeVisible();
  await expect.poll(async () => page.locator("#catalogBody tr").count()).toBeGreaterThan(0);
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
    "Config Service UI",
  ]);
});

test("freestanding catalog feature menu navigates to config-service UI when configured", async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== WITH_CONFIG_SERVICE);
  await openCatalog(page);
  await page.locator("#featureMenuSelect").selectOption({ label: "Config Service UI" });
  await expect(page).toHaveURL(/\/config-service\/ui/);
  await expect(page.getByRole("heading", { name: "Config Service" })).toBeVisible();
  await expect(page.locator("#featureMenuGroup")).toBeVisible();
  await expect(page.locator("#featureMenuSelect option")).toContainText([
    "Config Catalog",
    "Config Service UI",
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

test("freestanding catalog hides provider UI navigation link", async ({ page }) => {
  await openCatalog(page);
  const providerLink = page.locator("a.button-link", { hasText: "Provider UI" });
  await expect(providerLink).toHaveAttribute("aria-hidden", "true");
  await expect(providerLink).toHaveAttribute("style", /display:none/);
});

test("column filters for config type engine and version are discovered-value dropdowns", async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== WITH_CONFIG_SERVICE);
  await openCatalog(page);

  const configTypeFilter = await columnSelectFilter(page, "config_type");
  const engineFilter = await columnSelectFilter(page, "engine");
  const versionFilter = await columnSelectFilter(page, "version");
  await expect(configTypeFilter).toBeVisible();
  await expect(engineFilter).toBeVisible();
  await expect(versionFilter).toBeVisible();

  await expect(configTypeFilter.locator("option")).toContainText(["All", "fluentbit", "fluentd"]);
  await expect(engineFilter.locator("option")).toContainText(["All", "fluentbit", "fluentd"]);
  await expect(versionFilter.locator("option")).toContainText(["All", "1.16", "5.0.4"]);
});

test("dropdown column filters reduce rows using discovered values", async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== WITH_CONFIG_SERVICE);
  await openCatalog(page);

  const configTypeFilter = await columnSelectFilter(page, "config_type");
  const versionFilter = await columnSelectFilter(page, "version");

  await configTypeFilter.selectOption({ label: "fluentd" });
  await expect(page.locator("#catalogBody tr")).toHaveCount(1);
  await expect(page.locator("#catalogBody")).toContainText("freestanding-fluentd.yaml");

  await configTypeFilter.selectOption({ label: "All" });
  await versionFilter.selectOption({ label: "5.0.4" });
  await expect(page.locator("#catalogBody tr")).toHaveCount(1);
  await expect(page.locator("#catalogBody")).toContainText("freestanding-fluentbit.yaml");
});

test("table columns can be reordered by drag and drop and persist on reload", async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== WITH_CONFIG_SERVICE);
  await openCatalog(page);

  const versionHeader = page.locator("#catalogHeaderRow th", { hasText: /^version$/ }).first();
  const folderHeader = page.locator("#catalogHeaderRow th", { hasText: /^folder$/ }).first();
  await versionHeader.dragTo(folderHeader);
  await expect(page.locator("#catalogHeaderRow th").first()).toHaveText("version");

  await page.reload();
  await expect.poll(async () => page.locator("#catalogBody tr").count()).toBeGreaterThan(0);
  await expect(page.locator("#catalogHeaderRow th").first()).toHaveText("version");
});

test("reload UI button forces cache-busted catalog reload", async ({ page }) => {
  await openCatalog(page);
  await Promise.all([
    page.waitForURL(/_ui_reload_ts=/),
    page.locator("#reload-ui").click(),
  ]);
  await expect(page.getByRole("heading", { name: "Config Catalog" })).toBeVisible();
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
