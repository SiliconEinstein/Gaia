"""Prior records for the Galileo v0.5 example package.

Priors are registered through :func:`gaia.lang.register_prior` rather than the
legacy ``PRIORS = {...}`` dict (removed in v0.5+). Each call records a
multi-source ``PriorRecord``; the package-default ``ResolutionPolicy`` (see
:func:`gaia.ir.default_resolution_policy`) selects the winning value at
compile time and writes it to ``metadata['prior']`` for downstream BP /
render / brief consumers.

This example only registers the non-neutral empirical background prior. The two
model hypotheses are intentionally left unset, so Gaia treats them as MaxEnt
independent degrees of freedom instead of recording unsourced ``0.5`` author
priors.
"""

from gaia.lang import register_prior
from galileo_v0_5 import daily_observation

register_prior(
    daily_observation,
    value=0.90,
    justification=(
        "The everyday observation is treated as familiar empirical background, "
        "not as a new vacuum experiment."
    ),
)
