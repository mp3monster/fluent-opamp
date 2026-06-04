# Consumer Custom Handlers

This document explains how consumer custom handlers work, what handlers are provided, and how to implement and deploy an additional custom handler.

## Purpose

Custom handlers allow the consumer to process provider `ServerToAgent.custom_message` payloads by capability FQDN (reverse-DNS string).

The handler pipeline is capability-driven:

1. provider sends `custom_message.capability`
2. consumer resolves a handler class registered for that capability
3. consumer executes handler logic and optional custom response

## Main runtime components

- Handler interfaces: `consumer/src/opamp_consumer/custom_handlers/handler_interface.py`
- Discovery/registry: `consumer/src/opamp_consumer/custom_handlers/registry.py`
- Consumer message path: `consumer/src/opamp_consumer/client_server_message_mixin.py`
- Capability publication path: `consumer/src/opamp_consumer/abstract_client.py`

Key configuration switch:

- `consumer.allow_custom_capabilities` must be `true` for discovery and execution.

When disabled, handler discovery is skipped and custom capability handling is not active.

## Built-in handlers

## `ChatOpsCommand`

- File: `consumer/src/opamp_consumer/custom_handlers/chatops_command.py`
- Capability: `org.mp3monster.opamp_provider.chatopcommand`
- Behavior:
  - parses custom payload JSON
  - reads optional `tag` and `attributes`
  - issues local HTTP POST to ChatOps endpoint (`localhost:<chat_ops_port>`)
  - returns failure `CustomMessage` payload if endpoint response is non-2xx

## `ShutdownCommand`

- File: `consumer/src/opamp_consumer/custom_handlers/shutdowncommand.py`
- Capability: `org.mp3monster.opamp_provider.command_shutdown_agent`
- Behavior:
  - disables heartbeat
  - sends disconnect
  - terminates agent process
  - exits process

## `NullCommand`

- File: `consumer/src/opamp_consumer/custom_handlers/nullcommand.py`
- Capability: `org.mp3monster.opamp_provider.nullcommand`
- Behavior:
  - parses optional `dummyValue` field
  - logs message details
  - no further action (no-op validation path)

## How discovery works

`build_factory_lookup(...)` scans the handler folder for `.py` files, imports classes that inherit `CustomMessageHandlerInterface`, and creates an FQDN -> class map.

Default folder per client implementation:

- Fluent Bit client: `consumer/src/opamp_consumer/custom_handlers`
- Fluentd client: `consumer/src/opamp_consumer/custom_handlers`
- Simulator client: `consumer/src/opamp_consumer/custom_handlers`

Folder selection is provided by `get_custom_handler_folder()` in each concrete client.

## Handler lifecycle

1. consumer starts and builds handler lookup
2. inbound custom message arrives
3. consumer resolves handler by `custom_message.capability`
4. `set_custom_message_handler(...)` stores payload
5. `execute(...)`:
   - decodes payload
   - extracts optional `action`
   - calls `handle_message(...)`
   - calls `execute_action(...)`
6. if `execute_action(...)` returns `CustomMessage`, consumer sends it upstream

## Implementing a new custom handler

## 1. Create a handler file

Add a module under:

- `consumer/src/opamp_consumer/custom_handlers/<your_handler>.py`

Subclass `CustomMessageHandlerInterface` and implement:

- `get_fqdn(self) -> str`
- `set_client_data(self, data)`
- `handle_message(self, message: str, message_type: str) -> None`
- `execute_action(self, action: str, opamp_client) -> opamp_pb2.CustomMessage | None`

## 2. Keep capability name exact

`get_fqdn()` must exactly match provider `custom_message.capability`.

If the capability string differs, routing fails and no handler will be used.

## 3. Handle payload parsing defensively

- treat payload as untrusted input
- guard JSON parsing (`json.JSONDecodeError`)
- validate required fields and types
- fail closed where destructive actions are possible

## 4. Optional response payload

If handler needs to report result/failure upstream:

- build and return `opamp_pb2.CustomMessage` from `execute_action(...)`
- return `None` for no response

The shared execute path sends returned custom response automatically.

## 5. Enable custom capabilities

Set in consumer config:

```json
{
  "consumer": {
    "allow_custom_capabilities": true
  }
}
```

## 6. Deploy and restart consumer

Handler discovery occurs at startup, so restart the consumer process after adding/updating handler modules.

## Deployment checklist

1. Add handler module in `custom_handlers` folder.
2. Confirm provider emits matching capability FQDN.
3. Set `allow_custom_capabilities=true`.
4. Restart consumer.
5. Validate with provider command flow.
6. Check consumer logs for discovery and execution events.

## Testing guidance

Recommended tests:

1. discovery test (`build_factory_lookup` contains expected FQDN)
2. creation test (`create_handler` returns class instance)
3. payload parsing tests (valid + invalid JSON)
4. action execution tests (success/failure paths)
5. optional response message test when `execute_action` returns `CustomMessage`

Related examples:

- `consumer/tests/test_custom_handlers_chatops.py`
- `consumer/tests/test_custom_handlers_shutdown.py`
- `consumer/tests/test_custom_handlers_nullcommand.py`
- `consumer/tests/test_custom_handlers_registry.py`

## Notes on provider-side setup

Consumer handlers are one side of the custom command path. Provider command object/capability setup is documented in:

- `docs/dev/adding_your_own_custom_action.md`
