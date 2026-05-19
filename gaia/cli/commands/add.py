"""gaia add -- install a Gaia knowledge package from the official registry."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

import typer

from gaia.cli._registry import DEFAULT_REGISTRY, fetch_file_optional, resolve_package
from gaia.engine.packaging import GaiaPackagingError


def _run_uv(args: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(args, text=True, capture_output=True, **kwargs)
    except FileNotFoundError as exc:
        raise GaiaPackagingError(
            "uv is not installed. Install it with: curl -LsSf https://astral.sh/uv/install.sh | sh"
        ) from exc


def add_command(
    package: str = typer.Argument(help="Package name (e.g., galileo-falling-bodies-gaia)"),
    version: str | None = typer.Option(None, "--version", "-v", help="Specific version"),
    registry: str = typer.Option(DEFAULT_REGISTRY, "--registry", help="Registry GitHub repo"),
) -> None:
    """Install a registered Gaia knowledge package.

    Resolves ``<package>`` against the gaia registry (default:
    ``SiliconEinstein/gaia-registry`` on GitHub), runs ``uv add`` on the
    resolved ``git+<repo>@<sha>`` spec, and best-effort downloads the
    upstream ``beliefs.json`` into ``.gaia/dep_beliefs/<import_name>.json``
    so foreign-node priors flow into local inference. Must be run from
    within a Gaia knowledge package (``pyproject.toml`` carrying
    ``[tool.gaia]``).

    ``--version`` pins a specific release; omit to take the latest
    registered version.

    Example:

    .. code-block:: bash

        gaia pkg add galileo-falling-bodies-gaia
        gaia pkg add mendel-v0-5-gaia --version 0.1.0
    """
    try:
        resolved = resolve_package(package, version=version, registry=registry)
    except GaiaPackagingError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(1) from exc

    # Normalize: ensure -gaia suffix for the dep spec
    canonical_name = package if package.endswith("-gaia") else f"{package}-gaia"
    dep_spec = f"{canonical_name} @ git+{resolved.repo}@{resolved.git_sha}"
    typer.echo(f"Resolved {package} v{resolved.version} → {resolved.git_sha[:8]}")

    try:
        result = _run_uv(["uv", "add", dep_spec])
    except GaiaPackagingError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(1) from exc
    if result.returncode != 0:
        stderr = result.stderr.strip() or result.stdout.strip()
        typer.echo(f"Error: uv add failed: {stderr}", err=True)
        raise typer.Exit(1)

    typer.echo(f"Added {package} v{resolved.version}")

    # Download upstream beliefs manifest for foreign-node prior injection.
    # This is best-effort: older registry entries may not have beliefs.json.
    _fetch_dep_beliefs(
        package_name=canonical_name.removesuffix("-gaia"),
        version=resolved.version,
        registry=registry,
    )


def _find_gaia_package_root() -> Path | None:
    """Walk up from cwd to find the nearest Gaia package root (pyproject.toml with [tool.gaia])."""
    try:
        import tomllib
    except ImportError:
        import tomli as tomllib  # type: ignore[no-redef]

    current = Path.cwd().resolve()
    for directory in [current, *current.parents]:
        pyproject = directory / "pyproject.toml"
        if pyproject.exists():
            try:
                config = tomllib.loads(pyproject.read_text())
            except Exception:
                continue
            if config.get("tool", {}).get("gaia", {}).get("type") == "knowledge-package":
                return directory
    return None


def _fetch_dep_beliefs(
    *,
    package_name: str,
    version: str,
    registry: str,
) -> None:
    """Download beliefs.json from the registry into ``.gaia/dep_beliefs/``."""
    registry_path = f"packages/{package_name}/releases/{version}/beliefs.json"
    content = fetch_file_optional(registry, registry_path)
    if content is None:
        typer.echo(f"Note: no beliefs manifest for {package_name} v{version} (optional)")
        return

    # Validate it's valid JSON before writing
    try:
        json.loads(content)
    except json.JSONDecodeError:
        typer.echo(f"Warning: beliefs manifest for {package_name} is not valid JSON; skipping")
        return

    # Find the Gaia package root (may differ from cwd if invoked from subdirectory)
    pkg_root = _find_gaia_package_root()
    if pkg_root is None:
        typer.echo("Note: not inside a Gaia package; skipping dep_beliefs download")
        return

    dep_beliefs_dir = pkg_root / ".gaia" / "dep_beliefs"
    dep_beliefs_dir.mkdir(parents=True, exist_ok=True)

    import_name = package_name.replace("-", "_")
    dest = dep_beliefs_dir / f"{import_name}.json"
    dest.write_text(content)
    typer.echo(f"Saved upstream beliefs: {dest}")
