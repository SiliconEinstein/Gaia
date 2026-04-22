"""Logic utilities for Gaia graphs.

These helpers use external logic libraries as computation backends while keeping
Gaia IR as the persistent semantic contract.
"""

from gaia.logic.propositional import (
    are_equivalent,
    is_satisfiable,
    simplify_proposition,
    to_cnf_proposition,
    to_dnf_proposition,
    to_nnf_proposition,
    to_sympy_proposition,
)

__all__ = [
    "are_equivalent",
    "is_satisfiable",
    "simplify_proposition",
    "to_cnf_proposition",
    "to_dnf_proposition",
    "to_nnf_proposition",
    "to_sympy_proposition",
]
