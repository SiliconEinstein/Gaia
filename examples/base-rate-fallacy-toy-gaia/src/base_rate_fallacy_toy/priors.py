"""Prior records for the base-rate-fallacy-toy package.

The 1% prevalence is what makes this a base-rate fallacy. Drop it to 50%
and the posterior climbs to ~0.95 — at high base rate, naive intuition is
right; at low base rate, the prior dominates.
"""

from base_rate_fallacy_toy import disease_x
from gaia.engine.lang import register_prior

register_prior(
    disease_x,
    value=0.01,
    justification=(
        "Population prevalence of disease X in the screening cohort is 1% "
        "before any individual's test result."
    ),
)
