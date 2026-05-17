"""Didactic toy: derive direction vs infer evidence (formalization-best-practices §8.1).

This package shows the **correct** way to encode an "evidence-of-cause" relation
in Gaia v0.5. The companion how-to documents the wrong way (using ``derive``
in the reverse direction) inline as a counter-example.

Scenario:
    - It might rain today (low prior).
    - Wet ground is a usual but imperfect consequence of rain.
    - We observe wet ground. How should the belief in "it rained" update?

The key authoring choice:
    - ``derive(rain, given=[wet_ground])`` would encode "wet ground logically
      implies rain" — a reverse-direction logical implication that is too
      strong (after observing wet ground, BP would push rain belief almost
      to 1, ignoring base rate and alternative explanations).
    - ``infer(evidence=wet_ground, hypothesis=rain, p_e_given_h=...,
      p_e_given_not_h=...)`` correctly encodes "wet ground is probabilistic
      evidence for rain" with explicit likelihood ratios. BP then performs
      the proper Bayesian update from the prior.

Measured beliefs (after `gaia run infer`):
    correct (this file)        : it_rained = 0.199  (Bayes from prior 0.05)
    wrong   (derive reversed)  : it_rained = 0.972  (IMPLICATION-pushed, bug)
"""

from gaia.engine.lang import claim, infer, note, observe

context = note(
    "Didactic toy package. The propositions are everyday rather than "
    "scientific so the directional bug is easy to spot."
)

it_rained = claim(
    "It rained in this neighborhood today.",
    label="it_rained",
)

ground_is_wet = claim(
    "The ground in front of the house is wet.",
    label="ground_is_wet",
)

# Authoring choice (correct):
#
# ``infer(evidence=ground_is_wet, hypothesis=it_rained, ...)`` says
# "wet ground is probabilistic evidence for rain". The two parameters
# encode the likelihood ratio:
#   P(wet | rained)         = 0.95   — when it rains, the ground is almost
#                                       always wet
#   P(wet | not rained)     = 0.20   — even on dry days, ground can be wet
#                                       from sprinklers, dew, or a neighbor
#                                       washing the car
# BP combines these with the prior on it_rained to compute the posterior.
#
# Authoring choice (wrong, do NOT use):
#
# ``derive(it_rained, given=[ground_is_wet], rationale=...)`` would encode
# "wet ground logically implies rain". Under v0.5 BP this lowers to
# IMPLICATION (a near-deterministic potential), and observing wet ground
# would push it_rained's belief almost to 1 (~0.97), regardless of the
# 0.05 prior. That is precisely the §8.1 bug in
# formalization-best-practices.md.
wetness_is_evidence_of_rain = infer(
    evidence=ground_is_wet,
    hypothesis=it_rained,
    p_e_given_h=0.95,
    p_e_given_not_h=0.20,
    background=[context],
    rationale=(
        "Wet ground after rain is the usual case (P=0.95). Wet ground without "
        "rain happens too — sprinklers, dew, a neighbor washing the car — at "
        "an estimated base rate of 0.20."
    ),
    label="wetness_is_evidence_of_rain",
)

ground_observation = observe(
    ground_is_wet,
    background=[context],
    rationale="The author looks outside and confirms the ground is wet.",
    label="ground_observation",
)


__all__ = [
    "context",
    "ground_is_wet",
    "ground_observation",
    "it_rained",
    "wetness_is_evidence_of_rain",
]
