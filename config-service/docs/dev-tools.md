# Developer Tools

This page summarizes developer-facing helper scripts in `config-service/dev-tools`.

## Fluent Bit Asset Generator

Script:
- [generate_fluentbit_assets.py](../dev-tools/generate_fluentbit_assets.py)

Purpose:
1. Scrapes Fluent Bit plugin documentation for one or more versions
2. Supports:
   - the Fluent Bit docs website
   - the `fluent/fluent-bit-docs` GitHub repo
   - automatic GitHub → website fallback
3. Generates versioned Fluent Bit catalog JSON artifacts under:
   - `config-service/json-definitions`
   - `config-service/src/config_service/json-definitions`
4. Runs the post-processing pass that:
   - normalizes plugin names to the real Fluent Bit config `Name`
   - adds shared processor metadata
   - adds router-related fields
   - writes split manifest + per-plugin shard files
5. Optionally updates `config-service/config/catalog-registry.json`
6. Optionally regenerates runtime schemas for the requested versions

The generated catalog layout is versioned and sharded:
1. Top-level manifest file: `json-definitions/fluent-bit-<version>-all-plugins-catalog.json`
2. Version folder: `json-definitions/fluent-bit/<version>/`
3. Plugin-type manifests: `inputs.json`, `filters.json`, `outputs.json`
4. Per-plugin files under `inputs/`, `filters/`, and `outputs/`

Run it:

```bash
cd /mnt/d/dev/opamp
python3 config-service/dev-tools/generate_fluentbit_assets.py --version 5.0.7
```

Useful examples:

```bash
python3 config-service/dev-tools/generate_fluentbit_assets.py --version 5.0.7 --source website
python3 config-service/dev-tools/generate_fluentbit_assets.py --version 5.0.7 --source github --github-ref master
python3 config-service/dev-tools/generate_fluentbit_assets.py --version 5.0.7 --no-schemas
python3 config-service/dev-tools/generate_fluentbit_assets.py --version 5.0.7 --no-register
```

Notes:
1. The website root is resolved from `https://docs.fluentbit.io/manual/<version>/administration/configuring-fluent-bit`
2. If the exact patch path does not exist, the tool falls back to the series path and then the unversioned manual
3. GitHub mode resolves `.gitbook.yaml` first so plugin names come from the canonical docs mapping rather than page slugs

## Fluent Bit Schema Quick Reference Generator

Script:
- [generate_fluentbit_schema_quick_reference.py](../dev-tools/quick-references/generate_fluentbit_schema_quick_reference.py)

Purpose:
1. Reads the local Fluent Bit JSON schema files
2. Generates Markdown quick references for:
   - `env` environment variables
   - `upstream_servers` upstream server groups
   - pipeline plugins
3. Produces grouped pipeline sections for:
   - `inputs`
   - `filters`
   - `outputs`
4. Includes:
   - alphabetical plugin jump lists
   - plugin anchors
   - mandatory flags
   - default values
   - descriptions
   - hyperlinks to Fluent Bit documentation

The schema input files can be either direct JSON payloads or manifest files that point to
versioned shard trees such as `json-schemas/fluentbit/3.2.10/inputs/*.json`. Individual
plugin shard files may use JSON Schema `$ref` to shared version-local fragments such as
`json-schemas/fluentbit/3.2.10/processors.json`.

Inputs:
1. [fluentbit-3.2.10-config-schema.json](../json-schemas/fluentbit-3.2.10-config-schema.json)
2. [fluentbit-4.2.4-config-schema.json](../json-schemas/fluentbit-4.2.4-config-schema.json)
3. [fluentbit-5.0.4-config-schema.json](../json-schemas/fluentbit-5.0.4-config-schema.json)

Outputs:
1. [fluentbit-3-2-10-schema-quick-reference.md](../../quick-references/fluentbit-3-2-10-schema-quick-reference.md)
2. [fluentbit-4-2-4-schema-quick-reference.md](../../quick-references/fluentbit-4-2-4-schema-quick-reference.md)
3. [fluentbit-5-0-4-schema-quick-reference.md](../../quick-references/fluentbit-5-0-4-schema-quick-reference.md)

Run it:

```bash
cd /mnt/d/dev/opamp
python3 config-service/dev-tools/quick-references/generate_fluentbit_schema_quick_reference.py
```

Optional:

```bash
python3 config-service/dev-tools/quick-references/generate_fluentbit_schema_quick_reference.py --help
python3 config-service/dev-tools/quick-references/generate_fluentbit_schema_quick_reference.py --version 4.2.4
python3 config-service/dev-tools/quick-references/generate_fluentbit_schema_quick_reference.py --source-dir config-service/json-schemas --output-dir quick-references
```

What to expect:
1. The script overwrites the generated Markdown file
2. The output is deterministic for the current schema contents
3. Any formatting updates should be made in the generator, then regenerated

Recommended verification:

```bash
python3 -m ruff check config-service/dev-tools/quick-references/generate_fluentbit_schema_quick_reference.py
```

When to use it:
1. After schema regeneration for Fluent Bit `3.2.10`, `4.2.4`, or `5.0.4`
2. After adjusting schema metadata such as descriptions, defaults, or required flags
3. When refreshing the quick references in `quick-references`

## Fluent Bit Plugin Attribute Reference Generator

Script:
- [generate_fluentbit_plugin_attribute_reference.py](../dev-tools/quick-references/generate_fluentbit_plugin_attribute_reference.py)

Purpose:
1. Reads the local Fluent Bit catalog JSON files
2. Generates Markdown attribute reference files for each Fluent Bit version
3. Produces grouped sections for:
   - `inputs`
   - `filters`
   - `outputs`

The catalog input files can be either direct JSON payloads or manifest files that point to
versioned shard trees such as `json-definitions/fluent-bit/3.2.10/outputs/*.json`.

Inputs:
1. [fluent-bit-3.2.10-all-plugins-catalog.json](../json-definitions/fluent-bit-3.2.10-all-plugins-catalog.json)
2. [fluent-bit-4.2.4-all-plugins-catalog.json](../json-definitions/fluent-bit-4.2.4-all-plugins-catalog.json)
3. [fluent-bit-5.0.4-all-plugins-catalog.json](../json-definitions/fluent-bit-5.0.4-all-plugins-catalog.json)

Outputs:
1. [fluentbit-3-2-10-plugin-attribute-reference.md](../../quick-references/fluentbit-3-2-10-plugin-attribute-reference.md)
2. [fluentbit-4-2-4-plugin-attribute-reference.md](../../quick-references/fluentbit-4-2-4-plugin-attribute-reference.md)
3. [fluentbit-5-0-4-plugin-attribute-reference.md](../../quick-references/fluentbit-5-0-4-plugin-attribute-reference.md)

Run it:

```bash
cd /mnt/d/dev/opamp
python3 config-service/dev-tools/quick-references/generate_fluentbit_plugin_attribute_reference.py
```

Optional:

```bash
python3 config-service/dev-tools/quick-references/generate_fluentbit_plugin_attribute_reference.py --help
python3 config-service/dev-tools/quick-references/generate_fluentbit_plugin_attribute_reference.py --source-dir config-service/json-definitions --output-dir quick-references
```

## Fluent Bit Markdown Generator

Script:
- [generate_fluentbit_markdown.py](../dev-tools/generate_fluentbit_markdown.py)

Purpose:
1. Regenerates human-readable Fluent Bit Markdown references from local generated artifacts
2. Runs:
   - the schema quick-reference generator
   - the plugin attribute reference generator
3. Uses the already-generated local schema/catalog JSON artifacts as the source of truth

Run it:

```bash
cd /mnt/d/dev/opamp
python3 config-service/dev-tools/generate_fluentbit_markdown.py --version 5.0.7
```

Optional:

```bash
python3 config-service/dev-tools/generate_fluentbit_markdown.py --version 5.0.7 --skip-attribute-reference
python3 config-service/dev-tools/generate_fluentbit_markdown.py --version 5.0.7 --skip-schema-reference
```
