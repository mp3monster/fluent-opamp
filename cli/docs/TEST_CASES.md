# CLI Test Cases

This document is the maintained test-case index for the `cli` component.
Test modules should reference this file so the implementation and the documented coverage stay aligned.

## Unit Tests

### `cli/tests/test_main_unit.py`
- `test_split_script_directive_parses_output_name_and_command`
  - Verifies the `script` directive is split into an output filename and the remaining command text.
- `test_normalize_python_script_command_prefixes_python_launcher`
  - Verifies direct Python script targets are normalized to use an explicit Python launcher.
- `test_command_text_from_args_preserves_shell_quoting`
  - Verifies reconstructed command text preserves quoting semantics for shell execution.
- `test_materialize_ordered_actions_preserves_order_and_skips_missing`
  - Verifies guided action materialization preserves declared order and ignores undefined actions.
- `test_catalog_launch_config_path_enables_catalog`
  - Verifies generated runtime config for catalog launch enables the catalog feature.
- `test_process_tail_setting_round_trip`
  - Verifies process-tail settings are persisted and reloaded correctly.
- `test_main_writes_component_lifecycle_log`
  - Verifies the CLI component lifecycle log is created during execution.
- `test_status_command_reports_default_opamp_config_path`
  - Verifies `status` reports the default `config/opamp.json` path and successful load state.
- `test_status_command_reports_env_opamp_config_path`
  - Verifies `status` reports an `OPAMP_CONFIG_PATH` override and successful load state.
- `test_status_command_reports_invalid_opamp_config`
  - Verifies `status` reports invalid JSON instead of treating an unreadable config as loaded.
- `test_rejected_guided_action_is_logged`
  - Verifies invalid guided actions are rejected and logged.
- `test_resolve_guided_action_matches_aliases`
  - Verifies guided-action alias resolution maps common aliases to the correct action.
- `test_start_and_stop_action_orders_are_stable`
  - Verifies the ordered `start` and `stop` action lists remain stable.
- `test_broker_stop_action_uses_cli_managed_process_records`
  - Verifies broker shutdown uses CLI-managed process records instead of the retired broker PID-file wrapper flow.
- `test_script_mode_generates_broker_launcher_script`
  - Verifies `opamp-cli script ...` can generate a broker launcher script with the expected module command and config path.

## End-to-End Tests

### `cli/tests/test_main_e2e.py`
- `test_help_command_prints_usage`
  - Verifies `help` output is available from the CLI entrypoint.
- `test_status_command_reports_runtime_paths`
  - Verifies `status` reports the effective OpAMP config path, managed-process state path, log path, and CLI log path.
- `test_direct_execution_runs_python_command`
  - Verifies direct command execution works through the CLI entrypoint.
- `test_script_generation_writes_os_native_script`
  - Verifies `script ...` generation creates an OS-native output script.
- `test_unknown_guided_target_returns_error`
  - Verifies unknown guided targets fail cleanly with a non-zero exit path.
