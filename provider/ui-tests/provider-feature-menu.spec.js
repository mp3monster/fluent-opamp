import { expect, test } from "@playwright/test";

test("feature menu is hidden when no endpoints are configured", async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== "without-endpoints");
  await page.goto("/ui");
  await expect(page.getByRole("heading", { name: "OpAMP Server Console" })).toBeVisible();
  await expect(page.locator("#featureMenuGroup")).toHaveClass(/hidden/);
});

test("feature menu is shown when component endpoints are configured", async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== "with-endpoints");
  await page.goto("/ui");
  await expect(page.getByRole("heading", { name: "OpAMP Server Console" })).toBeVisible();
  await expect(page.locator("#featureMenuGroup")).toBeVisible();
  await expect(page.locator("#featureMenuSelect option")).toContainText(["Config Service UI", "Config Catalog"]);
});

test("config-service menu entry navigates to embedded config-service UI", async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== "with-endpoints");
  await page.goto("/ui");
  await page.locator("#featureMenuSelect").selectOption({ label: "Config Service UI" });
  await expect(page).toHaveURL(/\/config-service\/ui/);
  await expect(page.getByRole("heading", { name: "Config Service" })).toBeVisible();
  await expect(page.locator("#featureMenuGroup")).toBeVisible();
  await expect(page.locator("#featureMenuSelect option")).toContainText(["Config Service UI", "Config Catalog"]);
});

test("catalog menu entry navigates to catalog table view", async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== "with-endpoints");
  await page.goto("/ui");
  await page.locator("#featureMenuSelect").selectOption({ label: "Config Catalog" });
  await expect(page).toHaveURL(/\/catalog/);
  await expect(page.getByRole("heading", { name: "Config Catalog" })).toBeVisible();
  await expect(page.locator("#catalogBody tr")).toHaveCount(2);
  await expect(page.locator("#catalogBody")).toContainText("fluentbit-sample.yaml");
  await expect(page.locator("#catalogBody")).toContainText("fluentd-sample.conf");
});

test("catalog row click opens config-service editor with selected file", async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== "with-endpoints");
  await page.goto("/catalog");
  await page.locator("#catalogBody tr", { hasText: "fluentbit-sample.yaml" }).first().click();
  await expect(page).toHaveURL(/\/config-service\/ui/);
  await expect(page.getByRole("heading", { name: "Config Service" })).toBeVisible();
  await expect(page.locator("#open-file-display")).toHaveValue("fluentbit-sample.yaml");
});

test("catalog row click opens readonly viewer when config editor is not configured", async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== "catalog-readonly");
  await page.goto("/catalog");
  await page.locator("#catalogBody tr", { hasText: "fluentbit-sample.yaml" }).first().click();
  await expect(page.locator("#catalogReadonlyOverlay")).toBeVisible();
  await expect(page.locator("#catalogReadonlyTitle")).toContainText("fluentbit-sample.yaml");
  await expect(page.locator("#catalogReadonlyText")).toHaveValue(/service:/);
  await page.locator("#catalogReadonlyCloseTop").click();
  await expect(page.locator("#catalogReadonlyOverlay")).toHaveClass(/hidden/);
});
