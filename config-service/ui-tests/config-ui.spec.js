import { expect, test } from "@playwright/test";
import fs from "node:fs/promises";
import path from "node:path";

test.beforeEach(async ({ page }) => {
  await page.addInitScript(() => {
    Object.defineProperty(window, "showSaveFilePicker", {
      configurable: true,
      writable: true,
      value: undefined,
    });
  });
  await page.goto("/config-service/ui");
  await expect(page.getByRole("heading", { name: "Config Service" })).toBeVisible();
  await expect.poll(async () => page.locator("#plugin-name option").count()).toBeGreaterThan(0);
});

test("service log_level dropdown shows all expected enum values", async ({ page }) => {
  await page.getByLabel("Option").selectOption("log_level");
  const options = await page.locator("#service-value option").allTextContents();
  expect(options).toEqual(["off", "trace", "debug", "info", "warn", "error"]);
});

test("parser format dropdown loads Fluent Bit parser formats", async ({ page }) => {
  const parserOptions = await page.locator("#parser-format option").allTextContents();
  expect(parserOptions.length).toBeGreaterThan(0);
  expect(parserOptions).toContain("json");
});

test("added plugin appears immediately without changing config type or version", async ({ page }) => {
  const initialConfigType = await page.locator("#config-type-select").inputValue();
  const initialVersion = await page.locator("#version-select").inputValue();

  await page.locator("#plugin-section").selectOption("inputs");
  const pluginName = (await page.locator("#plugin-name").inputValue()).trim();
  expect(pluginName.length).toBeGreaterThan(0);

  await page.getByRole("button", { name: "Add Plugin" }).click();
  await expect(page.locator("#plugin-list")).toContainText(pluginName);

  await expect(page.locator("#config-type-select")).toHaveValue(initialConfigType);
  await expect(page.locator("#version-select")).toHaveValue(initialVersion);
});

test("console errors are posted to the server client-errors endpoint", async ({ page }) => {
  const requestPromise = page.waitForRequest((request) => {
    if (!request.url().includes("/config-service/api/v1/client-errors")) {
      return false;
    }
    if (request.method() !== "POST") {
      return false;
    }
    return request.postData()?.includes("playwright synthetic console error") || false;
  });

  await page.evaluate(() => {
    console.error("playwright synthetic console error");
  });

  const request = await requestPromise;
  expect(request).toBeTruthy();
});

test("plugin panel visibility stays mode-consistent when switching config type", async ({ page }) => {
  await expect(page.locator("#add-plugin-panel")).toBeVisible();
  await expect(page.locator("#labels-panel")).toBeHidden();
  await expect(page.locator("#workers-panel")).toBeHidden();

  await page.locator("#config-type-select").selectOption("fluentd");

  await expect(page.locator("#add-plugin-panel")).toBeHidden();
  await expect(page.locator("#labels-panel")).toBeVisible();
  await expect(page.locator("#workers-panel")).toBeVisible();
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

test("renderer panel exposes include loaded files toggle", async ({ page }) => {
  const renderCard = page.locator("#render-card");
  await expect(renderCard).toBeVisible();

  const includeToggle = renderCard.locator("#render-include-toggle");
  await expect(includeToggle).toBeVisible();
  await expect(renderCard).toContainText("Include loaded files");
});

test("metadata keys are separated from normal environment variables when loading YAML", async ({ page }) => {
  const fixturePath = path.resolve("ui-tests/fixtures/fluentbit-metadata-env.yaml");
  await page.locator("#open-file").setInputFiles(fixturePath);

  await expect(page.locator("#env-list")).toContainText("LOG_LEVEL");
  await expect(page.locator("#env-list")).not.toContainText("_metadata.config_version");
  await expect(page.locator("#metadata-env-list")).toContainText("config_version");
  await expect(page.locator("#metadata-env-list")).toContainText("configuration_date");
});

test("metadata keys can be added and are saved with the _metadata prefix", async ({ page }) => {
  await page.getByRole("button", { name: "New Configuration" }).click();
  await page.locator("#metadata-env-key-input").fill("_.metadata.team_owner");
  await page.locator("#metadata-env-value-input").fill("platform-observability");
  await page.getByRole("button", { name: "Add Metadata Variable" }).click();

  await page.locator("#metadata-env-key-input").fill("config_version");
  await page.locator("#metadata-env-value-input").fill("v-next");
  await page.getByRole("button", { name: "Add Metadata Variable" }).click();

  const [download] = await Promise.all([
    page.waitForEvent("download"),
    page.getByRole("button", { name: "Save" }).click(),
  ]);
  const saved = await fs.readFile((await download.path()) || "", "utf-8");

  expect(saved).toContain('"_metadata.team_owner": "platform-observability"');
  expect(saved).toContain('"_metadata.config_version": "v-next"');
  expect(saved).not.toContain('"_.metadata.');
});

test("header comments are written first when saving with environment variables", async ({ page }) => {
  await page.getByRole("button", { name: "New Configuration" }).click();
  await page.locator("#header-comments-toggle").click();
  await page.locator("#header-comments-input").fill("Owned by Team A\\nValidated before deploy");

  await page.locator("#env-key-input").fill("ENV_NAME");
  await page.locator("#env-value-input").fill("prod");
  await page.getByRole("button", { name: "Add Environment Variable" }).click();

  const [download] = await Promise.all([
    page.waitForEvent("download"),
    page.getByRole("button", { name: "Save" }).click(),
  ]);
  const saved = await fs.readFile((await download.path()) || "", "utf-8");

  expect(saved.startsWith("// Owned by Team A\\n// Validated before deploy\\n")).toBeTruthy();
  expect(saved).toContain('"ENV_NAME": "prod"');
  expect(saved.indexOf("// Owned by Team A")).toBeLessThan(saved.indexOf('"ENV_NAME": "prod"'));
});

test("view raw opens a read-only resizable text dialog", async ({ page }) => {
  await page.getByRole("button", { name: "New Configuration" }).click();

  await page.getByRole("button", { name: "View Raw" }).click();

  const dialog = page.locator("#raw-config-dialog");
  const rawText = page.locator("#raw-config-text");
  await expect(dialog).toBeVisible();
  await expect(rawText).toHaveValue(/\/\/ config-service: config_type=fluentbit/);
  await expect(rawText).toHaveValue(/"configType": "fluentbit"/);
  await expect(rawText).toHaveAttribute("readonly", "");
  await expect(dialog.getByRole("button")).toHaveCount(1);
  await expect(dialog.getByRole("button")).toHaveText("Close");
  await expect(page.locator(".raw-config-modal")).toHaveCSS("resize", "both");
  await expect(rawText).toHaveCSS("overflow-x", "auto");

  await page.getByRole("button", { name: "Close" }).click();
  await expect(dialog).toBeHidden();
});

test("header comments are prepended to rendered configuration output", async ({ page }) => {
  await page.getByRole("button", { name: "New Configuration" }).click();
  await page.locator("#header-comments-toggle").click();
  await page.locator("#header-comments-input").fill("Owned by Team A\\nValidated before deploy");

  await page.locator("#env-key-input").fill("ENV_NAME");
  await page.locator("#env-value-input").fill("prod");
  await page.getByRole("button", { name: "Add Environment Variable" }).click();

  await page.getByRole("button", { name: "Render" }).click();

  await expect(page.locator("#yaml-output")).toContainText("# Owned by Team A");
  await expect(page.locator("#yaml-output")).toContainText("# Validated before deploy");
});
