# CLI Scripts

This directory contains shell-specific helper scripts for setting up convenient
shortcuts to the local OpAMP CLI entrypoint at `cli/main.py`.

The scripts create commands named `opamp-cli` and `opamp`. Both commands run the
same CLI.

## Scripts

| Script | Shell | What it does |
|---|---|---|
| `install_cli_aliases.sh` | Bash or Zsh | Adds an alias block to `~/.bashrc` and `~/.zshrc` that runs `python3 cli/main.py`. Existing OpAMP alias blocks are replaced. |
| `install_cli_aliases.ps1` | PowerShell | Adds functions to the current PowerShell profile that run `python cli/main.py`. It also updates the legacy Windows PowerShell profile when needed. Existing OpAMP alias blocks are replaced. |
| `install_cli_aliases.cmd` | Windows cmd.exe | Writes a `doskey` macro file at `%USERPROFILE%\.opamp\opamp-cli.doskey` and prints commands for loading it now or through the optional `Command Processor\AutoRun` registry setting. |

## Usage

From the repository root:

```bash
./cli/scripts/install_cli_aliases.sh
```

```powershell
.\cli\scripts\install_cli_aliases.ps1
```

```cmd
cli\scripts\install_cli_aliases.cmd
```

After running the script for your shell, open a new terminal session or follow
the reload command printed by the script.

## Notes

- These helpers assume the CLI entrypoint exists at `cli/main.py`.
- The shell aliases call Python directly and use this checkout of the repository.
- For package-based installation, use the CLI setup instructions in
  `../README.md`.
