# Server Credentials Manager Playwright Tests

This folder contains browser tests for the standalone credentials manager UI.

## Target Suite

- Spec file: `svr-credentials-mgr/ui-tests/credentials-manager.spec.js`
- Main page under test:
  - `/svr-credentials-manager-service/ui`

## Covered Scenarios

1. The UI shows a status error when stale node-to-connection mappings are removed during load.
2. The cleaned assignment state is reflected in the connection table and assignment dialog.
3. The `Apply` action writes a fallback JSON record that matches the saved connection config.

## Run

From `svr-credentials-mgr`:

```bash
npm install
npx playwright install
npm run ui:test
```

Discovery:

```bash
npm run ui:test -- --list
```
