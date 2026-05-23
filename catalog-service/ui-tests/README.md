# Catalog Service UI Tests

Playwright coverage for the standalone `catalog-service` component.

Test-case index:

- `../docs/TEST_CASES.md`

Current coverage:

- freestanding catalog with config-service feature configured
- freestanding catalog without config-service feature configured
- feature-menu navigation from catalog to config-service UI
- row-click editor navigation when config-service is available
- row-click readonly fallback when config-service is not available

Scenario maintenance documents live in:

- `docs/freestanding-catalog-feature-menu-with-config-service.md`
- `docs/freestanding-catalog-feature-menu-navigation-to-config-service.md`
- `docs/freestanding-catalog-row-click-opens-config-editor.md`
- `docs/freestanding-catalog-row-click-opens-readonly-viewer.md`
