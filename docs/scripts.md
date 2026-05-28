# Scripts Reference

This table lists the helper scripts and their platform-specific names.

| Purpose | Linux / macOS | Windows |
| --- | --- | --- |
| Run the OpAMP server (provider) | `scripts/run_opamp_server.sh` | `scripts/run_opamp_server.cmd` |
| Run the OpAMP broker | `scripts/run_opamp_broker.sh` | `scripts/run_opamp_broker.cmd` |
| Stop OpAMP broker service mode | `scripts/run_opamp_broker_stop.sh` | `scripts/run_opamp_broker_stop.cmd` |
| Start Fluentd directly | `scripts/start_fluentd.sh` | `scripts/start_fluentd.cmd` |
| Configure local Keycloak for JWT auth testing | `scripts/configure_keycloak.sh` | `scripts/configure_keycloak.cmd` / `scripts/configure_keycloak.ps1` |
| Generate self-signed TLS cert/key for local HTTPS testing | `scripts/generate_self_signed_tls_cert.py` | `scripts\generate_self_signed_tls_cert.py` |
| Ensure `provider.tls` settings exist in config JSON | `scripts/ensure_provider_tls_config.py` | `scripts\ensure_provider_tls_config.py` |
| Render Mermaid `.mmd` to PNG (local wrapper) | `scripts/render_mermaid_png.sh` | n/a |
| Request server shutdown via API | `scripts/shutdown_opamp_server.sh` | `scripts/shutdown_opamp_server.cmd` |
| Install CLI aliases/macros for Linux shells | `cli/scripts/install_cli_aliases.sh` | n/a |
| Install CLI aliases/macros for cmd | n/a | `cli\scripts\install_cli_aliases.cmd` |
| Install CLI aliases/macros for PowerShell | n/a | `cli\scripts\install_cli_aliases.ps1` |
| Install repo git hooks path (`core.hooksPath=.githooks`) | `scripts/install_git_hooks.sh` | `scripts/install_git_hooks.cmd` |
| Build deployable Python artifacts (provider + consumer) | `scripts/build_artifacts.sh` | `scripts/build_artifacts.cmd` |
| Build wheel artifacts and optionally publish to GitHub release assets | `scripts/build_and_publish_wheels.py` | `scripts\build_and_publish_wheels.py` |
| Build consolidated OpAMP PDF manual | `scripts/build_opamp_manual.sh` | `scripts\build_opamp_manual.cmd` |
| Build compacted provider web UI JavaScript assets (`*.mini.js`) | `scripts/build_provider_ui_compact_assets.py` | `scripts\build_provider_ui_compact_assets.py` |
| Run security checks gate (minify, tests, ruff security, detect-secrets, pip-audit) | `scripts/security-checks` | `scripts\security-checks.cmd` |
| Configure MCP for Claude Desktop (wrapper) | `mcp/configure-claude-desktop-fastmcp.sh` | `mcp\configure-claude-desktop-fastmcp.ps1` |
| Configure MCP for ChatGPT/Codex (wrapper) | `mcp/configure-codex-fastmcp.sh` | `mcp\configure-codex-fastmcp.ps1` |
| Configure MCP for selected clients (canonical script) | `mcp/configure-mcp-clients-fastmcp.sh` | `mcp\configure-mcp-clients-fastmcp.ps1` |

`configure_keycloak` supports a container readiness-only mode:

- Linux / macOS: `./scripts/configure_keycloak.sh --ready-only`
- Windows cmd: `scripts\configure_keycloak.cmd --ready-only`
- Windows PowerShell: `.\scripts\configure_keycloak.ps1 -ReadyOnly`
- Optional runtime override: `CONTAINER_RUNTIME=docker|podman`

## MCP Client Setup Scripts

Detailed MCP client setup documentation has moved to:
[`../mcp/README.md`](../mcp/README.md)

That guide includes:

- script architecture (wrapper vs canonical)
- how FastMCP is used by ChatGPT/Codex and VS Code clients
- Claude Desktop remote transport behavior (`mcp-remote`)
- why `provider/uv.lock` is committed for reproducible `uv`-based MCP setup
- full command-line parameter reference
- usage and verification examples

## Provider HTTPS bootstrap

- `run_opamp_server` accepts `--https` on Linux and Windows launchers.
- When `--https` is supplied, the launcher:
  1. Generates a self-signed cert/key in `certs/provider-server.pem` and `certs/provider-server-key.pem`.
  2. Updates the active OpAMP config file (`OPAMP_CONFIG_PATH` or `config/opamp.json`) to include:
     - `provider.tls.cert_file`
     - `provider.tls.key_file`
     - `provider.tls.trust_anchor_mode` (`none`)
     - `provider.tls.enabled` defaults to `true` when omitted.
- The wrapper consumes `--https` itself and does not pass it through to `opamp_provider.server`.

## Supervisor config defaults

- `run_fluentbit_supervisor` legacy wrapper resolves config in this order:
  `tests/opamp.json` -> `config/opamp.json`.
- `run_fluentd_supervisor` legacy wrapper resolves config in this order:
  `consumer/opamp-fluentd.json` -> `tests/opamp.json` -> `config/opamp.json`.
- `run_fluentd_supervisor` and `start_fluentd` use `consumer/fluentd.conf`
  as the canonical Fluentd config path.

## CLI demo profile mapping

When `OPAMP_DEMO=true`, the CLI exposes profile-based demo start/stop options.
Profile mapping lives in:

- `cli/config/demo_consumer_profiles.json`

Each profile includes a logical name and file references for:

- simulator instances file
- Fluent Bit OpAMP config + agent config
- Fluentd OpAMP config + agent config

The CLI demo flow supports profile selection by logical name without relying on wrapper scripts.

## Artifact build scripts

`build_artifacts` scripts generate both `sdist` and `wheel` packages for:

- `provider` -> `dist/provider/`
- `consumer` -> `dist/consumer/`
- consolidated manual -> `dist/manual/opamp_manual.pdf`

The scripts:

- activate `.venv` when present
- refresh git-derived component version metadata via `scripts/update_component_versions.py`
- ensure the `build` package is installed
- ensure `reportlab` is installed
- run `security_checks.py` (which includes provider UI compaction)
- regenerate the consolidated OpAMP PDF manual
- clear old files in target artifact folders before building

Provider packaging note:

- provider wheel creation checks whether the separate `opamp-cli` component is available
- if the CLI is not detected in the workspace or as an installed distribution, the build prints a warning
- the CLI is not bundled into the provider wheel; install/deploy `opamp-cli` separately when you want the guided launcher experience

Example:

```bash
./scripts/build_artifacts.sh
```

```cmd
scripts\build_artifacts.cmd
```

## Wheel Build + GitHub Publish

Use `build_and_publish_wheels.py` to generate wheels for both components:

- provider (server) wheel -> `dist/provider/*.whl`
- consumer (agent) wheel -> `dist/consumer/*.whl`
- provider deployable artifact SBOM (CycloneDX JSON) -> `dist/sbom/opamp_provider_deployable_artifacts.cyclonedx.json`
- consumer deployable artifact SBOM (CycloneDX JSON) -> `dist/sbom/opamp_consumer_deployable_artifacts.cyclonedx.json`

Build only:

```bash
python3 scripts/build_and_publish_wheels.py
```

The provider wheel build in this flow also warns when `opamp-cli` is not available.

Build and publish to GitHub release assets in `mp3monster/fluent-opamp`:

```bash
GITHUB_TOKEN=<token> python3 scripts/build_and_publish_wheels.py --publish --tag v0.1.0
```

Optional publish flags:

- `--repo owner/name` to override repository target
- `--release-name "..."` to set release title (defaults to tag)
- `--release-notes "..."` or `--release-notes-file <path>`
- `--draft`
- `--prerelease`
- `--provider-sbom-path <path>` to override provider SBOM output path
- `--consumer-sbom-path <path>` to override consumer SBOM output path
- `--manual-path <path>` to override PDF manual output path
- `--skip-manual` to skip manual regeneration in this run
- `--skip-ui-compaction` to skip provider UI JavaScript compaction in this run
- `--skip-security-checks` to skip the security checks workflow

By default, `build_and_publish_wheels.py` regenerates:

- `dist/manual/opamp_manual.pdf`
- provider UI compact JS assets (`web_ui_*.mini.js`)
- provider and consumer deployable-artifact SBOMs (CycloneDX JSON)

SBOM freshness/integrity enforcement:

- after wheel build, each SBOM is validated against its wheel metadata and file hash
- validation checks include wheel name/version/hash, dependency refs, and timestamp ordering
- the wheel process fails if any SBOM is stale, malformed, or inconsistent with built artifacts

By default, `build_and_publish_wheels.py` also runs security checks via:

- `scripts/security_checks.py`

Security checks include:

- provider UI compaction (`build_provider_ui_compact_assets.py`)
- full unit test stack (`pytest`)
- Ruff security rules (`ruff check --select S .`)
- detect-secrets scan
- pip-audit across root/provider/consumer/broker requirements

`security_checks.py` behavior:

- if `APP_ENABLE_DEV_FEATURES` is set, it is unset for the check run and a message is logged before checks execute
- this ensures checks run against non-dev asset-selection behavior

When `--publish` is used, the provider wheel, consumer wheel, provider SBOM, consumer SBOM, and generated PDF manual are uploaded as release assets.

## Mermaid PNG rendering

Use the wrapper script after installing the Mermaid toolchain:

```bash
./scripts/render_mermaid_png.sh -i input.mmd -o output.png
```
