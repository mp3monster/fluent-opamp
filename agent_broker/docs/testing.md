# Broker Test Coverage Guide

This guide summarizes the current automated test coverage for `opamp_broker`
and the documentation convention used by the broker test suite.

## Test Documentation Convention

Broker test modules follow two lightweight documentation rules:

1. Each test module includes a module docstring describing the area under test.
2. Each `test_*` function includes a short docstring that explains the behavior
   or regression being verified.

The intent is to keep the tests easy to scan in editors, in pytest output, and
during maintenance reviews.

## Broker-Focused Test Suites

The broker-related tests are currently split across the repository root
`tests/` folder and `agent_broker/tests/`.

### Root `tests/`

- `tests/test_agent_broker_broker_app.py`
  Covers broker startup, shutdown, CLI option handling, and logging setup.
- `tests/test_agent_broker_mcp_client.py`
  Covers MCP client error handling and console-safe diagnostics.
- `tests/test_agent_broker_planner_and_nodes.py`
  Covers planner selection, graph node behavior, summarization, and AI-service
  integration helpers.
- `tests/test_agent_broker_session_manager.py`
  Covers session defaults and AI mode propagation rules.
- `tests/test_agent_broker_slack_handlers.py`
  Covers Slack command parsing, AI mode directives, and handler registration.
- `tests/test_agent_broker_social_collaboration_factory.py`
  Covers social collaboration adapter selection and validation.

### `agent_broker/tests/`

- `agent_broker/tests/test_agent_broker_config_loader.py`
  Covers runtime config loading and provider-port route derivation.
- `agent_broker/tests/test_agent_broker_mcp_proxy.py`
  Covers the broker MCP proxy session flow and proxy route behavior.

## When To Update This Page

Update this guide when:

1. A new broker test module is added.
2. A broker test module is renamed or moved.
3. The test documentation convention changes.
