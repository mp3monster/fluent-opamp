# Catalog Service Test Cases

This document is the maintained test-case index for `catalog-service`.
It covers unit tests, route-level tests, runtime-config tests, and the freestanding browser scenarios.

## Unit Tests

### `catalog-service/tests/test_catalog_service.py`
- `test_catalog_service_scans_configured_folders_and_header_metadata`
  - Verifies catalog scanning discovers files and extracts header metadata when present.
- `test_catalog_service_ignores_non_matching_extensions`
  - Verifies only configured file extensions are included in the catalog.
- `test_catalog_service_reads_only_allowed_files`
  - Verifies file reads are constrained to configured catalog sources.

### `catalog-service/tests/test_catalog_routes.py`
- `test_catalog_routes_render_ui_help_and_api`
  - Verifies the main UI route, help route, and API route are served.
- `test_catalog_routes_require_auth_when_standalone_auth_rejects`
  - Verifies standalone auth rejection blocks access.
- `test_catalog_routes_skip_embedded_auth_gate`
  - Verifies embedded mode leaves auth responsibility to the outer provider.
- `test_catalog_file_content_rejects_missing_and_out_of_scope_paths`
  - Verifies the readonly file endpoint rejects invalid and out-of-scope paths.
- `test_catalog_file_content_logs_rejections`
  - Verifies rejected file-content requests are logged.

### `catalog-service/tests/test_runtime_config.py`
- `test_catalog_component_entry_is_generated_when_enabled`
  - Verifies a component entry is synthesized when catalog config is enabled.
- `test_catalog_service_config_loads_sources_and_defaults`
  - Verifies freestanding catalog config loading preserves source definitions and defaults.
- `test_resolve_component_entry_points_reads_payload`
  - Verifies entry points are read from runtime config payload.
- `test_resolve_component_entries_merges_catalog_entry`
  - Verifies resolved component entries include generated catalog entries when enabled.
- `test_resolve_web_port_uses_catalog_payload`
  - Verifies freestanding web-port resolution uses catalog config values.

## Browser Tests

### `catalog-service/ui-tests/catalog-service-freestanding.spec.js`
- Playwright request prompts for this spec should follow the shared structure in `tests/playwright-test-prompt-template.md`, adapted for `/catalog` and `catalog-service/ui-tests/catalog-service-freestanding.spec.js`.
- `freestanding catalog feature menu appears with config-service`
  - Verifies the feature menu is visible when the config-service feature is configured.
- `freestanding catalog feature menu navigates to config-service`
  - Verifies selecting the feature-menu entry opens the embedded config-service UI.
- `freestanding catalog row click opens config editor`
  - Verifies row clicks open the config editor when config-service is available.
- `freestanding catalog row click opens readonly viewer`
  - Verifies row clicks fall back to the readonly viewer when config-service is not available.
- `selection checkbox click marks a row without opening the viewer`
  - Verifies checkbox interaction does not trigger the row-level navigation/view action.
- `selection filter isolates selected and unselected rows`
  - Verifies the fixed selection column supports direct selected/unselected filtering.
- `selection column remains fixed while other columns reorder`
  - Verifies drag-reordering does not move the fixed selection checkbox column.
