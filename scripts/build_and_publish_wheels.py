#!/usr/bin/env python3
"""Build provider/consumer wheels and optionally publish to a GitHub release."""

from __future__ import annotations

import argparse
import hashlib
import json
import mimetypes
import os
import subprocess
import sys
import tempfile
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from datetime import datetime, timedelta, timezone
from email import message_from_bytes
from pathlib import Path
from typing import Any

DEFAULT_REPO = "mp3monster/fluent-opamp"
DEFAULT_PROVIDER_SBOM_PATH = (
    "dist/sbom/opamp_provider_deployable_artifacts.cyclonedx.json"
)
DEFAULT_CONSUMER_SBOM_PATH = (
    "dist/sbom/opamp_consumer_deployable_artifacts.cyclonedx.json"
)
DEFAULT_MANUAL_PATH = "dist/manual/opamp_manual.pdf"


def _run(cmd: list[str], *, cwd: Path) -> None:
    """Run one subprocess command and stream output to the console."""
    print(f"+ {' '.join(cmd)}")
    subprocess.run(cmd, cwd=str(cwd), check=True)


def _ensure_python_build(repo_root: Path, python_exe: str) -> None:
    """Ensure the `build` package is available for wheel generation."""
    _ensure_python_package(
        repo_root=repo_root,
        python_exe=python_exe,
        package_name="build",
    )


def _ensure_cyclonedx_python_tool(repo_root: Path, python_exe: str) -> None:
    """Ensure cyclonedx-py CLI is available via the `cyclonedx-bom` package."""
    _ensure_python_package(
        repo_root=repo_root,
        python_exe=python_exe,
        package_name="cyclonedx-bom",
    )


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
    """Remove files from one directory, creating it when absent."""
    path.mkdir(parents=True, exist_ok=True)
    for child in path.iterdir():
        if child.is_file():
            child.unlink()


def _build_component_wheel(
    *,
    repo_root: Path,
    python_exe: str,
    component_dir: str,
    out_dir: Path,
) -> Path:
    """Build one wheel and return its path."""
    _clean_dir(out_dir)
    _run(
        [
            python_exe,
            "-m",
            "build",
            "--wheel",
            "--outdir",
            str(out_dir),
            str(repo_root / component_dir),
        ],
        cwd=repo_root,
    )
    wheels = sorted(out_dir.glob("*.whl"))
    if not wheels:
        raise RuntimeError(f"wheel build for {component_dir} produced no .whl files")
    if len(wheels) > 1:
        print(
            f"warning: multiple wheels found for {component_dir}; using latest: "
            f"{wheels[-1].name}"
        )
    return wheels[-1]


def _normalize_dist_name(value: str) -> str:
    """Normalize distribution name to a stable lowercase key."""
    return str(value or "").strip().lower().replace("_", "-")


def _sha256(path: Path) -> str:
    """Return SHA-256 digest for one file."""
    hasher = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def _read_wheel_metadata(wheel_path: Path) -> dict[str, Any]:
    """Read Name/Version/Requires-Dist from a wheel METADATA payload."""
    metadata_bytes: bytes | None = None
    with zipfile.ZipFile(wheel_path, "r") as archive:
        for member in archive.namelist():
            if member.endswith(".dist-info/METADATA"):
                metadata_bytes = archive.read(member)
                break
    if metadata_bytes is None:
        raise RuntimeError(f"wheel missing dist-info/METADATA: {wheel_path}")

    metadata = message_from_bytes(metadata_bytes)
    name = str(metadata.get("Name") or wheel_path.stem).strip()
    version = str(metadata.get("Version") or "0").strip()
    requires_dist = [str(item).strip() for item in metadata.get_all("Requires-Dist") or []]
    return {"name": name, "version": version, "requires_dist": requires_dist}


def _requirement_name(requirement: str) -> str:
    """Extract dependency package name from Requires-Dist entry."""
    cleaned = requirement.split(";", 1)[0].strip()
    stop_chars = [" ", "(", "[", "!", "<", ">", "=", "~", ";"]
    end = len(cleaned)
    for char in stop_chars:
        pos = cleaned.find(char)
        if pos != -1:
            end = min(end, pos)
    return cleaned[:end].strip()


def _build_cyclonedx_sbom(
    *,
    repo_root: Path,
    python_exe: str,
    component_dir: str,
    repo: str,
    artifact: Path,
    sbom_path: Path,
    root_component_name: str,
) -> Path:
    """Generate CycloneDX JSON SBOM for one deployable wheel artifact."""
    wheel_meta = _read_wheel_metadata(artifact)
    name = str(wheel_meta["name"])
    version = str(wheel_meta["version"])
    bom_ref = f"pkg:pypi/{_normalize_dist_name(name)}@{version}"
    _ensure_cyclonedx_python_tool(repo_root, python_exe)
    runtime_requirements = [
        requirement
        for requirement in wheel_meta["requires_dist"]
        if "extra ==" not in requirement.lower()
    ]

    with tempfile.TemporaryDirectory(prefix="opamp-wheel-sbom-") as temp_dir:
        temp_root = Path(temp_dir)
        requirements_path = temp_root / "requirements.txt"
        requirements_path.write_text(
            "".join(f"{requirement}\n" for requirement in runtime_requirements),
            encoding="utf-8",
        )
        tool_sbom_path = temp_root / "sbom-tool.json"
        _run(
            [
                python_exe,
                "-m",
                "cyclonedx_py",
                "requirements",
                str(requirements_path),
                "--output-format",
                "JSON",
                "--spec-version",
                "1.6",
                "--output-file",
                str(tool_sbom_path),
            ],
            cwd=repo_root,
        )
        sbom = json.loads(tool_sbom_path.read_text(encoding="utf-8"))

    if not isinstance(sbom, dict):
        raise RuntimeError("CycloneDX generation returned invalid SBOM payload.")

    components_raw = sbom.get("components")
    if not isinstance(components_raw, list):
        components_raw = []
    normalized_components: list[dict[str, Any]] = []
    seen_refs: set[str] = set()
    for component in components_raw:
        if not isinstance(component, dict):
            continue
        normalized_component = dict(component)
        purl = str(normalized_component.get("purl") or "").strip()
        if purl.startswith("pkg:pypi/"):
            normalized_component["bom-ref"] = purl
        component_ref = str(normalized_component.get("bom-ref") or "").strip()
        if not component_ref or component_ref in seen_refs:
            continue
        seen_refs.add(component_ref)
        normalized_components.append(normalized_component)

    wheel_component = {
        "type": "library",
        "name": name,
        "version": version,
        "bom-ref": bom_ref,
        "purl": bom_ref,
        "hashes": [
            {
                "alg": "SHA-256",
                "content": _sha256(artifact),
            }
        ],
        "properties": [
            {"name": "opamp.artifact.path", "value": str(artifact)},
        ],
    }
    sbom["components"] = [wheel_component] + [
        component
        for component in normalized_components
        if str(component.get("bom-ref") or "").strip() != bom_ref
    ]

    metadata = sbom.get("metadata")
    if not isinstance(metadata, dict):
        metadata = {}
    metadata["component"] = {
        "type": "application",
        "name": root_component_name,
        "version": version,
        "properties": [
            {"name": "github.repository", "value": repo},
            {"name": "wheel.name", "value": name},
            {"name": "component.directory", "value": component_dir},
        ],
    }
    sbom["metadata"] = metadata

    dependencies = sbom.get("dependencies")
    if not isinstance(dependencies, list):
        dependencies = []
    dependencies = [
        entry
        for entry in dependencies
        if isinstance(entry, dict) and str(entry.get("ref") or "").strip() != bom_ref
    ]
    dependencies.insert(
        0,
        {
            "ref": bom_ref,
            "dependsOn": _expected_dependency_refs(list(wheel_meta["requires_dist"])),
        },
    )
    sbom["dependencies"] = dependencies

    sbom_path.parent.mkdir(parents=True, exist_ok=True)
    sbom_path.write_text(f"{json.dumps(sbom, indent=2)}\n", encoding="utf-8")
    return sbom_path


def _expected_dependency_refs(requires_dist: list[str]) -> list[str]:
    """Return normalized CycloneDX dependency refs for non-extra requirements."""
    dep_refs: set[str] = set()
    for requirement in requires_dist:
        if "extra ==" in requirement.lower():
            continue
        dep_name = _requirement_name(requirement)
        if dep_name:
            dep_refs.add(f"pkg:pypi/{_normalize_dist_name(dep_name)}")
    return sorted(dep_refs)


def _property_value(properties: Any, name: str) -> str | None:
    """Return one CycloneDX property value by key from a properties list."""
    if not isinstance(properties, list):
        return None
    for entry in properties:
        if not isinstance(entry, dict):
            continue
        if str(entry.get("name") or "").strip() != name:
            continue
        value = entry.get("value")
        return str(value).strip() if value is not None else ""
    return None


def _parse_iso8601_utc(value: str) -> datetime | None:
    """Parse an ISO-8601 timestamp into UTC datetime when possible."""
    text = str(value or "").strip()
    if not text:
        return None
    if text.endswith("Z"):
        text = f"{text[:-1]}+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _validate_cyclonedx_sbom(
    *,
    artifact: Path,
    sbom_path: Path,
    root_component_name: str,
    repo: str,
) -> None:
    """Fail the build if a generated SBOM is stale or mismatched to its wheel."""
    if not artifact.exists():
        raise RuntimeError(f"SBOM validation failed: wheel artifact not found: {artifact}")
    if not sbom_path.exists():
        raise RuntimeError(f"SBOM validation failed: SBOM file not found: {sbom_path}")

    try:
        sbom = json.loads(sbom_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise RuntimeError(
            f"SBOM validation failed: invalid JSON in {sbom_path}: {exc}"
        ) from exc
    if not isinstance(sbom, dict):
        raise RuntimeError(f"SBOM validation failed: root JSON must be an object: {sbom_path}")

    wheel_meta = _read_wheel_metadata(artifact)
    wheel_name = str(wheel_meta["name"])
    wheel_version = str(wheel_meta["version"])
    wheel_ref = f"pkg:pypi/{_normalize_dist_name(wheel_name)}@{wheel_version}"
    wheel_sha = _sha256(artifact)
    expected_dep_refs = _expected_dependency_refs(list(wheel_meta["requires_dist"]))
    skew_allowance = timedelta(seconds=1)
    artifact_mtime_utc = datetime.fromtimestamp(artifact.stat().st_mtime, tz=timezone.utc)
    sbom_mtime_utc = datetime.fromtimestamp(sbom_path.stat().st_mtime, tz=timezone.utc)

    if sbom_mtime_utc + skew_allowance < artifact_mtime_utc:
        raise RuntimeError(
            "SBOM validation failed: SBOM file timestamp is older than wheel artifact; "
            f"regeneration required ({sbom_path} vs {artifact})."
        )

    metadata = sbom.get("metadata")
    if not isinstance(metadata, dict):
        raise RuntimeError("SBOM validation failed: missing/invalid metadata block.")

    timestamp_utc = _parse_iso8601_utc(str(metadata.get("timestamp") or ""))
    if timestamp_utc is None:
        raise RuntimeError(
            "SBOM validation failed: metadata.timestamp missing or invalid ISO-8601."
        )
    if timestamp_utc + skew_allowance < artifact_mtime_utc:
        raise RuntimeError(
            "SBOM validation failed: metadata.timestamp predates wheel artifact "
            f"({timestamp_utc.isoformat()} < {artifact_mtime_utc.isoformat()})."
        )

    metadata_component = metadata.get("component")
    if not isinstance(metadata_component, dict):
        raise RuntimeError("SBOM validation failed: metadata.component is missing.")
    if str(metadata_component.get("name") or "").strip() != root_component_name:
        raise RuntimeError(
            "SBOM validation failed: unexpected metadata.component.name "
            f"(expected {root_component_name!r})."
        )
    if str(metadata_component.get("version") or "").strip() != wheel_version:
        raise RuntimeError(
            "SBOM validation failed: metadata.component.version does not match wheel version."
        )
    if _property_value(metadata_component.get("properties"), "github.repository") != repo:
        raise RuntimeError(
            "SBOM validation failed: metadata github.repository does not match build target."
        )
    if _property_value(metadata_component.get("properties"), "wheel.name") != wheel_name:
        raise RuntimeError("SBOM validation failed: metadata wheel.name does not match wheel.")

    components = sbom.get("components")
    if not isinstance(components, list):
        raise RuntimeError("SBOM validation failed: components list is missing/invalid.")
    wheel_component = None
    for component in components:
        if not isinstance(component, dict):
            continue
        if str(component.get("bom-ref") or "").strip() == wheel_ref:
            wheel_component = component
            break
    if wheel_component is None:
        raise RuntimeError(
            "SBOM validation failed: wheel component entry not found in components."
        )

    hash_content: str | None = None
    hashes = wheel_component.get("hashes")
    if isinstance(hashes, list):
        for item in hashes:
            if not isinstance(item, dict):
                continue
            if str(item.get("alg") or "").strip().upper() == "SHA-256":
                value = item.get("content")
                hash_content = str(value).strip() if value is not None else ""
                break
    if hash_content != wheel_sha:
        raise RuntimeError(
            "SBOM validation failed: wheel SHA-256 hash in SBOM does not match artifact."
        )

    expected_path = str(artifact)
    sbom_artifact_path = _property_value(wheel_component.get("properties"), "opamp.artifact.path")
    if sbom_artifact_path != expected_path:
        raise RuntimeError(
            "SBOM validation failed: wheel artifact path in SBOM does not match built artifact."
        )

    dependencies = sbom.get("dependencies")
    if not isinstance(dependencies, list):
        raise RuntimeError("SBOM validation failed: dependencies list is missing/invalid.")
    dependency_entry = None
    for entry in dependencies:
        if not isinstance(entry, dict):
            continue
        if str(entry.get("ref") or "").strip() == wheel_ref:
            dependency_entry = entry
            break
    if dependency_entry is None:
        raise RuntimeError("SBOM validation failed: dependencies entry for wheel is missing.")

    depends_on = dependency_entry.get("dependsOn")
    if not isinstance(depends_on, list):
        raise RuntimeError("SBOM validation failed: dependencies.ref.dependsOn is invalid.")
    actual_dep_refs = sorted({str(item).strip() for item in depends_on if str(item).strip()})
    if actual_dep_refs != expected_dep_refs:
        raise RuntimeError(
            "SBOM validation failed: dependency refs do not match wheel metadata requirements."
        )


def _github_request(
    *,
    method: str,
    url: str,
    token: str,
    payload: dict[str, Any] | None = None,
    content_type: str = "application/json",
) -> Any:
    """Issue an authenticated GitHub API request and return parsed JSON (if any)."""
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
        with urllib.request.urlopen(req) as resp:  # nosec B310 - controlled GitHub API URL.
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
    """Upload one release asset to GitHub uploads API."""
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
        with urllib.request.urlopen(req) as resp:  # nosec B310 - controlled GitHub uploads URL.
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
        with urllib.request.urlopen(req) as resp:  # nosec B310 - controlled GitHub API URL.
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
    """Create or update one release and upload build artifacts as assets."""
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


def _parse_args() -> argparse.Namespace:
    """Parse command line options."""
    parser = argparse.ArgumentParser(
        description=(
            "Build wheel artifacts for provider (server) and consumer (agent), "
            "and optionally publish them to a GitHub release."
        )
    )
    parser.add_argument(
        "--repo",
        default=DEFAULT_REPO,
        help=f"GitHub repository in owner/name form (default: {DEFAULT_REPO})",
    )
    parser.add_argument(
        "--dist-root",
        default="dist",
        help="Artifact root directory (default: dist)",
    )
    parser.add_argument(
        "--provider-sbom-path",
        default=DEFAULT_PROVIDER_SBOM_PATH,
        help=(
            "Provider SBOM output path "
            f"(default: {DEFAULT_PROVIDER_SBOM_PATH})"
        ),
    )
    parser.add_argument(
        "--consumer-sbom-path",
        default=DEFAULT_CONSUMER_SBOM_PATH,
        help=(
            "Consumer SBOM output path "
            f"(default: {DEFAULT_CONSUMER_SBOM_PATH})"
        ),
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
    args = parser.parse_args()

    if args.publish and not args.tag:
        parser.error("--tag is required when --publish is provided")
    if args.release_notes and args.release_notes_file:
        parser.error("use either --release-notes or --release-notes-file, not both")
    return args


def main() -> int:
    """Entrypoint."""
    args = _parse_args()
    repo_root = Path(__file__).resolve().parents[1]
    dist_root = (repo_root / args.dist_root).resolve()
    provider_dist = dist_root / "provider"
    consumer_dist = dist_root / "consumer"
    manual_output_path = (repo_root / args.manual_path).resolve()

    _update_component_versions(repo_root, args.python)
    _ensure_python_build(repo_root, args.python)
    if not args.skip_security_checks:
        _run_security_checks(
            repo_root=repo_root,
            python_exe=args.python,
        )
    elif not args.skip_ui_compaction:
        _refresh_provider_ui_compact_assets(
            repo_root=repo_root,
            python_exe=args.python,
        )
    manual_pdf: Path | None = None
    if not args.skip_manual:
        manual_pdf = _refresh_pdf_manual(
            repo_root=repo_root,
            python_exe=args.python,
            manual_output_path=manual_output_path,
        )
    provider_wheel = _build_component_wheel(
        repo_root=repo_root,
        python_exe=args.python,
        component_dir="provider",
        out_dir=provider_dist,
    )
    consumer_wheel = _build_component_wheel(
        repo_root=repo_root,
        python_exe=args.python,
        component_dir="consumer",
        out_dir=consumer_dist,
    )
    provider_sbom_path = _build_cyclonedx_sbom(
        repo_root=repo_root,
        python_exe=args.python,
        component_dir="provider",
        repo=args.repo,
        artifact=provider_wheel,
        sbom_path=(repo_root / args.provider_sbom_path).resolve(),
        root_component_name="fluent-opamp-provider-deployable-artifact",
    )
    consumer_sbom_path = _build_cyclonedx_sbom(
        repo_root=repo_root,
        python_exe=args.python,
        component_dir="consumer",
        repo=args.repo,
        artifact=consumer_wheel,
        sbom_path=(repo_root / args.consumer_sbom_path).resolve(),
        root_component_name="fluent-opamp-consumer-deployable-artifact",
    )
    _validate_cyclonedx_sbom(
        artifact=provider_wheel,
        sbom_path=provider_sbom_path,
        root_component_name="fluent-opamp-provider-deployable-artifact",
        repo=args.repo,
    )
    _validate_cyclonedx_sbom(
        artifact=consumer_wheel,
        sbom_path=consumer_sbom_path,
        root_component_name="fluent-opamp-consumer-deployable-artifact",
        repo=args.repo,
    )
    print("SBOM validation complete.")

    print("Build complete.")
    print(f"Provider wheel: {provider_wheel}")
    print(f"Consumer wheel: {consumer_wheel}")
    print(f"Provider SBOM: {provider_sbom_path}")
    print(f"Consumer SBOM: {consumer_sbom_path}")
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
    _publish_wheels(
        repo=args.repo,
        tag=args.tag,
        release_name=args.release_name,
        release_notes=notes,
        draft=args.draft,
        prerelease=args.prerelease,
        token=token,
        artifact_paths=(
            [
                provider_wheel,
                consumer_wheel,
                provider_sbom_path,
                consumer_sbom_path,
            ]
            + ([manual_pdf] if manual_pdf is not None else [])
        ),
    )
    print("Publish complete.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
