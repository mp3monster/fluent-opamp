import { expect, test } from "@playwright/test";
import path from "node:path";

test.beforeEach(async ({ page }) => {
  await page.goto("/config-service/ui");
  await expect(page.getByRole("heading", { name: "Config Service" })).toBeVisible();
  await expect.poll(async () => page.locator("#plugin-name option").count()).toBeGreaterThan(0);
});

test("service log_level dropdown shows all expected enum values", async ({ page }) => {
  await page.getByLabel("Option").selectOption("log_level");
  const options = await page.locator("#service-value option").allTextContents();
  expect(options).toEqual(["off", "trace", "debug", "info", "warn", "error"]);
});

test("service _meta help link and comment toggle are available when service card is shown", async ({ page }) => {
  await page.getByLabel("Option").selectOption("daemon");
  await page.locator("#service-value").selectOption("on");
  await page.getByRole("button", { name: "Add Service Field" }).click();

  const serviceCard = page.locator(".service-card");
  await expect(serviceCard).toBeVisible();

  const metaHelpLink = serviceCard.locator('a.icon-help[href="/config-service/ui/docs/meta-comments"]');
  await expect(metaHelpLink).toBeVisible();
  await expect(metaHelpLink).toHaveAttribute("title", "Open help for comments and field comments.");
  await expect(metaHelpLink).toHaveAttribute("target", "_blank");

  const commentToggle = serviceCard.locator(".icon-note");
  await commentToggle.click();
  await expect(serviceCard.locator(".comment-editor textarea")).toBeVisible();
});

test("plugin field help tooltip does not include raw URLs", async ({ page }) => {
  await page.locator("#plugin-section").selectOption("inputs");
  await page.locator("#plugin-name").selectOption("dummy");
  await page.getByRole("button", { name: "Add Plugin" }).click();

  const pluginCard = page.locator(".plugin-card").filter({ hasText: "dummy" }).first();
  await expect(pluginCard).toBeVisible();

  const fieldHelp = pluginCard.locator(".field-row .icon-help").first();
  await expect(fieldHelp).toBeVisible();

  const title = await fieldHelp.getAttribute("title");
  expect(title).toBeTruthy();
  expect(title).not.toContain("http://");
  expect(title).not.toContain("https://");
});

test("loading partial Fluent Bit YAML shows loaded sections, status warning, and validation issue lines", async ({
  page,
}) => {
  const fixturePath = path.resolve("ui-tests/fixtures/fluentbit-partial-load.yaml");
  await page.locator("#open-file").setInputFiles(fixturePath);

  await expect(page.locator("#status-message")).toContainText("There were problems loading configuration file");
  await expect(page.locator("#plugin-list")).toContainText("dummy");
  await expect(page.locator("#plugin-list")).toContainText("null");
  await expect(page.locator("#validation-issues")).toContainText("Ignored YAML section");
  await expect(page.locator("#validation-issues")).toContainText("Line:");
});

test("service field help button keeps human-readable tooltip text only", async ({ page }) => {
  await page.getByLabel("Option").selectOption("log_level");
  await page.locator("#service-value").selectOption("info");
  await page.getByRole("button", { name: "Add Service Field" }).click();

  const serviceRowHelp = page.locator(".service-row .icon-help").first();
  await expect(serviceRowHelp).toBeVisible();

  const title = await serviceRowHelp.getAttribute("title");
  expect(title).toBeTruthy();
  expect(title).not.toContain("http://");
  expect(title).not.toContain("https://");
});
