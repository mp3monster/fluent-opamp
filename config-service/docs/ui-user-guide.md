# UI User Guide

## Start state
On load, the UI will:
1. Attempt to restore the last opened design document.
2. Fall back to a new configuration when no prior state exists.

## Main actions
1. Open configuration file (`.json` for design docs, `.yaml`/`.yml` for Fluent Bit, `.conf` for Fluentd)
2. Create new configuration
3. Save the current configuration
4. Save the current configuration to a new file via `Save As`
5. Choose configuration type
6. Choose configuration version

## Save behavior
1. `New Configuration` clears the current open-file display.
2. `Save` reuses the current file handle when the browser provides one.
3. `Save As` always prompts for a new file target.
4. Saved files include top-of-file header comments for:
   1. configuration type
   2. configuration version
5. When a saved file is reopened, the UI reads those header comments first and updates type/version selection before loading the rest of the document.
6. If the saved version is no longer available, the UI selects the next supported mapped version after that value. If there is no later mapped version, it uses the highest available version.

## File loading behavior
1. Fluent Bit files are loaded from YAML (`.yaml` / `.yml`).
2. Fluentd files are loaded from standard `.conf`.
3. If a Fluent Bit YAML file contains unsupported sections, the UI loads the supported parts and shows parser errors for the ignored sections in the validation panel.
4. The message bar will say when the file loaded with problems.
5. Empty files are rejected as load errors and are not treated as valid configurations.

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
3. If the configuration changes after a successful render, the rendered output is highlighted until it is rendered again.

## Developer-only reload
`Reload UI` button appears only when `APP_ENABLE_DEV_FEATURES` is enabled on the backend.

## Read-only mode
When backend read-only mode is enabled:
1. Editing controls are disabled.
2. Save and `Save As` are disabled.
3. Open file, validate, render, expand/collapse, and documentation help remain available.

## Notes on comments/annotations
- The preferred comment model is now object-local metadata:
  - `_meta.comment_lines`
  - `_meta.field_comment_lines`
- Comments are optional and can be included in YAML output if enabled.
- The UI exposes comment editors for:
  - the service block
  - individual service fields
  - plugin cards
  - plugin attribute rows
- Comment editors are opened from the right-hand notepad button on the related entity instead of always being shown inline.
- The `_meta` question-mark button opens the bundled in-application help page that explains the metadata structure and rendering behavior.
- Legacy `annotations` maps are migrated into `_meta` when older JSON documents are loaded.

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
