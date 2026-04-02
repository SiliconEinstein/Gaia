"""Gaia IR — data models for the Gaia reasoning hypergraph.

Three entities: Knowledge (propositions), Operator (deterministic constraints),
Strategy (reasoning declarations with three forms).

Parameterization (probability parameters) acts on LocalCanonicalGraph.

Spec: docs/foundations/gaia-ir/
"""

from gaia.gaia_ir.knowledge import (
    Knowledge,
    KnowledgeType,
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
from gaia.gaia_ir.graphs import LocalCanonicalGraph
from gaia.gaia_ir.formalize import FormalizationResult, formalize_named_strategy
from gaia.gaia_ir.parameterization import (
    CROMWELL_EPS,
    ParameterizationSource,
    PriorRecord,
    ResolutionPolicy,
    StrategyParamRecord,
)

__all__ = [
    # Knowledge
    "Knowledge",
    "KnowledgeType",
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
]
