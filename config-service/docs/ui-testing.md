# UI Testing

`config-service` now includes browser-based UI behavior tests using Playwright.

## What these tests cover
The Playwright suite focuses on high-value UI behaviors that are awkward to verify with backend tests alone.

Current test catalog (`config-service/ui-tests/config-ui.spec.js`):

1. `service log_level dropdown shows all expected enum values`
   - Verifies service `log_level` exposes the expected enum choices.
2. `parser format dropdown loads Fluent Bit parser formats`
   - Verifies parser formats are loaded and include expected entries (for example `json`).
3. `added plugin appears immediately without changing config type or version`
   - Verifies newly added plugin cards appear immediately, without forcing type/version changes.
4. `console errors are posted to the server client-errors endpoint`
   - Verifies browser `console.error(...)` is forwarded to `/config-service/api/v1/client-errors`.
5. `plugin panel visibility stays mode-consistent when switching config type`
   - Verifies Fluent Bit/Fluentd mode switching keeps plugin/label/worker panels consistent.
6. `plugin field help tooltip does not include raw URLs`
   - Verifies plugin field tooltip text remains human-readable and not raw links.
7. `loading partial Fluent Bit YAML shows loaded sections, status warning, and validation issue lines`
   - Verifies partial-load behavior, warning status, and validation line hints.
8. `service field help button keeps human-readable tooltip text only`
   - Verifies service field help text quality constraints.
9. `renderer panel exposes include loaded files toggle`
   - Verifies renderer controls include the include-files toggle.
10. `metadata keys are separated from normal environment variables when loading YAML`
    - Verifies `_metadata.*` keys are shown in metadata panel, not normal env panel.
11. `metadata keys can be added and are saved with the _metadata prefix`
    - Verifies metadata add/edit/save path and key normalization.
12. `header comments are written first when saving with environment variables`
    - Verifies save output includes header comments before config body.
13. `header comments are prepended to rendered configuration output`
    - Verifies rendered output in UI includes header comments at top.

Quick listing command:

```bash
cd config-service
npm run ui:test -- --list
```

## Location
- Playwright config: `config-service/playwright.config.js`
- Browser tests: `config-service/ui-tests/`
- UI fixtures: `config-service/ui-tests/fixtures/`

## Prerequisites
1. Node.js with `npm` / `npx`
2. Python 3.10+
3. Linux browser runtime dependencies required by Playwright Chromium

## Install and run manually
From repository root:

```bash
cd config-service
npm install
npx playwright install-deps chromium
npx playwright install chromium
npm run ui:test
```

Headed mode:

```bash
cd config-service
npm run ui:test:headed
```

## One-command runner
From repository root:

```bash
config-service/dev-tools/run_ui_quality_checks.sh
```

This runner will:
1. install Node dependencies
2. install the Chromium browser used by Playwright
3. run the Playwright UI suite

Note:
1. On Linux, Playwright may still require system packages such as `libnspr4`.
2. If browser launch fails with a missing shared-library error, run:

```bash
cd config-service
npx playwright install-deps chromium
```

3. `install-deps` may require `sudo`, depending on the machine.

## Container runner (recommended for dependency issues)
From repository root:

```bash
config-service/dev-tools/run_ui_quality_checks_in_container.sh
```

To run only the metadata/header-comments scenarios:

```bash
config-service/dev-tools/run_ui_quality_checks_in_container.sh -g "metadata|header comments"
```

This runner:
1. verifies Docker daemon availability
2. runs Playwright inside `mcr.microsoft.com/playwright:v1.59.1-noble`
3. installs Python and Node dependencies in-container
4. executes the UI tests, forwarding any extra Playwright arguments

## Runtime model
The Playwright suite tests the Python-served UI, not the old standalone frontend dev server.

Playwright starts:
1. `python3 -m config_service`
2. with `APP_ENABLE_DEV_FEATURES=1`
3. on port `8091`

That means the tests exercise the actual packaged HTML/CSS/JS served by Quart.

## Notes on tooltip testing
Native browser tooltips are not asserted visually.

Instead, tests verify:
1. the `title` attribute text
2. whether help controls are enabled or disabled
3. whether linked documentation targets are correct

That approach is more stable across browsers and CI environments.
