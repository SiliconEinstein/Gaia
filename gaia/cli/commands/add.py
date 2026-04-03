"""gaia add -- install a Gaia knowledge package from the official registry."""

from __future__ import annotations

import subprocess

import typer

from gaia.cli._packages import GaiaCliError
from gaia.cli._registry import DEFAULT_REGISTRY, resolve_package


def _run_uv(args: list[str], **kwargs) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(args, text=True, capture_output=True, **kwargs)
    except FileNotFoundError:
        raise GaiaCliError(
            "uv is not installed. Install it with: curl -LsSf https://astral.sh/uv/install.sh | sh"
        )


def add_command(
    package: str = typer.Argument(help="Package name (e.g., galileo-falling-bodies-gaia)"),
    version: str | None = typer.Option(None, "--version", "-v", help="Specific version"),
    registry: str = typer.Option(DEFAULT_REGISTRY, "--registry", help="Registry GitHub repo"),
) -> None:
    """Install a registered Gaia knowledge package."""
    try:
        resolved = resolve_package(package, version=version, registry=registry)
    except GaiaCliError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(1)

    # Normalize: ensure -gaia suffix for the dep spec
    canonical_name = package if package.endswith("-gaia") else f"{package}-gaia"
    dep_spec = f"{canonical_name} @ git+{resolved.repo}@{resolved.git_sha}"
    typer.echo(f"Resolved {package} v{resolved.version} → {resolved.git_sha[:8]}")

    try:
        result = _run_uv(["uv", "add", dep_spec])
    except GaiaCliError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(1)
    if result.returncode != 0:
        stderr = result.stderr.strip() or result.stdout.strip()
        typer.echo(f"Error: uv add failed: {stderr}", err=True)
        raise typer.Exit(1)

    typer.echo(f"Added {package} v{resolved.version}")
