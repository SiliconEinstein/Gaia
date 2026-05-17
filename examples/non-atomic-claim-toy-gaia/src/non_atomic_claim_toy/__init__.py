"""Didactic toy: atomic claims vs bundled claims (formalization-best-practices §8.3).

This package shows the **correct** atomic decomposition of a compound
assertion. The companion how-to documents the wrong way (one bundled claim
carrying two independent assertions) inline as a counter-example.

Scenario:
    - Drug X is studied for two endpoints: LDL cholesterol reduction and
      heart-attack incidence reduction.
    - One trial reads out positive on LDL, null on heart attacks.
    - Author wants to know two separate things: did the LDL claim survive,
      and did the heart-attack claim survive?

The key authoring choice:
    - Wrong: a single ``claim("Drug X reduces LDL AND reduces heart attacks")``
      with one combined prior. The two pieces of trial evidence (LDL
      positive, heart-attack null) pull the bundled claim in opposite
      directions; BP collapses both signals into a single mid-range belief
      that gives no actionable information about which sub-claim is
      supported.
    - Correct: two atomic claims ``reduces_ldl`` and ``reduces_heart_attacks``
      with their own priors and their own ``infer`` factors. BP returns one
      high belief and one low belief — readable, decision-grade.

Measured beliefs (after `gaia run infer`):
    correct (this file):
        reduces_ldl              = 0.904  (positive evidence sustained)
        reduces_heart_attacks    = 0.191  (null evidence sustained)

    wrong (one bundled claim, same evidence pulling both ways):
        ldl_and_heart_attack     = 0.690  (one mid-range number, both
                                            signals lost — author cannot
                                            tell which endpoint won)
"""

from gaia.engine.lang import claim, infer, note, observe

context = note(
    "Didactic toy: a single trial reports out on two distinct endpoints "
    "(LDL reduction, heart-attack incidence). They should be tracked as "
    "two atomic claims, not one bundled claim."
)

reduces_ldl = claim(
    "Drug X reduces LDL cholesterol in the target population.",
    label="reduces_ldl",
)

reduces_heart_attacks = claim(
    "Drug X reduces heart-attack incidence in the target population.",
    label="reduces_heart_attacks",
)

ldl_endpoint_positive = claim(
    "The trial's LDL endpoint readout was positive at the pre-specified threshold.",
    label="ldl_endpoint_positive",
)

heart_attack_endpoint_null = claim(
    "The trial's heart-attack endpoint readout was null (no significant reduction).",
    label="heart_attack_endpoint_null",
)

# Authoring choice (correct):
#
# Each endpoint becomes its own infer factor on its own atomic claim.
# Likelihood parameters (sensitivity / false-positive) describe how the
# trial readout maps to the underlying claim:
#   P(positive readout | drug works on LDL) = 0.95
#   P(positive readout | no LDL effect)     = 0.10
#
#   P(null readout | drug works on HA)      = 0.20  (true effect could miss)
#   P(null readout | no HA effect)          = 0.85  (no effect → likely null)
#
# BP applies each likelihood to its own claim independently, so the LDL
# claim climbs (positive evidence) while the heart-attack claim falls
# (null evidence).
#
# Authoring choice (wrong, do NOT use):
#
# Bundling both endpoints into one claim ``ldl_and_heart_attack`` and
# wiring both endpoint readouts to it forces the two opposing likelihoods
# to operate on a single variable. BP collapses to a single mid-range
# belief (~0.69) — both the strong LDL signal and the strong HA-null
# signal are lost, and the author cannot reason about either endpoint.
ldl_evidence_factor = infer(
    evidence=ldl_endpoint_positive,
    hypothesis=reduces_ldl,
    p_e_given_h=0.95,
    p_e_given_not_h=0.10,
    background=[context],
    rationale="A positive trial LDL readout is strong evidence that drug X reduces LDL.",
    label="ldl_evidence_factor",
)

ha_evidence_factor = infer(
    evidence=heart_attack_endpoint_null,
    hypothesis=reduces_heart_attacks,
    p_e_given_h=0.20,
    p_e_given_not_h=0.85,
    background=[context],
    rationale=(
        "A null heart-attack readout is more consistent with no real effect "
        "(P=0.85) than with a real effect that the trial happened to miss "
        "(P=0.20)."
    ),
    label="ha_evidence_factor",
)

ldl_observation = observe(
    ldl_endpoint_positive,
    background=[context],
    rationale="The author records the trial's positive LDL readout.",
    label="ldl_observation",
)

ha_observation = observe(
    heart_attack_endpoint_null,
    background=[context],
    rationale="The author records the trial's null heart-attack readout.",
    label="ha_observation",
)


__all__ = [
    "context",
    "ha_evidence_factor",
    "ha_observation",
    "heart_attack_endpoint_null",
    "ldl_endpoint_positive",
    "ldl_evidence_factor",
    "ldl_observation",
    "reduces_heart_attacks",
    "reduces_ldl",
]
