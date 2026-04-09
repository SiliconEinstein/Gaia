"""gaia compile -- compile Python DSL package to Gaia IR v2 JSON."""

from __future__ import annotations

import typer

from gaia.cli._packages import (
    GaiaCliError,
    build_package_manifests,
    compile_loaded_package_artifact,
    load_gaia_package,
    write_compiled_artifacts,
)
from gaia.ir import LocalCanonicalGraph
from gaia.ir.validator import validate_local_graph


def compile_command(
    path: str = typer.Argument(".", help="Path to knowledge package directory"),
) -> None:
    """Compile a knowledge package to .gaia/ir.json."""
    try:
        loaded = load_gaia_package(path)
        compiled = compile_loaded_package_artifact(loaded)
        ir = compiled.to_json()
        manifests = build_package_manifests(loaded, compiled)
    except GaiaCliError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(1)

    validation = validate_local_graph(LocalCanonicalGraph(**ir))
    for warning in validation.warnings:
        typer.echo(f"Warning: {warning}")
    if validation.errors:
        for error in validation.errors:
            typer.echo(f"Error: {error}", err=True)
        raise typer.Exit(1)

    gaia_dir = write_compiled_artifacts(loaded.pkg_path, ir, manifests=manifests)

    typer.echo(
        f"Compiled {len(ir['knowledges'])} knowledge, "
        f"{len(ir['strategies'])} strategies, "
        f"{len(ir['operators'])} operators"
    )
    typer.echo(f"IR hash: {ir['ir_hash'][:16]}...")
    typer.echo(f"Output: {gaia_dir / 'ir.json'}")
