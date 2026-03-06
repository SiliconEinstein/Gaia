"""Knowledge package read/write utilities."""

from pathlib import Path

import typer
import yaml

_DEFAULT_TOML = """\
[package]
name = "{name}"
version = "0.1.0"
description = ""
authors = []

[remote]
mode = "server"
# server_url = "https://gaia.example.com"
# registry = "github.com/gaia-registry/packages"
"""


def init_package(name: str | None = None) -> Path:
    """Create a new knowledge package directory structure."""
    if name:
        pkg_dir = Path.cwd() / name
        pkg_dir.mkdir(exist_ok=True)
    else:
        pkg_dir = Path.cwd()
        name = pkg_dir.name

    toml_path = pkg_dir / "gaia.toml"
    if toml_path.exists():
        typer.echo(f"Package already exists: {toml_path}")
        raise typer.Exit(code=1)

    toml_path.write_text(_DEFAULT_TOML.format(name=name))
    (pkg_dir / "claims").mkdir(exist_ok=True)
    typer.echo(f"Initialized package '{name}' at {pkg_dir}")
    return pkg_dir


def load_all_claims(pkg_dir: Path | None = None) -> list[dict]:
    """Load all claims from claims/*.yaml, sorted by ID."""
    if pkg_dir is None:
        from cli.commands.claim import find_package_dir

        pkg_dir = find_package_dir()
    claims_dir = pkg_dir / "claims"
    if not claims_dir.exists():
        return []
    all_claims = []
    for f in sorted(claims_dir.glob("*.yaml")):
        data = yaml.safe_load(f.read_text())
        if data and "claims" in data:
            all_claims.extend(data["claims"])
    all_claims.sort(key=lambda c: c.get("id", 0))
    return all_claims


def load_package_config(pkg_dir: Path) -> dict:
    """Load gaia.toml as a dict."""
    toml_path = pkg_dir / "gaia.toml"
    if not toml_path.exists():
        return {}
    import tomllib

    with open(toml_path, "rb") as f:
        return tomllib.load(f)
