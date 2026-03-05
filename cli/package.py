"""Knowledge package read/write utilities."""

from pathlib import Path

import typer

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
