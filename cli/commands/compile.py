"""gaia compile -- compile Python DSL package to Gaia IR v2 JSON."""

from __future__ import annotations

import importlib
import json
import sys
from pathlib import Path

import typer

try:
    import tomllib
except ImportError:
    import tomli as tomllib  # type: ignore[no-redef]


def compile_command(
    path: str = typer.Argument(".", help="Path to knowledge package directory"),
) -> None:
    """Compile a knowledge package to .gaia/ir.json."""
    pkg_path = Path(path).resolve()

    # Read pyproject.toml
    pyproject = pkg_path / "pyproject.toml"
    if not pyproject.exists():
        typer.echo("Error: no pyproject.toml found.", err=True)
        raise typer.Exit(1)

    with open(pyproject, "rb") as f:
        config = tomllib.load(f)

    gaia_config = config.get("tool", {}).get("gaia", {})
    if gaia_config.get("type") != "knowledge-package":
        typer.echo(
            "Error: not a Gaia knowledge package ([tool.gaia].type != 'knowledge-package').",
            err=True,
        )
        raise typer.Exit(1)

    # Derive Python import name: strip -gaia suffix, replace - with _
    project_name = config["project"]["name"]
    import_name = project_name.removesuffix("-gaia").replace("-", "_")

    pkg_src = pkg_path / import_name
    if not pkg_src.exists():
        typer.echo(f"Error: package source directory '{import_name}/' not found.", err=True)
        raise typer.Exit(1)

    # Add to sys.path and import
    if str(pkg_path) not in sys.path:
        sys.path.insert(0, str(pkg_path))

    try:
        mod = importlib.import_module(import_name)
    except Exception as e:
        typer.echo(f"Error importing package: {e}", err=True)
        raise typer.Exit(1)

    # Find the Package object
    from gaia.lang.runtime import Knowledge
    from gaia.lang.runtime import Package as GaiaPackage

    pkg = None
    for attr in dir(mod):
        obj = getattr(mod, attr)
        if isinstance(obj, GaiaPackage):
            pkg = obj
            break

    if pkg is None:
        typer.echo("Error: no Package object found in module.", err=True)
        raise typer.Exit(1)

    # Assign labels from module-level variable names
    for attr in dir(mod):
        obj = getattr(mod, attr)
        if isinstance(obj, Knowledge) and obj.label is None:
            obj.label = attr

    # Override package metadata from pyproject.toml
    pkg.version = config["project"]["version"]
    if "namespace" in gaia_config:
        pkg.namespace = gaia_config["namespace"]

    # Compile
    from gaia.lang.compiler import compile_package

    ir = compile_package(pkg)

    # Write output
    gaia_dir = pkg_path / ".gaia"
    gaia_dir.mkdir(exist_ok=True)
    ir_json = json.dumps(ir, ensure_ascii=False, indent=2, sort_keys=True)
    (gaia_dir / "ir.json").write_text(ir_json)
    (gaia_dir / "ir_hash").write_text(ir["ir_hash"])

    typer.echo(
        f"Compiled {len(ir['knowledge'])} knowledge, "
        f"{len(ir['strategies'])} strategies, "
        f"{len(ir['operators'])} operators"
    )
    typer.echo(f"IR hash: {ir['ir_hash'][:16]}...")
    typer.echo(f"Output: {gaia_dir / 'ir.json'}")
