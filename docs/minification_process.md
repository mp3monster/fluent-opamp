# Provider UI Minification Process

Provider UI minification is a small, explicit build step for the JavaScript files
served by `provider`.

## Scope

The provider runtime uses four JavaScript assets from
`provider/src/opamp_provider/html/`:

- `web_ui_state.js`
- `web_ui_functions.js`
- `web_ui_framework.js`
- `web_ui_bindings.js`

The minification process generates a matching `.mini.js` file beside each source
file:

- `web_ui_state.mini.js`
- `web_ui_functions.mini.js`
- `web_ui_framework.mini.js`
- `web_ui_bindings.mini.js`

## Build script

The canonical minification entry point is:

- `scripts/build_provider_ui_compact_assets.py`

It uses `npx esbuild --minify --legal-comments=none` and writes deterministic
output files next to the source assets.

The canonical asset list is shared in:

- `provider/src/opamp_provider/ui_assets.py`

Both provider runtime and the minification script read from that shared module so
the asset set stays aligned.

Manual usage:

```bash
python3 scripts/build_provider_ui_compact_assets.py --repo-root .
```

Clean-only usage:

```bash
python3 scripts/build_provider_ui_compact_assets.py --repo-root . --clean-only
```

## Runtime selection behavior

Provider runtime asset selection is controlled by `APP_ENABLE_DEV_FEATURES`.

- When `APP_ENABLE_DEV_FEATURES` is truthy (`1`, `true`, `yes`, `on`), provider
  prefers the readable source files.
- Otherwise, provider prefers the compacted `.mini.js` files.
- If the preferred file is missing, provider falls back to the available variant
  and logs a warning.

This behavior is implemented in:

- `provider/src/opamp_provider/app.py`

## Where minification is applied

Minification is expected to run in the main packaging and quality workflows.

### Security checks

`scripts/security_checks.py` runs provider UI compaction as the first step
before tests and security scans.

It also removes `APP_ENABLE_DEV_FEATURES` from the check environment so the
checks validate the non-dev asset-selection path.

### Provider/consumer artifact build

Both wrapper scripts:

- `scripts/build_artifacts.sh`
- `scripts/build_artifacts.cmd`

run `scripts/security_checks.py`, so provider UI compaction is part of the
standard artifact build path.

### Wheel build and publish flow

`scripts/build_and_publish_wheels.py` refreshes the provider UI compact assets
before building wheels unless `--skip-ui-compaction` is supplied.

## Consistency expectation

Whenever a provider UI JavaScript asset is added, renamed, or removed, update
the shared definitions in:

- `provider/src/opamp_provider/ui_assets.py`

If the runtime serves a new asset route, also update the relevant provider route
or asset-loading call in `provider/src/opamp_provider/app.py`.

Keeping the shared asset definition current prevents release builds from
silently falling back from minified assets to source assets.
