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
5. Open the top-level `Help` page in a separate browser tab
6. Choose configuration type
7. Choose configuration version

## Built-in help
1. The top-right `Help` button opens a bundled in-application guide.
2. The guide explains the major editor panels, nested blocks such as parsers, processors, and routes, and the meaning of icon buttons and color states.
3. Field-level `?` buttons still open documentation for the specific service option, parser format, plugin, processor, or attribute they sit beside.

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

## Parser panel placement
For Fluent Bit, the `Parsers` panel appears immediately before `Add Plugin`.

## Parser configuration
Use the `Parsers` panel to define reusable Fluent Bit parsers:
1. Expand or collapse the whole panel
2. Choose a parser format (`json`, `regex`, `ltsv`, `logfmt`, and others defined for the selected version)
3. Enter a parser name
4. Click `Add Parser`
5. Expand the parser card to edit required and optional parser attributes

Validation behavior:
1. Input plugin fields that reference parsers are matched against:
   1. parsers defined in the `Parsers` panel
   2. known built-in Fluent Bit parser names for the selected version
2. Unknown parser references are shown as validation errors.
3. Duplicate custom parser names are shown as validation errors.

## Add plugin configuration
Use the `Add Plugin` controls:
1. Select section (`inputs`, `filters`, `outputs`)
2. Select plugin name
3. Click `Add Plugin`

The editor displays a single plugin list view (not separate columns). Each plugin card still retains its pipeline section type.

## Fluent Bit route panel
For Fluent Bit 4.2+ input plugins, plugin cards can expose a nested `Route` panel.

Within that frame you can:
1. Add or remove the route block for the selected input
2. Enable or disable `per_record_routing`
3. Add route entries under signal groupings such as `logs`
4. Define route conditions with one or more rules
5. Choose one or more output names or aliases as destinations

Notes:
1. The editor stores this block internally as `route`.
2. Native Fluent Bit YAML is rendered back as `routes`.
3. Route-output matching is validated against configured output names and aliases where practical.
4. `metrics` and `traces` route groups are surfaced, but Fluent Bit currently parses them without fully evaluating them.

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
3. The Validation panel includes an `Include loaded files` toggle.
4. When enabled, validation sends any include documents already loaded into memory and asks the backend to merge them temporarily for validation only.
5. If no include documents are loaded, the UI leaves the current document unchanged and shows a status message to make that clear.
6. If the configuration changes after a successful render, the rendered output is highlighted until it is rendered again.
7. When a configuration was loaded from a source file and the original source positions are still trustworthy, validation issues also show the corresponding source line number.
8. After the configuration is edited in the UI, source-line hints are cleared so stale line numbers are not shown.

## Developer-only reload
`Reload UI` button appears only when `APP_ENABLE_DEV_FEATURES` is enabled on the backend.

## Read-only mode
When backend read-only mode is enabled:
1. Editing controls are disabled.
2. Save and `Save As` are disabled.
3. Open file, validate, render, expand/collapse, and documentation help remain available.

## Notes on comments/annotations
- Comments are optional and can be included in YAML output if enabled.
- The UI exposes comment editors for:
  - plugin cards
  - plugin attribute rows
- Comment editors are opened from the right-hand notepad button on the related entity instead of always being shown inline.
- Legacy `annotations` maps are migrated into the current internal comment metadata structure when older JSON documents are loaded.

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
