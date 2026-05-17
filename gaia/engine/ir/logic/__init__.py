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

__all__ = [
    "DiagnosticCondition",
    "FormulaDiagnostic",
    "FormulaDiagnosticReport",
    "are_equivalent",
    "inspect_formula_graphs",
    "is_satisfiable",
    "simplify_proposition",
    "to_cnf_proposition",
    "to_dnf_proposition",
    "to_nnf_proposition",
    "to_sympy_proposition",
]
