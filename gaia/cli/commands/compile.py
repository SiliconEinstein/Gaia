"""gaia compile -- compile Python DSL package to Gaia IR v2 JSON."""

from __future__ import annotations

import json

import typer

from gaia.cli._packages import GaiaCliError, compile_loaded_package, load_gaia_package
from gaia.cli._packages import write_compiled_artifacts
from gaia.ir import LocalCanonicalGraph
from gaia.ir.validator import validate_local_graph


def compile_command(
    path: str = typer.Argument(".", help="Path to knowledge package directory"),
    module_graphs: bool = typer.Option(
        False,
        "--module-graphs",
        help="Generate per-module detailed reasoning graphs (Mermaid + claim details).",
    ),
    readme: bool = typer.Option(
        False, "--readme", hidden=True, help="Deprecated alias for --module-graphs."
    ),
    github: bool = typer.Option(
        False, "--github", help="Generate GitHub presentation (.github-output/)"
    ),
) -> None:
    """Compile a knowledge package to .gaia/ir.json."""
    try:
        loaded = load_gaia_package(path)
        ir = compile_loaded_package(loaded)
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

    gaia_dir = write_compiled_artifacts(loaded.pkg_path, ir)

    typer.echo(
        f"Compiled {len(ir['knowledges'])} knowledge, "
        f"{len(ir['strategies'])} strategies, "
        f"{len(ir['operators'])} operators"
    )
    typer.echo(f"IR hash: {ir['ir_hash'][:16]}...")
    typer.echo(f"Output: {gaia_dir / 'ir.json'}")

    # Load beliefs/param data from latest review (shared by --readme and --github)
    beliefs_data = None
    param_data = None
    if module_graphs or readme or github:
        reviews_dir = loaded.pkg_path / ".gaia" / "reviews"
        if reviews_dir.exists():
            review_dirs = sorted(
                (d for d in reviews_dir.iterdir() if d.is_dir()),
                key=lambda p: p.stat().st_mtime,
                reverse=True,
            )
            for rd in review_dirs:
                beliefs_path = rd / "beliefs.json"
                if beliefs_path.exists():
                    beliefs_data = json.loads(beliefs_path.read_text())
                    param_path = rd / "parameterization.json"
                    if param_path.exists():
                        param_data = json.loads(param_path.read_text())
                    break

    if module_graphs or readme:
        from gaia.cli.commands._readme import generate_readme

        content = generate_readme(
            ir, loaded.project_config, beliefs_data=beliefs_data, param_data=param_data
        )
        if module_graphs:
            out_path = loaded.pkg_path / "docs" / "detailed-reasoning.md"
            out_path.parent.mkdir(parents=True, exist_ok=True)
            out_path.write_text(content)
            typer.echo(f"Module graphs: {out_path}")
        else:
            # Deprecated --readme: write to README.md for backwards compat
            out_path = loaded.pkg_path / "README.md"
            out_path.write_text(content)
            typer.echo(f"README: {out_path}")

    if github:
        from gaia.cli.commands._github import generate_github_output

        # Collect exported IDs from the compiled IR
        exported_ids = {k["id"] for k in ir.get("knowledges", []) if k.get("exported")}

        output_dir = generate_github_output(
            ir,
            loaded.pkg_path,
            beliefs_data=beliefs_data,
            param_data=param_data,
            exported_ids=exported_ids,
            pkg_metadata=loaded.project_config,
        )
        typer.echo(f"GitHub output: {output_dir}")
