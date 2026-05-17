"""Didactic toy: double counting via correlated evidence (formalization-best-practices §8.2).

This package shows the **correct** way to encode a single piece of evidence
that has been written up under two names. The companion how-to documents the
wrong way (treating the two names as independent likelihoods) inline as a
counter-example.

Scenario:
    - Rare disease X has population prevalence 5%.
    - A single lab assay produces a result that the lab report describes
      twice: once as "antibody titer above threshold", once as "biomarker
      panel positive". They are the SAME measurement, written up two ways.

The key authoring choice:
    - Wrong: ``infer(evidence=titer_high, hypothesis=disease_x, ...)`` AND
      ``infer(evidence=panel_positive, hypothesis=disease_x, ...)`` — two
      independent likelihood updates from the same underlying assay double
      the log-likelihood-ratio applied to the prior. The posterior is pushed
      far higher than the data warrants.
    - Correct: pick one canonical evidence claim (the lab result) and run a
      single ``infer`` against it. If the two descriptions matter for
      narrative, keep them as ``note`` text or as a single ``equal``-related
      claim — but only one should carry the likelihood factor.

Measured beliefs (after `gaia run infer`):
    correct (this file)            : disease_x = 0.320  (single-update Bayes
                                                          from prior 0.05)
    wrong (two infers, same lab)   : disease_x = 0.807  (double counting:
                                                          likelihood ratio
                                                          applied twice)
"""

from gaia.engine.lang import claim, infer, note, observe

context = note(
    "Didactic toy: a single lab assay was written up under two names in the "
    "report. The §8.2 bug is to treat the two names as independent evidence."
)

disease_x = claim(
    "Patient has rare disease X.",
    label="disease_x",
)

# Single canonical evidence claim. Anything from the same assay should
# attach to this claim, NOT spawn parallel evidence claims with their own
# infer chains.
lab_assay_positive = claim(
    "The lab assay for disease X returned a positive result.",
    label="lab_assay_positive",
)

# Authoring choice (correct):
#
# One assay → one infer factor. The likelihood parameters say:
#   P(positive | disease)    = 0.90   — sensitivity
#   P(positive | no disease) = 0.10   — false positive rate
# BP combines this with the 0.05 prior to get the proper posterior ~0.32.
#
# Authoring choice (wrong, do NOT use):
#
# Splitting the assay into two named claims (e.g. ``titer_high`` and
# ``panel_positive``) and writing two separate ``infer(...)`` factors
# applies the (0.90 / 0.10) likelihood ratio TWICE. The posterior on
# disease_x climbs to ~0.81 — well above what one assay supports.
assay_supports_diagnosis = infer(
    evidence=lab_assay_positive,
    hypothesis=disease_x,
    p_e_given_h=0.90,
    p_e_given_not_h=0.10,
    background=[context],
    rationale=(
        "The lab assay has 90% sensitivity and a 10% false-positive rate "
        "in the reference population. A single infer factor encodes both."
    ),
    label="assay_supports_diagnosis",
)

assay_observation = observe(
    lab_assay_positive,
    background=[context],
    rationale="The author records the lab assay result as observed.",
    label="assay_observation",
)


__all__ = [
    "assay_observation",
    "assay_supports_diagnosis",
    "context",
    "disease_x",
    "lab_assay_positive",
]
