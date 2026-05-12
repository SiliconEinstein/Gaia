"""Gaia IR — data models for the Gaia reasoning hypergraph.

Three entities: Knowledge (propositions), Operator (deterministic constraints),
Strategy (reasoning declarations with three forms).

Parameterization (probability parameters) acts on LocalCanonicalGraph.

Spec: docs/foundations/gaia-ir/
"""

from gaia.ir.compose import Compose
from gaia.ir.formalize import FormalizationResult, formalize_named_strategy
from gaia.ir.graphs import LocalCanonicalGraph
from gaia.ir.knowledge import (
    Knowledge,
    KnowledgeType,
    PackageRef,
    Parameter,
    make_qid,
)
from gaia.ir.operator import Operator, OperatorType
from gaia.ir.parameterization import (
    CROMWELL_EPS,
    ParameterizationSource,
    PriorRecord,
    ResolutionPolicy,
    StrategyParamRecord,
)
from gaia.ir.review import Review, ReviewManifest, ReviewStatus
from gaia.ir.schemas import (
    BUILTIN_DISTRIBUTION_KINDS,
    BuiltinDistributionKind,
    CallableRef,
    DistributionLiteral,
    DistributionParam,
    QuantityLiteral,
)
from gaia.ir.strategy import (
    CompositeStrategy,
    FormalExpr,
    FormalStrategy,
    Step,
    Strategy,
    StrategyType,
)

__all__ = [
    "BUILTIN_DISTRIBUTION_KINDS",  # Schemas
    "CROMWELL_EPS",  # Parameterization
    "BuiltinDistributionKind",  # Schemas
    "CallableRef",  # Schemas
    "Compose",  # Compose
    "CompositeStrategy",  # Strategy
    "DistributionLiteral",  # Schemas
    "DistributionParam",  # Schemas
    "FormalExpr",  # Strategy
    "FormalStrategy",  # Strategy
    "FormalizationResult",  # Formalization
    "Knowledge",  # Knowledge
    "KnowledgeType",  # Knowledge
    "LocalCanonicalGraph",  # Graphs
    "Operator",  # Operator
    "OperatorType",  # Operator
    "PackageRef",  # Knowledge
    "Parameter",  # Knowledge
    "ParameterizationSource",  # Parameterization
    "PriorRecord",  # Parameterization
    "QuantityLiteral",  # Schemas
    "ResolutionPolicy",  # Parameterization
    "Review",  # Review
    "ReviewManifest",  # Review
    "ReviewStatus",  # Review
    "Step",  # Strategy
    "Strategy",  # Strategy
    "StrategyParamRecord",  # Parameterization
    "StrategyType",  # Strategy
    "formalize_named_strategy",  # Formalization
    "make_qid",  # Knowledge
]
