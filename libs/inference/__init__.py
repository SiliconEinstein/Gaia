"""Pure inference algorithms (factor graph + belief propagation).

These live in ``libs/`` so both the CLI and the service layer can use them
without introducing a circular ``libs -> services`` dependency.
"""

from .bp import BeliefPropagation, InconsistentGraphError
from .factor_graph import FactorGraph

__all__ = ["BeliefPropagation", "FactorGraph", "InconsistentGraphError"]
