// Test-case reference: catalog-service/docs/TEST_CASES.md
// Detailed browser scenarios: catalog-service/ui-tests/docs/
import { expect, test } from "@playwright/test";

test("freestanding catalog shows config-service feature menu entry when configured", async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== "with-config-service");
  await page.goto("/catalog");
  await expect(page.getByRole("heading", { name: "Config Catalog" })).toBeVisible();
  await expect(page.locator("#featureMenuGroup")).toBeVisible();
  await expect(page.locator("#featureMenuSelect option")).toContainText([
    "Config Catalog",
    "Config Service UI",
  ]);
});

test("freestanding catalog feature menu navigates to config-service UI when configured", async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== "with-config-service");
  await page.goto("/catalog");
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
  test.skip(testInfo.project.name !== "with-config-service");
  await page.goto("/catalog");
  await page.locator("#catalogBody tr", { hasText: "freestanding-fluentbit.yaml" }).first().click();
  await expect(page).toHaveURL(/\/config-service\/ui/);
  await expect(page.getByRole("heading", { name: "Config Service" })).toBeVisible();
  await expect(page.locator("#open-file-display")).toHaveValue("freestanding-fluentbit.yaml");
});

test("freestanding catalog falls back to readonly viewer when config-service is not configured", async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== "without-config-service");
  await page.goto("/catalog");
  await expect(page.getByRole("heading", { name: "Config Catalog" })).toBeVisible();
  await expect(page.locator("#featureMenuSelect option")).not.toContainText(["Config Service UI"]);
  await page.locator("#catalogBody tr", { hasText: "freestanding-fluentbit.yaml" }).first().click();
  await expect(page.locator("#catalogReadonlyOverlay")).toBeVisible();
  await expect(page.locator("#catalogReadonlyTitle")).toContainText("freestanding-fluentbit.yaml");
  await expect(page.locator("#catalogReadonlyText")).toHaveValue(/service:/);
  await page.locator("#catalogReadonlyCloseTop").click();
  await expect(page.locator("#catalogReadonlyOverlay")).toHaveClass(/hidden/);
});
