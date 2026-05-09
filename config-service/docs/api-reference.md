# API Reference

Base path:
- `/config-service/api/v1`

## Authorization
When UI auth is enabled (`UI_AUTH_MODE=static` or `UI_AUTH_MODE=jwt`), send:
- `Authorization: Bearer <token>`

## GET `/health`
Returns service health and mode.

Example response:
```json
{
  "ok": true,
  "mode": "standalone",
  "app_enable_dev_features": true,
  "read_only": false
}
```

## GET `/versions`
Returns supported versions for the requested configuration type.

Query parameters:
- `config_type=fluentbit|fluentd`

## GET `/catalog/{version}`
Returns full catalog payload for the requested version.

Query parameters:
- `config_type=fluentbit|fluentd`

## GET `/service-options/{version}`
Returns the service-section definition for the requested version.

Query parameters:
- `config_type=fluentbit|fluentd`

## GET `/parser-options/{version}`
Returns the parser-section definition for the requested version.

Query parameters:
- `config_type=fluentbit|fluentd`

## POST `/catalog/{version}/validate`
Validates catalog JSON structure and metadata semantics.

## POST `/schema/{version}`
Compiles runtime JSON schema.

Request:
```json
{
  "strict": true
}
```

## POST `/validate/{version}`
Performs schema/semantic/rule-profile validation.

Optional request fields:
- `included_documents`: recursive include tree previously returned by a parse endpoint
- `merge_includes_for_validation`: when `true`, includes are merged into a temporary validation-only config. The root config and include documents are not mutated.

Request:
```json
{
  "config": {
    "parsers": [],
    "pipeline": {
      "inputs": [
        {
          "name": "tcp",
          "chunk_size": 32,
          "route": {
            "per_record_routing": true,
            "logs": [
              {
                "name": "error_logs",
                "condition": {
                  "op": "and",
                  "rules": [
                    {
                      "field": "$level",
                      "op": "eq",
                      "value": "error"
                    }
                  ]
                },
                "to": {
                  "outputs": ["error_destination"]
                }
              }
            ]
          }
        }
      ],
      "filters": [],
      "outputs": [{"name": "null", "alias": "error_destination"}]
    }
  },
  "annotations": {},
  "profile": "strict"
}
```

Response:
```json
{
  "ok": false,
  "errors": [
    {
      "order": 1,
      "code": "missing_required_field",
      "path": "$.config.pipeline.inputs[0].port",
      "message": "Required field 'port' is missing.",
      "severity": "error",
      "source": "semantic"
    }
  ]
}
```

## POST `/render/yaml/{version}`
Renders YAML text.

Optional request fields:
- `included_documents`: recursive include tree previously returned by a parse endpoint
- `render_included_files`: when `true`, the response also includes rendered YAML for each included document under `included_files`

Request:
```json
{
  "config": {
    "parsers": [
      {
        "name": "app_json",
        "format": "json",
        "time_key": "timestamp"
      }
    ],
    "pipeline": {
      "inputs": [
        {
          "name": "tcp",
          "chunk_size": 32,
          "parser": "app_json"
        }
      ],
      "filters": [],
      "outputs": [{"name": "null"}]
    }
  },
  "annotations": {},
  "include_comments": true
}
```

Response:
```json
{
  "ok": true,
  "yaml": "pipeline:\n  inputs: []\n"
}
```

## POST `/parse/fluentd/{version}`
Parses standard Fluentd `.conf` text into the internal JSON config model.

Request:
```json
{
  "text": "<source>\n  @type tail\n  ...\n</source>\n",
  "source_path": "/configs/main.conf",
  "resolve_includes": true
}
```

Response:
```json
{
  "ok": true,
  "config": {
    "service": {},
    "pipeline": {
      "inputs": [],
      "filters": [],
      "outputs": []
    },
    "labels": [],
    "workers": [],
    "includes": []
  },
  "included_documents": []
}
```

## POST `/parse/fluentbit/{version}`
Parses Fluent Bit YAML text into the internal JSON config model.

Behavior:
1. Supported sections are loaded into the editor model.
2. Unsupported or malformed sections are skipped and returned in `errors`.
3. Empty files return a `400` with an `empty_input_file` error.
4. Top-level `parsers:` entries are loaded into `config.parsers`.
5. Native Fluent Bit `routes:` blocks inside input plugins are normalized into the editor's internal `route` object.
6. When `resolve_includes` is enabled and `source_path` is provided, the response also contains a recursive `included_documents` tree.

Request:
```json
{
  "text": "service:\n  flush_interval: 5\npipeline:\n  inputs:\n    - name: dummy\n",
  "source_path": "/configs/main.yaml",
  "resolve_includes": true
}
```

Response with partial load:
```json
{
  "ok": false,
  "config": {
    "service": {
      "flush_interval": 5
    },
    "parsers": [],
    "pipeline": {
      "inputs": [{"name": "dummy"}],
      "filters": [],
      "outputs": []
    },
    "labels": [],
    "workers": [],
    "includes": []
  },
  "errors": [
    {
      "order": 1,
      "code": "fluentbit_yaml_ignored_section",
      "path": "$.plugins",
      "message": "Ignored unsupported Fluent Bit YAML section 'plugins'.",
      "severity": "error",
      "source": "parser"
    }
  ]
}
```

## POST `/render/fluentd/{version}`
Renders the internal JSON config model back into standard Fluentd `.conf` text.

Optional request fields:
- `included_documents`: recursive include tree previously returned by a parse endpoint
- `render_included_files`: when `true`, the response also includes rendered Fluentd text for each included document under `included_files`

Request:
```json
{
  "config": {
    "service": {},
    "pipeline": {
      "inputs": [],
      "filters": [],
      "outputs": []
    },
    "labels": [],
    "workers": [],
    "includes": []
  }
}
```

Response:
```json
{
  "ok": true,
  "text": "<source>\n  @type tail\n</source>\n"
}
```
