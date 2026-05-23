# Freestanding Catalog Row Click Opens Config Editor

## Purpose

Confirm that clicking a catalog row opens the config-service editor with the selected source file when the config-service feature is configured.

## Fixture

- Playwright project: `with-config-service`
- Config file: `ui-tests/fixtures/with-config-service/catalog-service.json`
- Target file: `freestanding-fluentbit.yaml`

## Steps

1. Open `/catalog`.
2. Click the row for `freestanding-fluentbit.yaml`.
3. Confirm navigation to `/config-service/ui`.
4. Confirm the config-service UI is visible.
5. Confirm the open-file display contains `freestanding-fluentbit.yaml`.

## Expected Result

- row click uses the configuration-driven config editor path
- the selected file is loaded into the editor context

## Maintenance Notes

- if the config editor changes the visible selected-file control, update the final assertion
- keep the fixture file small so the editor load remains fast and deterministic
