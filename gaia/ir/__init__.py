"""Gaia IR — data models for the Gaia reasoning hypergraph.

Three entities: Knowledge (propositions), Operator (deterministic constraints),
Strategy (reasoning declarations with three forms).

Parameterization (probability parameters) acts on LocalCanonicalGraph.

Spec: docs/foundations/gaia-ir/
"""

from gaia.ir.knowledge import (
    Knowledge,
    KnowledgeType,
    PackageRef,
    Parameter,
    make_qid,
)
from gaia.ir.operator import Operator, OperatorType
from gaia.ir.strategy import (
    CompositeStrategy,
    ComputeMethod,
    DeductionMethod,
    FormalExpr,
    FormalStrategy,
    LikelihoodModuleSpec,
    LikelihoodScoreRecord,
    ModuleUseMethod,
    OpaqueConditionalMethod,
    Step,
    Strategy,
    StrategyType,
)
from gaia.ir.review import ReviewManifest, ReviewNote, Warrant, WarrantStatus
from gaia.ir.graphs import LocalCanonicalGraph
from gaia.ir.formalize import FormalizationResult, formalize_named_strategy
from gaia.ir.likelihood_registry import (
    BINOMIAL_MODEL_REF,
    BINOMIAL_MODEL_SPEC,
    STANDARD_LIKELIHOOD_MODULES,
    TWO_BINOMIAL_AB_TEST_REF,
    TWO_BINOMIAL_AB_TEST_SPEC,
    get_likelihood_module_spec,
)
from gaia.ir.parameterization import (
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
    "ComputeMethod",
    "DeductionMethod",
    "FormalExpr",
    "FormalStrategy",
    "LikelihoodModuleSpec",
    "LikelihoodScoreRecord",
    "ModuleUseMethod",
    "OpaqueConditionalMethod",
    "Step",
    "Strategy",
    "StrategyType",
    # Review
    "ReviewManifest",
    "ReviewNote",
    "Warrant",
    "WarrantStatus",
    # Graphs
    "LocalCanonicalGraph",
    # Standard likelihood module registry
    "BINOMIAL_MODEL_REF",
    "BINOMIAL_MODEL_SPEC",
    "STANDARD_LIKELIHOOD_MODULES",
    "TWO_BINOMIAL_AB_TEST_REF",
    "TWO_BINOMIAL_AB_TEST_SPEC",
    "get_likelihood_module_spec",
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
