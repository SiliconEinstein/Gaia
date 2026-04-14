"""gaia check -- validate a Gaia knowledge package."""

from __future__ import annotations

import json

import typer

from gaia.cli._packages import GaiaCliError, load_gaia_package, validate_fills_relations
from gaia.cli._packages import apply_package_priors
from gaia.cli._packages import compile_loaded_package_artifact
from gaia.cli.commands._classify import classify_ir, node_role
from gaia.ir import LocalCanonicalGraph
from gaia.ir.validator import validate_local_graph


def _knowledge_diagnostics(ir: dict) -> list[str]:
    """Analyze the knowledge graph and return diagnostic lines."""
    lines: list[str] = []

    claims = {k["id"]: k for k in ir["knowledges"] if k["type"] == "claim"}
    settings = {k["id"]: k for k in ir["knowledges"] if k["type"] == "setting"}
    questions = {k["id"]: k for k in ir["knowledges"] if k["type"] == "question"}

    c = classify_ir(ir)

    independent = []
    derived = []
    structural = []
    background_only = []
    orphaned = []

    for cid, k in claims.items():
        label = k.get("label", cid.split("::")[-1])
        role = node_role(cid, "claim", c)
        if role == "structural":
            structural.append(label)
        elif role == "derived":
            derived.append(label)
        elif role == "independent":
            independent.append(label)
        elif role == "background":
            background_only.append(label)
        else:
            orphaned.append(label)

    # Summary
    lines.append("")
    lines.append(f"  Settings:  {len(settings)}")
    lines.append(f"  Questions: {len(questions)}")
    lines.append(f"  Claims:    {len(claims)}")
    lines.append(f"    Independent (need prior):  {len(independent)}")
    lines.append(f"    Derived (BP propagates):   {len(derived)}")
    lines.append(f"    Structural (deterministic): {len(structural)}")
    if background_only:
        lines.append(f"    Background-only:           {len(background_only)}")
    if orphaned:
        lines.append(f"    Orphaned (no connections): {len(orphaned)}")

    if independent:
        lines.append("")
        lines.append("  Independent premises (reviewer must assign prior):")
        for label in sorted(independent):
            lines.append(f"    - {label}")

    if derived:
        lines.append("")
        lines.append("  Derived conclusions (belief from BP, prior optional):")
        for label in sorted(derived):
            lines.append(f"    - {label}")

    if background_only:
        lines.append("")
        lines.append(
            "  Background-only claims (referenced in strategy background, not in BP graph):"
        )
        for label in sorted(background_only):
            lines.append(f"    - {label}")

    if orphaned:
        lines.append("")
        lines.append("  Orphaned claims (not referenced anywhere):")
        for label in sorted(orphaned):
            lines.append(f"    - {label}")

    return lines


def check_command(
    path: str = typer.Argument(".", help="Path to knowledge package directory"),
    brief: bool = typer.Option(
        False, "--brief", "-b", help="Show per-module warrant brief after check"
    ),
    show: str | None = typer.Option(
        None,
        "--show",
        "-s",
        help="Expand detail for a module name or claim/strategy label (implies --brief)",
    ),
) -> None:
    """Validate structure and artifact consistency for a Gaia knowledge package."""
    try:
        loaded = load_gaia_package(path)
        apply_package_priors(loaded)
        compiled = compile_loaded_package_artifact(loaded)
        ir = compiled.to_json()
        validate_fills_relations(loaded, compiled)
    except GaiaCliError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(1)

    errors: list[str] = []
    warnings: list[str] = []

    if not loaded.project_name.endswith("-gaia"):
        errors.append("Project name must end with '-gaia'.")

    validation = validate_local_graph(LocalCanonicalGraph(**ir))
    errors.extend(validation.errors)
    warnings.extend(validation.warnings)

    ir_hash_path = loaded.pkg_path / ".gaia" / "ir_hash"
    ir_json_path = loaded.pkg_path / ".gaia" / "ir.json"
    if ir_hash_path.exists():
        stored_hash = ir_hash_path.read_text().strip()
        if stored_hash != ir["ir_hash"]:
            errors.append("Compiled artifacts are stale; run `gaia compile` again.")
        if not ir_json_path.exists():
            errors.append("Found .gaia/ir_hash but missing .gaia/ir.json.")
    else:
        warnings.append("Compiled artifacts missing; run `gaia compile` before `gaia register`.")

    if ir_json_path.exists():
        try:
            stored_ir = json.loads(ir_json_path.read_text())
        except json.JSONDecodeError as exc:
            errors.append(f".gaia/ir.json is not valid JSON: {exc}")
        else:
            if stored_ir.get("ir_hash") != ir["ir_hash"]:
                errors.append(
                    "Stored .gaia/ir.json does not match current source; run `gaia compile`."
                )

    for warning in warnings:
        typer.echo(f"Warning: {warning}")

    if errors:
        for error in errors:
            typer.echo(f"Error: {error}", err=True)
        raise typer.Exit(1)

    typer.echo(
        f"Check passed: {len(ir['knowledges'])} knowledge, "
        f"{len(ir['strategies'])} strategies, "
        f"{len(ir['operators'])} operators"
    )

    for line in _knowledge_diagnostics(ir):
        typer.echo(line)

    if brief or show:
        from gaia.cli.commands._brief import (
            dispatch_show,
            generate_brief_overview,
        )

        if brief:
            for line in generate_brief_overview(ir):
                typer.echo(line)
        if show:
            for line in dispatch_show(ir, show):
                typer.echo(line)
