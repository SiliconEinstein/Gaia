"""Logic backends for compiled Gaia IR.

Provides solver-backed analysis of the IR's logical structure. Backends use
external libraries (sympy, future Z3/CVC5) while keeping `gaia.engine.ir`
data classes free of solver dependencies.

Current scope:
    propositional — sympy-based analysis of claim-level Operator graphs
        (NEGATION/CONJUNCTION/DISJUNCTION/IMPLICATION/EQUIVALENCE/
        CONTRADICTION/COMPLEMENT). Treats Knowledge nodes as atoms; does
        not look inside Claim.formula metadata.
    diagnostics — FormulaGraph-level inspection for reviewer-facing local
        formula issues and conservative cross-claim warnings.

Future (out of scope for this PR; tracked separately):
    predicate — first-order / SMT backends consuming `formula_atom` metadata
        for claim-internal predicate / quantifier / arithmetic analysis.
    smt — cross-cutting analysis combining Operator graph with claim-internal
        formula metadata.

See docs/specs/2026-05-16-engine-module-reorg-design.md §5 for the three-scope
taxonomy.
"""

from importlib import import_module
from typing import TYPE_CHECKING, Any

from gaia.engine.ir.logic.diagnostics import (
    DiagnosticCondition,
    FormulaDiagnostic,
    FormulaDiagnosticReport,
    inspect_formula_graphs,
)
from gaia.engine.ir.logic.propositional import (
    are_equivalent,
    is_satisfiable,
    simplify_proposition,
    to_cnf_proposition,
    to_dnf_proposition,
    to_nnf_proposition,
    to_sympy_proposition,
)

if TYPE_CHECKING:
    from gaia.engine.ir.logic.probability import (
        ConditionProbabilityEstimate,
        DiagnosticProbability,
        event_probability,
        score_condition,
        score_diagnostic_conditions,
    )

_LAZY_PROBABILITY_EXPORTS = {
    "ConditionProbabilityEstimate",
    "DiagnosticProbability",
    "event_probability",
    "score_condition",
    "score_diagnostic_conditions",
}

__all__ = [
    "ConditionProbabilityEstimate",
    "DiagnosticCondition",
    "DiagnosticProbability",
    "FormulaDiagnostic",
    "FormulaDiagnosticReport",
    "are_equivalent",
    "event_probability",
    "inspect_formula_graphs",
    "is_satisfiable",
    "score_condition",
    "score_diagnostic_conditions",
    "simplify_proposition",
    "to_cnf_proposition",
    "to_dnf_proposition",
    "to_nnf_proposition",
    "to_sympy_proposition",
]


def __getattr__(name: str) -> Any:
    """Lazily expose probability helpers without loading BP for pure logic imports."""
    if name in _LAZY_PROBABILITY_EXPORTS:
        probability_module = import_module("gaia.engine.ir.logic.probability")
        value = getattr(probability_module, name)
        globals()[name] = value
        return value
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
