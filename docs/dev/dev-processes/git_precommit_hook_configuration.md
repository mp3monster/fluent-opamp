# Git Pre-Commit Hook Configuration (Internal Note)

This note documents how the repository pre-commit hook is configured, what it runs, and how to apply/verify it locally.

## Scope

The hook is used to refresh component version metadata before each commit.

Managed version files:

- `provider/src/opamp_provider/version.json`
- `agent_broker/opamp_broker/version.json`
- `consumer/src/opamp_consumer/version.json`
- `consumer-sim/version.json`

## Hook implementation

Primary hook script:

- `.githooks/pre-commit`

Core behavior:

1. Resolve repo root with `git rev-parse --show-toplevel`.
1. Acquire a repo-local pre-commit guard so duplicate GUI/legacy hook invocations do not race on the Git index.
1. Resolve Python runtime (`python3` fallback to `python`).
1. Run `scripts/update_component_versions.py --quiet`.
1. Stage all generated version JSON files via `git add`.

## Installer scripts

Hook installation is automated through:

- Linux/macOS: `scripts/install_git_hooks.sh`
- Windows CMD: `scripts/install_git_hooks.cmd`

Installer behavior:

1. Set repo-local git config: `core.hooksPath=.githooks`.
1. Ensure `.githooks/pre-commit` is executable.
1. Create/update fallback shim `.git/hooks/pre-commit` (safe guard for GUI clients using legacy hook resolution).
1. Preserve unrelated custom legacy hooks (installer avoids replacing unknown custom hook content).

## How to apply in a clone

### Linux/macOS

```bash
./scripts/install_git_hooks.sh
```

### Windows CMD

```cmd
scripts\install_git_hooks.cmd
```

## How to verify

Check configured hooks path:

```bash
git config --local --get core.hooksPath
```

Expected output:

```text
.githooks
```

Inspect the primary hook:

```bash
sed -n '1,120p' .githooks/pre-commit
```

Inspect fallback shim:

```bash
LEGACY="$(git rev-parse --git-common-dir)/hooks/pre-commit"
echo "$LEGACY"
sed -n '1,80p' "$LEGACY"
```

## GitKraken notes

- GitKraken commits should execute hooks when repository git hooks are enabled.
- If hooks do not run, confirm GitKraken preferences are not disabling hooks.
- Because this repo sets `core.hooksPath=.githooks` and also writes a legacy `.git/hooks/pre-commit` shim, both standard and legacy hook paths are covered.
- Some GUI clients can invoke both the configured hooks path and the legacy shim; the pre-commit hook now de-duplicates concurrent runs with a guard under the repo git-common-dir to avoid `.git/index.lock` collisions.

## Manual test flow

1. Edit one tracked file.
1. Run `git commit`.
1. Confirm version files were updated/staged by the hook (`git status`).

## Related files

- `scripts/update_component_versions.py`
- `scripts/install_git_hooks.sh`
- `scripts/install_git_hooks.cmd`
- `.githooks/pre-commit`
