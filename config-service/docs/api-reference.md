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

Request:
```json
{
  "config": {
    "pipeline": {
      "inputs": [],
      "filters": [],
      "outputs": []
    }
  },
  "annotations": {},
  "profile": "strict"
}
```

Comment metadata can also live directly on objects:
```json
{
  "config": {
    "pipeline": {
      "inputs": [
        {
          "name": "forward",
          "port": 24224,
          "_meta": {
            "comment_lines": ["Ingress listener"],
            "field_comment_lines": {
              "port": ["Matches upstream sender port"]
            }
          }
        }
      ],
      "outputs": [{"name": "stdout"}]
    }
  }
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

Request:
```json
{
  "config": {
    "pipeline": {
      "inputs": [],
      "filters": [],
      "outputs": []
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
  "text": "<source>\n  @type tail\n  ...\n</source>\n"
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
  }
}
```

## POST `/parse/fluentbit/{version}`
Parses Fluent Bit YAML text into the internal JSON config model.

Behavior:
1. Supported sections are loaded into the editor model.
2. Unsupported or malformed sections are skipped and returned in `errors`.
3. Empty files return a `400` with an `empty_input_file` error.

Request:
```json
{
  "text": "service:\n  flush_interval: 5\npipeline:\n  inputs:\n    - name: dummy\n"
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
