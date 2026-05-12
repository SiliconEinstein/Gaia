"""gaia check -- validate a Gaia knowledge package."""

from __future__ import annotations

import json
from collections.abc import Iterator
from dataclasses import dataclass, field
from math import log2
from typing import Any

import typer
from sympy import And, Equivalent, Symbol
from sympy.logic.boolalg import Not
from sympy.logic.inference import satisfiable

from gaia.bp import lower_local_graph
from gaia.bp.exact import exact_joint_over
from gaia.bp.factor_graph import CROMWELL_EPS
from gaia.cli._packages import (
    GaiaCliError,
    apply_package_priors,
    compile_loaded_package_artifact,
    load_gaia_package,
    validate_fills_relations,
)
from gaia.cli.commands._classify import classify_ir, is_note_type, node_role
from gaia.cli.commands._inquiry import InquiryNode, build_goal_trees, render_inquiry
from gaia.cli.commands._review_manifest import (
    latest_reviews,
    load_or_generate_review_manifest,
)
from gaia.ir import LocalCanonicalGraph, ReviewManifest
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


@dataclass
class _BayesCheckDiagnostics:
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def _walk_inquiry_nodes(node: InquiryNode) -> Iterator[InquiryNode]:
    yield node
    for edge in node.incoming:
        if edge.kind == "candidate_relation":
            continue
        for child in edge.inputs:
            yield from _walk_inquiry_nodes(child)


def _boundary_claim_analysis(
    ir: dict[str, Any],
    *,
    formalization_manifest: dict[str, Any] | None = None,
) -> _BoundaryAnalysis:
    """Identify load-bearing boundary claims for exported goals.

    Prefer the goal-oriented inquiry boundary when exported goals exist. A
    zero-premise observe action pins its conclusion to 1 - CROMWELL_EPS, so it
    is not treated as an unparameterized boundary DOF.
    """

    def needs_probability_input(node: InquiryNode) -> bool:
        return not node.incoming or all(edge.kind == "candidate_relation" for edge in node.incoming)

    def expand_decomposition_boundary(boundary_ids: set[str]) -> set[str]:
        expanded = set(boundary_ids)
        for operator in ir.get("operators", []):
            metadata = operator.get("metadata") or {}
            decomposition = metadata.get("decomposition")
            if not isinstance(decomposition, dict):
                continue
            whole = decomposition.get("whole")
            parts = decomposition.get("parts")
            if whole not in expanded or not isinstance(parts, list):
                continue
            expanded.discard(whole)
            expanded.update(part for part in parts if isinstance(part, str) and part)
        return expanded

    trees = build_goal_trees(
        ir,
        ReviewManifest(reviews=[]),
        formalization_manifest=formalization_manifest,
    )
    if trees:
        boundary_claim_ids = {
            node.knowledge_id
            for tree in trees
            for node in _walk_inquiry_nodes(tree)
            if needs_probability_input(node)
        }
        return _BoundaryAnalysis(
            boundary_claim_ids=expand_decomposition_boundary(boundary_claim_ids),
            scoped_to_exports=True,
        )

    c = classify_ir(ir)
    boundary_claim_ids = {
        knowledge["id"]
        for knowledge in ir.get("knowledges", [])
        if knowledge.get("type") == "claim"
        and knowledge.get("id")
        and node_role(knowledge["id"], "claim", c) == "independent"
    }
    return _BoundaryAnalysis(
        boundary_claim_ids=expand_decomposition_boundary(boundary_claim_ids),
        scoped_to_exports=False,
    )


def _deterministic_operator_theory(graph: LocalCanonicalGraph) -> Any:
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


def _maxent_state_space(ir: dict[str, Any], claim_ids: set[str]) -> _MaxEntStateSpace:
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


def _formalization_dependency_claim_ids(
    formalization_manifest: dict[str, Any] | None,
) -> tuple[set[str], set[str]]:
    conclusions: set[str] = set()
    inputs: set[str] = set()
    for dependency in (formalization_manifest or {}).get("dependencies", []):
        if not isinstance(dependency, dict):
            continue
        kind = dependency.get("kind")
        if kind == "depends_on":
            conclusion = dependency.get("conclusion")
            if isinstance(conclusion, str) and conclusion:
                conclusions.add(conclusion)
            for given in dependency.get("given", []):
                if isinstance(given, str) and given:
                    inputs.add(given)
    return conclusions, inputs


def _candidate_relation_dependencies(
    formalization_manifest: dict[str, Any] | None,
) -> list[dict[str, Any]]:
    relations: list[dict[str, Any]] = []
    for dependency in (formalization_manifest or {}).get("dependencies", []):
        if isinstance(dependency, dict) and dependency.get("kind") == "candidate_relation":
            relations.append(dependency)
    return relations


def _candidate_relation_claim_ids(relations: list[dict[str, Any]]) -> set[str]:
    claim_ids: set[str] = set()
    for relation in relations:
        for claim_id in relation.get("claims", []):
            if isinstance(claim_id, str) and claim_id:
                claim_ids.add(claim_id)
    return claim_ids


def _candidate_relation_line(relation: dict[str, Any], claims: dict[str, dict[str, Any]]) -> str:
    label = relation.get("label") or relation.get("id") or "candidate_relation"
    proposed = relation.get("proposed") or "relation"
    status = relation.get("status") or "hypothesis"
    claim_labels = [
        _node_name(claims.get(claim_id), claim_id)
        for claim_id in relation.get("claims", [])
        if isinstance(claim_id, str) and claim_id
    ]
    endpoints = " <-> ".join(claim_labels) if claim_labels else "<no claims>"
    return f"    - {label} [{proposed}, {status}]: {endpoints}"


def _get_prior(k: dict[str, Any]) -> float | None:
    """Extract prior from a knowledge node's metadata, or None if absent."""
    meta = k.get("metadata") or {}
    return meta.get("prior")


def _node_name(node: dict[str, Any] | None, fallback: str | None = None) -> str:
    if node is None:
        return fallback or "<missing>"
    return str(node.get("label") or node.get("id") or fallback or "<unknown>")


def _bayes_metadata(node: dict[str, Any]) -> dict[str, Any]:
    metadata = node.get("metadata") or {}
    bayes = metadata.get("bayes") or {}
    return bayes if isinstance(bayes, dict) else {}


def _bayes_role(node: dict[str, Any]) -> str | None:
    role = _bayes_metadata(node).get("role")
    return role if isinstance(role, str) else None


def _is_local_ir_id(ir: dict[str, Any], qid: str) -> bool:
    namespace = ir.get("namespace")
    package_name = ir.get("package_name")
    if not isinstance(namespace, str) or not isinstance(package_name, str):
        return True
    return qid.startswith(f"{namespace}:{package_name}::")


def _formula_binding_symbols(node: dict[str, Any]) -> set[str]:
    metadata = node.get("metadata") or {}
    bindings = metadata.get("formula_bindings") or []
    symbols: set[str] = set()
    for binding in bindings:
        if not isinstance(binding, dict):
            continue
        symbol = binding.get("symbol")
        if isinstance(symbol, str) and "value" in binding:
            symbols.add(symbol)
    return symbols


def _hypothesis_prior(node: dict[str, Any] | None) -> float:
    # Fallback to 0.5 when a hypothesis has no IR-level prior. This treats
    # un-priored hypotheses as maximally uninformative for the prior-coherence
    # sum, matching how authors typically read "no prior set yet". gaia check
    # applies priors.py before compilation, so sidecar priors are visible here
    # once they have been injected into the IR metadata.
    if node is None:
        return 0.5
    prior = _get_prior(node)
    if prior is None:
        return 0.5
    try:
        return float(prior)
    except (TypeError, ValueError):
        return 0.5


def _bayes_check_diagnostics(ir: dict[str, Any]) -> _BayesCheckDiagnostics:
    diagnostics = _BayesCheckDiagnostics()
    nodes = {node["id"]: node for node in ir.get("knowledges", []) if node.get("id")}
    predictions = {
        node_id: node for node_id, node in nodes.items() if _bayes_role(node) == "prediction"
    }
    comparisons = {
        node_id: node for node_id, node in nodes.items() if _bayes_role(node) == "comparison"
    }

    referenced_models = {
        model
        for comparison in comparisons.values()
        if isinstance((model := _bayes_metadata(comparison).get("model")), str)
    }
    for comparison in comparisons.values():
        against = _bayes_metadata(comparison).get("against")
        if isinstance(against, list):
            referenced_models.update(model for model in against if isinstance(model, str))
    observed_symbols = {
        symbol for node in nodes.values() for symbol in _formula_binding_symbols(node)
    }

    for prediction_id, prediction in predictions.items():
        prediction_name = _node_name(prediction)
        if _is_local_ir_id(ir, prediction_id) and prediction_id not in referenced_models:
            diagnostics.warnings.append(
                "bayes:dangling-prediction: "
                f"PredictiveModel {prediction_name} is never referenced by likelihood(). "
                "Fix: add bayes.likelihood(data, model=model, against=[...]) or remove the "
                "unused model."
            )

        observable = _bayes_metadata(prediction).get("observable") or {}
        symbol = observable.get("symbol") if isinstance(observable, dict) else None
        if (
            _is_local_ir_id(ir, prediction_id)
            and isinstance(symbol, str)
            and symbol not in observed_symbols
        ):
            diagnostics.warnings.append(
                "bayes:unobserved-prediction-target: "
                f"PredictiveModel {prediction_name} observable {symbol!r} has no "
                "matching observation() value. Fix: declare an observation() for that "
                "Variable or import observed data from another package."
            )

    for _comparison_id, comparison in comparisons.items():
        bayes = _bayes_metadata(comparison)
        comparison_name = _node_name(comparison)
        model_id = bayes.get("model")
        model = nodes.get(model_id) if isinstance(model_id, str) else None
        model_bayes = _bayes_metadata(model) if model is not None else {}
        observable = model_bayes.get("observable") or {}
        observable_symbol = observable.get("symbol") if isinstance(observable, dict) else None

        for data_id in bayes.get("data") or []:
            if not isinstance(data_id, str):
                continue
            data_node = nodes.get(data_id)
            if data_node is None:
                diagnostics.errors.append(
                    "bayes:likelihood-without-data: "
                    f"likelihood {comparison_name} references missing data {data_id}. "
                    "Fix: pass an observation() Claim that is compiled with the package."
                )
                continue
            binding_symbols = _formula_binding_symbols(data_node)
            if not binding_symbols or (
                isinstance(observable_symbol, str) and observable_symbol not in binding_symbols
            ):
                diagnostics.errors.append(
                    "bayes:likelihood-without-data: "
                    f"likelihood {comparison_name} references data {_node_name(data_node)} "
                    f"without a bound value for observable {observable_symbol!r}. "
                    "Fix: use observation() for the measured Variable or pass "
                    "precomputed likelihoods with a reviewable observation Claim."
                )

        hypotheses = bayes.get("hypotheses") or model_bayes.get("hypotheses") or []
        hypothesis_ids = [h for h in hypotheses if isinstance(h, str)]
        if not hypothesis_ids:
            continue
        prior_sum = sum(
            _hypothesis_prior(nodes.get(hypothesis_id)) for hypothesis_id in hypothesis_ids
        )
        exclusivity = bayes.get("exclusivity")
        if exclusivity == "pairwise_contradiction" and prior_sum > 1.0 + CROMWELL_EPS:
            diagnostics.errors.append(
                "bayes:hypothesis-prior-coherence: "
                f"likelihood {comparison_name} uses pairwise_contradiction over "
                f"{len(hypothesis_ids)} hypotheses with prior sum={prior_sum:g}. "
                "Fix: reduce the listed hypothesis priors so their at-most-one mass "
                "does not exceed 1, or choose a different exclusivity mode."
            )
        elif (
            exclusivity == "exhaustive_pairwise_complement" and abs(prior_sum - 1.0) > CROMWELL_EPS
        ):
            diagnostics.errors.append(
                "bayes:hypothesis-prior-coherence: "
                f"likelihood {comparison_name} uses exhaustive_pairwise_complement over "
                f"{len(hypothesis_ids)} hypotheses with prior sum={prior_sum:g}. "
                "Fix: set the exhaustive alternatives' priors to sum to 1."
            )

        for strategy in ir.get("strategies", []):
            strategy_bayes = (strategy.get("metadata") or {}).get("bayes") or {}
            if strategy_bayes.get("role") == "likelihood_factor":
                continue
            if strategy.get("type") != "infer":
                continue
            premises = set(strategy.get("premises") or [])
            conclusion = strategy.get("conclusion")
            if premises.intersection(hypothesis_ids) and conclusion in (bayes.get("data") or []):
                diagnostics.warnings.append(
                    "bayes:infer-likelihood-overlap: "
                    f"likelihood {comparison_name} overlaps with a low-level infer() "
                    "strategy for the same hypothesis/data pair. Fix: keep either "
                    "bayes.likelihood() or the hand-written infer() CPT."
                )
                break

    return diagnostics


def _knowledge_diagnostics(
    ir: dict[str, Any],
    *,
    induced_summary: _InducedMaxEntSummary | None = None,
    formalization_manifest: dict[str, Any] | None = None,
) -> list[str]:
    """Analyze the knowledge graph and return diagnostic lines."""
    lines: list[str] = []

    claims = {k["id"]: k for k in ir["knowledges"] if k["type"] == "claim"}
    notes = {k["id"]: k for k in ir["knowledges"] if is_note_type(k["type"])}
    questions = {k["id"]: k for k in ir["knowledges"] if k["type"] == "question"}

    c = classify_ir(ir)
    boundary = _boundary_claim_analysis(ir, formalization_manifest=formalization_manifest)

    independent: list[tuple[str, str]] = []  # goal-boundary load-bearing claims
    derived = []
    structural = []
    background_only = []
    scaffolded = []
    candidate_relation_endpoints = []
    orphaned = []
    scaffold_conclusions, scaffold_inputs = _formalization_dependency_claim_ids(
        formalization_manifest
    )
    scaffold_connected = scaffold_conclusions | scaffold_inputs
    candidate_relations = _candidate_relation_dependencies(formalization_manifest)
    candidate_relation_claim_ids = _candidate_relation_claim_ids(candidate_relations)

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
        elif cid in scaffold_connected:
            scaffolded.append(label)
        elif cid in candidate_relation_claim_ids:
            candidate_relation_endpoints.append(label)
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
    if scaffolded:
        lines.append(f"    Scaffolded (unformalized): {len(scaffolded)}")
    if candidate_relation_endpoints:
        lines.append(f"    Candidate relation endpoints: {len(candidate_relation_endpoints)}")
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

    if scaffolded:
        lines.append("")
        lines.append("  Scaffolded claims (tracked in formalization manifest):")
        for label in sorted(scaffolded):
            lines.append(f"    - {label}")

    if candidate_relations:
        lines.append("")
        lines.append("  Candidate relations (tracked in formalization manifest):")
        for relation in sorted(
            candidate_relations,
            key=lambda item: str(item.get("label") or item.get("id") or ""),
        ):
            lines.append(_candidate_relation_line(relation, claims))

    if orphaned:
        lines.append("")
        lines.append("  Orphaned claims (not referenced anywhere):")
        for label in sorted(orphaned):
            lines.append(f"    - {label}")

    return lines


def _hole_report(
    ir: dict[str, Any],
    *,
    induced_summary: _InducedMaxEntSummary | None = None,
    formalization_manifest: dict[str, Any] | None = None,
) -> list[str]:
    """Return detailed report of all independent claims without priors (holes)."""
    claims = {k["id"]: k for k in ir["knowledges"] if k["type"] == "claim"}
    boundary = _boundary_claim_analysis(ir, formalization_manifest=formalization_manifest)
    lines: list[str] = []
    holes: list[tuple[str, dict[str, Any]]] = []
    covered: list[tuple[str, dict[str, Any]]] = []

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


def _warrant_report(manifest: ReviewManifest, *, blind: bool = False) -> list[str]:
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


def _load_check_artifacts(path: str) -> tuple[Any, Any, dict[str, Any]]:
    """Load, compile, and validate package-specific references for check."""
    try:
        loaded = load_gaia_package(path)
        apply_package_priors(loaded)
        compiled = compile_loaded_package_artifact(loaded)
        ir = compiled.to_json()
        validate_fills_relations(loaded, compiled)
    except GaiaCliError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(1) from exc
    return loaded, compiled, ir


def _collect_check_diagnostics(loaded: Any, ir: dict[str, Any]) -> tuple[list[str], list[str]]:
    """Collect structural and artifact-state diagnostics for ``gaia check``."""
    errors: list[str] = []
    warnings: list[str] = []
    if not loaded.project_name.endswith("-gaia"):
        errors.append("Project name must end with '-gaia'.")

    validation = validate_local_graph(LocalCanonicalGraph(**ir))
    errors.extend(validation.errors)
    warnings.extend(validation.warnings)
    bayes_diagnostics = _bayes_check_diagnostics(ir)
    errors.extend(bayes_diagnostics.errors)
    warnings.extend(bayes_diagnostics.warnings)
    _collect_compiled_artifact_diagnostics(loaded, ir, errors, warnings)
    return errors, warnings


def _collect_compiled_artifact_diagnostics(
    loaded: Any,
    ir: dict[str, Any],
    errors: list[str],
    warnings: list[str],
) -> None:
    """Check stored compile artifacts against the freshly compiled IR."""
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

    if not ir_json_path.exists():
        return
    try:
        stored_ir = json.loads(ir_json_path.read_text())
    except json.JSONDecodeError as exc:
        errors.append(f".gaia/ir.json is not valid JSON: {exc}")
    else:
        if stored_ir.get("ir_hash") != ir["ir_hash"]:
            errors.append("Stored .gaia/ir.json does not match current source; run `gaia compile`.")


def _emit_check_diagnostics(errors: list[str], warnings: list[str]) -> None:
    """Print diagnostics and exit on errors."""
    for warning in warnings:
        typer.echo(f"Warning: {warning}")
    if errors:
        for error in errors:
            typer.echo(f"Error: {error}", err=True)
        raise typer.Exit(1)


def _check_review_manifest_needed(
    *,
    warrants: bool,
    inquiry: bool,
    gate: bool,
    hole: bool,
    blind: bool,
) -> bool:
    """Return whether check needs a ReviewManifest."""
    return warrants or inquiry or gate or hole or not (warrants and blind)


def _load_check_review_manifest(loaded: Any, compiled: Any) -> ReviewManifest:
    """Load or generate a review manifest with CLI error handling."""
    try:
        return load_or_generate_review_manifest(loaded.pkg_path, compiled)
    except GaiaCliError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(1) from exc


def _check_induced_summary(
    ir: dict[str, Any],
    compiled: Any,
    review_manifest: ReviewManifest | None,
) -> _InducedMaxEntSummary:
    """Build induced MaxEnt summary for prior diagnostics."""
    boundary = _boundary_claim_analysis(
        ir,
        formalization_manifest=compiled.formalization_manifest,
    )
    maxent_claim_ids = {
        cid
        for cid in boundary.boundary_claim_ids
        if (node := next((k for k in ir["knowledges"] if k.get("id") == cid), None))
        and _get_prior(node) is None
    }
    return _induced_maxent_summary(
        compiled.graph,
        review_manifest=review_manifest,
        claim_ids=maxent_claim_ids,
    )


def _emit_warrant_and_inquiry_sections(
    *,
    ir: dict[str, Any],
    compiled: Any,
    review_manifest: ReviewManifest,
    warrants: bool,
    blind: bool,
    inquiry: bool,
) -> None:
    """Print optional warrant and inquiry sections."""
    if warrants:
        for line in _warrant_report(review_manifest, blind=blind):
            typer.echo(line)
    if inquiry:
        trees = build_goal_trees(
            ir,
            review_manifest,
            formalization_manifest=compiled.formalization_manifest,
        )
        typer.echo("")
        typer.echo(render_inquiry(trees))


def _run_check_quality_gate(
    *,
    ir: dict[str, Any],
    loaded: Any,
    compiled: Any,
    review_manifest: ReviewManifest,
) -> None:
    """Run the quality gate and print its result."""
    from gaia.cli.commands._quality_gate import (
        check_quality_gate,
        load_beliefs,
        load_quality_config,
    )

    try:
        config = load_quality_config(loaded.gaia_config.get("quality"))
        beliefs = load_beliefs(loaded.pkg_path)
        failures = check_quality_gate(
            ir,
            beliefs,
            review_manifest,
            config,
            formalization_manifest=compiled.formalization_manifest,
        )
    except GaiaCliError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(1) from exc
    if failures:
        typer.echo("")
        typer.echo("Quality gate failed:")
        for failure in failures:
            typer.echo(f"  - {failure}")
        raise typer.Exit(1)
    typer.echo("")
    typer.echo("Quality gate passed")


def _emit_check_brief_sections(ir: dict[str, Any], *, brief: bool, show: str | None) -> None:
    """Print optional brief and show sections."""
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


def _emit_prior_diagnostic_sections(
    *,
    ir: dict[str, Any],
    compiled: Any,
    induced_summary: _InducedMaxEntSummary | None,
    blind: bool,
    warrants: bool,
    hole: bool,
) -> None:
    """Print knowledge and hole diagnostics."""
    if not (warrants and blind):
        for line in _knowledge_diagnostics(
            ir,
            induced_summary=induced_summary,
            formalization_manifest=compiled.formalization_manifest,
        ):
            typer.echo(line)

    if hole:
        for line in _hole_report(
            ir,
            induced_summary=induced_summary,
            formalization_manifest=compiled.formalization_manifest,
        ):
            typer.echo(line)


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
    loaded, compiled, ir = _load_check_artifacts(path)
    errors, warnings = _collect_check_diagnostics(loaded, ir)
    _emit_check_diagnostics(errors, warnings)

    typer.echo(
        f"Check passed: {len(ir['knowledges'])} knowledge, "
        f"{len(ir['strategies'])} strategies, "
        f"{len(ir['operators'])} operators"
    )

    review_manifest = None
    induced_summary = None
    if _check_review_manifest_needed(
        warrants=warrants,
        inquiry=inquiry,
        gate=gate,
        hole=hole,
        blind=blind,
    ):
        review_manifest = _load_check_review_manifest(loaded, compiled)

    if hole or not (warrants and blind):
        induced_summary = _check_induced_summary(ir, compiled, review_manifest)

    if review_manifest is not None:
        _emit_warrant_and_inquiry_sections(
            ir=ir,
            compiled=compiled,
            review_manifest=review_manifest,
            warrants=warrants,
            blind=blind,
            inquiry=inquiry,
        )

    if gate:
        assert review_manifest is not None
        _run_check_quality_gate(
            ir=ir,
            loaded=loaded,
            compiled=compiled,
            review_manifest=review_manifest,
        )

    if warrants and blind and not (brief or show or hole):
        return

    if brief or show:
        _emit_check_brief_sections(ir, brief=brief, show=show)

    _emit_prior_diagnostic_sections(
        ir=ir,
        compiled=compiled,
        induced_summary=induced_summary,
        blind=blind,
        warrants=warrants,
        hole=hole,
    )
