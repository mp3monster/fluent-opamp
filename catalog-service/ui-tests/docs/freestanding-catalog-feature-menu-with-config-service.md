# Freestanding Catalog Feature Menu With Config Service

## Purpose

Confirm that the standalone `catalog-service` UI exposes the top-right feature menu with a `Config Service UI` entry when the freestanding configuration includes the config-service component entrypoint.

## Fixture

- Playwright project: `with-config-service`
- Config file: `ui-tests/fixtures/with-config-service/catalog-service.json`

## Steps

1. Open `/catalog`.
2. Confirm the catalog page heading is visible.
3. Confirm the feature menu group is visible.
4. Confirm the feature menu options include:
   - `Config Catalog`
   - `Config Service UI`

## Expected Result

- the standalone catalog page exposes the configuration-driven cross-feature menu
- the config-service feature is advertised when configured

## Maintenance Notes

- if labels change, update both the fixture config and this scenario document
- if the menu becomes hidden when only one item is present, keep this scenario focused on the configured config-service case only
