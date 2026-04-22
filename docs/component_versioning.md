# Component Versioning

Component version metadata is derived from the current git `HEAD` commit and commit date.

- `git_commit`: short commit reference (`git rev-parse --short=12 HEAD`)
- `git_commit_date`: commit timestamp (`git show -s --format=%cI HEAD`)
- `version`: formatted as `<git_commit> (<git_commit_date>)`

Generated files:

- `provider/src/opamp_provider/version.json`
- `agent_broker/opamp_broker/version.json`
- `consumer/src/opamp_consumer/version.json`
- `consumer-sim/version.json`

The generator script is:

- `scripts/update_component_versions.py`

## Where version is shown

- Server CLI: `opamp-provider --help` and `opamp-provider --version`
- Server UI help page: `http://localhost:8080/help`
- Broker CLI: `python -m opamp_broker.broker_app --help` and `--version`
- Consumer CLI help payload (`--help`): includes `component_version` in JSON output
- Consumer simulator launcher: `python consumer-sim/src/consumer_sim_launcher.py --help` and `--version`

## Git hook integration

The pre-commit hook updates and stages component version files automatically:

- `.githooks/pre-commit`

Install hook path once per clone:

- Linux/macOS: `./scripts/install_git_hooks.sh`
- Windows: `scripts\\install_git_hooks.cmd`

GUI clients:

- GitKraken commits use the repository git config, so after running the install script the hook is triggered for GUI commits as well.
- The installer also writes a fallback shim at `.git/hooks/pre-commit` (without overriding unrelated custom hooks) to cover clients that rely on legacy hook lookup.
- Verify current setup with:
  - `git config --local --get core.hooksPath` (expected: `.githooks`)

## Build and packaging integration

Build/package scripts refresh component version metadata before producing artifacts:

- `scripts/build_artifacts.sh`
- `scripts/build_artifacts.cmd`
- `scripts/build_and_publish_wheels.py`
- `agent_broker/scripts/package.sh`
- `agent_broker/scripts/package.ps1`
