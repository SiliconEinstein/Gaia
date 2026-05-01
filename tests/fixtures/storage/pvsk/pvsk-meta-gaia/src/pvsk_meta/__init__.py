"""PVSK Meta Propositions — core questions for perovskite solar cell development."""

from gaia.lang import claim

# ---------------------------------------------------------------------------
# Meta propositions (claim type to participate in BP)
# Priors are intentionally low — they represent the initial state of knowledge
# before any evidence is accumulated. BP will update these as papers are added.
# ---------------------------------------------------------------------------

p_viability = claim(
    "Organometal halide perovskites can function as viable photovoltaic absorbers",
    title="p_viability",
    prior=0.05,
)

p_efficiency = claim(
    "Perovskite solar cells can achieve commercially competitive power conversion "
    "efficiency exceeding 20%",
    title="p_efficiency",
    prior=0.03,
)

p_improvement = claim(
    "Perovskite solar cell efficiency can be continuously improved through "
    "materials engineering, interface engineering, and compositional engineering",
    title="p_improvement",
    prior=0.05,
)

p_stability = claim(
    "Perovskite solar cells can achieve operational stability sufficient for "
    "practical deployment (>1000 hours under standard test conditions)",
    title="p_stability",
    prior=0.03,
)

p_industrialization = claim(
    "Perovskite solar cells can be scaled to module/panel level and "
    "industrially manufactured via roll-to-roll or slot-die processes",
    title="p_industrialization",
    prior=0.01,
)

__all__ = [
    "p_viability",
    "p_efficiency",
    "p_improvement",
    "p_stability",
    "p_industrialization",
]
