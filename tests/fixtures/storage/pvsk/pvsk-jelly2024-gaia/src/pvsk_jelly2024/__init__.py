"""Jelly et al. Nat Commun 2024 — First demonstration of entirely roll-to-roll
fabricated perovskite solar cell modules under ambient room conditions."""

from gaia.lang import claim, setting, support
from pvsk_meta import p_viability, p_efficiency, p_improvement, p_industrialization

# ---------------------------------------------------------------------------
# Background settings
# ---------------------------------------------------------------------------
exp_context = setting(
    "Entirely roll-to-roll fabricated perovskite solar cell modules on "
    "flexible PET substrates. Device stack: flexible TCE/SnO2/"
    "FA0.45MA0.55PbI3/HTAB-P3HT/carbon electrode with screen-printed Ag "
    "grids. All layers deposited by industrial R2R tools (slot-die, reverse "
    "gravure, screen printing) under ambient room conditions."
)

r2r_challenges = setting(
    "Translating lab-scale perovskite solar cells to R2R manufacturing "
    "requires replacing vacuum-deposited electrodes with printable "
    "alternatives, developing ambient-compatible processing, and controlling "
    "crystallization on continuously moving flexible substrates."
)

# ---------------------------------------------------------------------------
# Core claims
# ---------------------------------------------------------------------------
first_r2r_modules = claim(
    "This work reports the first demonstration of perovskite solar cell "
    "modules, comprising serially-interconnected cells, produced entirely "
    "using industrial roll-to-roll printing tools under ambient room "
    "conditions",
    title="first_r2r_modules",
    prior=0.90,
)

r2r_cell_15_5 = claim(
    "Fully R2R-printed individual perovskite solar cells achieve a record "
    "PCE of 15.5% with Jsc of 19.9 mA cm-2, FF of 76.1%, and Voc of 1.02 V, "
    "using a printed carbon electrode to replace vacuum-deposited gold",
    title="r2r_cell_15_5_percent",
    prior=0.87,
)

r2r_module_11 = claim(
    "Entirely R2R-fabricated modules (49.5 cm2 active area, 5 cells in "
    "series) achieve up to 11.0% active-area PCE with 192 mA current, "
    "62.3% FF, and 4.59 V Voc",
    title="r2r_module_11_percent",
    prior=0.85,
)

carbon_electrode = claim(
    "Perovskite-friendly carbon inks enable vacuum-free printed back "
    "electrodes compatible with R2R manufacturing, replacing costly "
    "vacuum-deposited Au electrodes",
    title="carbon_electrode_r2r",
    prior=0.80,
)

pfsd_technique = claim(
    "The printing-friendly sequential deposition (PFSD) technique with "
    "shallow-angle edge blowing produces high-quality perovskite films on "
    "continuously moving substrates under ambient conditions (40-50% RH), "
    "with mirror-like film quality and no PbI2 residue",
    title="pfsd_edge_blowing",
    prior=0.82,
)

htab_p3ht_htl = claim(
    "The HTAB-P3HT hole transport layer system outperforms PPDT2FBT, "
    "achieving higher PCE and narrower performance distribution in R2R "
    "fabrication, by passivating perovskite surface traps and promoting "
    "self-assembly of P3HT",
    title="htab_p3ht_htl",
    prior=0.80,
)

high_throughput_screening = claim(
    "An automated R2R platform enables fabrication and testing of over "
    "10,000 solar cells per day, with 1600 cells fabricated in a single "
    "experiment using 20 parameter combinations for rapid optimization",
    title="high_throughput_screening",
    prior=0.85,
)

humidity_tolerance = claim(
    "Reliable production of R2R-fabricated PSCs with average PCE of ~13% is "
    "confirmed regardless of ambient humidity (30-60% RH), demonstrating "
    "manufacturing robustness",
    title="humidity_tolerance_r2r",
    prior=0.78,
)

cost_prediction = claim(
    "A cost model predicts manufacturing cost of ~0.7 USD W-1 for a "
    "production rate of 1,000,000 m2 per year in Australia, with potential "
    "for further cost reduction below 0.5 USD W-1 by eliminating remaining "
    "high-cost components",
    title="cost_prediction_0_7_usd",
    prior=0.55,
)

geometric_fill_factor = claim(
    "R2R-printed modules achieve a geometric fill factor (GFF) of 75% using "
    "stripe-pattern interconnection, lower than laser-scribed modules (99%) "
    "but compatible with high-throughput manufacturing",
    title="geometric_fill_factor_75",
    prior=0.78,
)

# ---------------------------------------------------------------------------
# Internal reasoning
# ---------------------------------------------------------------------------
support(
    [carbon_electrode, pfsd_technique, htab_p3ht_htl],
    r2r_cell_15_5,
    reason="Three enabling technologies — printed carbon electrode, PFSD "
    "deposition, and HTAB-P3HT HTL — together achieve record R2R cell "
    "efficiency by addressing electrode cost, film quality, and charge "
    "transport respectively",
    prior=0.468,
)

support(
    [r2r_cell_15_5, high_throughput_screening],
    r2r_module_11,
    reason="Optimized cell parameters from high-throughput screening "
    "translate to module fabrication using larger slot-die heads and "
    "screen-printed interconnections",
    prior=0.45,
)

support(
    [r2r_module_11, first_r2r_modules],
    cost_prediction,
    reason="The fully printed, vacuum-free manufacturing approach enables "
    "low-cost production estimated at 0.7 USD W-1",
    prior=0.33,
)

# ---------------------------------------------------------------------------
# Connections to meta propositions
# ---------------------------------------------------------------------------
support(
    [first_r2r_modules, r2r_module_11, carbon_electrode],
    p_industrialization,
    reason="This is the first demonstration of entirely R2R-printed "
    "perovskite modules with all industrial processes, replacing "
    "vacuum-deposited electrodes with printed carbon, establishing a "
    "manufacturing pathway for perovskite PV",
    prior=0.51,
)

support(
    [r2r_cell_15_5, humidity_tolerance],
    p_viability,
    reason="15.5% efficiency from fully printed cells under ambient "
    "conditions, combined with humidity-tolerant manufacturing, demonstrates "
    "practical viability of R2R perovskite production",
    prior=0.39,
)

support(
    [r2r_cell_15_5, cost_prediction],
    p_efficiency,
    reason="15.5% for fully R2R-printed cells represents significant "
    "progress toward matching batch-processed flexible PSCs, though a gap "
    "remains",
    prior=0.36,
)

support(
    [first_r2r_modules, high_throughput_screening],
    p_improvement,
    reason="The automated high-throughput R2R platform enables rapid "
    "parameter optimization, establishing infrastructure for continuous "
    "improvement of printed perovskite technology",
    prior=0.39,
)

__all__ = [
    "exp_context",
    "r2r_challenges",
    "first_r2r_modules",
    "r2r_cell_15_5",
    "r2r_module_11",
    "carbon_electrode",
    "pfsd_technique",
    "htab_p3ht_htl",
    "high_throughput_screening",
    "humidity_tolerance",
    "cost_prediction",
    "geometric_fill_factor",
]
