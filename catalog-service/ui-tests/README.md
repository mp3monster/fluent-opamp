# Catalog Service Playwright Tests

Playwright coverage for the standalone `catalog-service` component.

## Target Suite

- Spec file: `catalog-service/ui-tests/catalog-service-freestanding.spec.js`
- Main page under test: `/catalog`
- Related navigation target: `/config-service/ui` when the config-service feature is configured

## Prompt Standard

When asking Codex to add or update catalog-service browser tests, use the same prompt structure as
`tests/playwright-test-prompt-template.md`, adapted to the catalog suite.

Use this populated suite instance as the starting point:

```text
Create Playwright regression test(s) for the standalone Catalog Service UI covering navigation,
filters, selection behavior, callback apply flow, and table persistence.

Context:
- Page: /catalog
- Fixture/project context: with-config-service and without-config-service
- Current behavior: the suite covers feature-menu visibility, row click behavior, metadata-driven
  filters, selection checkboxes, callback-based Apply behavior, column reorder persistence, reload
  cache busting, and standalone client-error reporting
- Expected behavior: standalone catalog mode keeps working with or without config-service, row
  clicks do not interfere with selection, filters narrow rows correctly, callback Apply posts the
  ordered selection, and table state persists across reloads

Test scope:
- Add test(s) to: `catalog-service/ui-tests/catalog-service-freestanding.spec.js`
- Use the existing fixture style, selectors, and project layout from that file.
- Keep tests deterministic and avoid timing flakiness.

Steps to automate:
1. Open `/catalog` and wait for `#catalogBody` to populate before interacting with rows or filters.
2. In the `with-config-service` project, verify feature-menu navigation to `/config-service/ui`
   and editor row-click behavior; in `without-config-service`, verify readonly fallback behavior.
3. Exercise the discovered-value dropdown filters for `config type (metadata)`, `engine (inferred)`,
   `version`, and `selected`.
4. Click row checkboxes and assert that selection state changes without opening the readonly overlay.
5. When `selection_callback` is present, select rows in order, click `#catalogApplySelectionBtn`,
   and assert the posted payload, returned status text, popup close, and `window.opener.postMessage`.
6. Drag reorder table columns, reload the page, and confirm the fixed `selected` column remains
   first and the reordered column persists.
7. Trigger `console.error(...)` and assert the standalone client-errors endpoint receives the payload.

Assertions:
- `#featureMenuGroup` is visible only when config-service is configured.
- Row clicks open the embedded config editor when available and `#catalogReadonlyOverlay` otherwise.
- Dropdown filters reduce visible rows using discovered metadata values.
- Checkbox clicks set selection state without changing the current page or opening the file viewer.
- Apply posts the selected files in click order and returns basename-derived target names.
- Column reorder persists across reload and the fixed `selected` column does not move.
- Browser console errors reach `/catalog/api/client-errors`.

Constraints:
- Prefer role/name selectors for buttons and explicit IDs for catalog controls.
- Reuse the freestanding fixture projects instead of adding ad hoc runtime setup when possible.
- State clearly whether the scenario depends on config-service being available.

Deliverables:
- Implement test code.
- Run `npx playwright test ui-tests/catalog-service-freestanding.spec.js --list`.
- Summarize what was added and which files changed.
```

## Current Coverage

- freestanding catalog with config-service feature configured
- freestanding catalog without config-service feature configured
- feature-menu navigation from catalog to config-service UI
- row-click editor navigation when config-service is available
- row-click readonly fallback when config-service is not available
- standalone Server Console link visibility rules
- discovered-value dropdown column filters (`config_type`, `engine`, `version`)
- selection checkbox behavior and selected/unselected filtering
- column drag-and-drop reordering persistence
- standalone client error reporting endpoint wiring

## Run

```bash
cd catalog-service
npm install
npx playwright install
npx playwright test ui-tests/catalog-service-freestanding.spec.js
```

Discovery:

```bash
cd catalog-service
npx playwright test ui-tests/catalog-service-freestanding.spec.js --list
```

## Scenario Index

- Browser scenario reference: `catalog-service/docs/TEST_CASES.md`
