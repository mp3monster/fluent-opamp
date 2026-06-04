# Provider Playwright Tests

This folder contains the browser tests for the provider UI and its embedded feature-menu flows.

## Target Suite

- Spec file: `provider/ui-tests/provider-feature-menu.spec.js`
- Main pages under test:
  - `/ui`
  - `/catalog`
  - `/config-service/ui` when the embedded editor is configured

## Prompt Standard

When asking Codex to add or update provider Playwright coverage, follow the same structure as the
shared template in `tests/playwright-test-prompt-template.md`.

Use this populated suite instance as the starting point:

```text
Create Playwright regression test(s) for Provider UI feature-menu navigation, catalog integration,
and remote configuration file selection.

Context:
- Page: /ui, /catalog, and /config-service/ui when the embedded editor is configured
- Fixture/project context: with-endpoints, without-endpoints, and catalog-readonly
- Current behavior: the suite covers feature-menu visibility, navigation into the embedded catalog
  and config editor, requested configuration editability, and remote-config file selection through
  the provider Configuration tab
- Expected behavior: endpoint-dependent navigation stays correct, the requested configuration field
  is read-only only when config-service is available, and selected catalog files can be returned,
  reordered, trimmed, and sent as remote config

Test scope:
- Add test(s) to: `provider/ui-tests/provider-feature-menu.spec.js`
- Use existing test style, fixtures, and selectors from that file.
- Keep tests deterministic and avoid timing flakiness.

Steps to automate:
1. Open `/ui` in the correct Playwright project and verify whether `#featureMenuGroup` is visible.
2. Use `#featureMenuSelect` to navigate to `/config-service/ui` or `/catalog` when endpoints are configured.
3. Click catalog rows and verify they either open the embedded editor or the readonly viewer,
   depending on project setup.
4. Mock `/api/clients`, `/api/clients/<client_id>/remote-config-selection`, and
   `/api/clients/<client_id>/remote-config` when testing the Configuration tab flow.
5. Open the client modal, switch to the Configuration tab, launch the catalog popup, select files,
   apply the popup selection, reorder the chosen rows by drag-and-drop, remove unwanted rows, and
   send the remaining remote-config files.

Assertions:
- `#featureMenuGroup` is hidden when no component endpoints are configured and visible when they are.
- Navigation from the feature menu lands on the correct page and preserves the expected heading and controls.
- Catalog row clicks open `#open-file-display` in config-service when the editor is configured and
  `#catalogReadonlyOverlay` otherwise.
- `#configInput` is read-only and `#saveConfigBtn` is disabled only when config-service is available.
- The remote-config selection table preserves returned order, supports drag reorder and remove, and
  `/api/clients/<client_id>/remote-config` receives the final trimmed file list with basename target names.

Constraints:
- Prefer role/name selectors for tabs and buttons and explicit IDs for provider modal fields.
- Reuse the existing route mocks and fixture JSON files where possible.
- If endpoint availability matters, state which Playwright project should cover it.

Deliverables:
- Implement test code.
- Run `npx playwright test ui-tests/provider-feature-menu.spec.js --list` and confirm discovery.
- Summarize what was added and which files changed.
```

## Covered Scenarios

1. Provider started **without** configured component endpoints:
   - feature dropdown is hidden
2. Provider started **with** configured component endpoints:
   - feature dropdown is visible
   - config-service menu item is visible
   - catalog menu item is visible
3. Navigation checks:
   - selecting **Config Editor** opens `/config-service/ui`
   - selecting **Config Catalog** opens `/catalog` and renders indexed rows
4. Catalog file open behavior:
   - when config-service is configured as a component endpoint, clicking a catalog row opens the config editor
   - when config-service is not configured, clicking a catalog row opens the readonly catalog file viewer
5. Remote-config selection flow:
   - selected catalog files return to the provider modal
   - the selected list can be reordered and trimmed before send
6. Requested configuration editability:
   - read-only when config-service is available
   - editable when config-service is not available

## Run

From repository root:

```bash
cd provider
npm install
npx playwright install
npx playwright test ui-tests/provider-feature-menu.spec.js
```

Discovery:

```bash
cd provider
npx playwright test ui-tests/provider-feature-menu.spec.js --list
```

## Configuration And Fixtures

- Playwright config: `provider/playwright.config.js`
- Fixtures:
  - `provider/ui-tests/fixtures/opamp-with-endpoints.json`
  - `provider/ui-tests/fixtures/opamp-without-endpoints.json`
  - `provider/ui-tests/fixtures/opamp-catalog-readonly.json`
