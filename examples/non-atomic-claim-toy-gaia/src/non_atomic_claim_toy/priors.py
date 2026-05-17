"""Prior records for the non-atomic-claim-toy package.

Both atomic claims start at 0.5 (genuinely undecided before the trial).
With independent infer factors, BP separates them into one high-belief
claim (LDL ≈ 0.90) and one low-belief claim (heart attacks ≈ 0.19).
"""

from gaia.engine.lang import register_prior
from non_atomic_claim_toy import reduces_heart_attacks, reduces_ldl

register_prior(
    reduces_ldl,
    value=0.5,
    justification=(
        "Pre-trial neutrality: drug X is a candidate LDL-reducing agent "
        "but the trial is the first conclusive readout."
    ),
)

register_prior(
    reduces_heart_attacks,
    value=0.5,
    justification=(
        "Pre-trial neutrality: LDL-reducing drugs sometimes translate to "
        "heart-attack reduction and sometimes do not (statin literature)."
    ),
)
