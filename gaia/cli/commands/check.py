"""gaia check -- validate a Gaia knowledge package."""

from __future__ import annotations

import json

import typer

from gaia.cli._packages import GaiaCliError, load_gaia_package, validate_fills_relations
from gaia.cli._packages import apply_package_priors
from gaia.cli._packages import compile_loaded_package_artifact
from gaia.cli.commands.check_core import (
    analyze_knowledge_breakdown,
)
from gaia.ir import LocalCanonicalGraph
from gaia.ir.validator import validate_local_graph


def _knowledge_diagnostics(ir: dict) -> list[str]:
    """Format the role-based knowledge breakdown for `gaia check` output.

    Detection lives in ``check_core.analyze_knowledge_breakdown``; this is the
    text-rendering wrapper.
    """
    kb = analyze_knowledge_breakdown(ir)
    lines: list[str] = []
    n_holes = len(kb.holes)

    lines.append("")
    lines.append(f"  Settings:  {len(kb.settings)}")
    lines.append(f"  Questions: {len(kb.questions)}")
    lines.append(
        f"  Claims:    {len(kb.independent) + len(kb.derived) + len(kb.structural) + len(kb.background_only) + len(kb.orphaned)}"
    )
    lines.append(f"    Independent (need prior):  {len(kb.independent)}")
    if n_holes:
        lines.append(f"      Holes (no prior set):   {n_holes}")
    lines.append(f"    Derived (BP propagates):   {len(kb.derived)}")
    lines.append(f"    Structural (deterministic): {len(kb.structural)}")
    if kb.background_only:
        lines.append(f"    Background-only:           {len(kb.background_only)}")
    if kb.orphaned:
        lines.append(f"    Orphaned (no connections): {len(kb.orphaned)}")

    if kb.independent:
        lines.append("")
        lines.append("  Independent premises:")
        for entry in sorted(kb.independent, key=lambda e: e.label):
            if entry.prior is not None:
                lines.append(f"    - {entry.label}  prior={entry.prior}")
            else:
                lines.append(f"    - {entry.label}  ⚠ no prior (defaults to 0.5)")

    if kb.derived:
        lines.append("")
        lines.append("  Derived conclusions (belief from BP, prior optional):")
        for label in sorted(kb.derived):
            lines.append(f"    - {label}")

    if kb.background_only:
        lines.append("")
        lines.append(
            "  Background-only claims (referenced in strategy background, not in BP graph):"
        )
        for label in sorted(kb.background_only):
            lines.append(f"    - {label}")

    if kb.orphaned:
        lines.append("")
        lines.append("  Orphaned claims (not referenced anywhere):")
        for label in sorted(kb.orphaned):
            lines.append(f"    - {label}")

    return lines


def _hole_report(ir: dict) -> list[str]:
    """Format the hole-vs-covered breakdown for `gaia check --hole`."""
    kb = analyze_knowledge_breakdown(ir)
    holes = sorted(kb.holes, key=lambda e: e.cid)
    covered = sorted(kb.covered, key=lambda e: e.cid)
    lines: list[str] = []

    lines.append("")
    lines.append(
        f"  Hole analysis: {len(holes)} hole(s) / {len(holes) + len(covered)} independent claims"
    )

    if holes:
        lines.append("")
        lines.append("  Holes (independent claims missing prior — defaults to 0.5):")
        for entry in holes:
            preview = (entry.content[:72] + "...") if len(entry.content) > 75 else entry.content
            lines.append(f"    {entry.label}")
            lines.append(f"      id:      {entry.cid}")
            lines.append(f"      content: {preview}")
            lines.append("      prior:   NOT SET (defaults to 0.5)")

    if covered:
        lines.append("")
        lines.append("  Covered (independent claims with prior set):")
        for entry in covered:
            lines.append(f"    {entry.label}  prior={entry.prior}")
            if entry.prior_justification:
                preview = (
                    entry.prior_justification[:72] + "..."
                    if len(entry.prior_justification) > 75
                    else entry.prior_justification
                )
                lines.append(f"      reason: {preview}")

    if not holes:
        lines.append("")
        lines.append("  All independent claims have priors assigned.")

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
    hole: bool = typer.Option(
        False,
        "--hole",
        help="Show detailed prior review report for all independent claims",
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

    if hole:
        for line in _hole_report(ir):
            typer.echo(line)
