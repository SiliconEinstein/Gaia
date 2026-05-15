"""Public Gaia Lang DSL helper functions."""

from gaia.engine.lang.dsl.associate_verb import associate
from gaia.engine.lang.dsl.decompose import decompose
from gaia.engine.lang.dsl.formula import (
    equals,
    exists,
    forall,
    iff,
    implies,
    land,
    lnot,
    lor,
)
from gaia.engine.lang.dsl.infer_verb import infer
from gaia.engine.lang.dsl.knowledge import claim, context, note, question, setting
from gaia.engine.lang.dsl.operators import complement, contradiction, disjunction, equivalence
from gaia.engine.lang.dsl.propositional import and_, not_, or_
from gaia.engine.lang.dsl.register_prior import (
    DEFAULT_SOURCE_ID,
    PRIOR_RECORDS_METADATA_KEY,
    get_prior_records,
    register_prior,
)
from gaia.engine.lang.dsl.relate import contradict, equal, exclusive
from gaia.engine.lang.dsl.scaffold import candidate_relation, depends_on, materialize
from gaia.engine.lang.dsl.strategies import (
    abduction,
    analogy,
    case_analysis,
    compare,
    composite,
    deduction,
    elimination,
    extrapolation,
    fills,
    induction,
    mathematical_induction,
    noisy_and,
)
from gaia.engine.lang.dsl.strategies import (
    support as _strategy_support,
)
from gaia.engine.lang.dsl.sugar import parameter
from gaia.engine.lang.dsl.support import compute, derive, observe
from gaia.engine.lang.runtime.composition import compose, composition

# Importing gaia.lang.dsl.support installs a same-named submodule on this package.
support = _strategy_support

__all__ = [
    "abduction",
    "analogy",
    "and_",
    "associate",
    "candidate_relation",
    "case_analysis",
    "claim",
    "compare",
    "complement",
    "compose",
    "composite",
    "composition",
    "compute",
    "context",
    "contradict",
    "contradiction",
    "decompose",
    "deduction",
    "depends_on",
    "derive",
    "disjunction",
    "elimination",
    "equal",
    "equals",
    "equivalence",
    "exclusive",
    "exists",
    "extrapolation",
    "fills",
    "forall",
    "iff",
    "implies",
    "induction",
    "infer",
    "land",
    "lnot",
    "lor",
    "materialize",
    "mathematical_induction",
    "noisy_and",
    "not_",
    "note",
    "observe",
    "or_",
    "parameter",
    "question",
    "register_prior",
    "setting",
    "support",
]
