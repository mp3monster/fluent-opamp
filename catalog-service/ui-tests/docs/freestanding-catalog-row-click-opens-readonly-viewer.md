# Freestanding Catalog Row Click Opens Readonly Viewer

## Purpose

Confirm that the standalone catalog falls back to the built-in readonly viewer when the config-service feature is not configured.

## Fixture

- Playwright project: `without-config-service`
- Config file: `ui-tests/fixtures/without-config-service/catalog-service.json`
- Target file: `freestanding-fluentbit.yaml`

## Steps

1. Open `/catalog`.
2. Confirm the feature menu does not list `Config Service UI`.
3. Click the row for `freestanding-fluentbit.yaml`.
4. Confirm the readonly overlay opens.
5. Confirm the dialog title contains the selected filename.
6. Confirm file content is loaded into the readonly textarea.
7. Close the overlay and confirm it is hidden again.

## Expected Result

- row click does not attempt editor navigation
- the readonly viewer provides a safe fallback for catalog inspection

## Maintenance Notes

- this scenario should continue to pass even if catalog styling assets fail to load; it is focused on behavior
- if the readonly dialog ids change, update both the Playwright test and this document
