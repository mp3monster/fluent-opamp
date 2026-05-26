# UI Framework Decision (Why Custom Renderer)

`config-service` uses a schema-driven UI, but it intentionally does not use a generic JSON-schema-to-form framework (for example Form.io, React schema-form frameworks, JSON Forms, or similar) for the main editor.

## Decision summary
We use a custom renderer because the editor requirements are configuration-domain specific and go beyond standard JSON form generation.

## Why we chose a custom renderer
1. We support multiple configuration dialects, not just plain JSON forms.
   - Fluent Bit YAML and Fluentd `.conf` have structure and rendering rules that are not a simple one-to-one JSON form mapping.
2. We need deterministic round-trip behavior for operational configs.
   - The editor workflow includes parse, validate, and render semantics that are tightly coupled to backend services and versioned catalogs.
   - Example risk with generic schema-form frameworks: when a user switches a plugin selector that is implemented with schema branches (`oneOf`), the framework may rebuild that object from the newly selected branch defaults and then rebuild it again when switching back. This can reorder keys, drop fields not present in the active branch, or reinsert defaults differently. For operational configs this can create non-deterministic output diffs (same user intent, different rendered YAML/conf text), which is exactly what we avoid with the custom round-trip model.
3. The UI model includes domain-specific structures that need custom interaction patterns.
   - Examples include plugin cards, parser cards, processors, routes, labels/workers, and section-specific optional attribute flows.
4. Validation integration is more than client-side schema-field checks.
   - Advanced validation is backend-authoritative (schema + semantic + rule-profile). The UI still needs custom request shaping and deterministic issue-to-field mapping for this editor model (plugins, parsers, routes, labels/workers), so validation results remain actionable and stable for operators.
   - See [Custom Validation Logic](./custom-validation.md) for backend validation architecture and rule-profile details.
5. We optimize for maintainability and extension in this specific editor domain.
   - A generic framework can reduce boilerplate for standard CRUD-style forms, but our plugin/parsers/routes/labels/workers model still needs substantial custom wrappers and mapping logic. Keeping that behavior explicit in local renderer code has been easier to reason about, test, and extend. This also keeps the standalone wheel dependency surface focused on shipped runtime behavior.
6. We need stable UX behavior across rapidly evolving version catalogs.
   - Catalog and schema updates can change supported fields/options per version; the custom renderer lets us preserve predictable operator workflows while adapting metadata.

## Framework Goal Fit
The table below evaluates the previously discussed frameworks against the goals in this document.

| Framework | Meets all identified goals as-is? | Goals not fully met without heavy customization | Why this is a gap for `config-service` |
|---|---|---|---|
| Form.io | No | Deterministic round-trip output, Fluent Bit/Fluentd dialect-specific render behavior, tight plugin-card interaction model | Strong for generic form generation, but operational config authoring needs strict parse/validate/render stability and domain-specific editing flows that require substantial custom layers. |
| RJSF (`react-jsonschema-form`) | No | Deterministic round-trip behavior across `oneOf` branch switches, domain-specific nested editor patterns, minimal packaging/dependency surface | RJSF is strong for JSON Schema form rendering, but this editor still needs extensive custom wrappers/state guards for plugin/parser/route/worker behavior and stable YAML/conf output semantics. |
| Other React schema-form frameworks | No | Deterministic round-trip behavior across schema-branch switches, domain-specific nested editor patterns, minimal packaging/dependency surface | Similar to RJSF, these frameworks help with form scaffolding but still require substantial adaptation for `config-service` operator workflows and deterministic rendering goals. |
| JSON Forms | No | Deterministic operational round-trip behavior, domain-specific workflow composition, low-friction extension for this exact model | Flexible renderer architecture helps, but we still need significant custom renderer rules and mapping logic for this editor's catalog/version and workflow requirements. |

Conclusion:
1. All candidates can support schema-driven forms.
2. None meets the full `config-service` goal set out-of-the-box.
3. The deciding factor is not "can render forms", but "can preserve deterministic operational behavior with acceptable long-term complexity."

## What the custom layer still reuses
1. Runtime schema compilation from catalog metadata.
2. Schema-driven field definitions where appropriate.
3. Backend API contracts for versions, catalog, schema, validate, and render.

In short, this is not a non-schema approach. It is a schema-driven editor with a custom presentation and interaction layer.

## How Dynamic Page Generation Works
The custom renderer generates pages dynamically at runtime from backend catalog/schema APIs.

1. UI bootstrap loads versions/catalog context from backend APIs.
   - Frontend orchestrator: [`config_ui.js`](../src/config_service/html/config_ui.js)
2. For the selected version/type, UI requests a compiled runtime schema via `POST /schema/{version}`.
   - API route: [`routes/api.py`](../src/config_service/routes/api.py)
3. Backend `SchemaService` compiles schema from catalog metadata (required flags, data types, docs references, section shape rules).
   - Compiler: [`services/schema_service.py`](../src/config_service/services/schema_service.py)
4. Frontend stores compiled schema in runtime state (`compiledSchema`) and merges it with the current working document.
   - State + schema load flow: [`config_ui.js`](../src/config_service/html/config_ui.js)
5. `renderAll()` composes page sections dynamically (plugins, parsers, service, upstream servers, labels/workers, validation/output panels) from state + compiled schema + catalog metadata.
   - Core render loop: [`config_ui.js`](../src/config_service/html/config_ui.js)
6. Section-specific modules build cards/rows/controls on demand, then re-render deterministically after state changes.
   - Plugin cards/workflows: [`config_ui_plugins.js`](../src/config_service/html/config_ui_plugins.js)
   - Parser/service section rendering: [`config_ui_sections.js`](../src/config_service/html/config_ui_sections.js)
7. Validation/render actions call backend endpoints; returned issues are mapped to editor paths so dynamic controls can highlight the right fields consistently.
   - UI validation/render calls: [`config_ui.js`](../src/config_service/html/config_ui.js)
   - Backend validation/render endpoints: [`routes/api.py`](../src/config_service/routes/api.py)

This means the page structure is not static HTML authored per plugin/version. It is generated from versioned metadata and runtime schema responses, with custom renderer logic ensuring stable operator workflows.

## Tradeoffs
1. Higher in-repo maintenance cost for UI rendering logic.
2. More custom code to test compared with an off-the-shelf form renderer.
3. Finer control of behavior and compatibility for the specific Fluent Bit/Fluentd authoring workflows we need.

## Re-evaluation criteria
We should revisit this decision if:
1. The product scope shifts toward generic CRUD-style forms with minimal domain-specific behavior.
2. A framework can meet parse/render/validation and round-trip needs without heavy adaptation layers.
3. Operational dependency and packaging constraints change enough to justify a larger frontend framework footprint.
