# Provider Playwright Tests

This folder contains browser tests for provider feature-menu behavior and catalog navigation.

## Covered scenarios

1. Provider started **without** configured component endpoints:
   - feature dropdown is hidden
2. Provider started **with** configured component endpoints:
   - feature dropdown is visible
   - config-service menu item is visible
   - catalog menu item is visible
3. Navigation checks:
   - selecting **Config Service UI** opens `/config-service/ui`
   - selecting **Config Catalog** opens `/catalog` and renders indexed rows
4. Catalog file open behavior:
   - when config-service is configured as a component endpoint, clicking a catalog row opens the config editor
   - when config-service is not configured, clicking a catalog row opens the readonly catalog file viewer

## Run

From repository root:

```bash
cd provider
npm install
npx playwright install
npm run test:ui
```

Configuration file:

- `provider/playwright.config.js`

Fixtures:

- `provider/ui-tests/fixtures/opamp-with-endpoints.json`
- `provider/ui-tests/fixtures/opamp-without-endpoints.json`
- `provider/ui-tests/fixtures/opamp-catalog-readonly.json`
