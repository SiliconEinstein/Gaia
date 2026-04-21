from gaia.lang.dsl.knowledge import claim, context, question, setting
from gaia.lang.dsl.infer_verb import infer
from gaia.lang.dsl.operators import complement, contradiction, disjunction, equivalence
from gaia.lang.dsl.relate import contradict, equal
from gaia.lang.dsl.support import compute, derive, observe
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
    "case_analysis",
    "claim",
    "context",
    "compute",
    "compare",
    "composite",
    "complement",
    "contradict",
    "contradiction",
    "deduction",
    "derive",
    "disjunction",
    "equal",
    "elimination",
    "equivalence",
    "extrapolation",
    "fills",
    "induction",
    "infer",
    "mathematical_induction",
    "noisy_and",
    "observe",
    "question",
    "setting",
    "support",
]
