"""gaia register -- prepare or submit a registry registration for a Gaia package."""

from __future__ import annotations

import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID

import typer

from gaia.cli._packages import (
    GaiaCliError,
    apply_package_priors,
    build_package_manifests,
    load_gaia_package,
)
from gaia.cli._packages import compile_loaded_package_artifact
from gaia.cli._packages import render_manifest_json
from gaia.ir import LocalCanonicalGraph
from gaia.ir.validator import validate_local_graph

try:
    import tomllib
except ImportError:
    import tomli as tomllib  # type: ignore[no-redef]


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _read_gaia_lang_version_from_compile_metadata(pkg_path: Path) -> str:
    """Read `gaia_lang_version` from `.gaia/compile_metadata.json`.

    This is the source of truth for "which gaia-lang produced the IR we are
    about to register", pinned at compile time. We deliberately do NOT read
    the live `importlib.metadata.version("gaia-lang")` here — that would
    record the register-time environment, which can differ from the
    compile/infer environment if the operator upgraded gaia-lang between
    compile and register, and would silently misrepresent the BP engine
    provenance of the registered content.

    Returns "unknown" when the file is missing or malformed; register will
    still succeed, but a warning is printed by the caller.
    """
    metadata_path = pkg_path / ".gaia" / "compile_metadata.json"
    if not metadata_path.exists():
        return "unknown"
    try:
        data = json.loads(metadata_path.read_text())
    except (OSError, json.JSONDecodeError):
        return "unknown"
    version = data.get("gaia_lang_version")
    return version if isinstance(version, str) else "unknown"


def _run(
    args: list[str],
    *,
    cwd: Path,
    check: bool = True,
) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(args, cwd=cwd, text=True, capture_output=True)
    if check and result.returncode != 0:
        stderr = result.stderr.strip() or result.stdout.strip() or "command failed"
        raise GaiaCliError(f"Error running {' '.join(args)}: {stderr}")
    return result


def _normalize_github_url(url: str) -> str:
    value = url.strip()
    if value.startswith("git@github.com:"):
        value = "https://github.com/" + value.removeprefix("git@github.com:")
    elif value.startswith("ssh://git@github.com/"):
        value = "https://github.com/" + value.removeprefix("ssh://git@github.com/")
    elif value.startswith("http://github.com/"):
        value = "https://" + value.removeprefix("http://")
    if not value.startswith("https://github.com/"):
        raise GaiaCliError("Error: GitHub-only Phase 1 requires a GitHub repository URL.")
    if value.endswith(".git"):
        value = value[:-4]
    return value.rstrip("/")


def _parse_gaia_dependencies(dependencies: list[str]) -> dict[str, str]:
    deps: dict[str, str] = {}
    for dep in dependencies:
        requirement = dep.split(";", 1)[0].strip()
        idx = 0
        while idx < len(requirement) and requirement[idx] not in " <>=!~[":
            idx += 1
        name = requirement[:idx]
        specifier = requirement[idx:].strip() or "*"
        if name.endswith("-gaia"):
            deps[name] = specifier
    return deps


def _render_package_toml(
    *,
    uuid: str,
    name: str,
    pypi_name: str,
    repo: str,
    description: str,
    created_at: str,
) -> str:
    return "\n".join(
        [
            f'uuid = "{uuid}"',
            f'name = "{name}"',
            f'pypi_name = "{pypi_name}"',
            f'repo = "{repo}"',
            f'description = "{description}"',
            f'created_at = "{created_at}"',
            "",
        ]
    )


_VERSIONS_CANONICAL_KEYS = (
    "ir_hash",
    "git_tag",
    "git_sha",
    "registered_at",
    "gaia_lang_version",
)


def _render_toml_scalar(value: object) -> str:
    """Render a Python scalar as a TOML literal.

    Handles the common scalar types that might appear in a Versions.toml
    entry: strings, bools, ints, and floats. Raises ValueError on complex
    types (arrays, tables, datetimes) — rather than silently coercing them
    to strings, which would corrupt forward-compat extra fields if a future
    registry release adds any non-string field that an older CLI is asked
    to re-emit.
    """
    if isinstance(value, bool):
        # Must precede int check: bool is a subclass of int in Python.
        return "true" if value else "false"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        return repr(value)
    if isinstance(value, str):
        # Escape backslashes and double quotes — matches TOML basic string rules
        # for the scalar shapes we actually emit (ASCII, no control chars).
        escaped = value.replace("\\", "\\\\").replace('"', '\\"')
        return f'"{escaped}"'
    raise ValueError(
        f"Cannot render Versions.toml value of type {type(value).__name__} "
        f"({value!r}) as a TOML scalar. Supported types: str, bool, int, float."
    )


def _render_versions_toml(versions: dict[str, dict[str, object]]) -> str:
    lines: list[str] = []
    for version in sorted(versions):
        payload = versions[version]
        lines.append(f'[versions."{version}"]')
        for key in _VERSIONS_CANONICAL_KEYS:
            if key in payload:
                lines.append(f"{key} = {_render_toml_scalar(payload[key])}")
        # Preserve any extra keys not in the canonical list. This guards
        # against silently dropping or corrupting fields added by future gaia
        # versions when an older gaia reads and re-emits the same file.
        for key in sorted(payload):
            if key not in _VERSIONS_CANONICAL_KEYS:
                lines.append(f"{key} = {_render_toml_scalar(payload[key])}")
        lines.append("")
    return "\n".join(lines)


def _render_deps_toml(deps: dict[str, dict[str, str]]) -> str:
    lines: list[str] = []
    for version in sorted(deps):
        lines.append(f'[deps."{version}"]')
        for name in sorted(deps[version]):
            lines.append(f'"{name}" = "{deps[version][name]}"')
        lines.append("")
    return "\n".join(lines)


def _build_pr_body(
    *,
    pypi_name: str,
    version: str,
    repo: str,
    tag: str,
    ir_hash: str,
    exported: list[dict[str, str]],
    deps: dict[str, str],
) -> str:
    lines = [
        f"## Register: {pypi_name} {version}",
        "",
        f"- Repository: {repo}",
        f"- Tag: {tag}",
        f"- IR Hash: {ir_hash}",
        "",
    ]
    if exported:
        lines.append("### Exported claims")
        for item in exported:
            if item["content"]:
                lines.append(f"- `{item['label']}` - {item['content']}")
            else:
                lines.append(f"- `{item['label']}`")
        lines.append("")
    if deps:
        lines.append("### Dependencies")
        for name, specifier in sorted(deps.items()):
            lines.append(f"- {name} {specifier}")
        lines.append("")
    return "\n".join(lines)


def _prepare_exported_claims(ir: dict, exported_labels: list[str]) -> list[dict[str, str]]:
    knowledge_by_label = {
        item["label"]: item
        for item in ir["knowledges"]
        if item["type"] == "claim" and item.get("label") is not None
    }
    exported: list[dict[str, str]] = []
    for label in exported_labels:
        node = knowledge_by_label.get(label)
        if node is None:
            continue
        exported.append({"label": label, "content": node.get("content", "")})
    return exported


def _load_existing_versions(path: Path) -> dict[str, dict[str, str]]:
    if not path.exists():
        return {}
    return dict(tomllib.loads(path.read_text()).get("versions", {}))


def _load_existing_deps(path: Path) -> dict[str, dict[str, str]]:
    if not path.exists():
        return {}
    return dict(tomllib.loads(path.read_text()).get("deps", {}))


def register_command(
    path: str = typer.Argument(".", help="Path to knowledge package directory"),
    tag: str | None = typer.Option(None, help="Git tag to register. Defaults to v<version>."),
    repo: str | None = typer.Option(
        None, help="GitHub repository URL. Defaults to the git origin remote."
    ),
    registry_dir: str | None = typer.Option(
        None, help="Path to a local checkout of the official registry repository."
    ),
    registry_repo: str = typer.Option(
        "SiliconEinstein/gaia-registry", help="Registry GitHub repo slug for PR creation."
    ),
    create_pr: bool = typer.Option(False, help="Push the registry branch and open a GitHub PR."),
) -> None:
    """Prepare or submit a registration for a tagged GitHub-backed Gaia package."""
    try:
        loaded = load_gaia_package(path)
        apply_package_priors(loaded)
        compiled = compile_loaded_package_artifact(loaded)
        ir = compiled.to_json()
        manifests = build_package_manifests(loaded, compiled)
    except GaiaCliError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(1)

    validation = validate_local_graph(LocalCanonicalGraph(**ir))
    if validation.errors:
        for error in validation.errors:
            typer.echo(f"Error: {error}", err=True)
        raise typer.Exit(1)

    ir_hash_path = loaded.pkg_path / ".gaia" / "ir_hash"
    if not ir_hash_path.exists():
        typer.echo("Error: missing .gaia/ir_hash; run `gaia compile` first.", err=True)
        raise typer.Exit(1)
    stored_ir_hash = ir_hash_path.read_text().strip()
    if stored_ir_hash != ir["ir_hash"]:
        typer.echo("Error: compiled artifacts are stale; run `gaia compile` again.", err=True)
        raise typer.Exit(1)

    gaia_uuid = loaded.gaia_config.get("uuid")
    if not isinstance(gaia_uuid, str) or not gaia_uuid:
        typer.echo("Error: [tool.gaia].uuid is required for registration.", err=True)
        raise typer.Exit(1)
    try:
        UUID(gaia_uuid)
    except ValueError as exc:
        typer.echo(f"Error: invalid [tool.gaia].uuid: {exc}", err=True)
        raise typer.Exit(1)

    if not loaded.project_name.endswith("-gaia"):
        typer.echo("Error: [project].name must end with '-gaia'.", err=True)
        raise typer.Exit(1)

    package_name = loaded.project_name.removesuffix("-gaia")
    version = loaded.project_config["version"]
    tag_name = tag or f"v{version}"
    description = str(loaded.project_config.get("description", ""))
    dependencies = loaded.project_config.get("dependencies", [])
    if not isinstance(dependencies, list):
        typer.echo("Error: [project].dependencies must be a list if set.", err=True)
        raise typer.Exit(1)
    deps = _parse_gaia_dependencies(dependencies)

    try:
        _run(["git", "rev-parse", "--is-inside-work-tree"], cwd=loaded.pkg_path)
        worktree_state = _run(["git", "status", "--short"], cwd=loaded.pkg_path)
        if worktree_state.stdout.strip():
            raise GaiaCliError("Error: git worktree must be clean before registration.")
        origin_url = _run(
            ["git", "remote", "get-url", "origin"], cwd=loaded.pkg_path
        ).stdout.strip()
        head_sha = _run(["git", "rev-parse", "HEAD"], cwd=loaded.pkg_path).stdout.strip()
        tag_sha = _run(["git", "rev-list", "-n", "1", tag_name], cwd=loaded.pkg_path).stdout.strip()
        if tag_sha != head_sha:
            raise GaiaCliError(f"Error: tag '{tag_name}' must point to HEAD before registration.")
        remote_tag = _run(
            ["git", "ls-remote", "--tags", "origin", f"refs/tags/{tag_name}"], cwd=loaded.pkg_path
        )
        if not remote_tag.stdout.strip():
            raise GaiaCliError(f"Error: tag '{tag_name}' is not pushed to origin.")
    except GaiaCliError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(1)

    try:
        repo_url = _normalize_github_url(repo or origin_url)
    except GaiaCliError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(1)

    exported_claims = _prepare_exported_claims(ir, loaded.package.exported)
    registered_at = _utc_now()
    pr_title = f"register: {loaded.project_name} {version}"
    pr_body = _build_pr_body(
        pypi_name=loaded.project_name,
        version=version,
        repo=repo_url,
        tag=tag_name,
        ir_hash=ir["ir_hash"],
        exported=exported_claims,
        deps=deps,
    )

    package_toml = _render_package_toml(
        uuid=gaia_uuid,
        name=package_name,
        pypi_name=loaded.project_name,
        repo=repo_url,
        description=description,
        created_at=registered_at,
    )
    gaia_ver = _read_gaia_lang_version_from_compile_metadata(loaded.pkg_path)
    if gaia_ver == "unknown":
        typer.echo(
            "Warning: .gaia/compile_metadata.json is missing or malformed; "
            "Versions.toml will record gaia_lang_version as 'unknown'. "
            "Re-run `gaia compile` to generate the metadata file.",
        )
    versions = {
        version: {
            "ir_hash": ir["ir_hash"],
            "git_tag": tag_name,
            "git_sha": tag_sha,
            "registered_at": registered_at,
            "gaia_lang_version": gaia_ver,
        }
    }
    deps_payload = {version: deps}
    release_dir = f"packages/{package_name}/releases/{version}"
    release_files = {
        f"{release_dir}/{filename}": render_manifest_json(payload)
        for filename, payload in manifests.items()
    }

    plan = {
        "package": {
            "uuid": gaia_uuid,
            "name": package_name,
            "pypi_name": loaded.project_name,
            "repo": repo_url,
            "description": description,
        },
        "version": {
            "version": version,
            "git_tag": tag_name,
            "git_sha": tag_sha,
            "ir_hash": ir["ir_hash"],
        },
        "deps": deps,
        "registry_repo": registry_repo,
        "files": {
            f"packages/{package_name}/Package.toml": package_toml,
            f"packages/{package_name}/Versions.toml": _render_versions_toml(versions),
            f"packages/{package_name}/Deps.toml": _render_deps_toml(deps_payload),
            **release_files,
        },
        "pull_request": {"title": pr_title, "body": pr_body},
    }

    if registry_dir is None:
        typer.echo(json.dumps(plan, ensure_ascii=False, indent=2, sort_keys=True))
        return

    registry_path = Path(registry_dir).resolve()
    if not registry_path.exists():
        typer.echo(f"Error: registry directory does not exist: {registry_path}", err=True)
        raise typer.Exit(1)

    # ── Pre-branch validation ──
    # All read-only checks run BEFORE creating the branch so that failures
    # don't leave an orphan branch that blocks retries.
    try:
        registry_status = _run(["git", "status", "--short"], cwd=registry_path)
        if registry_status.stdout.strip():
            raise GaiaCliError("Error: registry checkout must be clean before registration.")
        branch_name = f"register/{package_name}-{version}"
        branch_exists = _run(
            ["git", "show-ref", "--verify", "--quiet", f"refs/heads/{branch_name}"],
            cwd=registry_path,
            check=False,
        )
        if branch_exists.returncode == 0:
            raise GaiaCliError(f"Error: registry branch already exists: {branch_name}")
    except GaiaCliError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(1)

    package_dir = registry_path / "packages" / package_name
    release_path = package_dir / "releases" / version
    package_toml_path = package_dir / "Package.toml"
    versions_toml_path = package_dir / "Versions.toml"
    deps_toml_path = package_dir / "Deps.toml"

    if package_toml_path.exists():
        existing_package = tomllib.loads(package_toml_path.read_text())
        if existing_package.get("uuid") != gaia_uuid:
            typer.echo("Error: registry package UUID does not match [tool.gaia].uuid.", err=True)
            raise typer.Exit(1)

    existing_versions = _load_existing_versions(versions_toml_path)
    if version in existing_versions:
        typer.echo(f"Error: version already exists in registry metadata: {version}", err=True)
        raise typer.Exit(1)

    if release_path.exists():
        typer.echo(
            f"Error: release directory already exists: {release_path}",
            err=True,
        )
        raise typer.Exit(1)

    # ── All validation passed — create branch and write ──
    try:
        _run(["git", "checkout", "-b", branch_name], cwd=registry_path)
    except GaiaCliError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(1)

    package_dir.mkdir(parents=True, exist_ok=True)
    release_path.mkdir(parents=True, exist_ok=False)

    # Write metadata files.
    if not package_toml_path.exists():
        package_toml_path.write_text(package_toml)

    existing_versions[version] = versions[version]
    versions_toml_path.write_text(_render_versions_toml(existing_versions))

    existing_deps = _load_existing_deps(deps_toml_path)
    existing_deps[version] = deps
    deps_toml_path.write_text(_render_deps_toml(existing_deps))

    for filename, payload in manifests.items():
        (release_path / filename).write_text(render_manifest_json(payload))

    try:
        _run(["git", "add", str(package_dir.relative_to(registry_path))], cwd=registry_path)
        _run(
            ["git", "commit", "-m", f"register: {loaded.project_name} {version}"],
            cwd=registry_path,
        )
    except GaiaCliError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(1)

    typer.echo(f"Prepared registry branch: {branch_name}")
    typer.echo(f"Updated metadata under: {package_dir}")

    if not create_pr:
        typer.echo("Next step: push the registry branch and open a pull request.")
        return

    try:
        _run(["git", "push", "-u", "origin", branch_name], cwd=registry_path)
        pr_result = _run(
            [
                "gh",
                "pr",
                "create",
                "--repo",
                registry_repo,
                "--base",
                "main",
                "--head",
                branch_name,
                "--title",
                pr_title,
                "--body",
                pr_body,
            ],
            cwd=registry_path,
        )
    except GaiaCliError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(1)

    typer.echo(pr_result.stdout.strip())
