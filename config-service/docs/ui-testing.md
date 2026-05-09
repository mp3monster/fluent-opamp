# UI Testing

`config-service` now includes browser-based UI behavior tests using Playwright.

## What these tests cover
The initial Playwright suite focuses on high-value UI behaviors that are awkward to verify with backend tests alone:

1. Page load and basic UI availability
2. Service enum dropdown population
3. Service section help/comment controls are not exposed
4. Tooltip text quality for help buttons
5. Partial Fluent Bit YAML load behavior, including warning/status output

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
