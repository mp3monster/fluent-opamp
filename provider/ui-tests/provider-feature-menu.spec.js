import { expect, test } from "@playwright/test";

function basenameForPath(pathValue) {
  const segments = String(pathValue || "").split(/[\\/]/);
  return String(segments[segments.length - 1] || "");
}

async function mockSingleClient(page, clientId = "abababababababababababababababab") {
  await page.context().route(/\/api\/clients(?:\?.*)?$/, async (route) => {
    if (route.request().method() !== "GET") {
      await route.continue();
      return;
    }
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        clients: [
          {
            client_id: clientId,
            agent_description: "",
            capabilities: ["Reports Status", "Accepts Remote Config"],
            current_config: "service:\n  flush: 1\n",
            current_config_version: "v1",
            requested_config: "service:\n  flush: 5\n",
            requested_config_version: "v2",
            disconnected: false,
            events: [],
            first_seen: "2026-06-03T08:00:00Z",
            last_channel: "HTTP",
            last_communication: "2026-06-03T08:05:00Z",
            remote_addr: "127.0.0.1",
            client_version: "1.2.3",
            health: {
              healthy: true,
            },
            commands: [],
            provider_remote_config_enabled: true,
            remote_config_files_allowed: true,
            remote_config_capability_reported: true,
          },
        ],
        total: 1,
        pending_approval_total: 0,
      }),
    });
  });

  return clientId;
}

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
  await expect(page.locator("#featureMenuSelect option")).toContainText(["Config Editor", "Config Catalog"]);
});

test("config-service menu entry navigates to embedded config-service UI", async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== "with-endpoints");
  await page.goto("/ui");
  await page.locator("#featureMenuSelect").selectOption({ label: "Config Editor" });
  await expect(page).toHaveURL(/\/config-service\/ui/);
  await expect(page.getByRole("heading", { name: "Config Service" })).toBeVisible();
  await expect(page.locator("#featureMenuGroup")).toBeVisible();
  await expect(page.locator("#featureMenuSelect option")).toContainText(["Config Editor", "Config Catalog"]);
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

test("requested configuration is read-only when config-service is available", async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== "with-endpoints");

  await mockSingleClient(page);
  await page.goto("/ui");
  await page.locator("#clientBody tr").first().click();
  await page.getByRole("button", { name: "Configuration" }).click();

  await expect(page.locator("#configInput")).toHaveJSProperty("readOnly", true);
  await expect(page.locator("#saveConfigBtn")).toBeDisabled();
});

test("requested configuration stays editable without config-service", async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== "without-endpoints");

  await mockSingleClient(page);
  await page.goto("/ui");
  await page.locator("#clientBody tr").first().click();
  await page.getByRole("button", { name: "Configuration" }).click();

  await expect(page.locator("#configInput")).toHaveJSProperty("readOnly", false);
  await expect(page.locator("#saveConfigBtn")).toBeEnabled();
});

test("optional columns include first registered", async ({ page }) => {
  await mockSingleClient(page);
  await page.goto("/ui");

  await expect(page.locator("#clientBody tr")).toHaveCount(1);
  await page.locator("#toggleColumnsBtn").click();

  const firstRegisteredToggle = page.locator('input[data-column-toggle="first_registered"]');
  await expect(firstRegisteredToggle).toBeVisible();
  await firstRegisteredToggle.check();

  const expectedFirstRegistered = await page.evaluate(
    () => new Date("2026-06-03T08:00:00Z").toLocaleString()
  );

  await expect(page.locator("#clientTableHeaderRow")).toContainText("First Registered");
  await expect(page.locator("#clientBody tr td")).toContainText([expectedFirstRegistered]);
});

test("optional columns include health status with summary styling", async ({ page }) => {
  await mockSingleClient(page);
  await page.goto("/ui");

  await expect(page.locator("#clientBody tr")).toHaveCount(1);
  await page.locator("#toggleColumnsBtn").click();

  const healthStatusToggle = page.locator('input[data-column-toggle="health_status"]');
  await expect(healthStatusToggle).toBeVisible();
  await healthStatusToggle.check();

  await expect(page.locator('th[data-column-key="health_status"]')).toContainText(/Health\s*Status/);
  await expect(page.locator('th[data-column-key="health_status"]')).toHaveJSProperty(
    "innerHTML",
    "Health<br>Status"
  );
  await expect(page.locator("#clientBody .health-text-healthy")).toContainText("healthy");

  await page.locator("#clientBody tr").first().click();
  await expect(page.locator("#modalFields .health-text-healthy")).toContainText("healthy");
});

test("provider UI uses connection status labels in table and summary", async ({ page }) => {
  await mockSingleClient(page);
  await page.goto("/ui");

  await expect(page.locator('th[data-column-key="status"]')).toContainText(/Connection\s*Status/);
  await expect(page.locator('th[data-column-key="status"]')).toHaveJSProperty(
    "innerHTML",
    "Connection<br>Status"
  );
  await expect(page.locator('th[data-column-key="config_version"]')).toContainText(/Config\s*Version/);
  await expect(page.locator('th[data-column-key="config_version"]')).toHaveJSProperty(
    "innerHTML",
    "Config<br>Version"
  );

  await page.locator("#clientBody tr").first().click();
  await expect(page.locator("#modalFields")).toContainText("Connection Status");
});

test("client data panel stays open across UI refresh updates", async ({ page }) => {
  let clientVersion = "1.2.3";

  await page.context().route(/\/api\/clients(?:\?.*)?$/, async (route) => {
    if (route.request().method() !== "GET") {
      await route.continue();
      return;
    }
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        clients: [
          {
            client_id: "abababababababababababababababab",
            agent_description: "",
            capabilities: ["Reports Status", "Accepts Remote Config"],
            current_config: "service:\n  flush: 1\n",
            current_config_version: "v1",
            requested_config: "service:\n  flush: 5\n",
            requested_config_version: "v2",
            disconnected: false,
            events: [],
            first_seen: "2026-06-03T08:00:00Z",
            last_channel: "HTTP",
            last_communication: "2026-06-03T08:05:00Z",
            remote_addr: "127.0.0.1",
            client_version: clientVersion,
            health: {
              healthy: true,
            },
            commands: [],
            provider_remote_config_enabled: true,
            remote_config_files_allowed: true,
            remote_config_capability_reported: true,
          },
        ],
        total: 1,
        pending_approval_total: 0,
      }),
    });
  });

  await page.goto("/ui");
  await page.locator("#refreshInput").fill("5");
  await page.locator("#refreshInput").dispatchEvent("change");

  await page.locator("#clientBody tr").first().click();
  await page.locator("#toggleDataBtn").click();
  await expect(page.locator("#clientDataPanel")).toBeVisible();
  await expect(page.locator("#clientDataYaml")).toContainText("client_version: 1.2.3");

  clientVersion = "9.9.9";
  await page.waitForTimeout(5500);

  await expect(page.locator("#clientDataPanel")).toBeVisible();
  await expect(page.locator("#toggleDataBtn")).toBeHidden();
  await expect(page.locator("#clientDataYaml")).toContainText("client_version: 9.9.9");
});

test("provider configuration tab collects catalog selections and sends remote config files", async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== "with-endpoints");

  const clientId = "abababababababababababababababab";
  let selectionCallbackPayload = null;
  let sendRemoteConfigPayload = null;

  await page.context().route(/\/api\/clients(?:\?.*)?$/, async (route) => {
    if (route.request().method() !== "GET") {
      await route.continue();
      return;
    }
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        clients: [
          {
            client_id: clientId,
            agent_description: "",
            capabilities: ["Reports Status", "Accepts Remote Config"],
            current_config: "service:\n  flush: 1\n",
            current_config_version: "v1",
            requested_config: "",
            requested_config_version: "--",
            disconnected: false,
            events: [],
            first_seen: "2026-06-03T08:00:00Z",
            last_channel: "HTTP",
            last_communication: "2026-06-03T08:05:00Z",
            remote_addr: "127.0.0.1",
            client_version: "1.2.3",
            commands: [],
            provider_remote_config_enabled: true,
            remote_config_files_allowed: true,
            remote_config_capability_reported: true,
          },
        ],
        total: 1,
        pending_approval_total: 0,
      }),
    });
  });

  await page.context().route(
    new RegExp(`/api/clients/${clientId}/remote-config-selection$`),
    async (route) => {
      selectionCallbackPayload = JSON.parse(route.request().postData() || "{}");
      const files = Array.isArray(selectionCallbackPayload.files)
        ? selectionCallbackPayload.files.map((item) => {
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
          client_id: clientId,
          files,
        }),
      });
    }
  );

  await page.context().route(
    new RegExp(`/api/clients/${clientId}/remote-config$`),
    async (route) => {
      sendRemoteConfigPayload = JSON.parse(route.request().postData() || "{}");
      const files = Array.isArray(sendRemoteConfigPayload.files)
        ? sendRemoteConfigPayload.files.map((item) => ({
          source_path: String(item.source_path || ""),
          target_name: String(item.target_name || ""),
          content_type: "text/plain",
          size_bytes: 10,
        }))
        : [];
      await route.fulfill({
        status: 201,
        contentType: "application/json",
        body: JSON.stringify({
          client_id: clientId,
          queued_action: "apply_config",
          config_hash: "deadbeef",
          payload_size_bytes: 123,
          files,
        }),
      });
    }
  );

  await page.goto("/ui");
  await expect(page.getByRole("heading", { name: "OpAMP Server Console" })).toBeVisible();
  await expect(page.locator("#clientBody tr")).toHaveCount(1);

  await page.locator("#clientBody tr").first().click();
  await page.getByRole("button", { name: "Configuration" }).click();
  await expect(page.locator("#remoteConfigEnhancedPanel")).toBeVisible();
  await expect(page.locator("#selectRemoteConfigsBtn")).toBeVisible();

  const popupPromise = page.waitForEvent("popup");
  await page.locator("#selectRemoteConfigsBtn").click();
  const popup = await popupPromise;
  await expect(popup.getByRole("heading", { name: "Config Catalog" })).toBeVisible();

  await popup.locator("#catalogBody tr", { hasText: "fluentd-sample.conf" }).first().locator('input[type="checkbox"]').click();
  await popup.locator("#catalogBody tr", { hasText: "fluentbit-sample.yaml" }).first().locator('input[type="checkbox"]').click();

  await Promise.all([
    popup.waitForEvent("close"),
    popup.locator("#catalogApplySelectionBtn").click(),
  ]);

  await expect(page.locator("#remoteConfigSelectionBody tr")).toHaveCount(2);
  await expect(page.locator("#remoteConfigSelectionBody tr").nth(0)).toContainText("fluentd-sample.conf");
  await expect(page.locator("#remoteConfigSelectionBody tr").nth(1)).toContainText("fluentbit-sample.yaml");

  await page.locator("#remoteConfigSelectionBody tr").nth(1).dragTo(
    page.locator("#remoteConfigSelectionBody tr").nth(0)
  );
  await expect(page.locator("#remoteConfigSelectionBody tr").nth(0)).toContainText("fluentbit-sample.yaml");

  await page.locator("#remoteConfigSelectionBody tr").nth(1).getByRole("button", { name: "Remove" }).click();
  await expect(page.locator("#remoteConfigSelectionBody tr")).toHaveCount(1);
  await expect(page.locator("#remoteConfigSelectionBody tr").nth(0)).toContainText("fluentbit-sample.yaml");

  await page.locator("#sendRemoteConfigFilesBtn").click();
  await expect(page.locator("#remoteConfigStatus")).toContainText("Queued 1 remote config file.");

  expect(selectionCallbackPayload).toEqual({
    files: [
      {
        source_path: expect.stringMatching(/fluentd-sample\.conf$/),
      },
      {
        source_path: expect.stringMatching(/fluentbit-sample\.yaml$/),
      },
    ],
  });
  expect(sendRemoteConfigPayload).toEqual({
    files: [
      {
        source_path: expect.stringMatching(/fluentbit-sample\.yaml$/),
        target_name: "fluentbit-sample.yaml",
      },
    ],
  });
});
