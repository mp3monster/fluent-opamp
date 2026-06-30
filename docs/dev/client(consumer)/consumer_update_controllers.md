# Consumer Full Update Controllers

This document explains how the consumer full update controllers work, what each controller does, and how they interact with reporting flags that control which `AgentToServer` message elements are sent.

## What problem the controllers solve

The consumer does not send all optional fields on every message by default. Instead, it uses reporting flags to decide when to include:

- `agent_description`
- `capabilities`
- `custom_capabilities`
- `health`

Full update controllers decide when those flags should be turned back on so the client periodically re-sends a fuller state.

## Main components

- `OpAMPClientData.reporting_flags`: flag map keyed by `ReportingFlag`.
- `FullUpdateControllerInterface`: common contract for controller implementations.
- `AlwaysSend`, `SentCount`, `TimeSend`: concrete strategies.
- `AbstractOpAMPClient.send()`: calls controller `update_sent()` after a successful send.
- `AbstractOpAMPClient._populate_agent_to_server()`: reads flags and conditionally populates message fields.

## Reporting flags and message fields

The mapping is:

- `REPORT_DESCRIPTION` -> include `agent_description`
- `REPORT_CAPABILITIES` -> include `capabilities`
- `REPORT_CUSTOM_CAPABILITIES` -> include `custom_capabilities`
- `REPORT_HEALTH` -> include `health`

When a field is included, its flag is immediately reset to `False` for subsequent sends.

## Send lifecycle and controller interaction

1. A send starts in `send()`.
2. Unless `send_as_is=True`, `_populate_agent_to_server()` checks each reporting flag and adds corresponding fields.
3. Included fields have their flags reset to `False`.
4. Message is sent via WebSocket or HTTP.
5. On successful send, `full_update_controller.update_sent()` is called.
6. Controller may call `set_all_reporting_flags(True)`, which affects the *next* send.

Important detail:

- Controllers run after a successful transmit, so they schedule future full-field sends rather than changing the message that was just sent.

## How server flags also affect reporting

`handle_flags()` checks `ServerToAgent.flags`.

If `ReportFullState` is present, the client sets all reporting flags to `True`. This makes the next outbound message include all reportable sections regardless of local controller timing.

## Controller behaviors

## `AlwaysSend`

- On every successful send, sets all reporting flags to `True`.
- Effect: every subsequent message tends to include all reportable fields.

## `SentCount`

- Config key: `fullResendAfter` (minimum `1`).
- Increments `sent_count` after each successful send.
- When `sent_count >= fullResendAfter`, sets all reporting flags to `True` and resets `sent_count` to `0`.
- Effect: full re-send cadence based on number of successful transmissions.

## `TimeSend`

- Config keys: `fullUpdateAfterSeconds` (preferred), `timeSendSeconds` (fallback), minimum `1`.
- Tracks `last_full_update_ms`.
- On successful send, if elapsed time threshold is exceeded, sets all reporting flags to `True` and updates `last_full_update_ms`.
- Effect: full re-send cadence based on elapsed time.

## Selection and configuration

Controller is selected from `consumer.full_update_controller_type`:

- `AlwaysSend`
- `SentCount` (default)
- `TimeSend`

Configuration payload is read from `consumer.full_update_controller`.

## Practical summary

- Flags decide what is included in the current outbound message.
- Controllers decide when to re-enable those flags for future messages.
- Provider `ReportFullState` can immediately override cadence by turning all flags on for the next send.

## Documentation evaluation

Current documentation coverage:

1. This document explains update controller behavior, selection, and cadence logic.
2. Before this update, it did not describe the implementation steps required to add a new controller type.

The next section provides those extension steps.

## How to add another update controller

## 1. Implement a new controller class

Create a new module under:

- `consumer/src/opamp_consumer/full_update_controller/<new_controller>.py`

Implement `FullUpdateControllerInterface` from:

- `consumer/src/opamp_consumer/full_update_controller/update_interface.py`

Required methods:

- `configure(self, full_update_controller)`
- `update_sent(self, ms_from_epoch=None)`

The constructor should accept:

- `set_all_reporting_flags: Callable[[bool], None]`

This callback is how your controller triggers full-field resend behavior.

## 2. Export the class in package init

Update:

- `consumer/src/opamp_consumer/full_update_controller/__init__.py`

Add import/export for the new controller so it is available where controllers are instantiated.

## 3. Register selection logic

Controller selection is currently explicit in:

- `consumer/src/opamp_consumer/abstract_client.py` (`_create_full_update_controller`)

Add a new branch for your controller type string (for example `"MyController"`), and instantiate your class there.

## 4. Add configuration shape

Use `consumer.full_update_controller` for controller-specific settings. Keep input parsing defensive:

- support dictionary or JSON string input
- clamp/validate numeric thresholds
- log warnings and fall back to safe defaults on malformed values

## 5. Add tests

At minimum add tests in:

- `consumer/tests/test_client_update_controllers.py`

Recommended cases:

1. Controller instantiation when `full_update_controller_type` matches new type.
2. Configuration parsing (valid + invalid inputs).
3. `update_sent` behavior across threshold/cadence boundaries.
4. Verification that reporting flags are set when expected.

## 6. Update docs/config examples

Update user-facing docs and sample configs to include:

- the new `full_update_controller_type` value
- the expected `full_update_controller` settings payload
