"""gaia check -- validate a Gaia knowledge package."""

from __future__ import annotations

import json

import typer

from gaia.cli._packages import GaiaCliError, compile_loaded_package, load_gaia_package
from gaia.ir import LocalCanonicalGraph
from gaia.ir.validator import validate_local_graph


def _knowledge_diagnostics(ir: dict) -> list[str]:
    """Analyze the knowledge graph and return diagnostic lines."""
    lines: list[str] = []

    # Collect all claim IDs
    claims = {k["id"]: k for k in ir["knowledges"] if k["type"] == "claim"}
    settings = {k["id"]: k for k in ir["knowledges"] if k["type"] == "setting"}
    questions = {k["id"]: k for k in ir["knowledges"] if k["type"] == "question"}

    # Identify strategy conclusions, premises, and background references
    strategy_conclusions: set[str] = set()
    strategy_premises: set[str] = set()
    strategy_background: set[str] = set()
    for s in ir.get("strategies", []):
        if s.get("conclusion"):
            strategy_conclusions.add(s["conclusion"])
        for p in s.get("premises", []):
            strategy_premises.add(p)
        for b in s.get("background", []):
            strategy_background.add(b)

    # Operator conclusions and variables
    operator_conclusions: set[str] = set()
    operator_variables: set[str] = set()
    for o in ir.get("operators", []):
        if o.get("conclusion"):
            operator_conclusions.add(o["conclusion"])
        for v in o.get("variables", []):
            operator_variables.add(v)

    # Classify claims
    independent = []  # leaf nodes — need reviewer prior
    derived = []  # strategy conclusions — BP propagates belief
    structural = []  # operator conclusions — deterministic
    background_only = []  # referenced only in background, not in premise/conclusion
    orphaned = []  # not referenced anywhere

    for cid, k in claims.items():
        label = k.get("label", cid.split("::")[-1])
        if cid in operator_conclusions:
            structural.append(label)
        elif cid in strategy_conclusions:
            derived.append(label)
        elif cid in strategy_premises or cid in operator_variables:
            independent.append(label)
        elif cid in strategy_background:
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

    # List independent premises — these are what the reviewer needs to assess
    if independent:
        lines.append("")
        lines.append("  Independent premises (reviewer must assign prior):")
        for label in sorted(independent):
            lines.append(f"    - {label}")

    # List derived conclusions
    if derived:
        lines.append("")
        lines.append("  Derived conclusions (belief from BP, prior optional):")
        for label in sorted(derived):
            lines.append(f"    - {label}")

    # List background-only claims
    if background_only:
        lines.append("")
        lines.append("  Background-only claims (referenced in strategy background, not in BP graph):")
        for label in sorted(background_only):
            lines.append(f"    - {label}")

    # Warn about truly orphaned claims
    if orphaned:
        lines.append("")
        lines.append("  Orphaned claims (not referenced anywhere):")
        for label in sorted(orphaned):
            lines.append(f"    - {label}")

    return lines


def check_command(
    path: str = typer.Argument(".", help="Path to knowledge package directory"),
) -> None:
    """Validate structure and artifact consistency for a Gaia knowledge package."""
    try:
        loaded = load_gaia_package(path)
        ir = compile_loaded_package(loaded)
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

    # Knowledge graph diagnostics
    for line in _knowledge_diagnostics(ir):
        typer.echo(line)
