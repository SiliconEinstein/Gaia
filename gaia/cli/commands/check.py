"""gaia check -- validate a Gaia knowledge package."""

from __future__ import annotations

import json

import typer

from gaia.cli._packages import GaiaCliError, load_gaia_package, validate_fills_relations
from gaia.cli._packages import apply_package_priors
from gaia.cli._packages import compile_loaded_package_artifact
from gaia.cli.commands._classify import classify_ir, node_role
from gaia.cli.commands._review_manifest import (
    latest_reviews,
    load_or_generate_review_manifest,
)
from gaia.ir import LocalCanonicalGraph
from gaia.ir.validator import validate_local_graph


def _get_prior(k: dict) -> float | None:
    """Extract prior from a knowledge node's metadata, or None if absent."""
    meta = k.get("metadata") or {}
    return meta.get("prior")


def _knowledge_diagnostics(ir: dict) -> list[str]:
    """Analyze the knowledge graph and return diagnostic lines."""
    lines: list[str] = []

    claims = {k["id"]: k for k in ir["knowledges"] if k["type"] == "claim"}
    settings = {k["id"]: k for k in ir["knowledges"] if k["type"] == "setting"}
    questions = {k["id"]: k for k in ir["knowledges"] if k["type"] == "question"}

    c = classify_ir(ir)

    independent: list[tuple[str, str]] = []  # (label, cid)
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
            independent.append((label, cid))
        elif role == "background":
            background_only.append(label)
        else:
            orphaned.append(label)

    n_holes = sum(1 for _, cid in independent if _get_prior(claims[cid]) is None)

    # Summary
    lines.append("")
    lines.append(f"  Settings:  {len(settings)}")
    lines.append(f"  Questions: {len(questions)}")
    lines.append(f"  Claims:    {len(claims)}")
    lines.append(f"    Independent (need prior):  {len(independent)}")
    if n_holes:
        lines.append(f"      Holes (no prior set):   {n_holes}")
    lines.append(f"    Derived (BP propagates):   {len(derived)}")
    lines.append(f"    Structural (deterministic): {len(structural)}")
    if background_only:
        lines.append(f"    Background-only:           {len(background_only)}")
    if orphaned:
        lines.append(f"    Orphaned (no connections): {len(orphaned)}")

    if independent:
        lines.append("")
        lines.append("  Independent premises:")
        for label, cid in sorted(independent):
            prior = _get_prior(claims[cid])
            if prior is not None:
                lines.append(f"    - {label}  prior={prior}")
            else:
                lines.append(f"    - {label}  \u26a0 no prior (defaults to 0.5)")

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


def _hole_report(ir: dict) -> list[str]:
    """Return detailed report of all independent claims without priors (holes)."""
    claims = {k["id"]: k for k in ir["knowledges"] if k["type"] == "claim"}
    c = classify_ir(ir)
    lines: list[str] = []
    holes: list[tuple[str, dict]] = []
    covered: list[tuple[str, dict]] = []

    for cid, k in claims.items():
        if node_role(cid, "claim", c) != "independent":
            continue
        prior = _get_prior(k)
        if prior is None:
            holes.append((cid, k))
        else:
            covered.append((cid, k))

    lines.append("")
    lines.append(
        f"  Hole analysis: {len(holes)} hole(s) / {len(holes) + len(covered)} independent claims"
    )

    if holes:
        lines.append("")
        lines.append("  Holes (independent claims missing prior — defaults to 0.5):")
        for cid, k in sorted(holes, key=lambda x: x[0]):
            label = k.get("label", cid.split("::")[-1])
            content = k.get("content", "")
            preview = (content[:72] + "...") if len(content) > 75 else content
            lines.append(f"    {label}")
            lines.append(f"      id:      {cid}")
            lines.append(f"      content: {preview}")
            lines.append("      prior:   NOT SET (defaults to 0.5)")

    if covered:
        lines.append("")
        lines.append("  Covered (independent claims with prior set):")
        for cid, k in sorted(covered, key=lambda x: x[0]):
            label = k.get("label", cid.split("::")[-1])
            prior = _get_prior(k)
            justification = (k.get("metadata") or {}).get("prior_justification", "")
            lines.append(f"    {label}  prior={prior}")
            if justification:
                preview = (justification[:72] + "...") if len(justification) > 75 else justification
                lines.append(f"      reason: {preview}")

    if not holes:
        lines.append("")
        lines.append("  All independent claims have priors assigned.")

    return lines


def _warrant_report(manifest, *, blind: bool = False) -> list[str]:
    reviews = latest_reviews(manifest)
    lines: list[str] = []
    lines.append("")
    lines.append(f"Review warrants: {len(reviews)}")
    if not reviews:
        lines.append("  No reviewable v6 actions.")
        return lines

    for review in reviews:
        lines.append(f"  - {review.action_label}")
        lines.append(f"    target: {review.target_kind} {review.target_id}")
        if blind:
            lines.append("    status:")
        else:
            lines.append(f"    status: {review.status.value}")
        lines.append(f"    question: {review.audit_question}")
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
    warrants: bool = typer.Option(
        False,
        "--warrants",
        help="Show v6 ReviewManifest warrants with audit questions",
    ),
    blind: bool = typer.Option(
        False,
        "--blind",
        help="With --warrants, omit status values and prior diagnostics",
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

    if warrants:
        try:
            review_manifest = load_or_generate_review_manifest(loaded.pkg_path, compiled)
        except GaiaCliError as exc:
            typer.echo(str(exc), err=True)
            raise typer.Exit(1)
        for line in _warrant_report(review_manifest, blind=blind):
            typer.echo(line)
        if blind:
            return

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
