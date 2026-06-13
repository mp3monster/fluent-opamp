#!/usr/bin/env python3
"""Build deployable Python wheel artefacts and optionally publish them.

This script can build independent wheels for the OpAMP provider, consumer,
catalog service, CLI, and consumer simulator launcher. Each selected artefact
also receives its own CycloneDX SBOM.
"""

from __future__ import annotations

import argparse
import json
import mimetypes
import os
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from dev_tools.sbom import (  # noqa: E402
    validate_wheel_artifact_sbom,
    write_wheel_artifact_sbom,
)

DEFAULT_REPO = "mp3monster/fluent-opamp"
DEFAULT_MANUAL_PATH = "dist/manual/opamp_manual.pdf"
DEFAULT_COMPONENTS = ("provider", "consumer", "catalog", "cli", "consumer-sim")
LEGACY_DEFAULT_PROVIDER_SBOM_PATH = (
    "dist/sbom/opamp_provider_deployable_artifacts.cyclonedx.json"
)
LEGACY_DEFAULT_CONSUMER_SBOM_PATH = (
    "dist/sbom/opamp_consumer_deployable_artifacts.cyclonedx.json"
)


@dataclass(frozen=True)
class ComponentTarget:
    """Describes one independently buildable wheel artefact."""

    key: str
    source_dir: str
    dist_dirname: str
    root_component_name: str
    default_sbom_relpath: str
    display_name: str


COMPONENT_TARGETS: dict[str, ComponentTarget] = {
    "provider": ComponentTarget(
        key="provider",
        source_dir="provider",
        dist_dirname="provider",
        root_component_name="fluent-opamp-provider-deployable-artifact",
        default_sbom_relpath="dist/sbom/opamp_provider_deployable_artifacts.cyclonedx.json",
        display_name="Provider",
    ),
    "consumer": ComponentTarget(
        key="consumer",
        source_dir="consumer",
        dist_dirname="consumer",
        root_component_name="fluent-opamp-consumer-deployable-artifact",
        default_sbom_relpath="dist/sbom/opamp_consumer_deployable_artifacts.cyclonedx.json",
        display_name="Consumer",
    ),
    "catalog": ComponentTarget(
        key="catalog",
        source_dir="catalog-service",
        dist_dirname="catalog",
        root_component_name="fluent-opamp-catalog-service-deployable-artifact",
        default_sbom_relpath="dist/sbom/opamp_catalog_service_deployable_artifacts.cyclonedx.json",
        display_name="Catalog service",
    ),
    "cli": ComponentTarget(
        key="cli",
        source_dir="cli",
        dist_dirname="cli",
        root_component_name="fluent-opamp-cli-deployable-artifact",
        default_sbom_relpath="dist/sbom/opamp_cli_deployable_artifacts.cyclonedx.json",
        display_name="CLI",
    ),
    "consumer-sim": ComponentTarget(
        key="consumer-sim",
        source_dir="consumer-sim",
        dist_dirname="consumer-sim",
        root_component_name="fluent-opamp-consumer-sim-deployable-artifact",
        default_sbom_relpath="dist/sbom/opamp_consumer_sim_deployable_artifacts.cyclonedx.json",
        display_name="Consumer simulator",
    ),
}


def _run(cmd: list[str], *, cwd: Path) -> None:
    """Run one subprocess command and stream output to the console."""
    print(f"+ {' '.join(cmd)}")
    subprocess.run(cmd, cwd=str(cwd), check=True)


def _ensure_python_package(
    *,
    repo_root: Path,
    python_exe: str,
    package_name: str,
) -> None:
    """Ensure a Python package is available in the active environment."""
    probe = subprocess.run(
        [python_exe, "-m", "pip", "show", package_name],
        cwd=str(repo_root),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    if probe.returncode == 0:
        return
    print(f"Python package `{package_name}` not found; installing it now...")
    _run([python_exe, "-m", "pip", "install", package_name], cwd=repo_root)


def _ensure_python_build(repo_root: Path, python_exe: str) -> None:
    """Ensure the `build` package is available for wheel generation."""
    _ensure_python_package(
        repo_root=repo_root,
        python_exe=python_exe,
        package_name="build",
    )


def _update_component_versions(repo_root: Path, python_exe: str) -> None:
    """Refresh component version metadata from git before packaging."""
    _run(
        [
            python_exe,
            str(repo_root / "scripts" / "update_component_versions.py"),
            "--repo-root",
            str(repo_root),
        ],
        cwd=repo_root,
    )


def _refresh_pdf_manual(
    *,
    repo_root: Path,
    python_exe: str,
    manual_output_path: Path,
) -> Path:
    """Regenerate the consolidated OpAMP PDF manual and return its path."""
    _ensure_python_package(
        repo_root=repo_root,
        python_exe=python_exe,
        package_name="reportlab",
    )
    _run(
        [
            python_exe,
            str(repo_root / "scripts" / "build_opamp_manual.py"),
            "--repo-root",
            str(repo_root),
            "--output",
            str(manual_output_path),
        ],
        cwd=repo_root,
    )
    if not manual_output_path.exists():
        raise RuntimeError(
            f"manual build did not produce expected file: {manual_output_path}"
        )
    return manual_output_path


def _refresh_provider_ui_compact_assets(
    *,
    repo_root: Path,
    python_exe: str,
) -> None:
    """Regenerate compacted provider web UI JavaScript assets."""
    _run(
        [
            python_exe,
            str(repo_root / "scripts" / "build_provider_ui_compact_assets.py"),
            "--repo-root",
            str(repo_root),
        ],
        cwd=repo_root,
    )


def _run_security_checks(
    *,
    repo_root: Path,
    python_exe: str,
) -> None:
    """Run the consolidated security checks workflow script."""
    _run(
        [
            python_exe,
            str(repo_root / "scripts" / "security_checks.py"),
            "--repo-root",
            str(repo_root),
            "--python",
            python_exe,
        ],
        cwd=repo_root,
    )


def _clean_dir(path: Path) -> None:
    """Remove build files from one directory, creating it when absent."""
    path.mkdir(parents=True, exist_ok=True)
    for child in path.iterdir():
        if child.is_file():
            child.unlink()


def _build_component_wheel(
    *,
    repo_root: Path,
    python_exe: str,
    component: ComponentTarget,
    out_dir: Path,
    no_isolation: bool,
) -> Path:
    """Build one component wheel and return its path."""
    _clean_dir(out_dir)
    cmd = [
        python_exe,
        "-m",
        "build",
        "--wheel",
        "--outdir",
        str(out_dir),
    ]
    if no_isolation:
        cmd.append("--no-isolation")
    cmd.append(str(repo_root / component.source_dir))
    _run(cmd, cwd=repo_root)
    wheels = sorted(out_dir.glob("*.whl"))
    if not wheels:
        raise RuntimeError(
            f"wheel build for {component.source_dir} produced no .whl files"
        )
    if len(wheels) > 1:
        print(
            f"warning: multiple wheels found for {component.source_dir}; "
            f"using latest: {wheels[-1].name}"
        )
    return wheels[-1]


def _github_request(
    *,
    method: str,
    url: str,
    token: str,
    payload: dict[str, Any] | None = None,
    content_type: str = "application/json",
) -> Any:
    """Issue an authenticated GitHub API request and return parsed JSON."""
    data: bytes | None = None
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "User-Agent": "opamp-wheel-publisher",
    }
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = content_type

    req = urllib.request.Request(url, data=data, headers=headers, method=method.upper())
    try:
        with urllib.request.urlopen(req) as resp:  # nosec B310
            raw = resp.read()
            if not raw:
                return None
            return json.loads(raw.decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"GitHub API {method} {url} failed: {exc.code} {body}") from exc


def _github_upload_asset(
    *,
    upload_url_template: str,
    asset_path: Path,
    token: str,
) -> Any:
    """Upload one release asset to the GitHub uploads API."""
    base_upload_url = upload_url_template.split("{", 1)[0]
    query = urllib.parse.urlencode({"name": asset_path.name})
    url = f"{base_upload_url}?{query}"
    data = asset_path.read_bytes()
    content_type = mimetypes.guess_type(asset_path.name)[0] or "application/octet-stream"
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "User-Agent": "opamp-wheel-publisher",
        "Content-Type": content_type,
        "Content-Length": str(len(data)),
    }
    req = urllib.request.Request(url, data=data, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req) as resp:  # nosec B310
            raw = resp.read()
            return json.loads(raw.decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(
            f"GitHub asset upload failed for {asset_path.name}: {exc.code} {body}"
        ) from exc


def _release_by_tag(*, repo: str, tag: str, token: str) -> dict[str, Any] | None:
    """Return release JSON for one tag when it exists; otherwise None."""
    url = f"https://api.github.com/repos/{repo}/releases/tags/{urllib.parse.quote(tag)}"
    req = urllib.request.Request(
        url,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "User-Agent": "opamp-wheel-publisher",
        },
        method="GET",
    )
    try:
        with urllib.request.urlopen(req) as resp:  # nosec B310
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            return None
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"GitHub release lookup failed: {exc.code} {body}") from exc


def _create_release(
    *,
    repo: str,
    tag: str,
    token: str,
    name: str | None,
    body: str,
    draft: bool,
    prerelease: bool,
) -> dict[str, Any]:
    """Create a GitHub release and return its JSON payload."""
    payload = {
        "tag_name": tag,
        "name": name or tag,
        "body": body,
        "draft": bool(draft),
        "prerelease": bool(prerelease),
    }
    return _github_request(
        method="POST",
        url=f"https://api.github.com/repos/{repo}/releases",
        token=token,
        payload=payload,
    )


def _delete_existing_assets(
    *,
    repo: str,
    release: dict[str, Any],
    token: str,
    asset_names: set[str],
) -> None:
    """Delete same-name assets from a release so re-uploads succeed."""
    for asset in release.get("assets", []):
        name = str(asset.get("name") or "")
        if name not in asset_names:
            continue
        asset_id = asset.get("id")
        if not isinstance(asset_id, int):
            continue
        print(f"Removing existing release asset: {name}")
        _github_request(
            method="DELETE",
            url=f"https://api.github.com/repos/{repo}/releases/assets/{asset_id}",
            token=token,
        )


def _publish_wheels(
    *,
    repo: str,
    tag: str,
    release_name: str | None,
    release_notes: str,
    draft: bool,
    prerelease: bool,
    token: str,
    artifact_paths: list[Path],
) -> None:
    """Create or update one release and upload build artefacts as assets."""
    release = _release_by_tag(repo=repo, tag=tag, token=token)
    if release is None:
        print(f"Creating GitHub release {tag} in {repo}...")
        release = _create_release(
            repo=repo,
            tag=tag,
            token=token,
            name=release_name,
            body=release_notes,
            draft=draft,
            prerelease=prerelease,
        )
    else:
        print(f"Using existing GitHub release for tag {tag}.")

    _delete_existing_assets(
        repo=repo,
        release=release,
        token=token,
        asset_names={path.name for path in artifact_paths},
    )

    upload_url = str(release.get("upload_url") or "")
    if not upload_url:
        raise RuntimeError("GitHub release payload missing upload_url")

    for artifact_path in artifact_paths:
        print(f"Uploading {artifact_path.name}...")
        asset = _github_upload_asset(
            upload_url_template=upload_url,
            asset_path=artifact_path,
            token=token,
        )
        print(f"Uploaded: {asset.get('browser_download_url', '<no download URL>')}")


def _load_release_notes(args: argparse.Namespace) -> str:
    """Resolve release notes from CLI options."""
    if args.release_notes_file:
        return Path(args.release_notes_file).read_text(encoding="utf-8")
    if args.release_notes:
        return args.release_notes
    return "Automated wheel upload from build_and_publish_wheels.py"


def _parse_component_keys(raw_components: str) -> list[str]:
    """Parse and validate selected component keys."""
    component_keys = [
        item.strip() for item in str(raw_components or "").split(",") if item.strip()
    ]
    if not component_keys:
        raise ValueError("at least one component must be selected")
    invalid = [item for item in component_keys if item not in COMPONENT_TARGETS]
    if invalid:
        valid_keys = ", ".join(sorted(COMPONENT_TARGETS))
        raise ValueError(
            f"unknown component(s): {', '.join(invalid)}; valid values: {valid_keys}"
        )
    return component_keys


def _resolve_sbom_paths(
    args: argparse.Namespace,
    *,
    repo_root: Path,
    component_keys: list[str],
) -> dict[str, Path]:
    """Resolve SBOM output paths for all selected components."""
    sbom_paths = {
        key: (repo_root / COMPONENT_TARGETS[key].default_sbom_relpath).resolve()
        for key in component_keys
    }
    if "provider" in sbom_paths:
        sbom_paths["provider"] = (repo_root / args.provider_sbom_path).resolve()
    if "consumer" in sbom_paths:
        sbom_paths["consumer"] = (repo_root / args.consumer_sbom_path).resolve()
    for override in args.component_sbom_path:
        key, separator, raw_path = override.partition("=")
        if separator != "=" or not key.strip() or not raw_path.strip():
            raise ValueError(
                "--component-sbom-path must use KEY=PATH, for example "
                "catalog=dist/sbom/catalog.cyclonedx.json"
            )
        normalized_key = key.strip()
        if normalized_key not in COMPONENT_TARGETS:
            raise ValueError(f"unknown component in --component-sbom-path: {normalized_key}")
        sbom_paths[normalized_key] = (repo_root / raw_path.strip()).resolve()
    return sbom_paths


def _build_parser() -> argparse.ArgumentParser:
    """Build the command-line parser."""
    component_help = ", ".join(DEFAULT_COMPONENTS)
    parser = argparse.ArgumentParser(
        description=(
            "Build wheel artefacts for independently deployable OpAMP components "
            "and optionally publish them to a GitHub release."
        )
    )
    parser.add_argument(
        "--repo",
        default=DEFAULT_REPO,
        help=f"GitHub repository in owner/name form (default: {DEFAULT_REPO})",
    )
    parser.add_argument(
        "--components",
        default=",".join(DEFAULT_COMPONENTS),
        help=f"Comma-separated component keys to build (default: {component_help})",
    )
    parser.add_argument(
        "--dist-root",
        default="dist",
        help="Artefact root directory (default: dist)",
    )
    parser.add_argument(
        "--provider-sbom-path",
        default=LEGACY_DEFAULT_PROVIDER_SBOM_PATH,
        help=(
            "Provider SBOM output path "
            f"(default: {LEGACY_DEFAULT_PROVIDER_SBOM_PATH})"
        ),
    )
    parser.add_argument(
        "--consumer-sbom-path",
        default=LEGACY_DEFAULT_CONSUMER_SBOM_PATH,
        help=(
            "Consumer SBOM output path "
            f"(default: {LEGACY_DEFAULT_CONSUMER_SBOM_PATH})"
        ),
    )
    parser.add_argument(
        "--component-sbom-path",
        action="append",
        default=[],
        help="Override one component SBOM path using KEY=PATH",
    )
    parser.add_argument(
        "--manual-path",
        default=DEFAULT_MANUAL_PATH,
        help=f"PDF manual output path (default: {DEFAULT_MANUAL_PATH})",
    )
    parser.add_argument(
        "--skip-manual",
        action="store_true",
        help="Skip PDF manual refresh step",
    )
    parser.add_argument(
        "--skip-ui-compaction",
        action="store_true",
        help="Skip provider web UI JavaScript compaction step",
    )
    parser.add_argument(
        "--skip-security-checks",
        action="store_true",
        help="Skip consolidated security checks workflow step",
    )
    parser.add_argument(
        "--python",
        default=sys.executable,
        help="Python executable to use for builds (default: current interpreter)",
    )
    parser.add_argument(
        "--no-isolation",
        action="store_true",
        help="Pass --no-isolation to python -m build for local/offline builds",
    )
    parser.add_argument(
        "--publish",
        action="store_true",
        help="Publish built wheels to a GitHub release",
    )
    parser.add_argument(
        "--tag",
        help="Release tag used when publishing (required with --publish)",
    )
    parser.add_argument(
        "--release-name",
        help="Release name/title (defaults to tag)",
    )
    parser.add_argument(
        "--release-notes",
        default="",
        help="Release notes text for new release creation",
    )
    parser.add_argument(
        "--release-notes-file",
        help="Path to markdown/text file used as release notes body",
    )
    parser.add_argument(
        "--draft",
        action="store_true",
        help="Create the release as draft when publishing",
    )
    parser.add_argument(
        "--prerelease",
        action="store_true",
        help="Mark the release as prerelease when publishing",
    )
    parser.add_argument(
        "--github-token",
        default="",
        help="GitHub token (default: env GITHUB_TOKEN or GH_TOKEN)",
    )
    return parser


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse command line options."""
    parser = _build_parser()
    args = parser.parse_args(argv)

    if args.publish and not args.tag:
        parser.error("--tag is required when --publish is provided")
    if args.release_notes and args.release_notes_file:
        parser.error("use either --release-notes or --release-notes-file, not both")
    try:
        args.component_keys = _parse_component_keys(args.components)
        args.resolved_sbom_paths = _resolve_sbom_paths(
            args,
            repo_root=REPO_ROOT,
            component_keys=args.component_keys,
        )
    except ValueError as exc:
        parser.error(str(exc))
    return args


def main(argv: list[str] | None = None) -> int:
    """Entrypoint."""
    args = _parse_args(argv)
    dist_root = (REPO_ROOT / args.dist_root).resolve()
    manual_output_path = (REPO_ROOT / args.manual_path).resolve()

    _update_component_versions(REPO_ROOT, args.python)
    _ensure_python_build(REPO_ROOT, args.python)
    if not args.skip_security_checks:
        _run_security_checks(
            repo_root=REPO_ROOT,
            python_exe=args.python,
        )
    elif not args.skip_ui_compaction:
        _refresh_provider_ui_compact_assets(
            repo_root=REPO_ROOT,
            python_exe=args.python,
        )

    manual_pdf: Path | None = None
    if not args.skip_manual:
        manual_pdf = _refresh_pdf_manual(
            repo_root=REPO_ROOT,
            python_exe=args.python,
            manual_output_path=manual_output_path,
        )

    built_wheels: dict[str, Path] = {}
    built_sboms: dict[str, Path] = {}
    for component_key in args.component_keys:
        component = COMPONENT_TARGETS[component_key]
        wheel_path = _build_component_wheel(
            repo_root=REPO_ROOT,
            python_exe=args.python,
            component=component,
            out_dir=dist_root / component.dist_dirname,
            no_isolation=args.no_isolation,
        )
        sbom_path = write_wheel_artifact_sbom(
            repo_root=REPO_ROOT,
            python_exe=args.python,
            artifact=wheel_path,
            sbom_path=args.resolved_sbom_paths[component_key],
            root_component_name=component.root_component_name,
            repo=args.repo,
            component_dir=component.source_dir,
        )
        validate_wheel_artifact_sbom(
            artifact=wheel_path,
            sbom_path=sbom_path,
            root_component_name=component.root_component_name,
            repo=args.repo,
        )
        built_wheels[component_key] = wheel_path
        built_sboms[component_key] = sbom_path

    print("SBOM validation complete.")
    print("Build complete.")
    for component_key in args.component_keys:
        component = COMPONENT_TARGETS[component_key]
        print(f"{component.display_name} wheel: {built_wheels[component_key]}")
        print(f"{component.display_name} SBOM: {built_sboms[component_key]}")
    if manual_pdf is not None:
        print(f"PDF Manual: {manual_pdf}")

    if not args.publish:
        print("Publish skipped (use --publish to upload to GitHub release assets).")
        return 0

    token = (
        args.github_token.strip()
        or os.environ.get("GITHUB_TOKEN", "").strip()
        or os.environ.get("GH_TOKEN", "").strip()
    )
    if not token:
        raise RuntimeError(
            "GitHub token is required for publish; use --github-token or set GITHUB_TOKEN/GH_TOKEN"
        )

    notes = _load_release_notes(args)
    publish_paths = [
        path
        for component_key in args.component_keys
        for path in (built_wheels[component_key], built_sboms[component_key])
    ]
    if manual_pdf is not None:
        publish_paths.append(manual_pdf)

    _publish_wheels(
        repo=args.repo,
        tag=args.tag,
        release_name=args.release_name,
        release_notes=notes,
        draft=args.draft,
        prerelease=args.prerelease,
        token=token,
        artifact_paths=publish_paths,
    )
    print("Publish complete.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
