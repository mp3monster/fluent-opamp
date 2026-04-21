# Slack Command Syntax

## Purpose

Define a strict Slack slash-command syntax that lets users issue OpAMP
operations directly with deterministic parsing and execution.

Also document how this explicit command mode coexists with conversational,
LLM-driven multi-step execution.

## Scope

- Primary entry point: `/opamp`
- Supported explicit verbs:
  - `help`
  - `tools`
  - `call`
- Compatibility aliases still accepted:
  - `/opamp api <verb> ...`
  - `/api <verb> ...`
- Explicit command-mode path assumption:
  - no destructive-operation confirmation step is required, because command
    intent is explicit and syntax is strict

## Syntax

General form:

```text
/opamp <verb> [subject] [arguments...]
```

### 1) Help

```text
/opamp help
/opamp help syntax
/opamp help tools
/opamp help call
/opamp help <tool_name>
```

Behavior:

- `help` (no topic): returns full syntax and examples.
- `help <tool_name>`: returns guidance to discover/invoke that tool.

### 2) Tool Discovery

```text
/opamp tools
/opamp tools <filter_text>
```

Behavior:

- Lists discovered tool names and short descriptions.
- Optional filter narrows results by substring.

### 3) Direct Tool Call

```text
/opamp call <tool_name> [key=value ...]
/opamp call <tool_name> --json '{"key":"value"}'
```

Argument rules:

- `key=value` pairs map to tool arguments.
- `--json` may be used instead of `key=value`.
- If both are supplied, reject with a usage error.

Examples:

```text
/opamp call tool_otel_agents host_name=alpha-node client_version=1.2.3
/opamp call tool_invoke_custom_command client_id=collector-a operation=restart
/opamp call tool_status target=collector-a
/opamp call tool_status --json '{"target":"collector-a"}'
```

## Processing Model

### 1) Route Detection

- If text starts with `/opamp` (or compatibility aliases) and uses a supported
  explicit verb (`help|tools|call`), route to strict command parser.
- Do not send strict command syntax through natural-language planner routing.

### 2) Parse

Recommended tokenizer:

- `shlex.split(...)` for quoted values

Internal model shape:

```json
{
  "verb": "call",
  "subject": "tool_status",
  "args": {
    "target": "collector-a"
  }
}
```

### 3) Validate

Validation checks:

1. verb is supported (`help|tools|call`)
2. tool exists for `call`
3. arguments are valid JSON or valid `key=value` tokens
4. reject unknown syntax with deterministic help text

### 4) Execute (Strict Command Mode)

For explicit command mode (`/opamp help|tools|call`):

- Execute a deterministic single operation path.
- Do not trigger iterative LLM re-planning.
- Return concise deterministic output.

### 5) Respond

Response contract:

- success: concise result summary + tool name
- validation error: exact syntax issue + one correction example
- unknown tool: suggest `/opamp tools`

## Conversational Multi-Step Flow (AI Mode)

When users send natural language (non-strict command syntax) and AI mode is
enabled, the graph now supports bounded iterative execution:

1. LLM selects next tool and args.
2. Broker executes tool.
3. Broker summarizes tool result.
4. LLM receives original user intent + latest tool result summary and decides:
   - stop with final response (`tool_name = null`), or
   - select another tool step.

This allows command-style workflows in one turn, for example:

- identify target agent
- check if action is valid/actionable for that agent
- execute action
- report result back to user

and status workflows:

- determine relevant status tool(s)
- fetch latest data
- return formatted response

### Multi-Step Guardrails

- `planner.max_execution_steps` controls loop depth (default `4`).
- Runtime clamps to safe bounds (minimum `1`, maximum `8`).
- Loop stops when:
  - planner returns no next tool,
  - next tool is unavailable,
  - next step repeats identical tool + args,
  - step limit reached.

## Help Output Contract

`/opamp help` should always include:

1. one-line purpose
2. grammar
3. examples for `help`, `tools`, and `call`
4. reminder that strict command mode is deterministic

Suggested footer:

```text
Tip: Run `/opamp tools` to discover callable tool names.
```

## Non-Goals

- replacing conversational `/opamp` usage
- removing LLM-driven planning for natural language
- changing MCP tool contracts
