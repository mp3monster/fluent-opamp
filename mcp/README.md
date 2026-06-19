# MCP Client Setup Scripts

This folder contains MCP setup utility and some scripts for Claude Desktop, ChatGPT/Codex CLI, and VS Code.

For the full repository script catalog (all non-MCP scripts included), see
[`../docs/scripts.md`](../docs/scripts.md).

## Layout

- `mcp/*.py`
  Python entry points and packaging metadata live at the top of the `mcp` folder.
- `mcp/scripts/`
  Shell, PowerShell, and cmd wrappers live here so platform scripts are kept separate from Python sources.
- `mcp/src/opamp_mcp_config/`
  Installable Python package implementation.

## Script roles

- `configure_mcp_clients.py`
  Menu-driven Python CLI that reads JSON defaults, supports source/package/python-env
  deployment modes, and can configure Claude, Codex, VS Code, LibreChat, and Gemini.
- `build_mcp_config_tool.py`
  Builds the installable MCP configuration CLI wheel/sdist, can pip install the
  wheel, and writes a CycloneDX SBOM for the deployable artifact.
- `remove_legacy_mcp_scripts.cmd`
  Local Windows cleanup helper that can remove the legacy shell/PowerShell/cmd
  MCP configure wrappers after the Python CLI is available.

Wrappers forward arguments to the canonical script and only change defaults and naming compatibility.
The Python CLI is the preferred path when you want a guided workflow or need
targets beyond the legacy shell/PowerShell scripts.

## How the scripts work

The canonical shell/PowerShell script configures one or more targets from
`claude`, `chatgpt`, and `vscode`.

The Python CLI configures one or more targets from `claude`, `codex`,
`vscode`, `librechat`, and `gemini`.

- Claude Desktop:
  writes `mcpServers` entry in Claude config using remote transport:
  `mcp-remote <http://host:port/sse>` or fallback `npx -y mcp-remote <http://host:port/sse>`.
- ChatGPT/Codex:
  creates a stdio MCP entry via `codex mcp add ... uv run ... fastmcp run ...`.
- VS Code:
  generates/merges `.vscode/mcp.json` `servers` entry using FastMCP JSON output.
- LibreChat:
  writes or merges an `mcpServers` entry in `librechat.yaml`.
- Gemini CLI:
  writes or merges an `mcpServers` entry in `~/.gemini/settings.json` or a
  configured settings path.
- Legacy cleanup:
  known old names (`OpAMP Server`, `opamp-server`, `opampServer`) are removed except for the active configured name.
- Validation:
  options requiring values fail fast when missing (for example `--opamp-server-ip` without a value).

## FastMCP role

FastMCP is used for local stdio-style MCP process wiring:

- Required for ChatGPT/Codex registration path (`fastmcp run ...`).
- Required for VS Code JSON generation path (`fastmcp install mcp-json ...`).
- Not required for Claude Desktop remote setup, because Claude uses `mcp-remote` to connect to the provider SSE endpoint.

In short:

- Claude path: remote transport (`mcp-remote`).
- ChatGPT/Codex and VS Code paths: local stdio tooling (`fastmcp` + `uv`).
- LibreChat and Gemini can use local stdio tooling or remote SSE entries,
  depending on the selected target transport.

## Python menu CLI

The Python utility reads defaults from
[`mcp-client-defaults.json`](./mcp-client-defaults.json), opens a small menu,
and writes client configs from the selected values. Source-tree execution
defaults to repo-local `source` mode; the packaged wheel defaults to `package`
mode so installed entry points do not assume repository paths exist. The root
defaults file is the single checked-in source of truth; the build helper creates
a temporary packaged resource with `deployment.mode` set to `package` while
building the wheel/sdist.

Run the guided menu:

```bash
python3 mcp/configure_mcp_clients.py
```

If installed from the wheel, use either entry point:

```bash
opamp-mcp-config
python3 -m opamp_mcp_config
```

Run without prompts using defaults:

```bash
python3 mcp/configure_mcp_clients.py --yes
```

Preview without writing:

```bash
python3 mcp/configure_mcp_clients.py --preview
python3 mcp/configure_mcp_clients.py --yes --dry-run --clients claude,codex,vscode,gemini
```

Select clients and provider endpoint:

```bash
python3 mcp/configure_mcp_clients.py --yes --clients claude,codex,vscode --server-host localhost --server-port 8080
```

Use a wheel or pip package instead of repo source paths:

```bash
python3 mcp/configure_mcp_clients.py --yes --clients codex,vscode,gemini --deployment-mode package --package-spec dist/provider/opamp_server-0.4.0-py3-none-any.whl
```

Package mode uses `uv run --with <package-or-wheel> --with fastmcp ...` and
the import server spec `opamp_provider.mcptool.routes:mcpserver`. Source mode
uses the repo-local file spec under `provider/src`.

## Build, pip install, and SBOM

Build the MCP Python tool as a wheel and source distribution:

```bash
./mcp/scripts/build_mcp_config_tool.sh
```

PowerShell:

```powershell
.\mcp\scripts\build_mcp_config_tool.ps1
```

Windows cmd:

```cmd
mcp\scripts\build_mcp_config_tool.cmd
```

By default the build writes:

- wheel and sdist artifacts under `dist/mcp/`
- CycloneDX SBOM under `dist/sbom/opamp_mcp_config.cyclonedx.json`

The canonical repo-side SBOM helper implementation lives in:

- `dev-tools/src/opamp_dev_tools/sbom.py`

The MCP package vendors the helper under `mcp/src/opamp_build_tools/` so the
standalone wheel remains self-contained after installation.

During the build, `build_mcp_config_tool.py` copies
`mcp-client-defaults.json` into the package resource area and changes only
`deployment.mode` to `package`. The generated resource is removed again after
the build, keeping the repository defaults file as the only committed copy.

Build and install the wheel into the current Python environment with pip:

```bash
./mcp/scripts/build_mcp_config_tool.sh --install
```

Useful options:

- `--out-dir <path>`: choose the wheel/sdist output directory.
- `--sbom-path <path>`: choose the SBOM output file.
- `--skip-sbom`: build artifacts without writing the SBOM.
- `--no-clean`: keep existing `opamp_mcp_config-*` build artifacts.
- `--python <path>`: choose the Python executable used for build and install.

After installation, run:

```bash
opamp-mcp-config --preview
opamp-mcp-config --yes --clients claude,codex,vscode
```

## Retire legacy MCP wrapper scripts

Once `configure_mcp_clients.py` exists in this folder, or the packaged
`opamp-mcp-config` command is installed on `PATH`, the older target-specific
MCP configure wrappers are redundant.

Preview the files that would be removed:

```cmd
mcp\remove_legacy_mcp_scripts.cmd
```

Delete the legacy wrappers:

```cmd
mcp\remove_legacy_mcp_scripts.cmd --yes
```

The cleanup script removes only the legacy configure wrappers:

- `configure-claude-desktop-fastmcp.*`
- `configure-codex-fastmcp.*`
- `configure-mcp-clients-fastmcp.*`

It does not remove `configure_mcp_clients.py`, `mcp-client-defaults.json`, the
Python package files, or the build/SBOM scripts. Use `--force` only if you need
to remove wrappers before the replacement CLI can be detected.

### Python CLI defaults

The defaults file controls:

- provider host, port, scheme, and SSE path
- enabled client targets
- per-client server names and config paths
- remote versus stdio transport choices
- deployment mode: `source`, `package`, or `python-env`
- package or wheel specs used by package deployment mode

### Supported Python CLI targets

- `claude`: writes `mcpServers` in Claude Desktop config using remote SSE via `mcp-remote`.
- `codex`: runs `codex mcp add ...` with a generated stdio FastMCP command.
- `vscode`: writes `.vscode/mcp.json` using the VS Code `servers` schema.
- `librechat`: writes `mcpServers` in `librechat.yaml`; install `PyYAML` if you need to merge an existing YAML file.
- `gemini`: writes `mcpServers` in Gemini CLI `settings.json`.

### Extending the Python CLI

To add another LLM client:

1. Add default client settings under `clients` in `mcp-client-defaults.json`.
2. Add the client key to `SUPPORTED_CLIENTS` in `configure_mcp_clients.py`.
3. Implement a small target class with `apply(settings, dry_run)`.
4. Register it in the `TARGETS` map.

Most new stdio clients can reuse `build_stdio_server_entry()`. Remote clients
can reuse `build_remote_server_entry()`.

## opamp_cli delegation strategy

The `opamp-cli` project should treat `opamp-mcp-config` as the specialist MCP
configuration tool rather than duplicating this menu and client-specific logic.

Recommended detection order:

1. Explicit command override from the user or config, for example an
   `OPAMP_MCP_CONFIG_COMMAND` environment variable or future `opamp-cli`
   setting.
2. Installed console script found on `PATH`: `opamp-mcp-config`.
3. Installed Python module probe: `python -m opamp_mcp_config --preview`.
4. Workspace fallback when running from source: `python mcp/configure_mcp_clients.py`.

Recommended delegation behavior:

- `opamp-cli` keeps the conversation context and detects MCP setup intent such
  as “configure MCP”, “set up Claude MCP”, or “add Gemini”.
- Once intent is clear, `opamp-cli` launches the MCP tool in the same terminal
  for interactive mode, preserving stdin/stdout so the menu feels native.
- For non-interactive flows, `opamp-cli` passes explicit flags such as
  `--yes`, `--clients`, `--server-host`, `--server-port`,
  `--deployment-mode`, and `--package-spec`.
- The MCP tool remains the owner of target schema knowledge, config file merge
  behavior, and source/package/python-env deployment command construction.
- If the tool is missing, `opamp-cli` should explain the install/build command:
  `python mcp/build_mcp_config_tool.py --install`.
- If the user explicitly says which tool to use, `opamp-cli` should honor that
  command path before auto-detection.

This keeps `opamp-cli` as the conversational router and workflow shell, while
the MCP package stays independently testable, installable, and extendable for
future LLM clients.

## Why `uv.lock` is provided

The repository includes `provider/uv.lock` so `uv run --project provider ...`
resolves the same dependency graph across machines and over time.

This matters for MCP setup because ChatGPT/Codex and VS Code script paths depend
on `uv` + `fastmcp` execution consistency.

Benefits:

- reproducible installs and execution for MCP client registration
- fewer environment-specific breakages from transitive dependency drift
- better CI/local parity when validating MCP behavior

## Required server parameters

Always pass server host (and usually port) so scripts do not prompt:

- Bash: `--opamp-server-ip <host-or-ip>` and optional `--opamp-server-port <port>`
- PowerShell: `-OpAMPServerIp <host-or-ip>` and optional `-OpAMPServerPort <port>`

These values set:

- `OPAMP_SERVER_IP`
- `OPAMP_SERVER_URL` (`http://<host-or-ip>:<port>`, default `8080`)
- `OPAMP_MCP_SSE_URL` (`http://<host-or-ip>:<port>/sse`, default `8080`)

## Parameters

`configure-claude-desktop-fastmcp` wrapper:

- `--name` / `-Name`: Claude display/server name (default `OpAMP Server`)
- `--clients` / `-Clients`: optional override target list (default `claude`)
- `--opamp-server-ip` / `-OpAMPServerIp`: OpAMP server host/IP
- `--opamp-server-port` / `-OpAMPServerPort`: OpAMP server port (default `8080`)
- `--server-spec` / `-ServerSpec`: forwarded for compatibility (not used by Claude remote transport setup)
- `--project` / `-Project`: forwarded for compatibility
- `--no-editable` / `-NoEditable`: forwarded for compatibility
- `--help` / `-Help`: show usage

`configure-codex-fastmcp` wrapper:

- `--name` / `--server-name` / `-ServerName`: ChatGPT/Codex server name (default `opamp-server`)
- `--clients` / `-Clients`: optional override target list (default `chatgpt`)
- `--opamp-server-ip` / `-OpAMPServerIp`: OpAMP server host/IP
- `--opamp-server-port` / `-OpAMPServerPort`: OpAMP server port (default `8080`)
- `--server-spec` / `-ServerSpec`: Python server spec passed to `fastmcp run`
- `--project` / `-Project`: project path used by `uv run --project`
- `--no-editable` / `-NoEditable`: skip `--with-editable`
- `--help` / `-Help`: show usage

`configure-mcp-clients-fastmcp` canonical script:

- `--clients` / `-Clients`: comma-separated targets (`claude`, `chatgpt`, `vscode`)
- `--claude-name` / `-ClaudeName`: Claude entry name (default `OpAMP Server`)
- `--chatgpt-name` / `--server-name` / `-ChatGPTName`: Codex entry name (default `opamp-server`)
- `--vscode-name` / `-VSCodeName`: VS Code server key (default `opampServer`)
- `--vscode-config` / `-VSCodeConfigPath`: VS Code MCP config path (default `.vscode/mcp.json`)
- `--claude-config` (bash only): Claude config path override
- `--server-spec` / `-ServerSpec`: Python server spec passed to `fastmcp run`
- `--project` / `-Project`: project path used by `uv run --project`
- `--opamp-server-ip` / `-OpAMPServerIp`: OpAMP server host/IP
- `--opamp-server-port` / `-OpAMPServerPort`: OpAMP server port (default `8080`)
- `--no-editable` / `-NoEditable`: skip `--with-editable`
- `-h` / `--help` / `-Help`: show usage

## Usage examples

PowerShell:

```powershell
& ".\mcp\configure-claude-desktop-fastmcp.ps1" -OpAMPServerIp localhost -OpAMPServerPort 8080
& ".\mcp\configure-codex-fastmcp.ps1" -OpAMPServerIp localhost -OpAMPServerPort 8080
& ".\mcp\configure-mcp-clients-fastmcp.ps1" -Clients "claude,chatgpt" -OpAMPServerIp localhost -OpAMPServerPort 8080
```

Bash:

```bash
./mcp/configure-claude-desktop-fastmcp.sh --opamp-server-ip localhost --opamp-server-port 8080
./mcp/configure-codex-fastmcp.sh --opamp-server-ip localhost --opamp-server-port 8080
./mcp/configure-mcp-clients-fastmcp.sh --clients claude,chatgpt --opamp-server-ip localhost --opamp-server-port 8080
```

Python menu CLI:

```bash
python3 mcp/configure_mcp_clients.py --yes --clients claude,codex,vscode
python3 mcp/configure_mcp_clients.py --yes --clients librechat,gemini --deployment-mode package --package-spec opamp-server
opamp-mcp-config --yes --clients claude,codex,vscode
```

## Verify client config after running scripts

Claude Desktop (Windows):

```powershell
Get-Content "$env:APPDATA\Claude\claude_desktop_config.json"
```

Claude Desktop (Linux/macOS):

```bash
cat "${XDG_CONFIG_HOME:-$HOME/.config}/Claude/claude_desktop_config.json"
```

Confirm `mcpServers` contains your configured server (default wrapper name: `OpAMP Server`) and that the command is `mcp-remote` (or `npx` with `mcp-remote` args).

ChatGPT/Codex CLI:

```bash
codex mcp list
codex mcp get opamp-server
```

VS Code (only when using the canonical multi-client script with `vscode` target):

```bash
cat .vscode/mcp.json
```

LibreChat:

```bash
cat librechat.yaml
```

Gemini CLI:

```bash
cat ~/.gemini/settings.json
```

## Related docs

- Script catalog: [`../docs/scripts.md`](../docs/scripts.md)
- Auth and MCP bearer-token behavior: [`../docs/authentication.md`](../docs/authentication.md)
- Endpoint definitions (`/sse`, `/messages`, `/mcp`): [`../docs/endpoints.md`](../docs/endpoints.md)
- LibreChat MCP server config reference: https://www.librechat.ai/docs/configuration/librechat_yaml/object_structure/mcp_servers
- Gemini CLI MCP server config reference: https://github.com/google-gemini/gemini-cli/blob/main/docs/tools/mcp-server.md
