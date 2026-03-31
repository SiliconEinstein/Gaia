"""Gaia IR — data models for the Gaia reasoning hypergraph.

Three entities: Knowledge (propositions), Operator (deterministic constraints),
Strategy (reasoning declarations with three forms).

Parameterization (probability parameters) and BeliefState (BP output) act on
GlobalCanonicalGraph. CanonicalBinding tracks local→global mapping.

Spec: docs/foundations/gaia-ir/
"""

from gaia.gaia_ir.knowledge import (
    Knowledge,
    KnowledgeType,
    LocalCanonicalRef,
    PackageRef,
    Parameter,
    make_qid,
)
from gaia.gaia_ir.operator import Operator, OperatorType
from gaia.gaia_ir.strategy import (
    CompositeStrategy,
    FormalExpr,
    FormalStrategy,
    Step,
    Strategy,
    StrategyType,
)
from gaia.gaia_ir.graphs import GlobalCanonicalGraph, LocalCanonicalGraph
from gaia.gaia_ir.formalize import FormalizationResult, formalize_named_strategy
from gaia.gaia_ir.parameterization import (
    CROMWELL_EPS,
    ParameterizationSource,
    PriorRecord,
    ResolutionPolicy,
    StrategyParamRecord,
)
from gaia.gaia_ir.belief_state import BeliefState
from gaia.gaia_ir.binding import BindingDecision, CanonicalBinding

__all__ = [
    # Knowledge
    "Knowledge",
    "KnowledgeType",
    "LocalCanonicalRef",
    "PackageRef",
    "Parameter",
    "make_qid",
    # Operator
    "Operator",
    "OperatorType",
    # Strategy
    "CompositeStrategy",
    "FormalExpr",
    "FormalStrategy",
    "Step",
    "Strategy",
    "StrategyType",
    # Graphs
    "GlobalCanonicalGraph",
    "LocalCanonicalGraph",
    # Formalization
    "FormalizationResult",
    "formalize_named_strategy",
    # Parameterization
    "CROMWELL_EPS",
    "ParameterizationSource",
    "PriorRecord",
    "ResolutionPolicy",
    "StrategyParamRecord",
    # BeliefState
    "BeliefState",
    # Binding
    "BindingDecision",
    "CanonicalBinding",
]
