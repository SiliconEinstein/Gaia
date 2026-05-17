"""Didactic toy: base-rate fallacy (formalization-best-practices §8.4).

This package demonstrates a case where the Gaia formalization is
**structurally correct** yet the resulting belief looks "wrong" to
intuition. That is the §8.4 signal: the package is fine, the intuition is
the bug. The scientific insight is the point of the formalization.

Scenario:
    - Population prevalence of disease X: 1%.
    - Diagnostic test has 95% sensitivity and 95% specificity.
    - A patient tests positive.
    - Naive intuition: "the test is 95% accurate, so the patient probably
      has the disease (~95%)".
    - Bayes: posterior P(disease | positive) = 0.16. The base rate
      dominates because the disease is rare.

The package below is a clean, atomic, single-update Bayes formalization —
none of the §8.1, §8.2, §8.3 bugs are present. The 0.16 belief is what
the math actually produces. Authors who reach for the §8.1-§8.3 fixes here
will only break the formalization further; the right reaction is to study
the result and update the intuition.

Measured belief:
    disease_x = 0.161  (matches hand calc: 0.95·0.01 / (0.95·0.01 + 0.05·0.99))

Pedagogical use:
    - Run §8.1, §8.2, §8.3 toys first to see how their belief values move
      after the bug fix.
    - Then run this toy and confirm the belief is 0.16.
    - The §8.1-§8.3 toys teach "the package was wrong; the belief moves
      after fixing it"; this toy teaches "the package is right; the
      belief is the answer, even if it surprises you".
"""

from gaia.engine.lang import claim, infer, note, observe

context = note(
    "Didactic toy: a textbook base-rate fallacy. The package is a clean "
    "single-likelihood Bayes inversion; the surprising belief value is "
    "the scientifically correct posterior, not a formalization bug."
)

disease_x = claim(
    "Patient has rare disease X.",
    label="disease_x",
)

test_positive = claim(
    "The diagnostic test for disease X returned positive.",
    label="test_positive",
)

# Likelihood parameters from the test characteristics:
#   sensitivity      = P(positive | disease)    = 0.95
#   1 - specificity  = P(positive | no disease) = 0.05
test_supports_diagnosis = infer(
    evidence=test_positive,
    hypothesis=disease_x,
    p_e_given_h=0.95,
    p_e_given_not_h=0.05,
    background=[context],
    rationale=(
        "A standard textbook test with 95% sensitivity and 95% specificity. "
        "The likelihood ratio of a positive readout is 19:1, large but not "
        "large enough to overwhelm a 1:99 prior odds when combined."
    ),
    label="test_supports_diagnosis",
)

test_observation = observe(
    test_positive,
    background=[context],
    rationale="The patient's test result is recorded as positive.",
    label="test_observation",
)


__all__ = [
    "context",
    "disease_x",
    "test_observation",
    "test_positive",
    "test_supports_diagnosis",
]
