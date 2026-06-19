# Hatchling Usage In This Repository

This repository uses `hatchling` as the PEP 517 build backend for a subset of Python components.

## Where Hatchling Is Used

Hatchling is currently declared in these component `pyproject.toml` files:

- `agent_broker/pyproject.toml`
- `consumer/pyproject.toml`
- `provider/pyproject.toml`

Each of those files contains:

```toml
[build-system]
requires = ["hatchling>=1.25"]
build-backend = "hatchling.build"
```

## Why Hatchling Is Used

Hatchling is being used for these components because it provides a clean `pyproject.toml`-first packaging model and avoids the need for a metadata-heavy `setup.py`.

The main reasons in this repository are:

- To keep packaging metadata in `pyproject.toml`.
- To support modern `python -m build` workflows.
- To define wheel and source distribution contents declaratively under `tool.hatch`.
- To support custom build hook behavior where needed.

## Component-Specific Notes

### `agent_broker`

`agent_broker` uses Hatchling as a straightforward build backend. Its `pyproject.toml` defines:

- the build backend
- the package metadata
- wheel contents under `[tool.hatch.build.targets.wheel]`
- sdist contents under `[tool.hatch.build.targets.sdist]`

This component does not currently use a custom Hatch build hook.

### `consumer`

`consumer` also uses Hatchling in a straightforward way. Its `pyproject.toml` uses Hatchling mainly to:

- package from `pyproject.toml`
- define the wheel package roots
- include packaged JSON assets in the wheel

This component does not currently use a custom Hatch build hook either.

### `provider`

`provider` is the most advanced Hatchling user in the repo.

In addition to normal Hatchling packaging, it uses:

- `[tool.hatch.build.targets.wheel]` to define package roots
- `[tool.hatch.build.targets.wheel.force-include]` to pull extra repository content into the wheel
- `[tool.hatch.build.hooks.custom]` together with `provider/hatch_build.py`

The custom hook in `provider/hatch_build.py` is used to emit packaging-time warnings when the OpAMP CLI is not available during a provider build. That is the main repo-specific reason Hatchling is more useful here than a minimal backend.

## Interaction With `dev-tools`

The developer CLI builds artefacts with `python -m build`.

When `--no-isolation` is used, the selected Python environment must already have the component's build backend installed. For Hatchling-backed components that means `hatchling` must be importable by that Python interpreter.

To reduce failures such as:

```text
ERROR Backend 'hatchling.build' is not available.
```

the developer CLI now reads the component's `[build-system].requires` values and installs them before running `python -m build --no-isolation`.

## Practical Guidance

- If you are building `agent_broker`, `consumer`, or `provider` outside an isolated build environment, make sure `hatchling` is installed in the Python interpreter you are using.
- If you are converting another component to Hatchling, place the authoritative packaging metadata in `pyproject.toml`.
- Only add a custom Hatch build hook when there is a real build-time behavior need, as with `provider/hatch_build.py`.
