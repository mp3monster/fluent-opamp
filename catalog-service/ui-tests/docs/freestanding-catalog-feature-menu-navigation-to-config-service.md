# Freestanding Catalog Feature Menu Navigation To Config Service

## Purpose

Confirm that the standalone catalog feature menu can navigate from `/catalog` to the freestanding embedded config-service UI when the config-service endpoint is configured.

## Fixture

- Playwright project: `with-config-service`
- Config file: `ui-tests/fixtures/with-config-service/catalog-service.json`

## Steps

1. Open `/catalog`.
2. Select `Config Service UI` from the feature menu.
3. Confirm the browser navigates to `/config-service/ui`.
4. Confirm the Config Service heading is visible.
5. Confirm the feature menu still contains both configured features.

## Expected Result

- selecting the menu item moves from the catalog to the config editor UI
- the shared top-right menu logic remains active after navigation

## Maintenance Notes

- this scenario proves the freestanding component-entrypoint wiring, not just the catalog UI itself
- if the editor route path changes, update the config fixture and assertions here
