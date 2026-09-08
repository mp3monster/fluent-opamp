const crypto = require("node:crypto");
const fs = require("node:fs/promises");
const path = require("node:path");
const { expect, test } = require("@playwright/test");

const RUNTIME_DIRECTORY = path.resolve(__dirname, ".runtime");
const FALLBACK_LOG_PATH = path.join(
  RUNTIME_DIRECTORY,
  "connection-apply-fallback.jsonl"
);

function sortJsonValue(value) {
  if (Array.isArray(value)) {
    return value.map(sortJsonValue);
  }
  if (value && typeof value === "object") {
    return Object.keys(value)
      .sort()
      .reduce((sortedObject, key) => {
        sortedObject[key] = sortJsonValue(value[key]);
        return sortedObject;
      }, {});
  }
  return value;
}

function expectedConnectionSettings(definition) {
  const canonical = JSON.stringify(sortJsonValue(definition));
  const connectionSettings = {
    hash: crypto.createHash("sha256").update(canonical, "utf8").digest("base64"),
  };
  for (const [sectionName, sectionDefinition] of Object.entries(definition || {})) {
    if (
      sectionName === "other_connections"
      || !sectionDefinition
      || sectionDefinition.enabled === false
    ) {
      continue;
    }
    const payload = {};
    if (sectionDefinition.destination_endpoint) {
      payload.destination_endpoint = sectionDefinition.destination_endpoint;
    }
    if (sectionDefinition.headers && Object.keys(sectionDefinition.headers).length) {
      payload.headers = {
        headers: Object.entries(sectionDefinition.headers).map(([key, value]) => ({
          key: String(key),
          value: String(value),
        })),
      };
    }
    if (Object.keys(payload).length) {
      connectionSettings[sectionName] = payload;
    }
  }
  return connectionSettings;
}

async function readLastFallbackRecord() {
  const logText = await fs.readFile(FALLBACK_LOG_PATH, "utf8");
  const logLines = logText
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter(Boolean);
  if (!logLines.length) {
    throw new Error(`No fallback log records were found in ${FALLBACK_LOG_PATH}`);
  }
  return JSON.parse(logLines.at(-1));
}

test.beforeEach(async ({ page }) => {
  await page.goto("/svr-credentials-manager-service/ui");
  await expect(
    page.getByRole("heading", { name: "Server Credentials Manager" })
  ).toBeVisible();
});

test("load removes stale assignments and reports the missing connection", async ({ page }) => {
  await expect(page.locator("#status")).toContainText(
    "Removed assignments for missing connections:"
  );
  await expect(page.locator("#status")).toContainText("missing-node -> missing-connection");

  const connectionRow = page.locator("#connection-items .connection-row").filter({
    hasText: "shared",
  });

  await expect(connectionRow).toBeVisible();
  await expect(connectionRow).toContainText("valid-node");
  await expect(page.locator("#connection-items")).not.toContainText("missing-node");
});

test("assignment dialog reflects the reconciled mapping state", async ({ page }) => {
  await page.getByRole("button", { name: "Assign" }).click();

  await expect(page.locator("#assignment-dialog")).toBeVisible();
  await expect(page.locator("#assignment-selected")).toContainText("valid-node");
  await expect(page.locator("#assignment-selected")).not.toContainText("missing-node");
  await expect(page.locator("#assignment-available")).not.toContainText("missing-node");
});

test("apply uses the fallback JSON log when the provider endpoint is unavailable", async ({ page }) => {
  await page.locator("#connection-items").getByRole("button", { name: "Apply" }).click();

  await expect(page.locator("#status")).toContainText(
    "Applied shared to 1 client using fallback JSON log"
  );
});

test("apply fallback log matches the saved shared connection config", async ({ page }) => {
  const connectionResponse = await page.request.get(
    "/svr-credentials-manager-service/api/v1/connections/shared"
  );
  expect(connectionResponse.ok()).toBeTruthy();
  const connectionPayload = await connectionResponse.json();

  await page.locator("#connection-items").getByRole("button", { name: "Apply" }).click();
  await expect(page.locator("#status")).toContainText(
    "Applied shared to 1 client using fallback JSON log"
  );

  const fallbackRecord = await readLastFallbackRecord();

  expect(fallbackRecord.connection_name).toBe("shared");
  expect(fallbackRecord.client_id).toBe("valid-node");
  expect(fallbackRecord.delivery).toBe("fallback_log");
  expect(fallbackRecord.server_to_agent.connection_settings).toEqual(
    expectedConnectionSettings(connectionPayload.definition)
  );
  expect(fallbackRecord.server_to_agent.connection_settings.opamp.certificate).toBeUndefined();
});
