# Custom Validation Logic

## Validation architecture
Validation runs in layers:
1. Schema/semantic checks (`validation_service`)
2. Rule-engine checks (`rule_engine_service`)

The rule engine is profile-driven:
- A profile selects rulesets.
- A ruleset selects one adapter and parameters.

## Existing extension points
- Adapter interface: `config-service/config_service/rule_engine/base.py`
- Adapter registry: `config-service/config_service/rule_engine/registry.py`
- Built-in adapters: `config-service/config_service/rule_engine/adapters/builtin.py`
- Rules configuration: `config-service/config/validation-rules-registry.json`

## Add a custom rule adapter
### 1. Create adapter module
Add a new module under:
- `config-service/config_service/rule_engine/adapters/`

Implement class extending `RuleAdapter` and return normalized issues:
```python
{
  "code": "my_rule_code",
  "path": "$.config.pipeline.inputs[0].field_name",
  "message": "Validation message",
  "severity": "error",
  "source": "rules"
}
```

### 2. Register adapter
In `config_service/rule_engine/registry.py`, map adapter name to class.

Example adapter name:
- `custom.require_tls_on_forward`

### 3. Add ruleset configuration
Update `validation-rules-registry.json`:
```json
{
  "rulesets": {
    "require_tls_on_forward": {
      "adapter": "custom.require_tls_on_forward",
      "enabled": true,
      "params": {
        "enforce": true
      }
    }
  }
}
```

### 4. Add profile binding
Add ruleset to one or more profiles:
```json
{
  "profiles": {
    "strict": {
      "rulesets": [
        "catalog_required_fields",
        "data_type_enforcement",
        "require_tls_on_forward"
      ]
    }
  }
}
```

### 5. Optional version-specific binding
Use `version_overrides` to append rulesets for specific versions.

## Choosing validation profile at runtime
Request payload for `POST /config-service/api/v1/validate/{version}`:
```json
{
  "config": { "pipeline": { "inputs": [], "filters": [], "outputs": [] } },
  "annotations": {},
  "profile": "strict"
}
```

If `profile` is omitted, backend uses `default_profile` from registry.

## Good practices
1. Keep adapters pure and deterministic.
2. Use `params` for behavior switches, not hardcoded constants.
3. Return path-specific issues for good UI mapping.
4. Use stable `code` values for easy filtering/reporting.
5. Add tests for each new adapter and profile behavior.
