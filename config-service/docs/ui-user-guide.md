# UI User Guide

## Start state
On load, the UI will:
1. Attempt to restore the last opened design document.
2. Fall back to a new configuration when no prior state exists.

## Main actions
1. Open configuration file (`.json` for design docs, `.conf` for Fluentd)
2. Create new configuration
3. Choose configuration version
4. Choose configuration type

## Add plugin configuration
Use the `Add Plugin` controls:
1. Select section (`inputs`, `filters`, `outputs`)
2. Select plugin name
3. Click `Add Plugin`

The editor displays a single plugin list view (not separate columns). Each plugin card still retains its pipeline section type.

## Fluent Bit processors
For Fluent Bit `inputs` and `outputs`, plugin cards now include a nested `Processors` frame.

Within that frame you can:
1. Choose a signal type (`logs`, `metrics`, `traces`)
2. Choose a processor
3. Add one or more processors to the plugin
4. Edit required and optional processor attributes
5. Remove processors from the plugin

Notes:
1. Processors are modeled for YAML-based Fluent Bit configuration only.
2. Log processors can also use Fluent Bit filters as processors.
3. Conditional processing is exposed only for Fluent Bit versions that support it in the current catalog metadata.

## Fluentd labels and workers
When `Configuration Type` is set to `Fluentd`, the UI also shows:
1. `Labels` panel for top-level `<label>` containers
2. `Workers` panel for top-level `<worker>` containers

Each label or worker card supports:
1. Add/remove the container
2. Edit the container name
3. Add scoped plugins inside that container
4. Edit/remove scoped plugins using the same plugin-card controls as the main pipeline

## Plugin editing
Each plugin card supports:
1. Expand/collapse
2. Move up/down
3. Remove
4. Field editing through schema-driven form controls
5. Section reassignment (`inputs`, `filters`, `outputs`)

## Service section support
The UI includes a `Service Section` panel to manage top-level service settings:
1. Select from common Fluent Bit service options (not only `flush`)
2. Edit existing fields
3. Remove fields
4. Use `custom...` when a key is not in the predefined list

## Mandatory vs optional attributes
1. Mandatory attributes are always present.
2. Optional attributes can be added via `Add Optional Attribute` dropdown.
3. Optional attributes can be removed from the plugin instance unless constrained by dependencies.

## Validate and render
1. `Validate` calls backend validation (`/validate/{version}`)
2. `Render Configuration` renders:
   - YAML for Fluent Bit
   - standard `.conf` text for Fluentd

## Developer-only reload
`Reload UI` button appears only when `APP_ENABLE_DEV_FEATURES` is enabled on the backend.

## Notes on comments/annotations
- The design model supports `annotations` separate from runtime config.
- Comments are optional and can be included in YAML output if enabled.

## Current Fluentd UI scope
Supported today:
1. Top-level pipeline editing
2. Top-level labels
3. Top-level workers
4. Fluentd `.conf` open/save/render through backend parse/render endpoints

Not yet exposed in the UI:
1. Worker-nested labels
2. Root-level `@include` editing
3. Arbitrary nested Fluentd child-section editors beyond the current field-driven card model
