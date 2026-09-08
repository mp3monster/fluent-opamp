# Playwright Batch Config

This folder contains JSON configuration files for the Config Service Playwright
chapter batch runner:

- `default-batch-config.json` is the default validation profile used by the
  container regression pack.
- `scenarios/` is for additional named validation profiles.

The runner itself lives at:

- `config-service/dev-tools/playwright_chapter_batch_runner.mjs`

The container harness is documented at:

- `tests/test-containers/config-service-ui-playwright-batch/README.md`

## Default Profile

`default-batch-config.json` targets direct Fluent Bit YAML chapter examples that
are expected to load into the editor, render back to YAML, and save cleanly.

It excludes known files that are not direct editor inputs or are not expected to
round-trip through the current UI validation flow, including:

- Helm and Kubernetes manifests
- Docker Compose files
- Prometheus configuration
- duplicate-key samples
- answer or expected-output samples
- advanced shorthand examples that are not currently one-for-one editor documents

## Supported Keys

| Key | Purpose |
|---|---|
| `yamlExtensions` | File extensions the batch runner treats as YAML inputs. |
| `excludePathPatterns` | Case-insensitive regular expressions matched against relative input paths to skip known non-target files. |
| `saveSuffix` | Suffix appended when the UI save workflow writes a validated copy. |
| `additionalPluginAttribute.pluginName` | Optional plugin name to target for a small UI mutation check. |
| `additionalPluginAttribute.field` | Optional field added during the mutation check. |
| `additionalPluginAttribute.value` | Value assigned to the added field. |

## Running The Batch

Run the regression-pack entry:

```bash
python tests/test-containers/run_regression_pack.py --only config-service-ui-playwright-batch
```

Or pass a scenario file directly to the container:

```bash
docker run --rm \
  -e PLAYWRIGHT_BATCH_CONFIG=/workspace/opamp/config-service/dev-tools/playwright-batch-config/scenarios/<name>.json \
  -v "$PWD:/workspace/opamp" \
  config-service-ui-playwright-batch:latest
```

See `scenarios/README.md` for guidance on adding extra validation profiles.
