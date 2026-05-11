from gaia.lang.dsl.knowledge import claim, context, note, question, setting
from gaia.lang.dsl.associate_verb import associate
from gaia.lang.dsl.decompose import decompose
from gaia.lang.dsl.formula import causes, equals, exists, forall, iff, implies, land, lnot, lor
from gaia.lang.dsl.infer_verb import infer
from gaia.lang.dsl.operators import complement, contradiction, disjunction, equivalence
from gaia.lang.dsl.propositional import and_, not_, or_
from gaia.lang.dsl.relate import contradict, equal, exclusive
from gaia.lang.dsl.scaffold import candidate_relation, depends_on, tension
from gaia.lang.dsl.support import compute, derive, observe, predict
from gaia.lang.dsl.sugar import causal, parameter
from gaia.lang.runtime.composition import compose, composition
from gaia.lang.dsl.strategies import (
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
    support,
)

__all__ = [
    "abduction",
    "analogy",
    "associate",
    "case_analysis",
    "candidate_relation",
    "claim",
    "context",
    "compute",
    "compare",
    "composite",
    "compose",
    "composition",
    "complement",
    "contradict",
    "contradiction",
    "deduction",
    "decompose",
    "depends_on",
    "derive",
    "disjunction",
    "equal",
    "equals",
    "elimination",
    "exists",
    "exclusive",
    "equivalence",
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
    "mathematical_induction",
    "noisy_and",
    "causes",
    "causal",
    "and_",
    "not_",
    "note",
    "observe",
    "or_",
    "parameter",
    "predict",
    "question",
    "setting",
    "support",
    "tension",
]
