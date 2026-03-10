"""Compile a resolved Gaia Language package into a factor graph for BP."""

from __future__ import annotations

import warnings
from dataclasses import dataclass, field
from itertools import combinations

from .models import (
    ChainExpr,
    Declaration,
    Equivalence,
    Package,
    Ref,
    Relation,
    StepApply,
    StepLambda,
    StepRef,
)


# Types that participate in BP as variable nodes
BP_VARIABLE_TYPES = {"claim", "setting", "contradiction", "equivalence"}


@dataclass
class CompiledFactorGraph:
    """Factor graph built from Gaia Language package structure.

    variables: name -> prior
    factors: list of {name, premises: [name], conclusions: [name], probability, gate_var?}
    """

    variables: dict[str, float] = field(default_factory=dict)
    factors: list[dict] = field(
        default_factory=list
    )  # [{name, premises, conclusions, probability}]


def compile_factor_graph(pkg: Package) -> CompiledFactorGraph:
    """Compile a resolved package into a factor graph.

    Variable nodes: Claims and Settings with priors.
    Factor nodes: Applications and Lambdas from ChainExpr steps.
    Edges: determined by direct dependencies (indirect excluded).
    """
    fg = CompiledFactorGraph()

    # Collect all declarations across modules (resolving refs)
    all_decls: dict[str, Declaration] = {}

    for module in pkg.loaded_modules:
        for decl in module.declarations:
            if isinstance(decl, Ref):
                # Use the resolved target
                if decl._resolved is not None:
                    all_decls[decl.name] = decl._resolved
            else:
                all_decls[decl.name] = decl

    # Build set of exported names across all modules
    exported: set[str] = set()
    for module in pkg.loaded_modules:
        exported.update(module.export)

    # Add variable nodes (only exported Claims and Settings)
    for name, decl in all_decls.items():
        if decl.type in BP_VARIABLE_TYPES and name in exported:
            prior = decl.prior if decl.prior is not None else 1.0
            fg.variables[name] = prior

    # Add factor nodes from ChainExpr steps
    for module in pkg.loaded_modules:
        for decl in module.declarations:
            if not isinstance(decl, ChainExpr):
                continue
            _compile_chain(decl, all_decls, fg)

    # Add constraint factors from Relation declarations.
    # Iterate all_decls (not module.declarations) so that Ref aliases are handled:
    # a Relation re-exported via Ref appears under the alias name in all_decls.
    for name, decl in all_decls.items():
        if isinstance(decl, Relation):
            _compile_relation(name, decl, all_decls, fg)

    return fg


def _compile_chain(
    chain: ChainExpr,
    all_decls: dict[str, Declaration],
    fg: CompiledFactorGraph,
) -> None:
    """Compile a ChainExpr into factor nodes connecting variable nodes."""
    if chain.edge_type is not None:
        warnings.warn(
            f"ChainExpr.edge_type is deprecated. Use Relation declarations instead. "
            f"Chain '{chain.name}' uses edge_type='{chain.edge_type}'.",
            DeprecationWarning,
            stacklevel=2,
        )
    steps = chain.steps
    for i, step in enumerate(steps):
        if isinstance(step, (StepApply, StepLambda)):
            # This step is a factor node
            factor_name = f"{chain.name}.step_{step.step}"
            probability = step.prior if step.prior is not None else 1.0

            # Premises: direct dependencies from args (for Apply)
            # or the previous ref step (for Lambda)
            premises = []
            conclusions = []

            if isinstance(step, StepApply):
                for arg in step.args:
                    if arg.dependency == "direct":
                        # Resolve arg ref name
                        ref_name = arg.ref
                        if ref_name in fg.variables:
                            premises.append(ref_name)
            elif isinstance(step, StepLambda):
                # Lambda: previous step is the implicit input
                if i > 0:
                    prev = steps[i - 1]
                    if isinstance(prev, StepRef) and prev.ref in fg.variables:
                        premises.append(prev.ref)

            # Conclusions: next ref step is the output
            if i + 1 < len(steps):
                next_step = steps[i + 1]
                if isinstance(next_step, StepRef) and next_step.ref in fg.variables:
                    conclusions.append(next_step.ref)

            if premises or conclusions:
                fg.factors.append(
                    {
                        "name": factor_name,
                        "premises": premises,
                        "conclusions": conclusions,
                        "probability": probability,
                        "edge_type": chain.edge_type or "deduction",
                    }
                )


def _compile_relation(
    var_name: str,
    rel: Relation,
    all_decls: dict[str, Declaration],
    fg: CompiledFactorGraph,
) -> None:
    """Compile a Relation into constraint factor(s) connecting related claims.

    Uses *var_name* (which may be a Ref alias) instead of ``rel.name``
    so that re-exported Relations are matched correctly against ``fg.variables``.

    Equivalence relations with 3+ members are decomposed into pairwise
    constraint factors (one per pair), since the BP potential is binary.
    Contradiction uses an n-ary all-true penalty and needs no decomposition.
    """
    # Only create constraint if the Relation itself is a variable node (exported)
    if var_name not in fg.variables:
        return

    related_vars = [name for name in rel.between if name in fg.variables]
    if len(related_vars) < 2:
        return

    edge_type = f"relation_{rel.type}"
    prob = rel.prior if rel.prior is not None else 0.5

    # Relation variable is NOT included in the constraint factor.
    # Instead, the factor stores a read-only gate_var reference so BP can use the
    # Relation's current belief as the effective constraint strength without sending
    # messages back into the gate.
    # probability stores the initial / fallback strength (the Relation prior).

    if isinstance(rel, Equivalence) and len(related_vars) > 2:
        # Decompose n-ary equivalence into pairwise constraints.
        # equiv(a,b,c) → factors for (a,b), (a,c), (b,c).
        for i, (v1, v2) in enumerate(combinations(related_vars, 2)):
            fg.factors.append(
                {
                    "name": f"{var_name}.constraint.{i}",
                    "premises": [v1, v2],
                    "conclusions": [],
                    "probability": prob,
                    "edge_type": edge_type,
                    "gate_var": var_name,
                }
            )
    else:
        fg.factors.append(
            {
                "name": f"{var_name}.constraint",
                "premises": related_vars,
                "conclusions": [],
                "probability": prob,
                "edge_type": edge_type,
                "gate_var": var_name,
            }
        )
