# Allow Remote Config Outcome

## Existing consumer behavior found

Before this change, the consumer already had partial remote-config support:

- `ServerToAgent.remote_config` messages were dispatched through `handle_remote_config`
- `CommonConfigHandler` already validated and applied `AgentRemoteConfig` payloads
- outbound capability advertisement was still hardwired and did not consult a consumer config flag
- inbound remote-config handling did not check whether remote config had been disabled in config
- no consumer config value existed to control remote-config capability advertisement or handling

## What was implemented

The consumer now fully supports `consumer.allow-remote-config` as a boolean config value with a default of `true`.

### Configuration

- added `consumer.allow-remote-config`
- default is `true`
- the default repo config in `config/opamp.json` now includes the setting explicitly

### Capability advertisement

- outbound `AgentToServer.capabilities` now includes `AcceptsRemoteConfig` only when:
  - the configured consumer service type supports remote config, and
  - `consumer.allow-remote-config` is `true`

### Inbound remote-config handling

- inbound `ServerToAgent.remote_config` now checks whether remote config is allowed for the current client
- when remote config is not allowed, the consumer:
  - logs an error
  - includes the provided filenames in that log entry
  - does not log configuration bodies
  - skips applying the payload

## Agent type support outcome

Current consumer service types are all treated as supporting file-based remote config through the shared client/config writer path:

- `fluentbit`
- `fluentd`
- `simulator`

Because all current consumer types can use that shared file-based path, there was no existing consumer type that needed a hardwired `false` override in this implementation pass.

## Validation added

Tests were added/updated to cover:

- default `allow-remote-config=true`
- explicit `allow-remote-config=false`
- capability mask includes `AcceptsRemoteConfig` when enabled
- capability mask excludes `AcceptsRemoteConfig` when disabled
- inbound remote-config rejection logs filenames but not file body content when disabled
