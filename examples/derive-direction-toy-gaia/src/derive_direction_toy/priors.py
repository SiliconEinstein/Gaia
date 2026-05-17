"""Prior records for the derive-direction-toy package.

A low base rate makes the §8.1 bug starkly visible: without the prior to
restrain it, a reverse-direction ``derive`` would push the belief from 0.05
all the way toward 1 after a single observation of wet ground. With the
correct ``infer`` lowering, BP performs proper Bayesian inversion and the
posterior stays modest.
"""

from derive_direction_toy import it_rained
from gaia.engine.lang import register_prior

register_prior(
    it_rained,
    value=0.05,
    justification=(
        "Local weather forecast and seasonal climatology suggest a 5% chance "
        "of rain today before any observation."
    ),
)
