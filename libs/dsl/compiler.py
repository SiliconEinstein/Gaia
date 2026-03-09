"""Compile a resolved DSL package into a factor graph for BP."""

from __future__ import annotations

from dataclasses import dataclass, field

from .models import (
    ChainExpr,
    Declaration,
    Package,
    Ref,
    StepApply,
    StepLambda,
    StepRef,
)


# Types that participate in BP as variable nodes
BP_VARIABLE_TYPES = {"claim", "setting"}


@dataclass
class DSLFactorGraph:
    """Factor graph built from DSL package structure.

    variables: name -> prior
    factors: list of {name, premises: [name], conclusions: [name], probability}
    """

    variables: dict[str, float] = field(default_factory=dict)
    factors: list[dict] = field(
        default_factory=list
    )  # [{name, premises, conclusions, probability}]


def compile_factor_graph(pkg: Package) -> DSLFactorGraph:
    """Compile a resolved package into a factor graph.

    Variable nodes: Claims and Settings with priors.
    Factor nodes: Applications and Lambdas from ChainExpr steps.
    Edges: determined by direct dependencies (indirect excluded).
    """
    fg = DSLFactorGraph()

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

    return fg


def _compile_chain(
    chain: ChainExpr,
    all_decls: dict[str, Declaration],
    fg: DSLFactorGraph,
) -> None:
    """Compile a ChainExpr into factor nodes connecting variable nodes."""
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
