"""Prior records for the double-counting-toy package.

A low base rate (5% prevalence) makes the double-counting bug starkly
visible: a single legitimate update lifts disease_x to ~0.33; counting the
same assay twice lifts it to ~0.83 — a 2.5x larger posterior on identical
evidence.
"""

from double_counting_toy import disease_x
from gaia.engine.lang import register_prior

register_prior(
    disease_x,
    value=0.05,
    justification=(
        "Population prevalence of disease X in the reference cohort is "
        "approximately 5% before any individual lab assay."
    ),
)
