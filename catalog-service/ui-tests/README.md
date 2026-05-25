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
- standalone provider link visibility rules
- discovered-value dropdown column filters (`config_type`, `engine`, `version`)
- column drag-and-drop reordering persistence
- reload UI cache-busting behavior
- standalone client error reporting endpoint wiring

Canonical scenario and maintenance reference:

- `../docs/TEST_CASES.md`
