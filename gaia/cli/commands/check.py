"""gaia check -- validate a Gaia knowledge package."""

from __future__ import annotations

import json
from dataclasses import dataclass
from math import log2

import typer
from sympy import And, Equivalent, Symbol
from sympy.logic.boolalg import Not
from sympy.logic.inference import satisfiable

from gaia.cli._packages import GaiaCliError, load_gaia_package, validate_fills_relations
from gaia.cli._packages import apply_package_priors
from gaia.cli._packages import compile_loaded_package_artifact
from gaia.cli.commands._classify import classify_ir, is_note_type, node_role
from gaia.cli.commands._inquiry import InquiryNode, build_goal_trees
from gaia.cli.commands._review_manifest import (
    latest_reviews,
    load_or_generate_review_manifest,
)
from gaia.bp import lower_local_graph
from gaia.bp.exact import exact_joint_over
from gaia.ir import LocalCanonicalGraph
from gaia.ir import ReviewManifest
from gaia.ir.operator import OperatorType
from gaia.ir.validator import validate_local_graph
from gaia.logic.propositional import to_sympy_proposition

_RELATION_OPERATOR_NAMES = frozenset(
    {
        str(OperatorType.EQUIVALENCE),
        str(OperatorType.CONTRADICTION),
        str(OperatorType.COMPLEMENT),
        str(OperatorType.IMPLICATION),
    }
)
_MAXENT_ENUM_LIMIT = 12


@dataclass
class _BoundaryAnalysis:
    boundary_claim_ids: set[str]
    scoped_to_exports: bool


@dataclass
class _MaxEntStateSpace:
    feasible_assignments: int | None = None
    total_assignments: int | None = None
    effective_bits: float | None = None
    skipped_reason: str | None = None


@dataclass
class _InducedMaxEntSummary:
    entropy_bits: float | None = None
    effective_states: float | None = None
    skipped_reason: str | None = None


def _walk_inquiry_nodes(node: InquiryNode):
    yield node
    for edge in node.incoming:
        for child in edge.inputs:
            yield from _walk_inquiry_nodes(child)


def _boundary_claim_analysis(ir: dict) -> _BoundaryAnalysis:
    """Identify load-bearing boundary claims for exported goals.

    Prefer the goal-oriented inquiry boundary when exported goals exist. A
    grounding-only root observation is still an independent probabilistic DOF:
    the grounding makes the observation reviewable, but it does not supply a
    numeric prior.
    """

    def needs_probability_input(node: InquiryNode) -> bool:
        return not node.incoming or all(edge.kind == "grounding" for edge in node.incoming)

    trees = build_goal_trees(ir, ReviewManifest(reviews=[]))
    if trees:
        boundary_claim_ids = {
            node.knowledge_id
            for tree in trees
            for node in _walk_inquiry_nodes(tree)
            if needs_probability_input(node)
        }
        return _BoundaryAnalysis(boundary_claim_ids=boundary_claim_ids, scoped_to_exports=True)

    c = classify_ir(ir)
    boundary_claim_ids = {
        knowledge["id"]
        for knowledge in ir.get("knowledges", [])
        if knowledge.get("type") == "claim"
        and knowledge.get("id")
        and node_role(knowledge["id"], "claim", c) == "independent"
    }
    return _BoundaryAnalysis(boundary_claim_ids=boundary_claim_ids, scoped_to_exports=False)


def _deterministic_operator_theory(graph: LocalCanonicalGraph):
    constraints = []
    for operator in graph.operators:
        if not operator.conclusion:
            continue
        expression = to_sympy_proposition(graph, operator.conclusion)
        if str(operator.operator) in _RELATION_OPERATOR_NAMES:
            constraints.append(expression)
        else:
            constraints.append(Equivalent(Symbol(operator.conclusion), expression))
    if not constraints:
        return None
    return And(*constraints)


def _maxent_state_space(ir: dict, claim_ids: set[str]) -> _MaxEntStateSpace:
    ordered_ids = sorted(claim_ids)
    total_assignments = 1 << len(ordered_ids)
    if not ordered_ids:
        return _MaxEntStateSpace(feasible_assignments=1, total_assignments=1, effective_bits=0.0)
    if len(ordered_ids) > _MAXENT_ENUM_LIMIT:
        return _MaxEntStateSpace(
            skipped_reason=f"too many MaxEnt claims ({len(ordered_ids)} > {_MAXENT_ENUM_LIMIT})"
        )

    try:
        graph = LocalCanonicalGraph(**ir)
        theory = _deterministic_operator_theory(graph)
    except Exception as exc:  # pragma: no cover - defensive diagnostic path
        return _MaxEntStateSpace(skipped_reason=str(exc))

    if theory is None:
        return _MaxEntStateSpace(
            feasible_assignments=total_assignments,
            total_assignments=total_assignments,
            effective_bits=float(len(ordered_ids)),
        )

    symbols = {claim_id: Symbol(claim_id) for claim_id in ordered_ids}
    feasible = 0
    for assignment in range(total_assignments):
        assumptions = [
            symbols[claim_id] if ((assignment >> bit) & 1) else Not(symbols[claim_id])
            for bit, claim_id in enumerate(ordered_ids)
        ]
        if satisfiable(And(theory, *assumptions)) is not False:
            feasible += 1

    return _MaxEntStateSpace(
        feasible_assignments=feasible,
        total_assignments=total_assignments,
        effective_bits=log2(feasible) if feasible > 0 else 0.0,
    )


def _state_space_line(state_space: _MaxEntStateSpace) -> str | None:
    if state_space.feasible_assignments is not None and state_space.total_assignments is not None:
        return (
            "      Effective MaxEnt state space: "
            f"{state_space.feasible_assignments}/{state_space.total_assignments} "
            f"assignments ({state_space.effective_bits:.2f} bits)"
        )
    if state_space.skipped_reason:
        return f"      Effective MaxEnt state space: skipped ({state_space.skipped_reason})"
    return None


def _induced_maxent_summary(
    graph: LocalCanonicalGraph,
    *,
    review_manifest: ReviewManifest | None,
    claim_ids: set[str],
) -> _InducedMaxEntSummary:
    ordered_ids = sorted(claim_ids)
    if not ordered_ids:
        return _InducedMaxEntSummary(entropy_bits=0.0, effective_states=1.0)

    try:
        factor_graph = lower_local_graph(graph, review_manifest=review_manifest)
        probs = exact_joint_over(factor_graph, ordered_ids)
    except Exception as exc:  # pragma: no cover - diagnostic path
        return _InducedMaxEntSummary(skipped_reason=str(exc))

    positive = [float(p) for p in probs if p > 0]
    entropy_bits = -sum(p * log2(p) for p in positive)
    return _InducedMaxEntSummary(
        entropy_bits=entropy_bits,
        effective_states=2**entropy_bits,
    )


def _induced_entropy_line(summary: _InducedMaxEntSummary) -> str | None:
    if summary.entropy_bits is not None and summary.effective_states is not None:
        return (
            "      Induced MaxEnt entropy: "
            f"{summary.entropy_bits:.2f} bits "
            f"({summary.effective_states:.2f} effective states)"
        )
    if summary.skipped_reason:
        return f"      Induced MaxEnt entropy: skipped ({summary.skipped_reason})"
    return None


def _get_prior(k: dict) -> float | None:
    """Extract prior from a knowledge node's metadata, or None if absent."""
    meta = k.get("metadata") or {}
    return meta.get("prior")


def _knowledge_diagnostics(
    ir: dict,
    *,
    induced_summary: _InducedMaxEntSummary | None = None,
) -> list[str]:
    """Analyze the knowledge graph and return diagnostic lines."""
    lines: list[str] = []

    claims = {k["id"]: k for k in ir["knowledges"] if k["type"] == "claim"}
    notes = {k["id"]: k for k in ir["knowledges"] if is_note_type(k["type"])}
    questions = {k["id"]: k for k in ir["knowledges"] if k["type"] == "question"}

    c = classify_ir(ir)
    boundary = _boundary_claim_analysis(ir)

    independent: list[tuple[str, str]] = []  # goal-boundary load-bearing claims
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
        elif cid in boundary.boundary_claim_ids:
            independent.append((label, cid))
        elif role == "background":
            background_only.append(label)
        else:
            orphaned.append(label)

    n_holes = sum(1 for _, cid in independent if _get_prior(claims[cid]) is None)
    state_space = _maxent_state_space(
        ir,
        {cid for _, cid in independent if _get_prior(claims[cid]) is None},
    )

    # Summary
    lines.append("")
    lines.append(f"  Notes:     {len(notes)}")
    lines.append(f"  Questions: {len(questions)}")
    lines.append(f"  Claims:    {len(claims)}")
    lines.append(f"    Independent DOF:           {len(independent)}")
    if n_holes:
        lines.append(f"      MaxEnt (no external prior): {n_holes}")
        state_space_line = _state_space_line(state_space)
        if state_space_line is not None:
            lines.append(state_space_line)
        induced_line = _induced_entropy_line(induced_summary or _InducedMaxEntSummary())
        if induced_line is not None:
            lines.append(induced_line)
    lines.append(f"    Derived (BP propagates):   {len(derived)}")
    lines.append(f"    Structural (deterministic): {len(structural)}")
    if background_only:
        lines.append(f"    Background-only:           {len(background_only)}")
    if orphaned:
        lines.append(f"    Orphaned (no connections): {len(orphaned)}")

    if independent:
        lines.append("")
        lines.append("  Independent boundary premises:")
        for label, cid in sorted(independent):
            prior = _get_prior(claims[cid])
            if prior is not None:
                lines.append(f"    - {label}  prior={prior}")
            else:
                lines.append(f"    - {label}  no external prior (MaxEnt)")

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


def _hole_report(
    ir: dict,
    *,
    induced_summary: _InducedMaxEntSummary | None = None,
) -> list[str]:
    """Return detailed report of all independent claims without priors (holes)."""
    claims = {k["id"]: k for k in ir["knowledges"] if k["type"] == "claim"}
    boundary = _boundary_claim_analysis(ir)
    lines: list[str] = []
    holes: list[tuple[str, dict]] = []
    covered: list[tuple[str, dict]] = []

    for cid, k in claims.items():
        if cid not in boundary.boundary_claim_ids:
            continue
        prior = _get_prior(k)
        if prior is None:
            holes.append((cid, k))
        else:
            covered.append((cid, k))

    state_space = _maxent_state_space(ir, {cid for cid, _ in holes})

    lines.append("")
    lines.append(
        f"  Independent DOF analysis: {len(holes)} MaxEnt / "
        f"{len(holes) + len(covered)} independent claims"
    )
    if holes:
        state_space_line = _state_space_line(state_space)
        if state_space_line is not None:
            lines.append(state_space_line)
        induced_line = _induced_entropy_line(induced_summary or _InducedMaxEntSummary())
        if induced_line is not None:
            lines.append(induced_line)

    if holes:
        lines.append("")
        lines.append("  MaxEnt independent claims (no external prior):")
        for cid, k in sorted(holes, key=lambda x: x[0]):
            label = k.get("label", cid.split("::")[-1])
            content = k.get("content", "")
            preview = (content[:72] + "...") if len(content) > 75 else content
            lines.append(f"    {label}")
            lines.append(f"      id:      {cid}")
            lines.append(f"      content: {preview}")
            lines.append("      prior:   not externalized; MaxEnt over independent DOF")

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
        lines.append("  All independent claims have external priors assigned.")

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
    inquiry: bool = typer.Option(
        False,
        "--inquiry",
        help="Show goal-oriented reasoning progress and review status",
    ),
    gate: bool = typer.Option(
        False,
        "--gate",
        help="Run quality gate checks and exit non-zero on failure",
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

    review_manifest = None
    induced_summary = None
    if warrants or inquiry or gate or hole or not (warrants and blind):
        try:
            review_manifest = load_or_generate_review_manifest(loaded.pkg_path, compiled)
        except GaiaCliError as exc:
            typer.echo(str(exc), err=True)
            raise typer.Exit(1)

    if hole or not (warrants and blind):
        boundary = _boundary_claim_analysis(ir)
        maxent_claim_ids = {
            cid
            for cid in boundary.boundary_claim_ids
            if (node := next((k for k in ir["knowledges"] if k.get("id") == cid), None))
            and _get_prior(node) is None
        }
        induced_summary = _induced_maxent_summary(
            compiled.graph,
            review_manifest=review_manifest,
            claim_ids=maxent_claim_ids,
        )

    if warrants:
        for line in _warrant_report(review_manifest, blind=blind):
            typer.echo(line)

    if inquiry:
        from gaia.cli.commands._inquiry import build_goal_trees, render_inquiry

        trees = build_goal_trees(ir, review_manifest)
        typer.echo("")
        typer.echo(render_inquiry(trees))

    if gate:
        from gaia.cli.commands._quality_gate import (
            check_quality_gate,
            load_beliefs,
            load_quality_config,
        )

        try:
            config = load_quality_config(loaded.gaia_config.get("quality"))
            beliefs = load_beliefs(loaded.pkg_path)
            failures = check_quality_gate(ir, beliefs, review_manifest, config)
        except GaiaCliError as exc:
            typer.echo(str(exc), err=True)
            raise typer.Exit(1)
        if failures:
            typer.echo("")
            typer.echo("Quality gate failed:")
            for failure in failures:
                typer.echo(f"  - {failure}")
            raise typer.Exit(1)
        typer.echo("")
        typer.echo("Quality gate passed")

    if warrants and blind and not (brief or show or hole):
        return

    if not (warrants and blind):
        for line in _knowledge_diagnostics(ir, induced_summary=induced_summary):
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
        for line in _hole_report(ir, induced_summary=induced_summary):
            typer.echo(line)
