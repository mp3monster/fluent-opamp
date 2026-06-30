## Phase 1: Request Classification

### Steps
1. Determine whether the request is for help/capabilities.
2. Determine whether the request is for status/inspection.
3. Determine whether the request is for command/action.

### Outputs
1. `help/capabilities`
2. `status/inspection`
3. `command/action`

## Phase 2: Help and Capability Handling

### Steps
1. Return guidance and available tools.
2. Do not execute tools for pure help/capability requests.

## Phase 3: Status and Inspection Handling

### Steps
1. Choose the best status/list tool.
2. Determine whether the user requested filter attributes.
3. Extract only schema-valid filter arguments from user text.
4. Use only filter keys supported by the selected tool input schema (for example: `service_instance_id`, `host_name`, `host_ip`, `client_version`, `invert_filter`) and only when present in schema.
5. If requested attributes cannot be mapped to supported schema fields, tell the user which attributes cannot be provided.
6. Execute and summarize results with a compact table or bullets.

## Phase 4: Command Target Resolution

### Steps
1. Determine target scope:
   1. Explicit single instance id/target.
   2. Filter-based target set when non-UID attributes are used or wildcard-like intent is present.
2. If a single instance is requested, validate that the target exists.
3. If no single valid target is confirmed, treat as ambiguous.
4. If ambiguous:
   1. Do not execute the command yet.
   2. Call list/filter tool to resolve candidates.
   3. Return candidate summary (instance id, name, IP, hostname, client id if available, plus attributes used for matching) and ask the user to confirm one target.

## Phase 5: Target Cardinality and Policy Gate

### Steps
1. Detect explicit plurality intent in user request (for example: `ANY`, `ALL`, `all agents`, `every`).
2. Count resolved targets.
3. Enforce configured cap on number of targets allowed for a command.
4. Check trusted slash-command mode (`api_command_mode`) and trusted-bypass policy.

### Decision Rules
1. If count is `0`, stop and tell the user no matching targets were found.
2. If count is `1`, proceed as single-target execution.
3. If count is greater than `1` and plurality intent is `true`, and count is within cap, proceed with multi-target execution.
4. If count is greater than `1` and plurality intent is `false`, do not execute and ask user to confirm multi-target intent.
5. If count exceeds cap, do not execute and ask user to narrow filters or increase cap.
6. If request is from trusted slash-command mode and trusted bypass is enabled, allow execution to proceed while still enforcing discovered-tool and schema-valid argument checks.

## Phase 6: Command Execution

### Multi-Target Execution
1. Prefer bulk command path when available.
2. If no bulk command path exists, explicitly state that execution will run one instance at a time and iterate across resolved targets.
3. Summarize total matched/sent/succeeded/failed actions.

### Single-Target Execution
1. Execute command tool with schema-valid arguments.
2. Return accepted/queued/failed outcome and user-friendly error text when relevant.

## Phase 7: Cross-Cutting Rules

### Rules
1. Never invent tools or arguments.
2. Use only discovered tools and input schema fields.
3. If provider is offline, return offline guidance.
4. Preserve best-effort fallback behavior:
   1. First attempt to map unresolved requests to the safest compatible status/health/list behavior.
   2. Only return "request not understood" when safe fallback mapping is not possible.
5. Troubleshooting presentation policy:
   1. Default user mode: translate tool-specific errors and codes to user-friendly neutral language.
   2. Developer mode: include additional troubleshooting detail (for example tool name, error classification, and actionable diagnostics), while keeping sensitive data redacted.
6. If the request cannot be resolved and no safe fallback applies, tell the user it was not understood.
7. Trusted slash commands are allowed:
   1. `/opamp call ...` in trusted mode may bypass ambiguity/cardinality confirmation prompts.
   2. Trusted mode does not bypass tool discovery validation or input schema validation.

## Phase 8: Configuration Controls

### Settings
1. `planner.max_command_targets`: maximum number of targets allowed for a single command execution.
2. `planner.require_plurality_for_multi_target`: controls whether multi-target execution requires explicit plurality intent.
3. `planner.developer_troubleshooting_enabled`: enables developer-facing troubleshooting detail in responses.
4. `planner.trusted_api_command_bypass_enabled`: allows trusted slash-command mode to bypass ambiguity/cardinality confirmation prompts.
